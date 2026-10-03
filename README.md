# MusicalBox

Luis Miguel Perez Valderrama

Tienda online de música física (vinilos, CDs, cassettes y merch) de Bogotá, Colombia. Este repositorio une la
tienda original con el gestor de pedidos a la medida: catálogo, carrito, compra sin cuenta, pagos con
MercadoPago, costo de envío cotizado con EnvíoClick, pedidos a la medida y panel administrativo.

## Qué incluye

- **Tienda pública**: lanzamientos, productos (con variantes de talla/color y packs), vista rápida en modal,
  posts de Instagram/TikTok en el inicio.
- **Compra sin cuenta**: carrito → checkout (nombre, correo, celular y envío; el método de pago lo elige el
  cliente dentro de MercadoPago) → orden PENDIENTE
  → `/pedido/<token>` con el payment brick de MercadoPago → confirmación idempotente del pago.
- **Costo de envío**: se calcula al crear la orden (reglas de envío gratis → cotización real de EnvíoClick →
  tarifa por zona de respaldo) y se cobra con la compra. El cliente ve el estimado en vivo al escribir su
  municipio; página pública en `/politica-envios`. El admin puede corregirlo hasta que el pedido es ENVIADO.
- **Pedidos a la medida**: `/solicitud/` ("Pide tu disco") → el admin cotiza un producto y precio →
  `/solicitud/confirmar/<token>` cobra el precio cotizado reutilizando el checkout.
- **Panel admin** (`/dashboard`): métricas, solicitudes (cotizar, WhatsApp), órdenes (estado de envío,
  rótulo, costo de envío), lanzamientos y productos, artistas/géneros/categorías, redes del inicio,
  reglas de envío gratis y nuevo administrador.
- **Notificaciones**: correo de confirmación al cliente (backend consola/SMTP) y avisos al admin por
  Telegram en los eventos clave (solicitud nueva, orden pendiente, pago aprobado/rechazado).
- **Spotify**: búsqueda de álbumes en "Nuevo lanzamiento" y re-sincronización de metadatos (requiere
  `SPOTIFY_CLIENT_ID`/`SPOTIFY_CLIENT_SECRET`; sin llaves la búsqueda responde con un error amigable).

## Stack

Python 3.12 · Flask 3.1 · Flask-SQLAlchemy 2 / SQLAlchemy 2 · Flask-Migrate (Alembic) · Flask-WTF ·
Marshmallow 3 · Pillow · Jinja + Bootstrap 5.3 + Bootstrap Icons + jQuery 3.7 (solo el panel) ·
SQLite en `instance/musicalbox.sqlite3` (fuera de git). Producción prevista: PythonAnywhere.

## Correr en local

```bash
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python scripts\migrate_legacy.py --force   # BD desde cero: migraciones + datos legacy (BORRA la actual)
.venv\Scripts\python run.py                              # http://127.0.0.1:5000
```

> Si pip falla con `CERTIFICATE_VERIFY_FAILED` (antivirus/proxy del PC), instala primero `truststore` y usa
> `pip install --use-feature=truststore -r requirements.txt`. La app ya inyecta `truststore` al arrancar.

Copia `.env.example` a `.env` y ajusta las llaves. Variables principales:

| Variable | Para qué |
|---|---|
| `SECRET_KEY` | firma de sesiones y tokens (obligatoria en producción) |
| `DATABASE_URL` | BD SQLite (por defecto `sqlite:///musicalbox.sqlite3`) |
| `MERCADOPAGO_PUBLIC_KEY` / `MERCADOPAGO_ACCESS_TOKEN` | payment brick y preferencias |
| `ENVIOCLICK_TOKEN` | cotización real de fletes (sin ella cae la tarifa por zona) |
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | buscar y refrescar metadatos de lanzamientos |
| `MAIL_BACKEND` + `MAIL_*` | `consola` (default, `.eml` en `instance/correos/`) o `smtp` |
| `TG_BACKEND` / `TG_BOT_TOKEN` / `TG_ADMIN_CHAT_ID` | avisos al admin por Telegram |
| `APP_CONFIG=production` | modo producción (sin debug ni simulación, cookies seguras) |

### Migraciones (Flask-Migrate / Alembic)

El esquema se versiona en `migrations/versions/`; la app **no** crea tablas al arrancar.

```bash
.venv\Scripts\flask --app run db upgrade                 # aplica las migraciones pendientes
.venv\Scripts\flask --app run db migrate -m "mensaje"    # genera una migración tras cambiar los modelos (revísala antes de aplicarla)
.venv\Scripts\flask --app run crear-admin correo@x.com   # crea/promueve un administrador
```

## Flujo de compra

1. Carrito en sesión (sueltos, variantes y packs).
2. `POST /purchase/process_checkout` → `crear_pedido()` crea la orden PENDIENTE con su costo de envío y
   devuelve un token `secrets.token_urlsafe(32)`; en la BD solo se guarda su SHA-256.
3. `/pedido/<token>` carga el brick de MercadoPago; el monto es **total + costo de envío**.
4. El brick o el webhook llaman a `confirmar_pago()`, idempotente: descuenta el stock una sola vez, libera
   las reservas, pasa a PAGADO / POR PREPARAR, marca la solicitud COMPRADA y envía los avisos.
   Rechazados: `rechazar_pago()` libera la reserva.
5. El comprador sin cuenta es un `usuario` con rol `CLIENTE` (contraseña aleatoria); activa su cuenta con el
   enlace firmado del correo (`/activar/<token>`, 7 días, de un solo uso).
6. En desarrollo, `/pedido/<token>/simular` permite simular la confirmación del pago.

## Pruebas

```bash
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest tests        # BD temporal creada con las migraciones; pago simulado
```

## Rutas principales

| Ruta | Qué es |
|---|---|
| `/`, `/releases/`, `/products/` | Tienda: catálogo |
| `/purchase/` | Carrito y checkout |
| `/pedido/<token>` | Seguimiento y pago de la orden (pública) |
| `/solicitud/` | Formulario público "Pide tu disco" |
| `/politica-envios` | Política de envíos y promociones de envío gratis |
| `/account` | Perfil, compras y solicitudes del usuario |
| `/dashboard` | Panel admin (rol ADMIN) |
| `/dashboard/pedido/<id>/rotulo` | Rótulo de envío imprimible (admin) |

## Interfaz

Bootstrap 5.3 + Bootstrap Icons, con el sistema de diseño de la marca en `app/static/css/app.css`
(prefijo `mb-`) y utilidades JS en `app/static/js/app.js` (autocompletado con `data-autocomplete`,
carga del panel con `data-load`, vista rápida en modal). Macros reutilizables en `templates/_macros.html`
(campos de formulario) y `templates/_cards.html` (tarjetas).

Capturas de pantalla con Playwright (con la app corriendo; guarda PNGs en `.capturas/` y reporta
errores JS y scroll horizontal):

```bash
.venv\Scripts\python -m pip install playwright
.venv\Scripts\python -m playwright install chromium
.venv\Scripts\python scripts\capturas.py
```

## Documentación

- **Wiki del proyecto**: https://github.com/miguelperezv/MusicalBox/wiki (desarrollo local, estructura,
  pagos MercadoPago, costo de envío, notificaciones y despliegue).
- **Guía de despliegue en PythonAnywhere**: `docs/DEPLOY_PYTHONANYWHERE.md`.
- **Notificaciones por Telegram**: `docs/ANALISIS_NOTIFICACIONES.md`.
