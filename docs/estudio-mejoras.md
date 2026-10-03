# Estudio de tiendas de discos + mejoras deep para MusicalBox

Fecha: 2026-10-02 · Método: revisión directa de sitios reales (fetch de páginas vivas) + baseline de nuestras
plantillas actuales (`_producto_detalle.html`, `singleRelease.html`, `releases.html`, `checkout.html`, `home.html`, `_cards.html`).

## 1. Sitios revisados (estado)

| Sitio | ¿Se pudo ver? | Qué aportó |
|---|---|---|
| Taylor Swift (taylorswift.com + store.taylorswift.com) | Sí | Catálogo por álbum, PDP con "qué hay en la caja", límites por cliente, política de envío completa |
| Lady Gaga (ladygaga.com) | Sí | Tienda por álbum/era/tour, PDP, "Sold Out" + avisarme, Help & Support (pedidos/envíos/devoluciones) |
| Discogs | Sí | PDP de lanzamiento (tracklist, créditos, stats Have/Want, reviews) + ofertas por vendedor con envío incluido |
| Juno Records (juno.co.uk) | Sí | Secciones de catálogo: New This Week, Preorders, Coming Soon, Back In Stock, Bestsellers |
| Bandcamp | Sí | Hotlist (próximos), "selling right now" (feed vivo), New & Notable, discover por formato |
| XL Recordings (sello de Charli XCX, Charlotte Day Wilson, Arca, Adele…) | Sí | Releases con tipo + fecha + cat number, "Buy Now" por artista, Classics, notas editorial |
| PinkPantheress (shop.pantheress.pink, Warner) | Sí | Store oficial (plataforma Warner/WMIS): **línea por álbum** (2LP, 3CD, cassette, keyring + bundles), "Sold out" con precio, banner de aduanas, help centralizada |
| PinkPantheress (pinkpantheress.shop) | Sí | **Tienda NO oficial** (clon dropship con tracking de "Merchjoys", warehouse en Shenzhen) → anti-ejemplo |
| Warner Artists (storesupport.warnerartists.net) | Sí | Política real de envío de la plataforma de PinkPantheress: tiempos por zona, preventas, tracking |
| Charli XCX (store.charlixcx.com) | Sí | Tienda oficial US: todo el merch en **Pre-Order** (álbum próximo), políticas en footer, "fees waived on returns" |
| Zara Larsson (zaralarssonuk.store) | Sí | Tienda UK: colección por **tour** (MIDNIGHT SUN ☀️), vinilo/CD propios, "Sold out" con precio visible, email list para drops |
| Madonna (shopuk.madonna.com + US/EU/AU) | Sí | Red de stores por región, **ediciones regionales** (UK/US/INTL), merch profundo (posters holográficos, stickers, keychains) |
| Rough Trade / Amoeba / Kung Fu Shop / Third Man / Yes | No (403 / errores) | Pendiente de repintar en otra sesión |

## 2. Hallazgos por dimensión

### 2.1 Shipping: cómo lo presentan (nadie pone el costo real en la PDP)

- **Promesa corta y visible**: "orders ship within 2–3 business days" (Gaga), "free domestic shipping over $50"
  (Taylor), "super-fast delivery" en el title tag (Juno), "Worldwide Shipping" en el pie (pinkpantheress).
- **Página de ayuda "Shipping" dedicada** (Taylor y Gaga): tiempos de procesado, transportistas + transito por
  método, cuándo llega el tracking, "Label Created" = pre-shipment, paquete perdido (30 días → reenvío o
  reembolso), "dice entregado pero no llegó" (hasta 5 días), dirección incorrecta = responsabilidad del cliente,
  aduanas (internacional), pre-órdenes (se cobra completo al checkout; por defecto el pedido no sale hasta que
  todo esté disponible, salvo opción "enviar por separado"; plazos en la descripción del producto y en el correo).
- **Discogs (marketplace)**: el envío es **parte de la oferta** — "€32.99 + €59.99 shipping", "Ships From:
  Germany", rating del vendedor, "Unavailable in Colombia" (geo-restricción por comprador).
- **Lección para nosotros**: en Colombia no hay aduanas; el equivalente es **zonas de envío + plazos + tracking +
  política de perdido/dañado**, dicho en 1 línea en PDP/checkout y en una página `/ayuda/envios`.

### 2.2 Producto (PDP) y preset de información

