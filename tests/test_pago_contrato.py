"""Lo que /process_payment le devuelve al navegador, para PSE y para tarjeta.

El navegador no debería tener que hurgar dentro de `mp_response` para saber el id del pago o
su estado, y en PSE necesita además la URL del banco. Este es el contrato que pidió
MercadoPago al revisar el error 424: `payment_id`, `status`, `status_detail` y, solo en PSE,
`redirect_url`.
"""
from test_pse import preparar  # reusa el SDK de mentira y el armado del pedido

from app.store.models import Invoice


def pago_tarjeta(status="approved", detail="accredited"):
    return {"id": "1328475388", "status": status, "status_detail": detail,
            "payment_method_id": "debvisa"}


def test_tarjeta_devuelve_el_id_y_el_estado_pero_ninguna_url_de_banco(client, app, monkeypatch):
    _sdk, token, _ = preparar(client, app, monkeypatch, pago_tarjeta())

    r = client.post("/mercadopago/process_payment", json={
        "payment_method_id": "debvisa", "token": "tok-falso", "installments": 1, "token_hash": token})

    assert r.status_code == 201
    datos = r.get_json()
    assert datos["payment_id"] == "1328475388"
    assert datos["status"] == "approved"
    assert datos["status_detail"] == "accredited"
    assert "redirect_url" not in datos          #la tarjeta no manda a ningún banco


def test_tarjeta_en_proceso_tambien_trae_su_estado(client, app, monkeypatch):
    #el caso del log real: la tarjeta quedó en proceso, ni aprobada ni rechazada
    _sdk, token, _ = preparar(client, app, monkeypatch, pago_tarjeta("in_process", "pending_contingency"))

    r = client.post("/mercadopago/process_payment", json={
        "payment_method_id": "debvisa", "token": "tok-falso", "installments": 1, "token_hash": token})

    assert r.status_code == 201
    datos = r.get_json()
    assert (datos["status"], datos["status_detail"]) == ("in_process", "pending_contingency")
    assert "redirect_url" not in datos


def test_tarjeta_en_proceso_deja_el_pedido_sin_boton_de_pagar(client, app, monkeypatch):
    #el pago quedó en proceso (MP lo revisa hasta 2 días): el pedido no debe invitar a pagar de
    #nuevo, porque eso sería un segundo cobro por lo mismo
    _sdk, token, _ = preparar(client, app, monkeypatch, pago_tarjeta("in_process", "pending_contingency"))
    client.post("/mercadopago/process_payment", json={
        "payment_method_id": "debvisa", "token": "tok-falso", "installments": 1, "token_hash": token})

    with app.app_context():
        pedido = Invoice.query.one()
        assert pedido.mp_payment_id == "1328475388"      #el pedido recuerda el pago en curso
        assert pedido.mp_external_resource_url is None   #no fue PSE

    html = client.get(f"/pedido/{token}").get_data(as_text=True)
    assert "Tu pago con tarjeta está en proceso" in html
    assert "No necesitas pagar de nuevo" in html
    assert '<button id="btnOpenMp"' not in html          #no se ofrece pagar otra vez


def test_tarjeta_rechazada_si_deja_volver_a_pagar(client, app, monkeypatch):
    #si MP rechaza el pago, el pedido queda RECHAZADO y el botón tiene que volver
    _sdk, token, _ = preparar(client, app, monkeypatch, pago_tarjeta("rejected", "cc_rejected_other_reason"))
    client.post("/mercadopago/process_payment", json={
        "payment_method_id": "debvisa", "token": "tok-falso", "installments": 1, "token_hash": token})

    with app.app_context():
        assert Invoice.query.one().mp_payment_id is None   #un rechazo no se guarda como pago en curso

    assert '<button id="btnOpenMp"' in client.get(f"/pedido/{token}").get_data(as_text=True)
