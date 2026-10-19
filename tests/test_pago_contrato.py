"""Lo que /process_payment le devuelve al navegador, para PSE y para tarjeta.

El navegador no debería tener que hurgar dentro de `mp_response` para saber el id del pago o
su estado, y en PSE necesita además la URL del banco. Este es el contrato que pidió
MercadoPago al revisar el error 424: `payment_id`, `status`, `status_detail` y, solo en PSE,
`redirect_url`.
"""
from test_pse import preparar  # reusa el SDK de mentira y el armado del pedido


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
