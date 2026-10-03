# Mejoras generales de la página: stock, contenido y presentación

Fecha: 2026-10-02 · Compañero de `docs/estudio-mejoras.md` (ese cubre **shipping/logística**; este cubre
**cómo se presenta la información**: stock, contenido, tarjetas, páginas y navegación). Método: revisión de
plantillas/modelos actuales + 11 tiendas reales (Taylor, Gaga, Discogs, Juno, Bandcamp, XL, Charli, Zara,
Madonna, PinkPantheress/Warner y pinkpantheress.shop como anti-ejemplo).

## 1. Baseline: lo que ya tenemos y está bien (no reinventar)

- **Chips de estado en PDP**: "Agotado" y "¡Últimos N!" (`_producto_detalle.html`) + variantes que muestran
  "quedan N / agotado / disponible".
- **CTA agotado con salida real**: "Agotado · Pedirlo" → pedido a la medida. Nadie de los analizados tiene esto:
  es diferenciador, se conserva.
- **Vista rápida** (`data-quickview` / `#mbModal`): modal de producto y post de lanzamiento. Poco común en
  tiendas de discos; ventaja.
- **Multi-imagen por producto**: tabla `Imagen` N:1 con `orden`, reorden en admin y ruta con `?orden=N`
  (carrusel ya existe).
- **"desde $X"** en cards con variantes/packs (`precio_desde`).
- **Empty states** (`mb-empty`) en home, catálogos, cuenta, carrito + **404 con CTAs**.
- **Categorías** ya son colecciones: `/products/<categoria>` (VINILO, CD, CASSETTE...).
- **Redes en el lanzamiento** (`url_social` + modal): diferenciador propio.
- **Privacidad**: `/pedido` con `noindex` y token.

Gaps confirmados en código: **sin buscador público**, **sin captura de email en ninguna parte**, footer **sin
enlaces de ayuda** ("Contacto" apunta a Instagram), `Lanzamiento` **sin campo de descripción** (solo
nombre/fecha/portada/url_social), cards **sin "Últimos N"**, `/pedido` **sin timeline de envío ni tracking**.

## 2. Lo que hacen bien las referencias

### 2.1 Presentación del stock (tema central pedido)

Regla de oro: **el stock nunca desaparece, se comunica**. Cada estado tiene badge + CTA visible:

| Estado | Ejemplo real | CTA que ofrecen |
|---|---|---|
| Agotado | Zara, PinkPantheress: "Sold out" **con el precio visible** | "Avisen cuando vuelva a estar disponible" (Gaga) |
| Últimos N | Taylor "Last 3" | Compra + urgencia |
| Coming soon | Juno "Coming Soon" (con fecha) | "Avísenme del lanzamiento" |
| Pre-order | Charli: **toda la colección** en badge "Pre-Order"; Warner: "se despacha el día antes del release" | Agregar al carrito ("se cobra ahora, se envía ~fecha") |
| Limitado | Taylor "Limit 4 per customer · US customers only · While supplies last" | Urgencia explícita |
| Recién restockeado | Juno "Back In Stock (14 days)" | Sección propia en el catálogo |
| Restock anunciado | Taylor: banner superior "Opalite 7 is back for 00:00:00" (cuenta regresiva) | Botón al producto |

