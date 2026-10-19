"""PSE (Avanza): el pago se arma con el banco que eligió el comprador y se redirige al banco.

Cubre el fallo real que tumbaba el checkout en producción: con SIMULACION_PAGO activo (la
configuración de la tienda) `process_payment` usaba una variable que todavía no existía
(`request_options`) y el servidor devolvía 500 sin llegar nunca a MercadoPago.
"""
from app.db import db
from app.store.models import Invoice, Producto
from conftest import comprar
from test_checkout_invitado import token_de


class SDKFalso:
    """SDK de MercadoPago de mentira: devuelve el pago que le pasemos y guarda lo que se creó.

    Igual que el SDK real, cada llamada devuelve {"status": http, "response": pago}."""

    def __init__(self, pago, http=201):
        self.pago = pago
        self.http = http
        self.creado = None
        self.opciones = None

    def payment(self):
        return self

    def get(self, _id):
        return {"status": 200, "response": self.pago}

    def create(self, payment_data, request_options=None):
        self.creado = payment_data
        self.opciones = request_options
        return {"status": self.http, "response": self.pago}

    def cabeceras(self):
        return (self.opciones.custom_headers if self.opciones else {}) or {}


def pago_pse_pendiente(**extra):
    pago = {
        "id": "123456",
        "status": "pending",
        "status_detail": "pending_waiting_transfer",
        "payment_method_id": "pse",
        "transaction_details": {
            "financial_institution": "1052",
            "external_resource_url": "https://www.mercadopago.com.co/sandbox/payments/123456/bank_transfer",
        },
    }
    pago.update(extra)
    return pago


PAYLOAD_PSE = {
    "payment_method_id": "pse",
    "payer": {"email": "laura@correo.com", "entity_type": "individual",
              "identification": {"type": "CC", "number": "123456789"}},
    "transaction_details": {"financial_institution": "1052"},
    "intento": 1,
}


def preparar(client, app, monkeypatch, pago, http=201):
    from app.store.mercadopago import views as mp_views

    app.config["SIMULACION_PAGO"] = True
    sdk = SDKFalso(pago, http)
    monkeypatch.setattr(mp_views, "get_mp_sdk", lambda: sdk)
    token = token_de(comprar(client, {1: 1}))
    with app.app_context():
        pedido = Invoice.query.one()
        esperado = pedido.total + (pedido.p_envio or 0)
    return sdk, token, esperado


def test_pse_manda_el_banco_y_devuelve_la_url_del_banco(client, app, monkeypatch):
    sdk, token, esperado = preparar(client, app, monkeypatch, pago_pse_pendiente())

    r = client.post("/mercadopago/process_payment", json=dict(PAYLOAD_PSE, token_hash=token))
    assert r.status_code == 201
    datos = r.get_json()
    #la respuesta que el navegador usa para redirigir al banco
    assert datos["redirect_url"] == pago_pse_pendiente()["transaction_details"]["external_resource_url"]

    creado = sdk.creado
    assert creado["transaction_amount"] == esperado           #monto del pedido, no del navegador
    assert creado["payment_method_id"] == "pse"
    assert creado["transaction_details"]["financial_institution"] == "1052"
    #MercadoPago exige anidar el banco: en la raíz responde 400 "the name of the parameters is wrong"
    assert "financial_institution" not in creado
    assert creado["callback_url"].endswith(f"/pedido/{token}")  #vuelve al pedido del comprador
    assert creado["notification_url"].endswith("/mercadopago/webhook")
    assert creado["additional_info"]["ip_address"]              #PSE lo exige
    assert creado["payer"]["entity_type"] == "individual"
    assert creado["payer"]["address"]["zip_code"] == "110111"
    assert sdk.cabeceras()["x-test-token"] == "true"            #solo en modo pruebas

    with app.app_context():
        pedido = Invoice.query.one()
        assert pedido.estado == "PENDIENTE"                     #hasta que el banco confirme
        assert pedido.mp_payment_id == "123456"
        assert pedido.mp_external_resource_url == datos["redirect_url"]

    #y al volver del banco el pedido lo cuenta (no parece que "no pasó nada")
    html = client.get(f"/pedido/{token}").get_data(as_text=True)
    assert "Tu pago con PSE está en trámite" in html


def test_pse_reutiliza_el_pago_pendiente_al_volver_del_banco(client, app, monkeypatch):
    _sdk, token, _ = preparar(client, app, monkeypatch, pago_pse_pendiente())
    assert client.post("/mercadopago/process_payment", json=dict(PAYLOAD_PSE, token_hash=token)).status_code == 201

    #el comprador vuelve a darle pagar: se reusa el mismo pago y su URL (no se crea otro)
    r = client.post("/mercadopago/process_payment", json=dict(PAYLOAD_PSE, token_hash=token, intento=2))
    assert r.status_code == 200 and r.get_json()["reused"] is True
    assert r.get_json()["redirect_url"].endswith("/bank_transfer")


def test_pse_sin_banco_lo_dice_claro(client, app, monkeypatch):
    sdk, token, _ = preparar(client, app, monkeypatch, pago_pse_pendiente())
    r = client.post("/mercadopago/process_payment", json={
        "payment_method_id": "pse", "token_hash": token,
        "payer": PAYLOAD_PSE["payer"]})
    assert r.status_code == 400 and "banco" in r.get_json()["error"].lower()
    assert sdk.creado is None  #ni se molesta a MercadoPago


def test_pse_caido_no_revienta_avisa_al_admin_y_no_toca_el_stock(client, app, monkeypatch):
    from app.store.mercadopago import views as mp_views

    error_mp = {"status": 424, "cause": [{"code": 9032, "description": "BankTransfers Api fail"}]}
    _sdk, token, _ = preparar(client, app, monkeypatch, error_mp, http=424)
    monkeypatch.setattr(mp_views.time, "sleep", lambda _s: None)  #los reintentos no esperan de verdad

    r = client.post("/mercadopago/process_payment", json=dict(PAYLOAD_PSE, token_hash=token))
    assert r.status_code == 424
    assert "PSE" in r.get_json()["error"]

    with app.app_context():
        assert Invoice.query.one().estado == "PENDIENTE"
        assert db.session.get(Producto, 1).stock == 4  #la reserva sigue en pie para reintentar
    avisos = [a for a in app.extensions.get("telegram_enviados", []) if "PAGO NO INICIADO" in a]
    assert len(avisos) == 1 and "error 424" in avisos[0]


def test_pse_no_pierde_la_ip_ni_el_nombre_del_pedido(client, app, monkeypatch):
    sdk, token, _ = preparar(client, app, monkeypatch, pago_pse_pendiente())
    assert client.post("/mercadopago/process_payment", json=dict(PAYLOAD_PSE, token_hash=token)).status_code == 201
    assert sdk.creado["payer"]["first_name"] == "Laura"
    assert sdk.creado["payer"]["last_name"] == "Invitada Pérez"
    assert sdk.creado["additional_info"]["ip_address"]


def test_webhook_de_prueba_solo_existe_en_desarrollo(client, app):
    assert client.post("/mercadopago/webhook-test", json={"type": "payment"}).status_code == 404
    app.config["SIMULACION_PAGO"] = True
    assert client.post("/mercadopago/webhook-test", json={"type": "payment"}).status_code == 200
