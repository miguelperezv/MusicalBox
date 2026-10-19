"""Criterios de aceptación del checkout sin cuenta (paso 2)."""
import re

from app.db import db
from app.store.models import Invoice, Producto, Usuario, hash_token
from conftest import DATOS_ENVIO, comprar, simular_pago


def token_de(resp):
    m = re.search(r"/pedido/([A-Za-z0-9_\-]+)$", resp.headers["Location"])
    assert m, resp.headers.get("Location")
    return m.group(1)


def test_compra_completa_sin_login_ni_registro(client, app):
    carrito = client.get("/purchase/")
    resp = comprar(client, {1: 2})
    assert resp.status_code == 302
    token = token_de(resp)

    #en ningún paso aparece un formulario de login/registro ni un campo de contraseña
    client.post("/purchase/addtocart", data={"product_id": "2", "quantity": "1"}, headers={"Referer": "/"})
    for pagina in [client.get("/purchase/"), client.get("/purchase/checkout"), client.get(f"/pedido/{token}")]:
        html = pagina.get_data(as_text=True)
        assert pagina.status_code == 200
        assert 'type="password"' not in html
        assert 'action="/login"' not in html and 'action="/signup"' not in html

    with app.app_context():
        pedido = Invoice.query.one()
        assert pedido.estado == "PENDIENTE"
        assert pedido.total == 240000
        assert (pedido.n_envio, pedido.email_envio, pedido.tel_envio) == ("Laura Invitada Pérez", "laura@correo.com", "3001234567")
        assert (pedido.dir_envio, pedido.lugar_envio, pedido.barrio_envio) == ("Cra 1 # 2-3", "Suba, Bogotá D.C.", "Niza")
        #el método de pago lo escribe MercadoPago al confirmar (aquí todavía no hay pago)
        assert pedido.metodo_pago is None
        comprador = db.session.get(Usuario, pedido.k_usuario)
        assert comprador.k_rol == "CLIENTE" and comprador.email_usuario == "laura@correo.com"
        assert [(i.k_producto, int(i.cant_item), i.p_item) for i in pedido.items] == [(1, 2, 120000)]
        assert pedido.items[0].producto.lanzamiento.n_lanzamiento == "negro swan"


def test_token_seguro_y_solo_se_guarda_su_hash(client, app):
    token = token_de(comprar(client, {1: 1}))
    assert len(token) >= 43  #secrets.token_urlsafe(32) = 256 bits
    with app.app_context():
        pedido = Invoice.query.one()
        assert pedido.token_hash == hash_token(token)
        fila = db.session.execute(db.text("SELECT * FROM invoice")).mappings().one()
        assert token not in [str(v) for v in fila.values()]


def test_enlace_no_permite_adivinar_ni_enumerar(client):
    token = token_de(comprar(client, {1: 1}))
    assert client.get(f"/pedido/{token}").status_code == 200
    for intento in ["1", "2", token[:-1] + ("A" if token[-1] != "A" else "B"), token.upper(), "x" * 300]:
        assert client.get(f"/pedido/{intento}").status_code == 404
    #sin sesión, desde otro navegador, el enlace funciona igual
    otro = client.application.test_client()
    assert otro.get(f"/pedido/{token}").status_code == 200


def test_segunda_compra_mismo_correo_no_duplica_comprador(client, app):
    comprar(client, {1: 1})
    otro_navegador = app.test_client()
    comprar(otro_navegador, {2: 1}, dict(DATOS_ENVIO, email="  LAURA@correo.COM ", direccion="Otra dirección 45"))
    with app.app_context():
        compradores = Usuario.query.filter(db.func.lower(Usuario.email_usuario) == "laura@correo.com").all()
        assert len(compradores) == 1
        pedidos_laura = Invoice.query.filter_by(k_usuario=compradores[0].id).order_by(Invoice.id).all()
        assert len(pedidos_laura) == 2
        #cada pedido conserva la dirección con la que se hizo
        assert [p.dir_envio for p in pedidos_laura] == ["Cra 1 # 2-3", "Otra dirección 45"]


def test_pago_aceptado_confirma_y_descuenta_stock_una_sola_vez(client, app):
    token = token_de(comprar(client, {1: 2}))
    for _ in range(2):  #MercadoPago avisa varias veces (webhook + el navegador al volver)
        assert simular_pago(client, app, token).status_code == 302
    with app.app_context():
        pedido = Invoice.query.one()
        assert pedido.estado == "PAGADO" and pedido.ref_payco == "SIMULADO"
        assert db.session.get(Producto, 1).stock == 3


