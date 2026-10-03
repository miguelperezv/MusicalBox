#avises al admin por Telegram: un texto por evento del negocio.
#cada aviso es opcional y nunca rompe el flujo (enviar_admin nunca lanza excepción).
from flask import url_for

from ..telegram import enviar_admin


def _cop(total):
    return "${:,}".format(int(total or 0)).replace(",", ".")


def _cliente(p):
    partes = [x for x in [p.n_envio, p.tel_envio, p.lugar_envio] if x]
    return " · ".join(partes) if partes else "sin datos de envío"


def _cuerpo(pedido, token=None, enlace=None):
    #total y método en una línea, cliente en la otra; enlace opcional con su etiqueta
    lineas = [f"{_cop(pedido.total)} · {pedido.metodo_pago or 'método por definir'}",
              f"Cliente: {_cliente(pedido)}"]
    if token and enlace:
        lineas.append(f"{enlace}: {url_for('pedido.ver', token=token, _external=True)}")
    return "\n".join(lineas)


def aviso_solicitud(s):
    items = "; ".join(f"{it.cantidad or 1} x {it.nombre}" for it in s.items)
    extra = f" · {s.email_contacto}" if s.email_contacto else ""
    enviar_admin(f"NUEVA SOLICITUD #{s.id} (a la medida)\nItems: {items}\nContacto: {s.cel_contacto}{extra}")


def aviso_pedido_creado(p, token=None):
    enviar_admin(f"ORDEN #{p.id} PENDIENTE DE PAGO\n{_cuerpo(p, token, 'Pago')}")


def aviso_pago_aprobado(p, token=None):
    enviar_admin(f"PAGO APROBADO · ORDEN #{p.id}\n{_cuerpo(p, token, 'Seguimiento')}\nPrepara el pedido.")


def aviso_pago_rechazado(p, token=None):
    enviar_admin(f"PAGO RECHAZADO · ORDEN #{p.id}\n{_cuerpo(p, token, 'Reintento')}\nEl cliente puede reintentar.")
