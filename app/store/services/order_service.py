"""Operaciones de pedidos.

La creación, confirmación y rechazo siguen en `models.py` por ahora; este módulo
es el punto de entrada para las vistas. `actualizar_envio` ya vive aquí.
"""
from ..models import (
    ESTADOS_ENVIO,
    Invoice,
    db,
    confirmar_pago,
    crear_pedido,
    liberar_reserva_stock,
    rechazar_pago,
    reservar_stock_pedido,
    validar_carrito,
)


def actualizar_envio(k_invoice, estado, guia=None, carrier=None):
    pedido = db.session.get(Invoice, k_invoice)
    if not pedido or pedido.estado != "PAGADO" or estado not in ESTADOS_ENVIO:
        return None
    pedido.estado_envio = estado
    #la guía y la transportadora se pueden corregir mientras el pedido no esté entregado
    if guia is not None and estado != "ENTREGADO":
        pedido.guia = (guia or "").strip()[:60] or None
    if carrier is not None and estado != "ENTREGADO":
        pedido.envio_carrier = (carrier or "").strip()[:30] or None
    db.session.commit()
    return pedido


__all__ = [
    "actualizar_envio",
    "confirmar_pago",
    "crear_pedido",
    "liberar_reserva_stock",
    "rechazar_pago",
    "reservar_stock_pedido",
    "validar_carrito",
]