- **Taylor (PDP de vinilo)**: título con edición (color/variantes: "Moonstone Blue Edition", "Blood Moon"),
  fotos de frente/dorso/disco/detalles, y sobre todo la lista de contenido: "12 Tracks · Portofino Orange Glitter
  vinyl · double gatefold jacket · full size gatefold photograph · double-sided foldout panel · collectible album
  sleeves con fotos inéditas y letras" + **"Limit 4 per customer. U.S. customers only. While supplies last."**
- **Gaga (PDP de merch)**: vistas Frente/Dorso, nombre, precio, una línea de descripción, selector de talla
  (S–2XL), Add to cart, y "You may also like" (carrito relacionado).
- **Discogs (PDP de lanzamiento)**: densidad máxima — sello, formato ("2× Vinyl, LP, Album, Reissue, 180 Gram"),
  país, fecha de lanzamiento, género/estilo, **tracklist completa con créditos y duraciones**, notas, otras
  versiones, stats (Have 48.871 / Want 14.761 / rating 4.73 / Last Sold / Low-Median-High) y reviews de coleccionistas.
- **Tarjetas de colección**: Taylor muestra múltiples fotos por producto + Quick View + Add to Cart al hover;
  filtros de precio (rango), álbum y formato; orden: Best selling, precio, fecha, A-Z.
- **Nuestro gap**: la PDP no dice nada de envío, no formaliza "qué hay en la caja" (solo `descripcion`/`incluye`
  suelto), no tiene relacionados, y agotado → solo "Pedirlo" (sin avisarme).

### 2.3 Lanzamiento (release)

- **XL**: cada release muestra **tipo + fecha + cat number** (`lp2026-11-13 XL1712MF`, `single2026-09-10 XL1699DS`),
  "Buy Now" hacia microsite del artista, secciones Loud / Tracks & EPs / Classics + notas "Behind the Scenes".
- **Taylor**: "Shop by Album" = landing por álbum (lo que ya somos nosotros: página por lanzamiento).
- **Gaga**: colecciones por álbum **y por tour/ciudad** (MAYHEM Ball, Singapore, CDMX) → el merch de gira como
  línea de producto propia.
- **Bandcamp**: Hotlist de próximos álbumes (genera expectativa), "New and Notable", feed "selling right now".
- **Nuestro gap**: la página de lanzamiento no lleva tracklist, créditos, descripción, ni estado
  "próximo/coming soon" cuando `f_lanzamiento` es futura; el dato de fecha existe pero se usa poco.

### 2.4 Orden e información de página (home y nav)

- **Nav de tienda de música**: Catálogo por álbum · Música (Vinilo/CD/Cassette) · Merch · Ofertas (+ Preorders/
  Coming Soon como secciones de primera, Juno).
- **Home**: hero de campaña o release destacado con CTA; secciones editoriales (Novedades, Hotlist, New &
  Notable); CTA de "pedido a la medida" ya lo tenemos y es diferenciador.
- **Footer**: siempre "Shipping / Returns / Order Information / Payments" + newsletter (Taylor, Gaga).
- **Nuestro gap**: el footer no tiene enlaces de ayuda; el home promete "Envíos a todo el país" sin tiempos.

### 2.5 Segunda ola: stores oficiales de Charli, Zara, Madonna y PinkPantheress

