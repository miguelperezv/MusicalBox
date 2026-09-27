"""Paso 3: correo de confirmación y creación opcional de contraseña."""
import re

from app import correo
from app.db import db
from app.store import pedidos
from app.store.models import Invoice, Usuario, referencia_epayco
from app.store.notificaciones import token_activacion
from conftest import DATOS_ENVIO, comprar
from test_checkout_invitado import token_de


def correos(app):
    return app.extensions.get("correos_enviados", [])


def texto(msg):
    return msg.get_body(preferencelist=("plain",)).get_content()


def html(msg):
    return msg.get_body(preferencelist=("html",)).get_content()


def pagar(client, app, monkeypatch, token):
    with app.app_context():
        p = Invoice.query.order_by(Invoice.id.desc()).first()
        ref, monto = referencia_epayco(p), str(p.total)
    monkeypatch.setattr(pedidos, "consultar_epayco", lambda r: {"x_response": "Aceptada", "x_id_invoice": ref, "x_amount": monto})
    return client.get(f"/pedido/{token}/respuesta?ref_payco=ok1")


def enlace_activacion(msg):
    m = re.search(r"http://localhost/activar/(\S+)", texto(msg))
    return m.group(1) if m else None


def test_correo_de_confirmacion_una_sola_vez_con_enlace_de_seguimiento(client, app, monkeypatch):
    token = token_de(comprar(client, {1: 1}))
    assert correos(app) == []  #el pedido pendiente no envía nada
    pagar(client, app, monkeypatch, token)
    pagar(client, app, monkeypatch, token)  #respuesta + confirmación de ePayco
    assert len(correos(app)) == 1
    msg = correos(app)[0]
    assert msg["To"] == "laura@correo.com"
    assert f"http://localhost/pedido/{token}" in texto(msg)
    assert f"http://localhost/pedido/{token}" in html(msg)
    assert "Negro Swan" in texto(msg) and "$120.000" in texto(msg)
    assert enlace_activacion(msg)  #oferta opcional de contraseña


def test_si_falla_el_correo_el_pedido_igual_queda_pagado(client, app, monkeypatch):
    token = token_de(comprar(client, {1: 1}))
    def smtp_caido(*a, **k):
        raise ConnectionError("SMTP caído")
    monkeypatch.setattr(correo, "_mensaje", smtp_caido)
    assert pagar(client, app, monkeypatch, token).status_code == 302
    with app.app_context():
        assert Invoice.query.one().estado == "PAGADO"
    assert client.get(f"/pedido/{token}").status_code == 200


def test_ignorar_la_oferta_no_afecta_el_pedido(client, app, monkeypatch):
    token = token_de(comprar(client, {1: 1}))
    pagar(client, app, monkeypatch, token)
    with app.app_context():
        comprador = Usuario.query.filter_by(email_usuario="laura@correo.com").one()
        assert comprador.k_rol == "CLIENTE"
    otro_navegador = app.test_client()
    assert "¡Pago confirmado!" in otro_navegador.get(f"/pedido/{token}").get_data(as_text=True)


def test_crear_contrasena_desde_el_correo_y_ver_pedidos(client, app, monkeypatch):
    token = token_de(comprar(client, {1: 1}))
    pagar(client, app, monkeypatch, token)
    activacion = enlace_activacion(correos(app)[0])

    nuevo = app.test_client()
    assert nuevo.get(f"/activar/{activacion}").status_code == 200
    resp = nuevo.post(f"/activar/{activacion}", data={"pwd": "clave-segura", "confirmar": "clave-segura"})
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/account")
    assert "Pedido #" in nuevo.get("/account").get_data(as_text=True)
    with app.app_context():
        assert Usuario.query.filter_by(email_usuario="laura@correo.com").one().k_rol == "USER"
    #de un solo uso
    assert nuevo.get(f"/activar/{activacion}").status_code == 400
    #y ya puede ingresar con su correo (sin importar mayúsculas)
    otro = app.test_client()
    assert otro.post("/login", data={"email_usuario": "LAURA@correo.com", "pwd_usuario": "clave-segura"}).status_code == 302
    assert otro.get("/account").status_code == 200


def test_enlace_de_activacion_no_se_muestra_en_pantalla(client, app, monkeypatch):
    token = token_de(comprar(client, {1: 1}))
    pagar(client, app, monkeypatch, token)
    activacion = enlace_activacion(correos(app)[0])
    assert activacion not in client.get(f"/pedido/{token}").get_data(as_text=True)
    assert "/activar/" not in client.get(f"/pedido/{token}").get_data(as_text=True)


def test_enlace_de_activacion_alterado_o_vencido_no_sirve(client, app, monkeypatch):
    token = token_de(comprar(client, {1: 1}))
    pagar(client, app, monkeypatch, token)
    activacion = enlace_activacion(correos(app)[0])
    assert client.get(f"/activar/{activacion[:-2]}xx").status_code == 400
    assert client.get("/activar/inventado").status_code == 400
    app.config["ACTIVACION_MAX_DIAS"] = -1
    assert client.get(f"/activar/{activacion}").status_code == 400


def test_registrarse_con_correo_ajeno_no_da_acceso_a_sus_pedidos(client, app, monkeypatch):
    #la víctima compró sin cuenta; el atacante intenta registrarse con su correo
    token = token_de(comprar(client, {1: 1}))
    pagar(client, app, monkeypatch, token)
    atacante = app.test_client()
    resp = atacante.post("/signup", data={"name": "X", "lastname": "Y", "email_usuario": "laura@correo.com", "pwd_usuario": "hackeo123"})
    assert resp.status_code == 302
    assert atacante.post("/login", data={"email_usuario": "laura@correo.com", "pwd_usuario": "hackeo123"}).status_code == 302
    assert atacante.get("/account").status_code == 302  #sin sesión: redirige al login
    with app.app_context():
        u = Usuario.query.filter_by(email_usuario="laura@correo.com").one()
        assert u.k_rol == "CLIENTE" and u.pwd_usuario != "hackeo123"
    #el enlace de activación se envió al correo de la víctima, no al atacante
    assert correos(app)[-1]["To"] == "laura@correo.com"
    assert "Crea tu contraseña" in correos(app)[-1]["Subject"]


def test_usuario_con_cuenta_no_recibe_oferta_de_contrasena(client, app, monkeypatch):
    client.post("/login", data={"email_usuario": "ana@cuenta.com", "pwd_usuario": "clave"})
    token = token_de(comprar(client, {1: 1}, dict(DATOS_ENVIO, email="ana@cuenta.com")))
    pagar(client, app, monkeypatch, token)
    assert enlace_activacion(correos(app)[0]) is None


def test_registro_normal_sigue_funcionando(client, app):
    resp = client.post("/signup", data={"name": "Pepe", "lastname": "Nuevo", "email_usuario": "Pepe@Nuevo.com", "pwd_usuario": "abc12345"})
    assert resp.status_code == 302
    assert client.post("/login", data={"email_usuario": "pepe@nuevo.com", "pwd_usuario": "abc12345"}).status_code == 302
    assert client.get("/account").status_code == 200
