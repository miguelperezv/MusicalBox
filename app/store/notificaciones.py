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
from .models import Usuario, items_efectivos, token_pedido, get_pedido_por_token

SALT_ACTIVACION = "activar-cuenta"


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=SALT_ACTIVACION)


def _huella(user):
    # Para mantener compatibilidad con las contraseñas ya cifradas, usamos el hash directamente
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


def notificar_pago_aprobado(pedido, token, etapa=None):
    """Avisa al comprador y al admin según la etapa pagada: abono (queda saldo) o pago completo.
    Nunca lanza: un fallo de correo/Telegram no puede dañar una confirmación de pago ya guardada."""
    from .notif_admin import aviso_abono_recibido, aviso_pago_aprobado
    #el webhook solo tiene el hash del token: si no resuelve, se firma uno para que el enlace sirva
    encontrado = get_pedido_por_token(token) if token else None
    if encontrado is None or encontrado.id != pedido.id:
        token = token_pedido(pedido)
    abono = pedido.abono
    if etapa == 'ABONO' and abono is not None:
        correo_abono_recibido(pedido, token, abono)
        aviso_abono_recibido(pedido, token)
    else:
        correo_pedido_pagado(pedido, token)
        aviso_pago_aprobado(pedido, token)


def correo_abono_recibido(pedido, token, abono):
    #apenas se aprueba el abono: el comprador queda con constancia del saldo que le falta
    if not pedido.email_envio:
        return False
    ctx = {"pedido": pedido, "abono": abono,
           "enlace_pedido": url_for("pedido.ver", token=token, _external=True)}
    return correo.enviar(pedido.email_envio, f"Recibimos tu abono del pedido #{pedido.id}",
                         render_template("correos/abono_recibido.txt", **ctx),
                         render_template("correos/abono_recibido.html", **ctx))


def correo_saldo_pendiente(pedido, abono):
    #recordatorio manual del saldo (lo dispara el admin desde el panel)
    if not pedido.email_envio:
        return False
    ctx = {"pedido": pedido, "abono": abono,
           "enlace_pedido": url_for("pedido.ver", token=token_pedido(pedido), _external=True)}
    return correo.enviar(pedido.email_envio, f"Te queda un saldo pendiente del pedido #{pedido.id}",
                         render_template("correos/saldo_pendiente.txt", **ctx),
                         render_template("correos/saldo_pendiente.html", **ctx))


def correo_pedido_enviado(pedido):
    #se llama cuando el pedido pasa a ENVIADO; si falla, el pedido igual queda guardado
    if not pedido.email_envio:
        return False
    ctx = {"pedido": pedido,
           "enlace_pedido": url_for("pedido.ver", token=token_pedido(pedido), _external=True)}
    return correo.enviar(pedido.email_envio, f"Tu pedido #{pedido.id} ya salió de Musical Box",
                         render_template("correos/pedido_enviado.txt", **ctx),
                         render_template("correos/pedido_enviado.html", **ctx))


def correo_solicitud_recibida(solicitud):
    #apenas entra la solicitud a la medida: el comprador queda con constancia en su correo
    if not solicitud.email_contacto:
        return False
    ctx = {"solicitud": solicitud, "items": items_efectivos(solicitud)}
    return correo.enviar(solicitud.email_contacto, "Recibimos tu solicitud en Musical Box",
                         render_template("correos/solicitud_recibida.txt", **ctx),
                         render_template("correos/solicitud_recibida.html", **ctx))


def correo_cotizacion_lista(solicitud, mensaje, enlace):
    #cuando el admin cotiza: el mismo mensaje del WhatsApp, por correo, con el enlace para pagar.
    #así el comprador no depende de que el WhatsApp no se pierda.
    if not solicitud.email_contacto:
        return False
    ctx = {"solicitud": solicitud, "mensaje": mensaje, "enlace": enlace}
    return correo.enviar(solicitud.email_contacto, "Tu cotización está lista en Musical Box",
                         render_template("correos/cotizacion_lista.txt", **ctx),
                         render_template("correos/cotizacion_lista.html", **ctx))


def correo_enlaces_seguimiento(destino, pedidos, solicitudes):
    #reenvío de enlaces pedido desde /seguimiento: va SOLO al correo del comprador
    ctx = {"pedidos": pedidos, "solicitudes": solicitudes}
    return correo.enviar(destino, "Tus enlaces de seguimiento en Musical Box",
                         render_template("correos/enlaces_seguimiento.txt", **ctx),
                         render_template("correos/enlaces_seguimiento.html", **ctx))


def correo_activacion(user):
    ctx = {"usuario": user, "enlace_activacion": enlace_activacion(user)}
    return correo.enviar(user.email_usuario, "Crea tu contraseña en Musical Box",
                         render_template("correos/activar_cuenta.txt", **ctx),
                         render_template("correos/activar_cuenta.html", **ctx))