def test_el_webhook_no_confirma_si_el_monto_no_es_el_del_pedido(client, app, monkeypatch):
    #antes sólo se miraba el estado del pago: un pago por menos plata confirmaba el pedido
    from app.store.mercadopago import views as mp_views

    token_de(comprar(client, {1: 1}))  #el pedido vale 120.000 + el envío cotizado
    with app.app_context():
        pedido = Invoice.query.one()
        referencia = pedido.token_hash  #MercadoPago manda el token_hash como referencia
        monto_del_pedido = pedido.total + (pedido.p_envio or 0)

    def pago_falso(monto):
        class SDK:
            def payment(self):
                return self

            def get(self, _id):
                return {"response": {"id": "999", "status": "approved", "payment_method_id": "pse",
                                     "external_reference": referencia, "transaction_amount": monto}}
        return SDK()

    monkeypatch.setattr(mp_views, "get_mp_sdk", lambda: pago_falso(1000))
    resp = client.post("/mercadopago/webhook", json={"type": "payment", "data": {"id": "999"}})
    assert resp.status_code == 409
    with app.app_context():
        assert Invoice.query.one().estado == "PENDIENTE"  #no se confirmó
        assert db.session.get(Producto, 1).stock == 4  #sigue reservado por el pedido pendiente

    #y con el monto correcto sí confirma (una sola vez)
    monkeypatch.setattr(mp_views, "get_mp_sdk", lambda: pago_falso(monto_del_pedido))
    for _ in range(2):
        assert client.post("/mercadopago/webhook", json={"type": "payment", "data": {"id": "999"}}).status_code == 200
    with app.app_context():
        assert Invoice.query.one().estado == "PAGADO"
        assert db.session.get(Producto, 1).stock == 4


def test_pago_rechazado_no_toca_stock_y_permite_reintentar(client, app):
    token = token_de(comprar(client, {1: 1}))
    simular_pago(client, app, token, resultado="rechazado")
    with app.app_context():
        assert Invoice.query.one().estado == "RECHAZADO"
        assert db.session.get(Producto, 1).stock == 5
    #la página del pedido deja volver a pagar (el botón arma la preferencia con el token del pedido)
    html = client.get(f"/pedido/{token}").get_data(as_text=True)
    assert "Pagar con MercadoPago" in html and "/mercadopago/create_preference/" in html
    simular_pago(client, app, token)
    with app.app_context():
        assert Invoice.query.one().estado == "PAGADO"


def test_no_permite_pedir_mas_que_el_stock(client, app):
    #el carrito no deja agregar de más, pero el stock puede bajar después (otra persona compró)
    client.post("/purchase/addtocart", data={"product_id": "2", "quantity": "9"}, headers={"Referer": "/"})
    with client.session_transaction() as s:
        assert s["purchase"] == {"2": 2}
    with app.app_context():
        db.session.get(Producto, 2).stock = 1
        db.session.commit()
    resp = client.post("/purchase/process_checkout", data=DATOS_ENVIO)
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/purchase/")
    with app.app_context():
        assert Invoice.query.count() == 0


def test_checkout_valida_datos_obligatorios(client, app):
    client.post("/purchase/addtocart", data={"product_id": "1", "quantity": "1"}, headers={"Referer": "/"})
    resp = client.post("/purchase/process_checkout", data=dict(DATOS_ENVIO, email="no-es-correo", telefono=""))
    #vuelve al checkout con lo que se escribió, no al carrito perdiendo todo
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/purchase/checkout")
    with app.app_context():
        assert Invoice.query.count() == 0
    html = client.get("/purchase/checkout").get_data(as_text=True)
    assert 'value="no-es-correo"' in html and "Laura Invitada Pérez" in html


def test_usuario_con_sesion_compra_con_su_cuenta(client, app):
    client.post("/login", data={"email_usuario": "ana@cuenta.com", "pwd_usuario": "clave"})
    client.post("/purchase/addtocart", data={"product_id": "1", "quantity": "1"}, headers={"Referer": "/"})
    assert 'value="ana@cuenta.com"' in client.get("/purchase/checkout").get_data(as_text=True)
    comprar(client, {}, dict(DATOS_ENVIO, email="ana@cuenta.com"))
    with app.app_context():
        assert Invoice.query.one().k_usuario == 50
        assert Usuario.query.count() == 1


def test_simulacion_desactivada_fuera_de_desarrollo(client):
    token = token_de(comprar(client, {1: 1}))
    assert client.post(f"/pedido/{token}/simular", data={"resultado": "aprobado"}).status_code == 404
