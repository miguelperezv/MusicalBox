#avises al admin por Telegram: un texto por evento del negocio, con negritas y datos completos.
#contrato: nunca romper el flujo (enviar_admin no lanza excepción) y escapar todo dato dinámico (HTML).
import html

from datetime import datetime
from flask import url_for

from ..telegram import enviar_admin


def _cop(total):
    return "${:,}".format(int(total or 0)).replace(",", ".")


def _esc(valor):
    return html.escape(str(valor or ""))


def _fecha(f):
    return f.strftime("%d/%m %H:%M") if f else "s/f"


def _donde(p):
    partes = [x for x in [p.dir_envio, p.barrio_envio, p.lugar_envio] if x]
    return ", ".join(partes) if partes else "sin dirección"


def _cuerpo(p, token=None, enlace=None, estado_texto=None):
    estado = estado_texto or p.estado
    lineas = [
        f"<b>Total:</b> {_esc(_cop(p.total))} · {_esc(p.metodo_pago or 'método por definir')}",
        f"<b>Quién:</b> {_esc(p.n_envio)} · {_esc(p.tel_envio)}",
        f"<b>Dónde:</b> {_esc(_donde(p))}",
        f"<b>Cuándo:</b> {_fecha(p.f_compra)}",
        f"<b>Estado:</b> {_esc(estado)}",
    ]
    if token and enlace:
        url = url_for('pedido.ver', token=token, _external=True)
        lineas.append(f"{_esc(enlace)}: <a href=\"{url}\">{url}</a>")
    return "\n".join(lineas)


def aviso_solicitud(s):
    items = "; ".join(f"{it.cantidad or 1} x {it.nombre}" for it in s.items)
    extra = f" · {_esc(s.email_contacto)}" if s.email_contacto else ""
    enviar_admin(
        f"<b>NUEVA SOLICITUD #{s.id}</b> — pedido a la medida\n"
        f"<b>Qué:</b> {_esc(items)}\n"
        f"<b>Quién:</b> {_esc(s.cel_contacto)}{extra}\n"
        f"<b>Cuándo:</b> {_fecha(s.f_solicitud)}\n"
        f"<b>Estado:</b> {s.estado}")


def aviso_pedido_creado(p, token=None):
    enviar_admin(f"<b>NUEVO PEDIDO #{p.id}</b>\n{_cuerpo(p, token, 'Pago', 'PENDIENTE DE PAGO')}")


def aviso_pago_aprobado(p, token=None):
    estado = f"PAGADO · envío {p.estado_envio}" if p.estado_envio else "PAGADO"
    enviar_admin(f"<b>PAGO APROBADO · PEDIDO #{p.id}</b>\n{_cuerpo(p, token, 'Seguimiento', estado)}\n<b>Prepara el pedido.</b>")


def aviso_pago_rechazado(p, token=None):
    enviar_admin(f"<b>PAGO RECHAZADO · PEDIDO #{p.id}</b>\n{_cuerpo(p, token, 'Reintento', 'RECHAZADO')}\nEl cliente puede reintentar.")
