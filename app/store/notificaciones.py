"""Correos al comprador y enlace para crear contraseña.

El enlace de activación viaja SOLO por correo (nunca se muestra en pantalla): así solo quien controla ese
buzón puede crear la contraseña de una cuenta CLIENTE, aunque otra persona haya comprado con ese correo.
Es un token firmado con SECRET_KEY (itsdangerous), vence en ACTIVACION_MAX_DIAS y deja de servir en cuanto
se crea la contraseña (incluye una huella de la contraseña aleatoria actual y exige rol CLIENTE).
"""
import hashlib

from flask import current_app, render_template, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .. import correo
from ..db import db
from .models import Usuario

SALT_ACTIVACION = "activar-cuenta"


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=SALT_ACTIVACION)


def _huella(user):
    return hashlib.sha256(user.pwd_usuario.encode("utf-8")).hexdigest()[:16]


def token_activacion(user):
    return _serializer().dumps({"u": user.id, "e": user.email_usuario.lower(), "h": _huella(user)})


def usuario_de_token(token):
    #devuelve el usuario CLIENTE del token, o None si es inválido, vencido o ya se usó
    try:
        datos = _serializer().loads(token, max_age=current_app.config["ACTIVACION_MAX_DIAS"] * 86400)
    except (BadSignature, SignatureExpired):
        return None
    user = db.session.get(Usuario, datos.get("u"))
    if not user or user.k_rol != "CLIENTE" or user.email_usuario.lower() != datos.get("e") or _huella(user) != datos.get("h"):
        return None
    return user


def enlace_activacion(user):
    return url_for("home.activar", token=token_activacion(user), _external=True)


def correo_pedido_pagado(pedido, token):
    #se llama una sola vez, cuando el pedido pasa a PAGADO; si falla, el pedido igual queda guardado
    comprador = pedido.usuario
    ctx = {
        "pedido": pedido,
        "enlace_pedido": url_for("pedido.ver", token=token, _external=True),
        "enlace_activacion": enlace_activacion(comprador) if comprador and comprador.k_rol == "CLIENTE" else None,
    }
    return correo.enviar(pedido.email_envio, f"Tu pedido #{pedido.id} en Musical Box está confirmado",
                         render_template("correos/pedido_pagado.txt", **ctx),
                         render_template("correos/pedido_pagado.html", **ctx))


def correo_activacion(user):
    ctx = {"usuario": user, "enlace_activacion": enlace_activacion(user)}
    return correo.enviar(user.email_usuario, "Crea tu contraseña en Musical Box",
                         render_template("correos/activar_cuenta.txt", **ctx),
                         render_template("correos/activar_cuenta.html", **ctx))
