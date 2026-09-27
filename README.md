# MusicalBox
# Luis Miguel Perez Valderrama

[![Top Langs](https://github-readme-stats.vercel.app/api/top-langs/?username=miguellperezzv&langs_count=8)](https://github.com/anuraghazra/github-readme-stats)

Tienda de CD's, vinilos y cassettes (lanzamientos, productos, carrito, pagos ePayco) con el gestor de
**solicitudes de pedido** y **rótulos de envío** que antes vivía en `musicalbox_manager`.

## Correr local

```bash
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python scripts\migrate_legacy.py   # crea instance/musicalbox.sqlite3 (migraciones + datos de ambas apps)
.venv\Scripts\python run.py                      # http://127.0.0.1:5000
```

### Migraciones (Flask-Migrate / Alembic)

El esquema se versiona en `migrations/versions/`. La app ya no crea tablas al arrancar.

```bash
.venv\Scriptslask --app run db upgrade                 # aplica las migraciones pendientes
.venv\Scriptslask --app run db migrate -m "mensaje"    # genera una migración tras cambiar los modelos (revísala antes de aplicarla)
.venv\Scriptslask --app run db downgrade               # revierte la última
```

Una BD creada antes de las migraciones se marca como línea base con `flask --app run db stamp 5b10cf662d03`.

Si pip falla con `CERTIFICATE_VERIFY_FAILED` (antivirus/proxy), instala primero `truststore` y usa
`pip install --use-feature=truststore -r requirements.txt`.

## Interfaz

Bootstrap 5.3 + Bootstrap Icons, con el sistema de diseño de la marca en `app/static/css/app.css`
(colores, tarjetas, navbar, panel admin) y utilidades JS en `app/static/js/app.js`
(autocompletado con `data-autocomplete="/url"`, carga del panel con `data-load`).
Macros reutilizables: `templates/_macros.html` (campos de formulario) y `templates/_cards.html` (tarjetas).

Para revisar el diseño en escritorio y celular (con la app corriendo):

```bash
.venv\Scripts\python -m pip install playwright
.venv\Scripts\python -m playwright install chromium
.venv\Scripts\python scripts\capturas.py        # guarda PNGs en .capturas/ y reporta errores JS y scroll horizontal
```

## Rutas principales

| Ruta | Qué es |
|---|---|
| `/releases/`, `/products/`, `/purchase/` | Tienda: catálogo y carrito |
| `/solicitud/` | Formulario público "Pide tu disco" (catálogo o pedido especial) |
| `/account` | Perfil, compras y solicitudes del usuario |
| `/dashboard` | Panel admin: lanzamientos, productos, órdenes de compra, solicitudes |
| `/solicitud/<id>/rotulo` | Rótulo de envío imprimible (admin) |

Quien hace una solicitud sin cuenta queda con rol `CLIENTE`; si luego se registra con el mismo email, reclama esa cuenta.
