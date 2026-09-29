# PROPUESTA: CHECKOUT UNIFICADO (CARRO + DATOS + PAGO)

## OBJETIVO:
Reducir el flujo actual de 3 pasos a 2 pasos:
1. `/purchase/` (carrito) → `/pedido/<token>` (pago directo)
2. Eliminar `/purchase/checkout` como página intermedia

## CAMBIOS PROPUESTOS:

### 1. MODIFICAR BOTÓN EN CARRO (purchase.html):
- Cambiar el enlace del botón "Continuar al pago"
- Que vaya directamente al proceso de creación de pedido
- Validar carrito y crear pedido en el acto

### 2. CREAR NUEVA RUTA `/purchase/checkout-direct`:
```python
@purchase.route("/checkout-direct")
def checkout_direct():
    # Validar carrito
    lineas, total, errores = validar_carrito(session.get("purchase"))
    if errores:
        for e in errores:
            flash(e, "warning")
        return redirect(url_for('purchase.summary'))
    
    # Crear pedido con datos mínimos (o últimos usados)
    datos = session.get("checkout_datos", {})
    if not datos and g.user:
        # Usar datos del usuario si está logueado
        datos = {
            "nombre": f"{g.user.get('n_usuario', '')} {g.user.get('ape_usuario', '')}".strip(),
            "email": g.user.get("email_usuario"),
            "telefono": g.user.get("cel_usuario") or "",
            "ciudad": g.user.get("lugar_usuario") or "",
            "direccion": g.user.get("dir_usuario") or "",
            "barrio": g.user.get("barrio_usuario") or "",
            "metodo_pago": "MercadoPago"  # Valor por defecto
        }
    
    # Si no hay datos suficientes, usar valores por defecto
    if not datos.get("nombre"):
        datos["nombre"] = "Cliente"
    if not datos.get("email"):
        datos["email"] = ""
    if not datos.get("metodo_pago"):
        datos["metodo_pago"] = "MercadoPago"
    
    # Crear pedido directamente
    nuevo, token, errores = crear_pedido(session.get("purchase"), datos, k_usuario=g.user["id"] if g.user else None)
    if errores:
        for e in errores:
            flash(e, "warning")
        return redirect(url_for('purchase.summary'))
    
    # Limpiar carrito y guardar datos
    session["purchase"] = {}
    session["checkout_datos"] = datos
    
    # Ir directamente a la página de pago
    return redirect(url_for('pedido.ver', token=token))
```

### 3. ACTUALIZAR TEMPLATE purchase.html:
```html
<!-- En lugar de ir a /purchase/checkout, ir directamente a crear pedido -->
<a class="btn btn-primary btn-lg w-100" href="{{ url_for('purchase.checkout_direct') }}">Continuar al pago <i class="bi bi-arrow-right ms-1"></i></a>
```

### 4. MANTENER COMPATIBILIDAD:
- Conservar `/purchase/checkout` para casos especiales
- La ruta existente sigue funcionando
- No romper flujos existentes

## VENTAJAS:
✅ Elimina un paso innecesario
✅ Menos formularios para llenar
✅ Flujo más directo al pago
✅ Menor abandono potencial
✅ Misma funcionalidad técnica
✅ Sin romper compatibilidad

## IMPLEMENTACIÓN:
1. Crear nueva ruta `/purchase/checkout-direct`
2. Modificar botón en carrito
3. Mantener validaciones existentes
4. Crear pedido directamente sin formulario intermedio
5. Ir a página de pago inmediatamente

¿Te gustaría que implemente esta solución?