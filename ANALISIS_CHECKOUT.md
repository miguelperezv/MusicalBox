# ANÁLISIS DEL FLUJO DE COMPRA ACTUAL

## FLUJO ACTUAL:
1. `/purchase/` - Carrito de compras
2. `/purchase/checkout` - Formulario de envío y método de pago
3. `/pedido/<token>` - Página de confirmación con botón de pago

## PROBLEMAS IDENTIFICADOS:

### 1. REDUNDANCIA DE INFORMACIÓN:
- Método de pago se selecciona en checkout y también en el Payment Brick
- Información de envío se repite en múltiples pantallas
- Demasiados pasos para llegar al pago real

### 2. CONFUSIÓN DE PROPÓSITO:
- `/checkout` parece un paso intermedio innecesario
- El usuario no entiende por qué necesita tantas páginas
- La separación de conceptos no es clara para el usuario promedio

### 3. FRICCIÓN EN EL FLUJO:
- 3 páginas diferentes para completar una compra
- Información repetida (método de pago en dos lugares)
- Tiempo de carga entre cada paso

## SOLUCIÓN PROPUESTA:

### OPCIÓN 1: MODAL DE CHECKOUT DIRECTO
- Eliminar la página `/purchase/checkout` por separado
- Mostrar formulario de envío en modal desde el carrito
- Ir directamente a `/pedido/<token>` con Payment Brick integrado

### OPCIÓN 2: CHECKOUT UNIFICADO
- Combinar carrito + checkout en una sola página
- Mostrar Payment Brick directamente en esa página
- Eliminar el paso intermedio completamente

### OPCIÓN 3: FLUJO MINIMALISTA
- Desde carrito → modal con datos mínimos → pago inmediato
- Solo pedir información esencial (dirección)
- Método de pago directamente en Payment Brick

## RECOMENDACIÓN:
Implementar OPCIÓN 2 (CHECKOUT UNIFICADO) porque:
- Mantiene compatibilidad con flujos existentes
- Reduce fricción significativamente
- Simplifica la experiencia de usuario
- No rompe funcionalidades actuales
- Menos páginas = menor abandonos

## CAMBIOS NECESARIOS:
1. Combinar templates de carrito y checkout
2. Mantener endpoint `/purchase/checkout` pero con nueva UI
3. Validar carrito y crear pedido directamente
4. Redirigir inmediatamente a `/pedido/<token>`
5. Ajustar Payment Brick para funcionar con flujo más corto

## IMPACTO:
- Reducción de 3 páginas a 2 pasos principales
- Menos abandonos en el proceso de compra
- Experiencia más directa y clara
- Sin romper funcionalidades existentes