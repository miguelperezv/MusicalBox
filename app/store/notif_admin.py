#avises al admin por Telegram: un mensaje por evento con contexto completo.
#bloques separados en blanco: productos (lanzamiento arriba, producto y precio debajo),
#totales (subtotal, envío, total compra), comprador, estado, acciones y enlace.
#HTML: se escapa todo dato dinámico; enviar_admin nunca rompe el flujo.
import html

from datetime import datetime
from flask import url_for

from ..telegram import enviar_admin
from .models import Item


def _cop(total):
    return "${:,}".format(int(total or 0)).replace(",", ".")


def _esc(valor):
    return html.escape(str(valor or ""))


def _fecha(f):
    return f.strftime("%d/%m %H:%M") if f else "s/f"


def _direccion(p):
    partes = [x for x in [p.dir_envio, p.barrio_envio, p.lugar_envio] if x]
    return ", ".join(partes) if partes else "sin dirección"


def _items_bloque(p):
    #ítems agrupados por lanzamiento: el lanzamiento va arriba (cursiva) y debajo, producto, cantidad y precio
    grupos = {}
    for item in Item.query.filter_by(k_factura=p.id).all():
        n = int(item.cant_item or 1)
        if item.producto:
            prod = item.producto.n_producto or "producto"
            if item.variante:
                vt = " ".join(x for x in [item.variante.talla, item.variante.color] if x)
                if vt:
                    prod += f" ({vt})"
            lanza = item.lanzamiento or item.producto.lanzamiento
        else:
            prod = item.n_item or "a la medida"
            lanza = None
        clave = lanza.n_lanzamiento.title() if lanza else None
        grupos.setdefault(clave, []).append(f"{prod} × {n} · {_cop(int((item.p_item or 0) * n))}")
    lineas = []
    for clave, filas in grupos.items():
        if clave:
            lineas.append(f"<i>{_esc(clave)}</i>")
        lineas.extend(_esc(f) for f in filas)
    return "\n".join(lineas) if lineas else "sin ítems"


def _total_bloque(p):
    items = Item.query.filter_by(k_factura=p.id).all()
    subtotal = sum(int((i.p_item or 0) * int(i.cant_item or 1)) for i in items)
    p_envio = int(p.p_envio or 0)
    lineas = [f"Subtotal: {_cop(subtotal)}"]
    if p_envio > 0:
        lineas.append(f"Envío: {_cop(p_envio)}" + (f" · {_esc(p.d_envio)}" if p.d_envio else ""))
    elif p.d_envio:
        lineas.append(f"Envío: {_esc(p.d_envio)}")
    lineas.append(f"<b>Total compra: {_cop(subtotal + p_envio)}</b> · {_esc(p.metodo_pago or 'método por definir')}")
    return "\n".join(lineas)


def _comprador_bloque(p):
    extra = f" · {_esc(p.email_envio)}" if p.email_envio else ""
    return f"{_esc(p.n_envio or 'sin nombre')}\n{_esc(p.tel_envio or 'sin teléfono')}{extra}\n{_esc(_direccion(p))}"


def _cuerpo(p, estado_texto, accion, token=None, enlace=None):
    bloques = [
        f"<b>PRODUCTOS</b>\n{_items_bloque(p)}",
        f"<b>TOTALES</b>\n{_total_bloque(p)}",
        f"<b>COMPRADOR</b>\n{_comprador_bloque(p)}",
        f"<b>ESTADO</b>\n{_esc(estado_texto)} · {_fecha(p.f_compra)}",
        f"<b>ACCIONES</b>\n{_esc(accion)}",
    ]
    if token and enlace:
        url = url_for('pedido.ver', token=token, _external=True)
        bloques.append(f"{_esc(enlace)}: <a href=\"{url}\">{url}</a>")
    return "\n\n".join(bloques)


def aviso_solicitud(s):
    items = []
    for it in s.items:
        extra = f" ({it.categoria})" if it.categoria else ""
        desc = f" · “{it.descripcion}”" if it.descripcion else ""
        items.append(f"{it.cantidad or 1} × {_esc(it.nombre)}{extra}{desc}")
    extra = f" · {_esc(s.email_contacto)}" if s.email_contacto else ""
    bloques = [
        f"<b>NUEVA SOLICITUD #{s.id}</b> · pedido a la medida",
        f"<b>ÍTEMS SOLICITADOS</b>\n" + "\n".join(items),
        f"<b>CONTACTO</b>\n{_esc(s.cel_contacto)}{extra}",
        f"<b>ESTADO</b>\n{s.estado} · {_fecha(s.f_solicitud)}",
        "Elige cómo continuar:",
    ]
    enviar_admin("\n\n".join(bloques), botones=[
        {"texto": "💻 Cotizar en web", "url": url_for('home.admin', sol=s.id, _external=True)},
        {"texto": f"📩 Ver y cotizar en el chat", "callback": f"mtx:{s.id}"},
    ])


def aviso_pedido_creado(p, token=None):
    enviar_admin(f"<b>NUEVO PEDIDO #{p.id}</b> · orden de compra\n\n"
                 + _cuerpo(p, "PENDIENTE DE PAGO", "El cliente aún no paga; el stock queda reservado 30 min.",
                           token, "Pago"))


def aviso_pago_aprobado(p, token=None):
    estado = "PAGADO" + (f" · envío {p.estado_envio.lower()}" if p.estado_envio else "")
    enviar_admin(f"<b>PAGO APROBADO · PEDIDO #{p.id}</b>\n\n"
                 + _cuerpo(p, estado, "Prepara el pedido.", token, "Seguimiento"))


def aviso_pago_rechazado(p, token=None):
    enviar_admin(f"<b>PAGO RECHAZADO · PEDIDO #{p.id}</b>\n\n"
                 + _cuerpo(p, "RECHAZADO", "El cliente puede reintentar el pago.", token, "Reintento"))
