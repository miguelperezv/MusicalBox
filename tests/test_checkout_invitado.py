"""Criterios de aceptación del checkout sin cuenta (paso 2)."""
import re

import pytest

from app.db import db
from app.store import pedidos
from app.store.models import Invoice, Item, Producto, Usuario, hash_token, referencia_epayco
from conftest import DATOS_ENVIO, comprar


def token_de(resp):
    m = re.search(r"/pedido/([A-Za-z0-9_\-]+)$", resp.headers["Location"])
    assert m, resp.headers.get("Location")
    return m.group(1)


def respuesta_epayco(monkeypatch, **data):
    monkeypatch.setattr(pedidos, "consultar_epayco", lambda ref: data)


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
        assert (pedido.dir_envio, pedido.lugar_envio, pedido.barrio_envio, pedido.metodo_pago) == ("Cra 1 # 2-3", "Suba, Bogotá D.C.", "Niza", "PSE")
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


def test_pago_aceptado_confirma_y_descuenta_stock_una_sola_vez(client, app, monkeypatch):
    token = token_de(comprar(client, {1: 2}))
    with app.app_context():
        pedido = Invoice.query.one()
        ref = referencia_epayco(pedido)
    respuesta_epayco(monkeypatch, x_response="Aceptada", x_id_invoice=ref, x_amount="240000.00", x_id_factura="F-1", x_franchise="PSE")
    for _ in range(2):  #ePayco llama la respuesta (navegador) y la confirmación (servidor)
        assert client.get(f"/pedido/{token}/respuesta?ref_payco=abc123").status_code == 302
    with app.app_context():
        pedido = Invoice.query.one()
        assert pedido.estado == "PAGADO" and pedido.ref_payco == "abc123"
        assert db.session.get(Producto, 1).stock == 3


@pytest.mark.parametrize("cambio", [{"x_id_invoice": "MB999-otro"}, {"x_amount": "1000"}])
def test_respuesta_de_otro_pedido_o_monto_distinto_no_confirma(client, app, monkeypatch, cambio):
    token = token_de(comprar(client, {1: 1}))
    with app.app_context():
        ref = referencia_epayco(Invoice.query.one())
    respuesta_epayco(monkeypatch, **dict({"x_response": "Aceptada", "x_id_invoice": ref, "x_amount": "120000"}, **cambio))
    client.get(f"/pedido/{token}/respuesta?ref_payco=abc")
    with app.app_context():
        assert Invoice.query.one().estado == "PENDIENTE"
        assert db.session.get(Producto, 1).stock == 5


def test_pago_rechazado_no_toca_stock_y_permite_reintentar(client, app, monkeypatch):
    token = token_de(comprar(client, {1: 1}))
    with app.app_context():
        ref = referencia_epayco(Invoice.query.one())
    respuesta_epayco(monkeypatch, x_response="Rechazada", x_id_invoice=ref, x_amount="120000")
    client.get(f"/pedido/{token}/respuesta?ref_payco=r1")
    with app.app_context():
        assert Invoice.query.one().estado == "RECHAZADO"
        assert db.session.get(Producto, 1).stock == 5
    assert "checkout.epayco.co" in client.get(f"/pedido/{token}").get_data(as_text=True)
    respuesta_epayco(monkeypatch, x_response="Aceptada", x_id_invoice=ref, x_amount="120000")
    client.get(f"/pedido/{token}/respuesta?ref_payco=r2")
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
    resp = client.post("/purchase/checkout", data=DATOS_ENVIO)
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/purchase/")
    with app.app_context():
        assert Invoice.query.count() == 0


def test_checkout_valida_datos_obligatorios(client, app):
    client.post("/purchase/addtocart", data={"product_id": "1", "quantity": "1"}, headers={"Referer": "/"})
    resp = client.post("/purchase/checkout", data=dict(DATOS_ENVIO, email="no-es-correo", telefono=""))
    assert resp.status_code == 200
    with app.app_context():
        assert Invoice.query.count() == 0


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
