# Cotizaciones v2: pedidos a la medida con ítems

Propuesta de análisis antes de tocar esquema. Flujo: cliente cotiza uno o más productos →
admin pone precios (sin obligación de asociar producto del catálogo, pero sí puede asociar
lanzamiento por ítem) → mensaje de WhatsApp ordenado con preview → cliente paga con sus datos
prellenados y puede ajustar cantidades del "carrito" de la cotización.

## 1. Qué existe hoy

- **Solicitud 1:1 con producto**: `Solicitud.k_producto`, `n_producto_solicitado`, `cantidad`,
  `precio_cotizado` (`app/store/models.py:228`). Una solicitud = un disco, un precio.
- **Cliente** (`/solicitud`, `app/store/solicitudes.py:17`, plantilla `solicitud.html`):
  un único campo "disco" con autocompletado del catálogo (`/solicitud/productos`), detalles,
  celular y correo. Sin categoría, sin cantidad, un solo producto.
- **Admin** (`solicitudes.html` + `solicitudes.py:104`): cotizar exige producto del catálogo
  individual (`cotizar_solicitud`, `models.py:1624` rechaza BUNDLE y variantes) y genera el
  mensaje actual: "Conseguimos tu pedido: X unidades de DISCO - PRODUCTO por $Y. Confirma aquí: enlace".
- **Confirmar** (`solicitudes.py:115`): requiere `s.producto` y `s.precio_cotizado`, pinta una
  sola línea en `checkout.html` (cover vía `product_cover`), prellena datos con
  `datos_envio_previos(email)` y llama a `crear_pedido(cotizacion=(producto, precio, cantidad))`
  sin revisar ni reservar stock (`models.py:1332`).
- **Orden**: `Item.k_producto` es `NOT NULL` (`models.py:155`); todas las vistas de orden
  (`pedido.html`, `invoices.html`, `account.html`, correos `pedido_pagado.*`) pintan
  `item.producto` y su lanzamiento para el cover.

## 2. Propuesta

### 2.1 Modelo de datos (1 migración nueva, SQLite con batch)

| Cambio | Tipo | Detalle |
|---|---|---|
| Tabla `solicitud_item` | **aditivo** | Ítem de la solicitud: `id`, `k_solicitud` (FK, no null, índice), `k_lanzamiento` (FK, opcional: da la imagen), `k_producto` (FK, opcional: asociación de catálogo), `nombre` (varchar 150, no null), `descripcion` (varchar 200), `categoria` (varchar 30, la que elige el cliente), `cantidad` (int, default 1), `precio_unit` (numeric 11,2, lo pone el admin), `f_creacion` |
| `solicitud.d_cotizacion` | **aditivo** | Nota del admin sobre la cotización (tiempos, edición, comentarios). varchar 300, va en el mensaje |
| `solicitud_item.id` en `Solicitud.items` | **aditivo** | Relación 1:N con cascade; `Solicitud.d_cotizacion` |
| `item.k_lanzamiento` + `item.n_item` | **aditivo** | La línea de orden puede referirse a un lanzamiento y a un texto propio sin producto de catálogo |
| `item.k_producto` → nullable | **rompe esquema** | En SQLite se reconstruye la tabla con `batch_alter_table` (precedente: migración `3c91f0d79d11`, que ya reconstruyó `item`). Downgrade: revertir |

**Retrocompatibilidad**: las columnas legacy de `Solicitud` (`k_producto`, `n_producto_solicitado`,
`d_producto_solicitado`, `cantidad`, `precio_cotizado`) **se conservan** para las solicitudes
viejas. Se agrega un helper `items_efectivos(s)`: si `s.items` no está vacío lo usa; si no,
construye un ítem virtual con los campos legacy. Cero migración de datos, cero borrar.

### 2.2 Cliente (`/solicitud`)

- Formulario con **lista dinámica de ítems** (JavaScript: fila base + botón "Agregar ítem"):
  cada fila tiene **nombre** (con el autocompletado del catálogo actual, que sigue resolviendo
  `producto_id` cuando es exacto), **categoría** (select: categorías de la tabla `Categoria`
  vía `get_categories()` + "OTRO"), **cantidad** (1–99, default 1) y **detalles**.
