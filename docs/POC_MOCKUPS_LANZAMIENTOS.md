# POC: mockups y pieza de preventa por lanzamiento

Esta prueba de concepto valida el flujo más importante de la feature: **partir de un lanzamiento**, no de un producto suelto, y obtener dos piezas listas para revisar.

## Qué genera

Para un lanzamiento dado:

1. **Mockup limpio** (`1400 × 1400`): portada + disco. Sirve para la ficha del lanzamiento, la galería o una publicación.
2. **Pieza de preventa** (`1080 × 1350`): portada, artista, álbum, formato, precio, abono, fecha estimada y CTA. Si el lanzamiento no es preorden, el encabezado cambia a `A LA VENTA`.

Los mockups se generan con Pillow a partir de la portada del lanzamiento. No se modifica el lanzamiento ni los productos; cuando se generan desde el panel, la bitácora registra la acción.

## Desde el panel

En el admin: **Marketing → Mockups de lanzamiento** (`/dashboard/mockups`).

1. Elegí el lanzamiento.
2. Elegí **Estilos rápidos** para marcar varios presets, o **Variante personalizada** para combinar un color base con un acabado.
3. Elegí fondo claro (catálogo) u oscuro (estudio).
4. Generá y mirá las piezas en la misma página; cada una se puede abrir o descargar.

También podés entrar directo desde el ícono <i class="bi bi-images"></i> en la fila de **Lanzamientos**. Los archivos se guardan en `instance/mockups/admin/<id>/` y no se publican solos en la tienda.

## Cómo correrlo por CLI

La CLI sigue sirviendo para pruebas o para generar varias piezas sin abrir el navegador. Desde la raíz del proyecto:

```bash
venv/bin/python scripts/poc_mockup_lanzamiento.py 2 --demo
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

# Mockup limpio tipo fotografía de producto
venv/bin/python scripts/poc_mockup_lanzamiento.py 2 \
  --demo --presets cherry --fondo claro
```

`--fondo claro` genera el mockup sobre un fondo marfil, sin la tarjeta oscura. Es la variante más cercana a una foto de catálogo.

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

Los presets siguen siendo atajos curados para generar varias piezas de una vez. La variante personalizada es la que abre el catálogo de 34 colores y 9 acabados. `cherry` toma la idea de la página de VinylMockup que revisamos, pero no usa sus assets ni pretende ser una copia exacta: es una variante propia para validar el look.

## De dónde salen los datos

- **Portada**: `Lanzamiento.i_lanzamiento` (por ejemplo, la imagen de Spotify). Si no existe, usa la primera foto de un producto. Si tampoco hay, genera una portada abstracta con las iniciales.
- **Artista y álbum**: relaciones del lanzamiento.
- **Precio y abono**: solo de un producto `VINILO` simple. Si el lanzamiento no tiene vinilo, la pieza muestra “Precio y reserva por confirmar”.
- **Fecha**: `f_lanzamiento`.
- **Preorden**: `Lanzamiento.preorden` o `Producto.preorden`.

## Límites de este POC

- La pantalla del admin ya existe, pero todavía no guarda el mockup como `Imagen` ni lo asocia a un producto.
- No hay historial de versiones: si regenerás con otro fondo, quedan los archivos anteriores en la carpeta.
- Los colores y acabados son procedurales; si se necesita calidad fotográfica, el siguiente paso es usar texturas PNG/PSD propias o un servicio de mockups con una plantilla de vinilo.
- La tarjeta está pensada para `1080 × 1350`. Falta la variante `1080 × 1920` para historias.
- La portada se descarga en cada corrida; falta caché local.
- Algunas portadas externas pueden traer marcas de agua de su fuente. Para producción hay que usar el arte original en buena calidad.

## Siguiente paso recomendado

1. Guardar el mockup limpio como `Imagen` del lanzamiento o del producto de vinilo.
2. Sumar texturas propias (foto/PSD) para acercarse al look fotográfico de VinylMockup sin usar sus assets.
3. Agregar la variante de historia y un botón de “descargar las dos piezas”.
4. Si se quiere reutilizar el catálogo visual de otra prensadora, pedir licencia o permiso antes de copiar sus imágenes.
