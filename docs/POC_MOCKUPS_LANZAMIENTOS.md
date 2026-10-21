# POC: mockups y pieza de preventa por lanzamiento

Esta prueba de concepto valida el flujo más importante de la feature: **partir de un lanzamiento**, no de un producto suelto, y obtener dos piezas listas para revisar.

## Qué genera

Para un lanzamiento dado:

1. **Mockup limpio** (`1400 × 1400`): portada + disco. Sirve para la ficha del lanzamiento, la galería o una publicación.
2. **Pieza de preventa** (`1080 × 1350`): portada, artista, álbum, formato, precio, abono, fecha estimada y CTA. Si el lanzamiento no es preorden, el encabezado cambia a `A LA VENTA`.

Los mockups se generan con Pillow a partir de la portada del lanzamiento. No se escribe nada en la base de datos.

## Cómo correrlo

Desde la raíz del proyecto:

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

El catálogo es deliberadamente corto. La idea es sumar variantes solo cuando el catálogo real las necesite, no replicar un editor de mockups completo. `cherry` toma la idea de la página de VinylMockup que revisamos, pero no usa sus assets ni pretende ser una copia exacta: es una variante propia para validar el look.

## De dónde salen los datos

- **Portada**: `Lanzamiento.i_lanzamiento` (por ejemplo, la imagen de Spotify). Si no existe, usa la primera foto de un producto. Si tampoco hay, genera una portada abstracta con las iniciales.
- **Artista y álbum**: relaciones del lanzamiento.
- **Precio y abono**: solo de un producto `VINILO` simple. Si el lanzamiento no tiene vinilo, la pieza muestra “Precio y reserva por confirmar”.
- **Fecha**: `f_lanzamiento`.
- **Preorden**: `Lanzamiento.preorden` o `Producto.preorden`.

## Límites de este POC

- No hay pantalla en el admin todavía: se corre por CLI.
- No guarda el mockup como `Imagen` ni lo asocia a un producto.
- Los presets son procedurales; si se necesita calidad fotográfica, el siguiente paso es usar presets PNG/PSD propios o un servicio de mockups con una plantilla de vinilo.
- La tarjeta está pensada para `1080 × 1350`. Falta la variante `1080 × 1920` para historias.
- La portada se descarga en cada corrida; falta caché local.
- Algunas portadas externas pueden traer marcas de agua de su fuente. Para producción hay que usar el arte original en buena calidad.

## Siguiente paso recomendado

1. Llevar esto a una ruta del admin: elegir lanzamiento, preset y previsualizar/descargar.
2. Guardar el mockup limpio como `Imagen` del lanzamiento o del producto de vinilo.
3. Reemplazar los presets procedurales por assets propios (foto/PSD) cuando estén disponibles.
4. Agregar la variante de historia y un botón de “descargar las dos piezas”.