- Confianza: la columna izquierda ya tiene los 3 pasos; se agrega una franja corta de sellos:
  "Cotización sin compromiso · Pagas solo por el enlace seguro · Envíos a todo Colombia ·
  Respondemos por WhatsApp". Sin inventar garantías que no existen.
- `RegistroSolicitudForm` pasa a un `FieldList` de ítems (WTForms) o parsing manual de
  `items[N]_*` (más simple y compatible con el autocomplete JS; prefiero parsing manual).

### 2.3 Admin (panel "Pedidos a la medida")

- Columna "Disco": muestra el primer ítem + "+N ítems" cuando hay varios.
- **Cotizar por ítem**: la fila de cotización de cada ítem deja:
  - **precio** (obligatorio por ítem; se prellena con `p_producto` si el ítem ya tiene producto),
  - **producto del catálogo** (opcional; autocomplete `editproduct_productList`; ya no es
    obligatorio y ya no se rechaza BUNDLE/variante: la orden no revisa stock),
  - **lanzamiento** (opcional; autocomplete `newproduct_releases`; es el que da la imagen en
    el mensaje y en la orden),
  - **cantidad** editable.
  - un campo **nota de la cotización** (`d_cotizacion`: tiempos, edición, lo que el admin dejó
    acordado) que va en el mensaje.
- Al cotizar: estado `COTIZADA`, `token_hash`, y la respuesta devuelta al panel incluye:
  - el **mensaje** reescrito (ver mockup),
  - la **preview** (URL del cover del lanzamiento del primer ítem con imagen) para pintarla
    junto al botón,
  - el link `wa.me` y el enlace para copiar.
- El "mini nuevo pedido a la medida" del panel mantiene su camino de 1 ítem (crea su
  `solicitud_item` igual que el formulario público).

**Límite técnico de WhatsApp**: `wa.me?text=` **no permite incrustar imágenes** en el texto
(lo haría la Business API con media, que no usamos). Por eso la preview vive **en el panel**,
junto al botón de enviar (la portada pequeña la reenvía el admin con un toque), y el mensaje
lleva un link a la página del lanzamiento en el sitio para que el cliente vea la portada.

**Mockup del mensaje** (números al estilo colombiano, `120.000`):

```
¡Hola! Tu pedido a la medida en Musical Box quedó así:

• 2 × Vinilo — Happier Than Ever (Billie Eilish)
   120.000 c/u  →  240.000
• 1 × Camiseta Logo MB (M)
   80.000

Total: 320.000
Tiempos: llega en 2 a 3 semanas
Portada: https://musicalbox.app/lanzamientos/12

Confirma tu compra y datos de envío aquí:
https://musicalbox.app/solicitud/confirmar/XXXX
```

(Solo incluye el link de portada si el ítem tiene lanzamiento asociado; la nota de tiempos solo
si el admin la dejó.)

### 2.4 Confirmar compra (`/solicitud/confirmar/<token>`)

- Mantiene el prefilled actual (`datos_envio_previos` + celular/correo de la solicitud).
- La caja lateral lista **todos los ítems** con su cover: `product_cover` si tiene producto de
  catálogo, si no la portada del lanzamiento asociado, si no el logo.
- **Cantidad editable por línea** (input 1–99; JS recalcula subtotal y total en vivo; el total
  final siempre se recalcula en el servidor como Σ `precio_unit × cantidad`, el cliente no
  envía el total).
- `crear_pedido` recibe `cotizacion=` ahora como **lista** de líneas
  `{producto, cantidad, precio, k_lanzamiento, n_item}` (antes era tupla de 1 línea).
  Sigue sin revisar ni reservar stock. Cada `Item` se crea con `k_producto` (puede ser null),
  `k_lanzamiento` y `n_item`.
- Vistas de orden (`pedido.html`, `invoices.html`, `account.html`, correos
  `pedido_pagado.html/.txt`): fallback cuando `item.producto` es null → pintar
  `item.lanzamiento` + `item.n_item` y su cover. Es el único punto "rompe": todos esos
  templates tocan `item.producto` a ras.

## 3. Qué es aditivo y qué rompe

