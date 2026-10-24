# POC: mockups y pieza de preventa por lanzamiento

Esta prueba de concepto valida el flujo más importante de la feature: **partir de un lanzamiento**, no de un producto suelto, y obtener una pieza lista para revisar.

## Qué genera

El panel genera únicamente la **story vertical de 1080 × 1920**. El CLI todavía puede generar el mockup limpio y la ficha de 1080 × 1350 para pruebas puntuales.

1. **Mockup limpio** (`1400 × 1400`, solo CLI): portada + disco. Sirve para la ficha del lanzamiento, la galería o una publicación.
2. **Story de preventa** (`1080 × 1920`): portada, artista, álbum, formato, precio, abono, fecha estimada y CTA. Si el lanzamiento no es preorden, el encabezado cambia a `A LA VENTA` y se usa el render dibujado.

La story de **pre-orden** se monta sobre la plantilla oficial vacía (`app/static/img/preventa_story_preorden.png`, 3126 × 5556) y solo agrega los datos dinámicos: portada, disco, sticker `1LP`/`2LP`, artista, álbum, formato, precio, abono, llegada estimada y el parche de “envío aparte”. El título, los rayos, el contorno naranja, el separador, las estrellas, la pastilla, la banda y el CTA ya vienen en la base y no se redibujan. El sticker es un vinilo troquelado (`app/static/img/preventa_sticker.png`) y el texto `1LP`/`2LP` se escribe en runtime.

Los textos de acento usan Playfair Display (licencia SIL OFL, incluida en `app/static/fonts/` junto a `PlayfairDisplay-OFL.txt`) para conservar acentos y cursivas; artista, álbum, precio y abono usan Berlin Sans. La variante `A LA VENTA` todavía usa el render dibujado hasta contar con su plantilla oficial.

Los mockups se generan con Pillow a partir de la portada del lanzamiento. No se modifica el lanzamiento ni los productos; cuando se generan desde el panel, la bitácora registra la acción.

## Desde el panel

En el admin: **Marketing → Mockups de lanzamiento** (`/dashboard/mockups`).

1. Elegí el lanzamiento.
2. Buscá el vinilo en **Elegí el vinilo** por color, acabado o prensa.
3. Elegí una sugerencia de la lista y tocá **Usar este vinilo en la story**.
4. Si no usás VinylMockup, abrí **Opciones sin VinylMockup** y elegí un vinilo de prueba.
5. Generá y mirá la pieza en la misma página; se puede abrir o descargar.

La story se genera siempre en 1080 × 1920 sobre la plantilla oficial de Halloween. El panel no genera la ficha de 1080 × 1350 ni el mockup con fondo claro; esas variantes quedaron disponibles desde el CLI.

En **Ajustar datos de la pieza de preventa** también se eligen los discos del sticker (`1LP`/`2LP`), el costo de envío y si ese envío se suma al precio mostrado o se muestra aparte. El precio del formulario es siempre el precio base, sin envío. El título puede quedar automático (según el lanzamiento) o forzarse a `Pre-orden` / `A la venta`; el automático usa pre-orden para la plantilla oficial.

También podés entrar directo desde el ícono <i class="bi bi-images"></i> en la fila de **Lanzamientos**. Los archivos se guardan en `instance/mockups/admin/<id>/` y no se publican solos en la tienda.

## Cómo correrlo por CLI

La CLI sigue sirviendo para pruebas o para generar varias piezas sin abrir el navegador. Desde la raíz del proyecto:

```bash
venv/bin/python scripts/poc_mockup_lanzamiento.py 2 --demo
venv/bin/python scripts/poc_mockup_lanzamiento.py 2 --demo --plantilla story
```

Salida:

```text
instance/mockups/lanzamiento_2_negro.png
instance/mockups/lanzamiento_2_color.png
instance/mockups/lanzamiento_2_splatter.png
instance/mockups/lanzamiento_2_picture.png
instance/mockups/lanzamiento_2_preventa.png
```

`instance/` está ignorado por git, así que las piezas generadas no se commitean.

### Opciones

```bash
# Elegir presets y carpeta
venv/bin/python scripts/poc_mockup_lanzamiento.py 2 \
  --presets negro,color,splatter,marble,clear,picture \
  --salida instance/mockups

# Ajustar los datos de la pieza sin tocar la base de datos
venv/bin/python scripts/poc_mockup_lanzamiento.py 2 \
  --precio 150000 --abono 95000 \
  --formato "Vinilo negro estándar" --eta "Diciembre 2026"

# Sticker 2LP y envío sumado al precio mostrado
venv/bin/python scripts/poc_mockup_lanzamiento.py 2 --demo --plantilla story \
  --lps 2 --envio 12000

# Envío aparte (no se suma al precio)
venv/bin/python scripts/poc_mockup_lanzamiento.py 2 --demo --plantilla story \
  --envio 12000 --envio-aparte

# Forzar el título de la plantilla
venv/bin/python scripts/poc_mockup_lanzamiento.py 2 --demo --plantilla story \
  --preorden si

# Mockup limpio tipo fotografía de producto
venv/bin/python scripts/poc_mockup_lanzamiento.py 2 \
  --demo --presets cherry --fondo claro
```