- **Línea completa por álbum** (PinkPantheress "Fancy Some More?", store Warner): un álbum = N formatos
  (2LP coloured €44,99 · 3CD mini gatefold €44,99 · 1CD gatefold €14,99 · cassette €10,99 · keyring €19,99)
  + **bundles** (Collectors' Bundle €109,99; "1CD & Cassette" €21,99; "2LP & 3CD" €75,99) + "Sold out" por
  formato (el 1CD agotado sigue visible con su precio). La page de campaña muestra todo junto. **Nuestro
  modelo ya soporta BUNDLE + variantes**: esto es disciplina de catálogo + presentación de la página de
  lanzamiento, no esquema.
- **Preventa como estado de catálogo** (Charli XCX store): toda la colección en badge "Pre-Order" antes del
  drop del álbum; Charli también la usa en merch del álbum próximo ("Oblivion Is Freedom" tees). Devoluciones:
  "fees waived on returns".
- **Tour como colección de primera** (Zara Larsson UK): nav "MIDNIGHT SUN ☀️" (colección del tour) + página
  "TOUR" (fechas) + APPAREL/ACCESSORIES/MUSIC; vende su propio vinilo/CD (Midnight Sun 2LP £34,99, CD £13,99)
  en la misma store; email list "first to know about exclusive drops and special offers".
- **Stores por región + ediciones regionales** (Madonna UK/US/EU/AU, interenlazadas; y PinkPantheress: US/AU/
  Ireland redirigen a la store regional de Warner): el **mismo producto en ediciones por país**
  ("Danceteria UK CD Edition / US CD Edition / INTL CD Edition") + pricing por región (GBP/USD/EUR) y
  selector de país con Colombia incluido (¡venden a Colombia!). Merch "profundo": posters holográficos,
  stickers, keychains, tumblers, gorras, totes, velos. Footer: "Right to Withdraw" (estilo EU).
- **Banner de envío destacado** (PinkPantheress/Warner): arriba del todo "Important delivery information" →
  "Do I have to pay import duties or taxes?" (crítico para compradores internacionales). El equivalente local
  es "¿Cómo funciona el envío?" visible en home/catálogo/PDP.
- **Política real de envío de Warner** (store de PinkPantheress, shipping = UK & EU):
  - Todo sale **de un solo warehouse (UK)**; procesado en **2 días hábiles** tras el pago (3–5 en temporada alta).
  - Tiempos desde el despacho: **UK 1–2 días** (Royal Mail 24/48 tracked) · **EU 5–14 días** (tracked/standard) ·
    **Internacional hasta 21 días hábiles**.
  - **Preventas: todo el pedido sale juntos en la fecha de salida del álbum, NO se separan entregas**; se despacha
    el día antes de la fecha de release. (Taylor, en cambio, ofrece la opción de "ship separately".)
  - Correo de "Shipment Confirmation" con **tracking link**; si llega tarde → contactan soporte para localizar el
    paquete. FAQ: aduanas/impuestos, métodos de pago, cancelación, devoluciones, guía de tallas + Trustpilot.
- **Help centralizada en el footer** (Warner, Madonna, Charli): "Help & FAQs · Delivery/Shipping · Contact ·
  Returns" siempre visibles; Warner lo sirve desde un sitio de soporte compartido por todas sus stores de artista.

## 3. Estado actual MusicalBox (baseline rápido)

- **PDP** (`_producto_detalle.html`): carrusel → chips (cat/PACK/Original/stock) → artista·lanzamiento → nombre →
  precio → descripción → contenido de pack (con ahorro) → variante + cantidad + agregar. **Sin envío, sin
  relacionados, sin avisarme, sin preventa.**
- **Lanzamiento** (`singleRelease.html`): banda con portada/artista/título/géneros/fecha + post social → Packs →
  Sueltos. **Sin tracklist, sin descripción, sin coming soon, sin preventa.**
- **Catálogo** (`releases.html`): filtros género/formato + orden (recientes/antiguos/nombre/precio). **Sin "esta
  semana", sin preventas, sin más vendidos.**
- **Checkout** (`checkout.html`): datos + dirección (autocomplete de municipios) + método de pago + resumen.
  **Sin costo/tiempo de envío, sin umbral gratis, sin "entregamos en X días".**
- **Home**: hero + últimos + destacados + redes + CTA pedidos a la medida + 3 promesas (envíos, pago seguro,
  ediciones especiales).

## 4. Mejoras deep (propuestas)

### P0 — sin esquema (solo plantillas/rutas, Quick Wins)

1. **Línea de envío en PDP y checkout**: "Preparamos tu pedido en 1–2 días hábiles · Bogotá 24–72 h · ciudades
   principales 2–5 días · resto del país 3–7 días". Datos en `Configuracion` (clave-valor ya existe) para no
   tocar código al cambiarlos.
2. **Página `/ayuda/envios`** (estilo Taylor/Gaga adaptado a Colombia): zonas y transportistas (Soporta/MailJet/
   Servientrega), cuándo sale el tracking (correo + `/pedido/<token>`), "dice entregado y no llegó" (5 días),
   paquete perdido (30 días → reenvío o reembolso), dañado/incompleto (fotos → reemplazo), dirección incorrecta,
   cambio de dirección antes de salir, devoluciones si las habilitamos.
3. **Footer**: enlaces "Envíos y entregas" + "Preguntas frecuentes" + "Términos".
4. **"También te puede interesar"** en PDP: otros productos del mismo lanzamiento (query directa) y, si el
   lanzamiento no tiene más, de la misma categoría. Estilo Gaga "You may also like".
5. **Acordeón en PDP**: "Qué incluye" (usa `incluye`/`descripcion` de forma formal, estilo Taylor "qué hay en la
   caja"), "Detalle del producto" (catálogo: material, contenido), "Envío" (resumen de la línea del punto 1).
6. **Badge "Próximamente" en lanzamiento** cuando `f_lanzamiento` > hoy (el dato ya existe): card y página,
   estilo Juno "Coming Soon". CTA "Avisen cuando salga" → por ahora a la solicitud a la medida.
7. **Orden "Más vendidos"** en el catálogo: conteo por `item` sobre pedidos PAGADOS (solo query, sin esquema).
8. **Home**: actualizar la promesa de envíos con los tiempos reales por zona (punto 1).
9. **Página de lanzamiento = línea completa del álbum** (modelo PinkPantheress "Fancy Some More?"): formatos
   (vinilo/CD/cassette) + bundles (coleccionista, combos, con ahorro) + "agotado" por formato visible con su
   precio. Es disciplina de catálogo y presentación: `BUNDLE`/`variante` ya existen, no toca esquema.
10. **Banner de envío** fijo sobre el listado y la PDP ("Envío: Bogotá 24–72 h · 3–7 días a todo el país ·
    pedido rastreable") enlazando a `/ayuda/envios` (patrón Warner "Important delivery information").

### P1 — esquema aditivo (requiere tu luz verde antes de migrar)

9. **"Avisen cuando haya stock"** (Gaga "Dont miss out when this item becomes available!"): tabla
   `notificacion_stock` (k_producto/k_variante, correo, celular opcional, activo, creado) + botón en PDP/agotado
   + disparo de correo/WhatsApp cuando el stock vuelve a >0. Reemplaza (no elimina) el CTA "Pedirlo".
10. **Preventa** (estilo Taylor/Gaga/Juno): campo `f_disponible_estimada` (o flag `preventiva` + fecha) en
    producto/variante; PDP muestra "Disponible desde ~fecha · se cobra ahora y se envía al llegar"; el checkout
    lo declara explícito; el pedido no descarga stock hasta estar disponible (o reserva como hoy con `ReservaStock`
    extendida a N días). **Modelo por defecto: el de Warner** — todo el pedido sale juntos en la fecha de salida
    del álbum y se despacha el día antes (simple, honesto, menos logística); la opción de Taylor "enviar lo que
    ya llegue" (split shipping) queda como avance posterior.
11. **Tracking real en la orden**: `Invoice.transportista` + `Invoice.n_rastreo`; se cargan en el panel al pasar a
    ENVIADO; el cliente lo ve en `/pedido/<token>` y llega en el correo de "pedido en camino" (nuevo correo).
12. **Envío gratis sobre $X**: clave en `Configuracion` (`envio.gratis.min`); el carrito/checkout lo calcula y lo
    muestra ("Te faltan $X para envío gratis"). Taylor lo usa en $50 de merch (excluye música); aquí sí lo
    incluiríamos todo.
13. **Límite por cliente** (Taylor "Limit 4 per customer") en productos exclusivos: campo opcional
    `limite_por_cliente` en producto, validado en `addtocart`/`crear_pedido`.
14. **Secciones de catálogo** (Juno): "Esta semana" (publicados en 7 días) y "Próximamente" (preventas +
    lanzamientos futuros) como vistas con filtro, no como tabs nuevas.
15. **Email para drops/ofertas** (Zara "first to know about exclusive drops", PinkPantheress "SUBSCRIBE TO
    RECEIVE SPECIAL OFFERS"): capturar correo pensando en preventas y restocks, no solo boletín genérico.
    Complementa el P1.9: "avísenme del próximo lanzamiento" además de "del stock".

### P2 — profundo (fase 2)

16. **Tracklist + créditos por lanzamiento** (estilo Discogs/Taylor): campo texto (o tabla `lanzamiento_pista`)
    en `lanzamiento`; se muestra en la página de release bajo los productos.
17. **Meta de release en card** (estilo XL): tipo de formato + año + (sello/código) en la tarjeta de lanzamiento.
18. **Merch de gira/tour como colección** (Zara/Gaga): colección por "evento" (reutilizando `genero`/`original_mb`
    o colección manual) + página "TOUR" con fechas (Zara: colección "MIDNIGHT SUN ☀️" + `/pages/tour`; Gaga:
    MAYHEM Ball por ciudad).
19. **Contador / aviso de restock** en barra superior (estilo Taylor "X is back for 00:00:00") para
    lanzamientos y preventas.
20. **Reviews/calificaciones** (estilo Discogs: Have/Want/rating) — exige comunidad; último de todos.
21. **Estadísticas de colección por lanzamiento** (cuántas copias vendimos de cada edición) → en dashboard.

## 5. Prototipo de página (orden de información)

### PDP propuesto

```
[Gallery: frente/dorso/disco/detalle]   [Chip: VINILO] [Chip: Original MB] [Chip: Últimos 3]
                                        Artista · Lanzamiento  (enlace)
                                        Nombre del producto (edición)
                                        $precio  (pack: ahorras $X)
                                        ─ envío: 1–2 días prep · Bogotá 24–72h · resto 3–7 días
                                        [Preventa?] Disponible desde ~fecha · se cobra ahora
                                        Descripción corta
                                        [Acordeón] Qué incluye / Detalle / Envío y devoluciones
                                        Talla|Color: [select]   Cant: [1]   [Agregar al carrito]
                                        (si agotado) [Avisen cuando haya stock]  [Pedirlo a la medida]
                                        También te puede interesar: [3–4 cards del mismo lanzamiento]
```

### Lanzamiento propuesto

```
[Banda: portada + Artista + Título + [Próximamente?] + géneros + fecha + sello]
Descripción del disco (1–2 párrafos)
[Preventa?] CTA preventa + "Disponible ~fecha"
Packs (ya existe)
Sueltos (ya existe)
Tracklist / Créditos (nuevo, opcional por lanzamiento)
Post de redes (ya existe)
```

## 6. Mapeo a Colombia (para redactar las políticas)

- **Zonas**: A) Bogotá + entornos (Chía, Mosquera, Funza, Soacha) 24–72 h · B) capitales (Medellín, Cali,
  Barranquilla, Bucaramanga, Cúcuta, Pereira, Cartagena) 2–5 días · C) resto del país 3–7 días.
- **Transportistas** (ejemplo, definir el real): Soporta / MailJet / Servientrega; tracking en correo y en
  `/pedido/<token>`; "Label Created/pre-shipment" = pedido en preparación.
- **Benchmark Warner** (referencia de tono y estructura): un solo warehouse, procesado en 2 días hábiles,
  tiempos contados **desde el despacho**, correo "Shipment Confirmation" con tracking; preventas salen el día
  antes de la fecha de release y **todo el pedido va junto**. Nuestra versión local: 1–2 días de preparación,
  zonas A/B/C desde el despacho, correo de "pedido en camino" con tracking.
- **Perdido**: 30 días desde el envío para reclamar (reenvío si hay stock o reembolso).
- **Dañado/incompleto**: fotos → reemplazo o reembolso (ventana 30 días desde recibido, como Gaga/Taylor).
- **Envío gratis**: umbral sugerido $150.000 (a ajustar por margen; `envio.gratis.min` en Configuracion).
- **Preventa**: cobrar al momento (MercadoPago ya lo resuelve), declarar fecha estimada, no prometer fecha
  exacta ("fechas no garantizadas", como Taylor/Gaga).

## 7. Sugerencia de orden de ejecución

1. P0.1–P0.3 + P0.10 (línea de envío + página de ayuda + footer + banner de envío): medio día, todo texto en
   `Configuracion`.
2. P0.4–P0.9 (relacionados, acordeón, coming soon, más vendidos, home, línea por álbum): 1–2 días.
3. P1.11 tracking + P1.12 envío gratis: alto impacto en confianza; ~1 día c/u (esquema aditivo, se aprueba).
4. P1.9 "avisen cuando haya stock" + P1.15 captura para drops: el que más factura a largo plazo; ~1 día +
   trigger en descuento de stock.
5. P1.10 preventa + P1.13 límite por cliente: cuando se tenga disco exclusivo/limitado en agenda.
6. P1.14 secciones de catálogo + P2.16–17 (tracklist, meta XL): cuando se complete el catálogo.
7. P2.18–21: últimos (merch de tour, contador, reviews, stats).

## 8. Pendiente de investigación

- Reintentar: Rough Trade, Amoeba, Kung Fu Shop (envío internacional LatAm), Third Man, Yes — bloquearon en esta
  sesión (403/errores de red).
- Miley Cyrus: su dominio está hackeado; revisar si su store vive en UMG/otro dominio.
- Resueltas: Charli XCX (store.charlixcx.com), Zara Larsson (zaralarssonuk.store), Madonna (shopuk.madonna.com +
  US/EU/AU), PinkPantheress (shop.pantheress.pink + shipping policy de Warner Artists).
