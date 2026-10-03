#avises al admin por Telegram: un texto por evento del negocio.
#cada aviso es opcional y nunca rompe el flujo (enviar_admin nunca lanza excepción).
from flask import url_for

from ..telegram import enviar_admin


def _cop(total):
    return "${:,}".format(int(total or 0)).replace(",", ".")


def _cliente(p):
    return ", ".join(x for x in [p.n_envio, p.tel_envio, p.lugar_envio] if x) or "sin datos de envío"


def aviso_solicitud(s):
    items = "; ".join(f"{it.cantidad or 1} x {it.nombre}" for it in s.items)
    extra = f", {s.email_contacto}" if s.email_contacto else ""
    enviar_admin(f"Nueva solicitud #{s.id} (a la medida): {items}\nContacto: {s.cel_contacto}{extra}")


def aviso_pedido_creado(p, token=None):
    texto = f"Nueva orden #{p.id} pendiente de pago: {_cop(p.total)} — {_cliente(p)}"
    if token:
        texto += f"\nPago: {url_for('pedido.ver', token=token, _external=True)}"
    enviar_admin(texto)


def aviso_pago_aprobado(p, token=None):
    texto = f"Pago aprobado: orden #{p.id} por {_cop(p.total)} ({p.metodo_pago}). {_cliente(p)}. Prepara el pedido."
    if token:
        texto += f"\nSeguimiento: {url_for('pedido.ver', token=token, _external=True)}"
    enviar_admin(texto)


def aviso_pago_rechazado(p):
    enviar_admin(f"Pago rechazado: orden #{p.id} ({_cop(p.total)}, {_cliente(p)}). El cliente puede reintentar.")
