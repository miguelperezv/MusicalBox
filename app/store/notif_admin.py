#avises al admin por Telegram y WhatsApp: un mensaje por evento con contexto completo.
#bloques separados en blanco: productos (lanzamiento arriba, producto y precio debajo),
#totales (subtotal, envío, total compra), comprador, estado, acciones y enlace.
#HTML: se escapa todo dato dinámico; enviar_admin/enviar_admin_wa nunca rompen el flujo.
import html

from datetime import datetime
from flask import url_for

from ..telegram import enviar_admin
from ..whatsapp import enviar_admin_wa
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
        "<b>ACCIONES</b>\nCotiza y escribe al cliente por WhatsApp.",
    ]
    url = url_for('solicitud.lista', _external=True)
    bloques.append(f"Cotizar en el panel: <a href=\"{url}\">{url}</a>")
    enviar_admin("\n\n".join(bloques))
    #también va a WhatsApp: es el momento en que el admin debe cotizar y escribirle al cliente
    lineas_wa = []
    for it in s.items:
        desc = f" · “{it.descripcion}”" if it.descripcion else ""
        lineas_wa.append(f"{it.cantidad or 1} × {it.nombre}{desc}")
    texto_wa = (f"🎵 Nueva solicitud #{s.id} · a la medida\n"
                f"Cliente: {s.cel_contacto or 'sin contacto'}"
                + (f" · {s.email_contacto}" if s.email_contacto else "") + "\n"
                + "\n".join(lineas_wa or ["sin ítems"]) + "\n"
                + f"Ver: {url}")
    enviar_admin_wa(texto_wa)


def _lineas_cotizacion(s):
    #ítems cotizados en texto plano: "1 × Nombre (talla) · $150.000"
    lineas = []
    for it in (s.items or []):
        if not it.precio_unit:
            continue
        n = int(it.cantidad or 1)
        nombre = it.nombre or (it.producto.n_producto if it.producto else "producto")
        desc = f" ({it.descripcion})" if it.descripcion else ""
        lineas.append(f"{n} × {str(nombre)}{desc} · {_cop(it.precio_unit * n)}")
    return lineas


def aviso_cotizacion(s, token=None):
    #nueva cotización del admin: va a los dos canales; en WhatsApp, enlace al panel
    total = int(s.total_cotizado or 0)
    contacto = s.cel_contacto or "sin contacto"
    bloques = [
        f"<b>NUEVA COTIZACIÓN #{s.id}</b> · pedido a la medida",
        f"<b>ÍTEMS</b>\n" + "\n".join(f"· {_esc(x)}" for x in _lineas_cotizacion(s)) or "sin ítems",
        f"<b>CONTACTO</b>\n{_esc(contacto)}",
        f"<b>TOTAL</b>\n{_cop(total)}" + (f" · {_esc(s.d_cotizacion)}" if s.d_cotizacion else ""),
        "<b>ACCIONES</b>\nRevisa y marca la cotización.",
    ]
    url = url_for('solicitud.lista', _external=True)
    bloques.append(f"Ver en el panel: <a href=\"{url}\">{url}</a>")
    enviar_admin("\n\n".join(bloques))
    linea_wa = "\n".join(_lineas_cotizacion(s)) or "sin ítems"
    texto_wa = (f"🎵 Nueva cotización #{s.id}\n"
                f"Cliente: {contacto}\n"
                f"{linea_wa}\n"
                f"Total: {_cop(total)}\n"
                f"Ver: {url}")
    enviar_admin_wa(texto_wa)


def aviso_pedido_creado(p, token=None):
    enviar_admin(f"<b>NUEVO PEDIDO #{p.id}</b> · orden de compra\n\n"
                 + _cuerpo(p, "PENDIENTE DE PAGO", "El cliente aún no paga; el stock queda reservado 30 min.",
                           token, "Pago"))


def _total_compra(p):
    #subsan + envío, en entero, para reutilizar en el aviso de WhatsApp
    items = Item.query.filter_by(k_factura=p.id).all()
    subtotal = sum(int((i.p_item or 0) * int(i.cant_item or 1)) for i in items)
    return subtotal + int(p.p_envio or 0)


def _lineas_producto(p):
    #ítems en texto plano (sin HTML) para el canal de WhatsApp
    items = Item.query.filter_by(k_factura=p.id).all()
    lineas = []
    for item in items:
        n = int(item.cant_item or 1)
        if item.producto:
            prod = item.producto.n_producto or "producto"
            if item.variante:
                vt = " ".join(x for x in [item.variante.talla, item.variante.color] if x)
                if vt:
                    prod += f" ({vt})"
        else:
            prod = item.n_item or "a la medida"
        lineas.append(f"{n} × {prod} · {_cop(int((item.p_item or 0) * n))}")
    return lineas or ["sin ítems"]


def aviso_pago_aprobado(p, token=None):
    estado = "PAGADO" + (f" · envío {p.estado_envio.lower()}" if p.estado_envio else "")
    enviar_admin(f"<b>PAGO APROBADO · PEDIDO #{p.id}</b>\n\n"
                 + _cuerpo(p, estado, "Prepara el pedido.", token, "Seguimiento"))
    url = url_for('dashboard.invoices', busca=p.id, _external=True)
    texto_wa = (f"✅ Pago aprobado · Pedido #{p.id}\n"
                + "\n".join(_lineas_producto(p)) + "\n"
                + f"Total: {_cop(_total_compra(p))}\n"
                + f"Cliente: {p.n_envio or 'sin nombre'} · {p.tel_envio or 'sin teléfono'}\n"
                + f"Ver: {url}")
    enviar_admin_wa(texto_wa)


def aviso_pago_rechazado(p, token=None):
    enviar_admin(f"<b>PAGO RECHAZADO · PEDIDO #{p.id}</b>\n\n"
                 + _cuerpo(p, "RECHAZADO", "El cliente puede reintentar el pago.", token, "Reintento"))
