"""Carrito en la sesión: {"producto" o "producto:variante": cantidad}."""
from ..db import db
from .models import Producto, Variante, clave_carrito, nombre_linea, requiere_variante, stock_disponible, validar_carrito, es_preorden


def _leer_clave(clave):
    partes = str(clave).split(":")
    producto = db.session.get(Producto, int(partes[0])) if partes[0].isdigit() else None
    variante = db.session.get(Variante, int(partes[1])) if len(partes) > 1 and partes[1].isdigit() else None
    if variante is not None and (producto is None or variante.k_producto != producto.id):
        return None, None
    return producto, variante


def agregar(cart, k_producto, k_variante, cantidad):
    """Suma al carrito sin pasar del stock disponible. Devuelve (carrito, mensaje, categoría)."""
    cart = dict(cart or {})
    producto = db.session.get(Producto, k_producto) if k_producto else None
    variante = db.session.get(Variante, k_variante) if k_variante else None
    if not producto or (variante is not None and variante.k_producto != producto.id):
        return cart, "Ese producto ya no está disponible", "warning"
    if requiere_variante(producto) and variante is None:
        return cart, "Elige talla o color antes de agregar", "warning"
    clave = clave_carrito(producto.id, variante.id if variante is not None else None)
    disponible = 99 if es_preorden(producto) else stock_disponible(producto, variante)
    actual = int(cart.get(clave, 0))
    if disponible <= actual:
        return cart, f"{nombre_linea(producto, variante)}: no quedan más unidades disponibles", "warning"
    nueva = min(actual + max(1, cantidad), disponible)
    cart[clave] = nueva
    if nueva < actual + cantidad:
        return cart, f"Solo quedan {disponible} de {nombre_linea(producto, variante)}; agregamos las disponibles", "info"
    return cart, f"Agregado al carrito: {nombre_linea(producto, variante)}", "success"


def cambiar_cantidad(cart, clave, delta):
    cart = dict(cart or {})
    if clave not in cart:
        return cart, None
    producto, variante = _leer_clave(clave)
    nueva = int(cart[clave]) + delta
    if producto is None or nueva <= 0:
        cart.pop(clave)
        return cart, None
    if delta > 0 and not es_preorden(producto) and nueva > stock_disponible(producto, variante):
        return cart, "No hay más unidades disponibles"
    cart[clave] = nueva
    return cart, None


def resumen(cart):
    """Líneas para mostrar (sin descartar las que tienen problemas) y los avisos de stock antes de pagar."""
    lineas, total = [], 0
    for clave, cantidad in (cart or {}).items():
        producto, variante = _leer_clave(clave)
        if producto is None:
            continue
        cantidad = int(cantidad)
        preorden = es_preorden(producto)
        disponible = 99 if preorden else stock_disponible(producto, variante)
        falta_variante = requiere_variante(producto) and variante is None
        lineas.append({"clave": clave, "producto": producto, "variante": variante, "cantidad": cantidad,
                       "disponible": disponible, "subtotal": producto.p_producto * cantidad,
                       "preorden": preorden,
                       "problema": "Elige talla o color" if falta_variante else
                                   (f"Solo quedan {disponible}" if cantidad > disponible else None)})
        total += producto.p_producto * cantidad
    errores = validar_carrito(cart)[2] if lineas else []
    return lineas, total, errores
