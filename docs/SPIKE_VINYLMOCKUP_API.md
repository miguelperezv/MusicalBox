# Spike local: API interna de VinylMockup

> **Solo lectura y uso interno.** La vista del panel está pensada para local y
> queda apagada en producción. Las imágenes siguen siendo de VinylMockup y/o de
> las plantas de prensado: no se deben publicar sin una licencia o permiso expreso.

## Qué hace

`app/store/vinylmockup_api.py` envuelve la API interna que usa VinylMockup:

```http
GET /api/variants/search?page=1&q=clear&press=<contentfulId>
GET /api/variants/<variantId>
GET /api/presses/<pressId>
GET /api/presses/<pressId>/variant
```

No hay endpoint de render: el mockup final se compone en el navegador con
Three.js. Este spike solo obtiene metadatos y, si se pide, una imagen puntual.

## Vista en el panel local

Con `APP_CONFIG=development` (el valor por defecto) y `DEBUG` activo, en
`/dashboard/mockups` aparece la sección **“Catálogo VinylMockup · solo local”**:

- busca variantes por nombre, color, tipo o estilo;
- muestra 20 miniaturas por página;
- al hacer clic en una, abre el detalle con la imagen grande, tipo, estilo,
  colores, prensa e ID de Contentful;
- el botón **“Usar en la pieza”** baja la imagen de 2160×2160 a
  `instance/mockups/vm_cache/` (ignorado por git), la recorta en círculo y
  genera con ella el mockup 1400×1400 y la pieza de preventa (ficha o story,
  según el select “Plantilla”) en `instance/mockups/admin/<release>/`, con los
  archivos sufijados `_vm`. La línea de formato usa el nombre real de la
  variante VM (p. ej. “Vinilo · 2 Color Splatter 4”).

Las imágenes siguen siendo de VinylMockup o de las plantas: sirve para revisar
el resultado en local, no para publicar en la tienda.

En `ProductionConfig` queda apagada. También se puede apagar en desarrollo:

```bash
VINYLMOCKUP_SPIKE=0
```

## Uso por CLI

```bash
# Buscar variantes
venv/bin/python scripts/spike_vinylmockup.py buscar clear
venv/bin/python scripts/spike_vinylmockup.py buscar splatter --limit 5

# Ver el detalle de una variante (incluye la imagen de 2160×2160)
venv/bin/python scripts/spike_vinylmockup.py variante 1rMSmdRmr1jOiLnZPpH1zc

# Ver una prensa
venv/bin/python scripts/spike_vinylmockup.py prensa 1o0Xf6NpetuZObPKw15vtQ

# Bajar una sola imagen a la carpeta temporal (no se commitea)
venv/bin/python scripts/spike_vinylmockup.py descargar 1rMSmdRmr1jOiLnZPpH1zc

# O a una carpeta concreta fuera del repo, o dentro de instance/ (ignorado por git)
venv/bin/python scripts/spike_vinylmockup.py descargar 1rMSmdRmr1jOiLnZPpH1zc --out /tmp/pruebas
venv/bin/python scripts/spike_vinylmockup.py descargar 1rMSmdRmr1jOiLnZPpH1zc --out instance/mockups/pruebas
```

También se puede pedir la salida en JSON:

```bash
venv/bin/python scripts/spike_vinylmockup.py buscar clear --json
venv/bin/python scripts/spike_vinylmockup.py variante <id> --json
```

## Límites conocidos

- El filtro `press` usa el **ID de Contentful**, no el slug. El detalle de la
  variante imprime `press_id`.
- La búsqueda devuelve 20 resultados por página.
- La API JSON no manda CORS: solo se puede consumir desde backend.
- No hay documentación, términos, SLA ni licencia visibles.
- Las imágenes son JPEG de 2160×2160, con fondo negro y sin transparencia.
- El cliente guarda las imágenes en la carpeta temporal del sistema
  (`tempfile.gettempdir()`, normalmente `/tmp`) y limita cada descarga a 12 MB.
- El CLI solo permite escribir fuera del repo o dentro de `instance/`, para no
  meter assets en git.
- No hay descarga masiva. La vista del panel solo previsualiza; no descarga ni
  guarda las imágenes.
- La vista del panel no se muestra si `DEBUG` está apagado o si
  `VINYLMOCKUP_SPIKE=0`.

## Variables opcionales

```bash
VINYLMOCKUP_API_BASE=https://vinylmockup.com
VINYLMOCKUP_TIMEOUT=20
VINYLMOCKUP_USER_AGENT=MusicalBox-spike/0.1
```

## Siguiente paso

Si se consigue una licencia, el contrato de `vinylmockup_api.py` se puede
convertir en un proveedor del renderer propio. Hasta entonces, la única
integración es la vista local del panel: no usar sus imágenes en producción
ni importar el cliente desde rutas públicas.