**Aditivo (no toca lo existente)**
- Tabla `solicitud_item`, `solicitud.d_cotizacion`, `item.k_lanzamiento`, `item.n_item`.
- Nuevo endpoint de JSON de ítems si hiciera falta (no hace falta: el catálogo ya existe).
- La página de confirmación y el mensaje de WhatsApp.

**Compatible con datos existentes**
- Solicitudes viejas sin `solicitud_item`: `items_efectivos()` las sirve con un ítem virtual
  desde los campos legacy; se pueden cotizar igual (el admin puede asociarles producto o
  lanzamiento ese momento).

**Rompe (cambios de contrato)**
- `Item.k_producto` queda nullable → **5 templates + 2 correos** necesitan el fallback de
  "sin producto de catálogo" (se listan en 2.4). Lógica de stock: `confirmar_pago` ya hace
  `if item.producto:` antes de `descontar_stock`, y la cotización no reserva stock: no hay
  camino de stock que se rompa.
- `crear_pedido(cotizacion=...)` cambia de tupla a lista: es interna, solo la llaman
  `solicitudes.py:confirmar` y tests (la suite vieja ya está desactualizada por ePayco).
- `cotizar_solicitud` cambia de signature (ítems en vez de producto único): la llama solo
  `solicitudes.py` (rutas `cotizar` y `nueva_admin`).
- `create_solicitud` ahora crea ítems: la llaman `nueva()` y `nueva_admin()`.

## 4. Archivos a tocar

| Archivo | Cambio |
|---|---|
| `app/store/models.py` | `SolicitudItem` + relación, `d_cotizacion` en `Solicitud`, campos nuevos en `Item`, `create_solicitud` con ítems, `cotizar_solicitud` por ítems, `crear_pedido` con lista de líneas, `items_efectivos()` |
| `migrations/versions/…` (nueva) | `solicitud_item`, `solicitud.d_cotizacion`, reconstrucción batch de `item` |
| `app/store/forms.py` | `RegistroSolicitudForm` con ítems/categorías/cantidades; `CotizacionRapidaForm` sin cambios de contrato |
| `app/store/solicitudes.py` | `nueva()` (parsing de ítems), `cotizar`/`nueva_admin` por ítems, `confirmar` con cantidades y covers, `_respuesta_cotizar` nuevo mensaje + preview |
| `app/templates/solicitud.html` | Lista dinámica de ítems + franja de confianza |
| `app/templates/solicitudes.html` | Cotizar por ítem (precio, producto, lanzamiento, cantidad, nota) + preview del cover en el resultado |
| `app/templates/checkout.html` | Líneas con cover propio, steppers de cantidad y total en vivo cuando viene de cotización |
| `app/templates/pedido.html`, `invoices.html`, `account.html`, `correos/pedido_pagado.html`, `correos/pedido_pagado.txt` | Fallback `item.producto → item.lanzamiento/n_item` |

## 5. Plan de ejecución y verificación

1. Worktree `..\MusicalBox-cotizaciones` en `feature/cotizaciones` (BD aislada, venv principal).
2. Modelos + migración (revisión manual) → respaldo de la BD local → `db upgrade`.
3. Vistas + forms + templates, en el orden: cliente → admin → confirmar → fallbacks de orden.
4. Verificación sin tests nuevos: curl de los endpoints (crear solicitud multi-ítem, cotizar,
   confirmar con cantidad cambiada, pedir `/pedido/<token>`) + capturas Playwright de
   `/solicitud`, panel de solicitudes y página de pedido (portada sin producto de catálogo).
5. Commits pequeños por capa; merge a `main` + push cuando apruebes; luego
   `git worktree remove`.

## 6. Decisiones por confirmar

1. **Categorías del cliente**: uso las de la tabla `Categoria` (las mismas del catálogo) + "OTRO". ¿Bien?
2. **Cantidad en el formulario del cliente** (no solo en la confirmación): ¿la dejamos?
3. **WhatsApp**: preview en el panel + link de portada en el texto (WhatsApp no incrusta imágenes en `wa.me`). ¿Aceptas ese alcance?
4. **Precio por ítem** (no un precio global de la solicitud): ¿es lo que quieres?
5. Nada se borra: solicitudes y datos de prueba legacy siguen sirviéndose vía ítem virtual.
