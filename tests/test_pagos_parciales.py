"""Pagos parciales de preorden (#7): el abono asegura el pedido y el saldo se cobra después."""
import re

from app.db import db
from app.store.models import AbonoPago, Invoice, Producto

from conftest import DATOS_ENVIO, comprar, simular_pago


def token_de(resp):
    m = re.search(r"/pedido/([A-Za-z0-9_\-]+)$", resp.headers["Location"])
    assert m, resp.headers.get("Location")
    return m.group(1)


def _preparar_preorden(pct=30):
    p = db.session.get(Producto, 1)
    p.preorden = True
    p.porcentaje_abono = pct
    db.session.commit()
    return p


def test_preorden_abonada_se_cobra_en_dos_etapas(client, app):
    _preparar_preorden(30)
    resp = comprar(client, {1: 2})
    token = token_de(resp)

    inv = Invoice.query.order_by(Invoice.id.desc()).first()
    assert inv.estado == 'PENDIENTE_ABONO'
    assert inv.es_preorden_abonada is True
    assert float(inv.monto_abono) == 72000.0
    assert float(inv.monto_saldo) == 168000.0
    ab = AbonoPago.query.filter_by(k_invoice=inv.id).first()
    assert ab and ab.estado_abono == 'PENDIENTE' and ab.estado_saldo == 'PENDIENTE'
    assert float(ab.p_abono) == 72000.0 and float(ab.p_saldo) == 168000.0
    #primera pasada: abono + envío
    assert inv.monto_pago == float(ab.p_abono) + float(inv.p_envio or 0)
    #el stock de una preorden no se reserva al crear el pedido
    assert int(db.session.get(Producto, 1).stock) == 5

    #abono aprobado -> ABONADO, sin descontar stock
    simular_pago(client, app, token, "aprobado")
    db.session.expire_all()
    inv = db.session.get(Invoice, inv.id)
    ab = AbonoPago.query.filter_by(k_invoice=inv.id).first()
    assert inv.estado == 'ABONADO'
    assert ab.estado_abono == 'PAGADO' and ab.estado_saldo == 'PENDIENTE'
    assert float(ab.p_abono_pagado) == 72000.0
    assert inv.estado_envio is None
    assert int(db.session.get(Producto, 1).stock) == 5
    #ahora se cobra el saldo, sin envío
    assert inv.monto_pago == 168000.0
    #la página del pedido se adapta a la etapa del abono
    pagina = client.get(f"/pedido/{token}").get_data(as_text=True)
    assert "Pagado" in pagina or "abono" in pagina.lower()
    assert "168.000" in pagina  #el saldo se muestra en el panel

    #saldo aprobado -> PAGADO y listo para preparar
    simular_pago(client, app, token, "aprobado")
    db.session.expire_all()
    inv = db.session.get(Invoice, inv.id)
    ab = AbonoPago.query.filter_by(k_invoice=inv.id).first()
    assert inv.estado == 'PAGADO'
    assert ab.estado_saldo == 'PAGADO'
    assert float(ab.p_saldo_pagado) == 168000.0
    assert inv.estado_envio == 'POR PREPARAR'


def test_pedido_normal_sigue_cobrandose_completo(client, app):
    resp = comprar(client, {1: 1})
    token_de(resp)
    inv = Invoice.query.order_by(Invoice.id.desc()).first()
    assert inv.estado == 'PENDIENTE'
    assert inv.es_preorden_abonada is False
    assert inv.abono is None
    assert inv.etapa_pago == 'TOTAL'
    assert inv.monto_pago == float(inv.total) + float(inv.p_envio or 0)


def test_carrito_mixto_no_aplica_abono(client, app):
    #producto 1 en preorden con abono y producto 2 normal: el pedido se cobra completo
    _preparar_preorden(30)
    resp = comprar(client, {1: 1, 2: 1})
    token_de(resp)
    inv = Invoice.query.order_by(Invoice.id.desc()).first()
    assert inv.estado == 'PENDIENTE'
    assert inv.es_preorden_abonada is False
    assert inv.abono is None


def test_cuenta_muestra_el_saldo_pendiente(client, app):
    _preparar_preorden(30)
    datos = dict(DATOS_ENVIO, email="ana@cuenta.com")
    resp = comprar(client, {1: 1}, datos)
    token = token_de(resp)
    simular_pago(client, app, token, "aprobado")  #el abono queda pagado

    client.post("/login", data={"email_usuario": "ana@cuenta.com", "pwd_usuario": "clave"})
    html = client.get("/account").get_data(as_text=True)
    assert "saldo pendiente" in html.lower()
    assert "Pagar el saldo" in html