`--fondo claro` es una opción del CLI para el mockup limpio: lo genera sobre un fondo marfil, sin la tarjeta oscura. El panel no la usa.

`--demo` solo existe para probar la pieza cuando el lanzamiento no tiene un vinilo cargado. En el caso del lanzamiento 2, sus productos reales son cachuchas; por eso el ejemplo visual usa precio/abono de demostración. Para un lanzamiento real, no se pasa `--demo`: el script toma el precio del producto de categoría `VINILO` (o con “vinilo” en el nombre).

## Catálogo propio de variantes

La variante personalizada usa un catálogo propio, sin copiar las texturas ni las imágenes de VinylMockup:

- **34 colores base**: 20 opacos, 5 translúcidos y 9 clear. Los nombres comerciales y los PMS se tomaron del catálogo público de Citizen Vinyl; los RGB son una aproximación propia para el render.
- **9 acabados**: estándar, splatter, swirl, mármol, humo, color en color, mitad y mitad, pinwheel y picture disc.
- Cualquier color se puede combinar con cualquier acabado. Eso deja el catálogo abierto para sumar los estilos que aparezcan en el catálogo real, sin exponer cientos de opciones en la pantalla: se eligen color + acabado + hasta tres acentos.

El render sigue siendo procedural con Pillow. Los archivos se generan con el nombre de la variante, por ejemplo `opaque-black-splatter.png` o `clear-blue-swirl.png`, y la tarjeta de preventa toma ese nombre como formato si no se escribe otro.

## Presets incluidos

| Preset | Qué muestra |
| --- | --- |
| `negro` | Vinilo negro clásico |
| `color` | Disco de color sólido |
| `splatter` | Base negra con salpicaduras |
| `marble` | Vetas de color |
| `cherry` | Aproximación procedural a un “Cherry Glaze”: rojo translúcido con vetas |
| `clear` | Disco translúcido claro |
| `picture` | La portada impresa en el disco, con label de papel |

En el panel, los presets son una alternativa de prueba: se elige uno y se dibuja ese vinilo en la story. El CLI puede combinar varios presets para generar varias piezas de una vez. La variante personalizada es la que abre el catálogo de 34 colores y 9 acabados. `cherry` toma la idea de la página de VinylMockup que revisamos, pero no usa sus assets ni pretende ser una copia exacta: es una variante propia para validar el look.

## De dónde salen los datos

- **Portada**: `Lanzamiento.i_lanzamiento` (por ejemplo, la imagen de Spotify). Si no existe, usa la primera foto de un producto. Si tampoco hay, genera una portada abstracta con las iniciales.
- **Artista y álbum**: relaciones del lanzamiento.
- **Precio y abono**: solo de un producto `VINILO` simple. Si el lanzamiento no tiene vinilo, la pieza muestra “Precio y reserva por confirmar”.
- **Discos (`1LP`/`2LP`)**: se eligen en el panel o con `--lps`; si no, se detectan del nombre del producto (`2LP`, “doble”).
- **Envío**: `--envio` o el campo del panel. Si `envio_incluido` está activo, se suma al precio que muestra la pieza; si no, la pastilla dice “envío aparte”.
- **Fecha**: `f_lanzamiento`.
- **Preorden**: `Lanzamiento.preorden` o `Producto.preorden`; se puede forzar desde el panel o con `--preorden si|no`.

## Límites de este POC

- La pantalla del admin ya existe, pero todavía no guarda el mockup como `Imagen` ni lo asocia a un producto.
- No hay historial de versiones: al regenerar la story se reemplaza el archivo; las piezas viejas con otro nombre quedan en la galería hasta borrarlas.
- Los colores y acabados de los discos son procedurales; si se necesita calidad fotográfica, el siguiente paso es usar texturas PNG/PSD propias o un servicio de mockups con una plantilla de vinilo.
- La story de pre-orden usa la plantilla oficial y un sticker de vinilo troquelado; si se cambia el arte base o el sticker, hay que volver a comparar contra la plantilla original. La story de venta sigue con el render dibujado.
- La plantilla y el sticker son assets de marca: conviene revisarlos antes de publicarlos.
- La portada se descarga en cada corrida; falta caché local.
- Algunas portadas externas pueden traer marcas de agua de su fuente. Para producción hay que usar el arte original en buena calidad.

## Siguiente paso recomendado

1. Guardar el mockup limpio como `Imagen` del lanzamiento o del producto de vinilo.
2. Sumar texturas propias (foto/PSD) para acercarse al look fotográfico de VinylMockup sin usar sus assets.
3. Agregar la variante de historia y un botón de “descargar las dos piezas”.
4. Si se quiere reutilizar el catálogo visual de otra prensadora, pedir licencia o permiso antes de copiar sus imágenes.
