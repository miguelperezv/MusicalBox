"""Bitácora del panel: registra los cambios que hacen los administradores.

No es un log técnico ni analytics: guarda una fila por acción que modifica datos
(pedidos, pagos, stock, precios, catálogo o ajustes), con el correo del admin que
la hizo. Las lecturas y las visitas no se registran.

Uso desde una vista, después de confirmar el cambio:

    registrar_evento("producto.stock", "producto", p.id,
                     f"{p.n_producto}: {antes} → {nuevo}",
                     datos={"antes": antes, "despues": nuevo})
"""
from datetime import date, datetime
from decimal import Decimal

from flask import g, has_request_context

from ..db import db
from .models import AdminEvent


# acción -> (texto para la tabla, icono de Bootstrap, color)
ACCIONES = {
    "pedido.eliminado": ("Pedido eliminado", "trash", "danger"),
    "pedido.rechazado": ("Pedido rechazado", "x-circle", "danger"),
    "pedido.envio": ("Envío actualizado", "truck", "primary"),
    "pedido.datos_envio": ("Datos de envío corregidos", "geo-alt", "warning"),
    "pedido.costo_envio": ("Costo de envío corregido", "cash-coin", "warning"),
    "pedido.nota": ("Nota interna", "chat-left-text", "secondary"),
    "solicitud.estado": ("Estado de solicitud", "arrow-repeat", "secondary"),
    "pago.recordatorio": ("Recordatorio de saldo", "bell", "warning"),
    "pago.recordatorio_masivo": ("Recordatorios masivos", "bell", "warning"),

    "producto.creado": ("Producto creado", "plus-circle", "success"),
    "producto.editado": ("Producto editado", "pencil", "primary"),
    "producto.stock": ("Stock de producto", "boxes", "warning"),
    "producto.precio": ("Precio actualizado", "tag", "warning"),
    "producto.preorden": ("Preorden de producto", "fire", "secondary"),
    "variante.creada": ("Talla/color creada", "plus-circle", "success"),
    "variante.editada": ("Talla/color editada", "pencil", "secondary"),
    "variante.eliminada": ("Talla/color eliminada", "trash", "danger"),
    "pack.actualizado": ("Contenido del pack", "box-seam", "secondary"),
    "lanzamiento.creado": ("Lanzamiento creado", "vinyl", "success"),
    "lanzamiento.editado": ("Lanzamiento editado", "pencil", "primary"),
    "lanzamiento.preorden": ("Preorden de lanzamiento", "fire", "secondary"),
    "lanzamiento.campo": ("Dato del lanzamiento", "pencil", "secondary"),
    "lanzamiento.mockup": ("Mockups generados", "images", "primary"),
    "catalogo.carga_masiva": ("Carga masiva", "file-earmark-arrow-up", "primary"),
    "catalogo.genero": ("Género creado", "tags", "success"),
    "catalogo.categoria": ("Categoría creada", "tags", "success"),
    "catalogo.artista": ("Artista creado", "person", "success"),

    "ajuste.devoluciones": ("Cambios y devoluciones", "arrow-repeat", "secondary"),
    "ajuste.notificaciones": ("Avisos del panel", "bell", "secondary"),
    "ajuste.envios": ("Configuración de envíos", "truck", "secondary"),
    "ajuste.regla_envio": ("Regla de envío", "truck", "secondary"),
    "ajuste.redes": ("Redes en el inicio", "camera-reels", "secondary"),
    "ajuste.secciones": ("Secciones de la tienda", "toggles", "secondary"),
    "ajuste.tema": ("Tema de temporada", "magic", "secondary"),
    "ajuste.negocio": ("Datos del negocio", "shop", "secondary"),

    "admin.creado": ("Administrador creado", "person-gear", "danger"),
}

GRUPOS = {
    "pedidos": ("Pedidos y pagos", ("pedido.", "pago.")),
    "catalogo": ("Catálogo y stock", ("producto.", "variante.", "pack.", "lanzamiento.", "catalogo.")),
    "ajustes": ("Ajustes de la tienda", ("ajuste.",)),
    "admins": ("Administradores", ("admin.",)),
}


def _json_limpio(valor):
    """Convierte Decimal/fechas para que `datos` se pueda guardar como JSON en SQLite y MySQL."""
    if isinstance(valor, dict):
        return {str(k): _json_limpio(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_json_limpio(v) for v in valor]
    if isinstance(valor, Decimal):
        return int(valor) if valor == valor.to_integral_value() else float(valor)
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    return valor


def registrar_evento(accion, entidad=None, entidad_id=None, detalle=None, datos=None):
    """Guarda una acción del admin. Nunca lanza: un fallo de la bitácora no puede
    dañar la operación que ya quedó guardada. Devuelve el evento o None."""
    if not has_request_context():
        return None
    usuario = g.get("user") or {}
    if usuario.get("k_rol") != "ADMIN":
        return None
    email = (usuario.get("email_usuario") or "").strip().lower()
    if not email:
        return None
    evento = AdminEvent(
        usuario_id=usuario.get("id"),
        usuario_email=email[:50],
        accion=accion[:40],
        entidad=(entidad or None),
        entidad_id=entidad_id,
        detalle=(detalle or "").strip()[:300] or None,
        datos=_json_limpio(datos),
    )
    try:
        db.session.add(evento)
        db.session.commit()
        return evento
    except Exception:
        db.session.rollback()
        return None


def consultar_eventos(grupo="", admin="", q="", page=1, per_page=50):
    """Lista la bitácora con filtros. Devuelve (eventos, total, page ya ajustada)."""
    consulta = AdminEvent.query
    if grupo in GRUPOS:
        prefijos = GRUPOS[grupo][1]
        consulta = consulta.filter(db.or_(*[AdminEvent.accion.like(p + "%") for p in prefijos]))
    if admin:
        consulta = consulta.filter(AdminEvent.usuario_email == admin)
    q = (q or "").strip()
    if q:
        like = f"%{q}%"
        filtros = [AdminEvent.detalle.ilike(like), AdminEvent.usuario_email.ilike(like),
                   AdminEvent.accion.ilike(like)]
        if q.isdigit():
            filtros.append(AdminEvent.entidad_id == int(q))
        consulta = consulta.filter(db.or_(*filtros))

    total = consulta.count()
    paginas = max(1, (total + per_page - 1) // per_page)
    page = min(max(1, page or 1), paginas)
    eventos = (consulta.order_by(db.desc(AdminEvent.created_at), db.desc(AdminEvent.id))
               .offset((page - 1) * per_page).limit(per_page).all())
    return eventos, total, page


def admins_con_registros():
    """Correos que aparecen en la bitácora, para el filtro por administrador."""
    filas = (db.session.query(AdminEvent.usuario_email)
             .distinct().order_by(AdminEvent.usuario_email).all())
    return [f[0] for f in filas]


__all__ = ["ACCIONES", "GRUPOS", "registrar_evento", "consultar_eventos", "admins_con_registros"]