Lecciones: (a) agotado = precio visible + 2 CTAs ("avísenme" y nuestro "pedirlo"); (b) "próximamente" es un
estado de catálogo, no solo del lanzamiento; (c) la escasez se declara por escrito (límite, "while supplies
last"), no se deja adivinar; (d) los restocks se anuncian, no solo aparecen.

### 2.2 Contenido de producto y de lanzamiento

- **"Qué hay en la caja"** (Taylor, PDP de vinilo): material, nº de tracks, tipo de vinilo, gatefold, posters,
  sleeves — una lista, no un párrafo.
- **Tracklist + créditos + duración por pista** (Discogs) — opcional por lanzamiento, denso para coleccionistas.
- **Descripción del lanzamiento** (1–2 párrafos) — Gaga por era/álbum; nosotros: campo nuevo en `Lanzamiento`.
- **Descripción corta + acordeón** (Gaga PDP): línea corta + detalles colapsables.
- **Meta en tarjeta** (XL): tipo · fecha · cat number ("lp2026-11-13 XL1712MF") bajo la portada.
- **"Otras versiones / otras ediciones"** (Discogs) → nuestro equivalente: cross-link entre formatos/packs del
  mismo lanzamiento ("también disponible en pack / en cassette").
- **Fotos multi-ángulo** (todos): frente/dorso/disco/detalle (Madonna F/B, Charli hasta 5 fotos por tee).
- **Merch "profundo"**: posters holográficos, stickers, keychains, tumblers, gorras, toallas (Madonna/Warner) —
  catálogo largo más allá de la ropa.

### 2.3 Presentación general de páginas

- **Tarjetas**: 2+ imágenes (hover cambia F/B), acciones al hover (Add to Cart + Quick View — Taylor),
  "From £X" cuando hay variantes de precio (Madonna), badges de estado (Gaga/Charli/Juno).
- **Listado**: sidebar de filtros (precio rango, categoría, álbum) + orden (Best selling, precio, fecha, A-Z) —
  Taylor. Secciones de catálogo: "New This Week / Preorders / Coming Soon / Back In Stock / Bestsellers" — Juno.
- **Home**: banner de campaña (GIF o cuenta regresiva) → últimos lanzamientos → colecciones → destacados → CTA →
  promesas (Taylor/Warner/Gaga). "Shop by Album" = nuestra página de lanzamiento ✓.
- **Migas de pan** (Gaga): Home > Colección > Producto.
- **Buscador** con preview de productos (Charli/Zara/Warner).
- **Captura de email**: "first to know about exclusive drops" (Zara), "SUBSCRIBE TO RECEIVE SPECIAL OFFERS"
  (PinkPantheress) — captura orientada a **drops/prevantas**, no boletín genérico, con checkbox de consent.
- **Footer**: "Help & FAQs · Shipping/Returns · Contact · Legal" + sociales (todas; Warner sirve el help desde
  un sitio de soporte central).
- **Navegación**: "Música (Vinilo/CD/Cassette) · Merch · Sale" + colecciones por tour (Zara "MIDNIGHT SUN ☀️").

## 3. Propuestas por página (prioridad · esfuerzo · ¿esquema?)

### 3.1 Sistema de badges y estados (transversal)

| Estado | Disparador | Card | PDP | CTA | Prioridad |
|---|---|---|---|---|---|
| Disponible | stock > 5 | — | — | Agregar | ya |
| Últimos N | 0 < stock ≤ 5 | **chip nuevo** | ✓ ya | Agregar + copy "quedan N" | P0 (sin esquema) |
| Agotado | stock = 0 | gris + precio ✓ ya | ✓ ya | **"Avisen cuando haya stock"** (nuevo) + "Pedirlo" ✓ | P1 (tabla `notificacion_stock`) |
| Próximamente | `f_lanzamiento` > hoy | **chip con fecha** | banner en el lanzamiento | "Avísenme del lanzamiento" | P0 dato + P1 email |
| Preventa | flag + fecha (nuevo) | chip "Preventa" | "se cobra ahora · sale ~fecha" | Agregar al carrito | P1 (esquema aditivo) |
| Limitado | campo opcional | copy "Solo N · mientras dure" | igual | Agregar | P1 |
| Restock reciente | fecha de re-abastecimiento | chip "Vuelve" | — | Sección "Recién restockeado" | P2 |

- P0: chips "Últimos N" en cards (el dato ya existe) y "Próximamente (fecha)" en card de lanzamiento + página
  (dato ya existe, solo mostrar).
- P1: "avisen cuando haya stock" (`notificacion_stock`: k_producto/k_variante, correo, celular opc, activo) +
  disparo cuando el stock vuelve a >0; state de preventa; límite por cliente (ver estudio-mejoras P1.13).
- P2: contador de restock en barra superior (Taylor) y sección "recién restockeado" (Juno).

### 3.2 Tarjetas (`_cards.html`)

- P0: chip "Últimos N" en `product_card` y `release_card`.
- P1: **hover con acciones** (botones "Agregar" + "Vista rápida" — el quickview ya existe, solo exponerlo en la
  card) + **segunda imagen al hover** (ya hay `?orden=1`).
- P2: meta bajo el nombre: "formato · año · [lanzamiento]" (estilo XL, barato y ordena el ojo).

### 3.3 PDP (`_producto_detalle.html`)

- P0: línea de envío (estudio-mejoras P0.1) · **acordeón** "Qué incluye" (formalizar `incluye`) / "Detalles" /
  "Envío y devoluciones" · **relacionados** (otros productos del mismo `k_lanzamiento`, query directa; si no
  hay, de la misma categoría) · **breadcrumbs** Inicio / Lanzamiento / Producto.
- P1: "Avisen cuando haya stock" cuando agotado (junto a "Pedirlo", no en su lugar) · estado **preventa**
  ("Disponible desde ~fecha · se cobra hoy y se envía al salir") · copy de limitación para exclusivos.
- P2: "También te puede interesar" (mismo artista/categoría, no solo mismo lanzamiento).

### 3.4 Lanzamiento (`singleRelease.html`)

- P0: **"línea completa del álbum"** (modelo PinkPantheress): presentar juntos los formatos (vinilo/CD/cassette)
  + packs **con el ahorro visible** (ya se calcula), ordenado packs → sueltos. Es disciplina de catálogo +
  presentación; el esquema ya lo soporta (BUNDLE + variantes).
- P1: **`descripcion` en `Lanzamiento`** (campo texto aditivo + admin editRelease) · estado **Próximamente /
  Preventa** con CTA ("Avísenme" / "Preventa") · fila "También disponible: [otros formatos/packs]" (cross-link
  entre productos del lanzamiento, barato).
- P2: **tracklist + créditos** (texto opcional o tabla `lanzamiento_pista`) · expandir redes a YouTube ·
  info de tour/evento (Zara).

### 3.5 Catálogo (`releases.html`, `products.html`)

- P0: CTA "Pide tu disco" en los empty states (hoy solo dicen "todavía no hay…").
- P1: orden **"Más vendidos"** (conteo por `item` sobre pedidos PAGADOS, solo query) · sección **"Esta semana"**
  (publicado/stockeo en 7 días) · **"Próximamente"** (lanzamientos futuros) · filtro de **precio** (min/max).
- P2: **buscador público** (`/buscar` sobre producto, artista, lanzamiento, categoría — hoy no existe) con
  preview tipo Charli/Warner · sección "Recién restockeado" (requiere `f_restock` al reponer stock).

### 3.6 Home

- P0: promesas con **tiempos reales por zona** (estudio-mejoras P0.1/8).
- P1: **banner de campaña** rotativo semanal (próximo lanzamiento / restock anunciado / pack nuevo) con CTA —
  contenido en `Configuracion` o gestión manual · **captura de email** "drops y preventas" (tabla o
  `Configuracion` + backend de correo; reusar para avisos de stock y lanzamientos).
- P2: sección "Esta semana" en home · cuenta regresiva a próximo lanzamiento (Taylor).

### 3.7 Carrito / checkout / pedido

- P0: nota de envío en el resumen ("salimos en 1–2 días · Bogotá 24–72 h · 3–7 días resto") + link a
  `/ayuda/envios` (estudio-mejoras).
- P1: **envío gratis con barra de progreso** ("te faltan $X") · **timeline en `/pedido`** (Pagado → En
  preparación → Enviado → Entregado con fechas; hoy solo muestra el estado y "te contactaremos"): las fechas
  salen de un par de campos nuevos (`f_enviado` etc.) o, barato, texto estático + tracking (estudio-mejoras
  P1.11).
- P2: "tu pedido está completo" → productos sugeridos en `/pedido` y en el correo de confirmación.

### 3.8 Transversales

- P0: **footer columna "Ayuda"**: Envíos y entregas · Preguntas frecuentes · Términos · Contacto (formulario
  real, no el link a Instagram) + newsletter.
- P1: buscador (3.5) + captura de email (3.6) + `/ayuda/envios` y `/ayuda/faq` (estudio-mejoras P0.2).
- P2: reviews/calificaciones (Discogs) — último, exige comunidad.

## 4. Anatomía de página propuesta (wireframes)

### PDP

```
[Inicio / Lanzamiento / Producto]
[Gallery: F/B/disco/detalle]      [Chip: VINILO] [Chip: Original MB] [Chip: Últimos 3 | Preventa | Agotado]
                                  Artista · Lanzamiento (link)
                                  Nombre (edición)
                                  $precio  (pack: ahorras $X)
                                  ─ envío: 1–2 días prep · Bogotá 24–72 h · resto 3–7 días [más]
                                  [Preventa?] Se cobra hoy · sale ~fecha      [Limitado?] Solo N · mientras dure
                                  Descripción corta (1–2 líneas)
                                  [Acordeón] Qué incluye / Detalles / Envío y devoluciones
                                  Talla|Color: [select]  Cant: [1]  [Agregar al carrito]
                                  (agotado) [Avisen cuando haya stock] + [Pedirlo a la medida]
                                  También te puede interesar: [3–4 cards del mismo lanzamiento]
```

### Lanzamiento

```
[Banda: portada + Artista + Título + [Próximamente: fecha | Preventa] + géneros + fecha]
Descripción del disco (1–2 párrafos)            [nuevo: campo]
[Preventa/Coming soon?] CTA (avísenme / pre-order)
Packs (con ahorro)                               → línea completa del álbum
Sueltos
También disponible: [cross-links de formatos]    [nuevo P1]
Tracklist / Créditos                            [nuevo P2, opcional]
Post de redes (ya existe)
```

### Card de producto

```
[img F (hover→B)]  [chip estado: Últimos N | Agotado | Preventa | Próximamente]
Nombre
formato · año · lanzamiento      [meta P2]
$precio  o  desde $X
[hover: [Agregar] [Vista rápida]]
```

### Home

```
[Banner campaña: próximo lanzamiento / restock / pack nuevo]   [P1]
Últimos lanzamientos (ya)
Colecciones: Vinilo · CD · Cassette · Merch (ya por /products/<cat>)
Destacados (ya)
Pide tu disco a la medida (ya)
Promesas: envío con tiempos reales · pago seguro · ediciones especiales
[Footer + Ayuda + email capture]
```

## 5. Orden de ejecución (integrando ambos docs)

1. **Quick wins sin esquema (1–2 días)**: P0 de ambos docs — línea de envío + `/ayuda/envios` + footer Ayuda +
   banner de envío; relacionados + acordeón + breadcrumbs en PDP; chips "Últimos N" y "Próximamente" en
   cards/lanzamiento; CTA en empty states; promesas con tiempos; nota de envío en checkout.
2. **Lote de esquema P1 (aprobar juntas y migrar una vez)**: `notificacion_stock` (avisen-que-hay-stock) ·
   `Lanzamiento.descripcion` · flag+fecha de preventa · `limite_por_cliente` · tracking en `Invoice` +
   timeline `/pedido` · envío gratis `envio.gratis.min` · (opcional) email capture.
3. **P2 cuando el catálogo esté listo**: buscador público, secciones "esta semana"/"próximamente"/
   "más vendidos", tracklist/credits, merch de tour + página TOUR, meta XL en cards, contador de restock,
   reviews.

## 6. Antipatrón visto (no hacer)

- `pinkpantheress.shop` (clon no oficial): tracking falso de dropship, "warehouse en Shenzhen", store montada
  sobre un template de terceros. Nuestro equivalente: **stock real declarado, tiempos honestos, tracking real,
  soporte real** — la tienda a la medida y el quickview ya nos dan ventaja; el stock transparente la consolida.
- No ocultar lo agotado: se mantiene **visible con precio y CTA** (Zara/PinkPantheress/Gaga).
- No prometer fechas exactas de preventa: "fechas no garantizadas" (Warner/Taylor).
- No guardar costos ni tiempos solo en el checkout: se muestran en PDP, listado y home.
