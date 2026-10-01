# Musical Box: contexto del proyecto

Tienda online de música física (vinilos, CD's, cassettes y merch) de Bogotá, Colombia.
Une la tienda original (`MusicalBox`) con el gestor de pedidos a la medida (`musicalbox_manager`).
Repo: `github.com/miguelperezv/MusicalBox` (rama `main`). El remoto `upstream` es el repo original
`miguellperezzv/MusicalBox`; su historial se reescribió aquí para quitar una llave de Stripe.

## Cómo trabajar con el dueño

- Todo en **español**: interfaz, comentarios, mensajes de commit y respuestas.
- Respuestas **breves y estratégicas**; ahorrar tokens.
- **No escribir tests salvo que se pidan.** Hay una suite (`tests/`), pero no se amplía ni se corre en cada cambio.
  Basta una verificación rápida (curl/requests o una captura) de lo tocado.
- Commits pequeños y descriptivos, **sin** línea `Co-Authored-By` (el dueño pidió no vincular el sistema a su cuenta). Hacer push cuando lo pida
  (suele pedir "commit y push").
- Antes de cambios de **esquema** en funcionalidades grandes suele pedir primero un análisis en texto
  (qué existe, qué es aditivo y qué rompe) y esperar su confirmación.
- Le gustan los datos de prueba en la BD local: **no borrarlos** sin confirmar.
- **Trabajo paralelo con worktrees**: la carpeta principal vive en `main` (estable; es el único punto que
  integra a `main`). Una tarea = un worktree: `git worktree add ..\MusicalBox-<nombre> -b feature/<nombre>`.
  Cada worktree tiene su `instance/` (BD aislada) y reusa el `.venv` principal (`..\MusicalBox\.venv\Scripts\python`).
  Una rama solo puede estar en un worktree a la vez (git lo impide). Merge a `main`, push y
  `git worktree remove` se hacen desde la terminal principal cuando la tarea termina y pasó su verificación.

## Stack

- Python 3.12 (el Python 3.14 del PC está roto: `enum`), Flask 3.1, Flask-SQLAlchemy 3.1 / SQLAlchemy 2,
  Flask-Migrate (Alembic), Flask-WTF / WTForms 3, marshmallow 3 (<4: se usa `Meta.fields`), Pillow, requests, truststore.
- Frontend: Jinja + Bootstrap 5.3 + Bootstrap Icons + jQuery 3.7 (solo en el panel) + `app/static/js/app.js`.
- BD: SQLite en `instance/musicalbox.sqlite3` (ignorada por git). Producción prevista: PythonAnywhere con SQLite.
- Pagos: **MercadoPago** (payment brick + webhook). ePayco se retiró por completo en 2026-09; la suite de
  tests aún asume el flujo viejo. No es Wompi ni Stripe.

## Correr en local (Windows)

```bash
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt      # si falla SSL: pip install --use-feature=truststore ...
.venv\Scripts\python scripts\migrate_legacy.py --force        # BD desde cero + datos de las dos apps viejas (BORRA la actual)
.venv\Scripts\python run.py                                   # http://127.0.0.1:5000
.venv\Scripts\flask --app run db upgrade                      # aplicar migraciones pendientes
.venv\Scripts\flask --app run db migrate -m "mensaje"         # nueva migración (revisarla a mano)
.venv\Scripts\flask --app run crear-admin correo@x.com        # crear/promover administrador
```

- La app **no** hace `create_all()`: el esquema solo viene de `migrations/versions/`.
- Antes de migrar: `cp instance/musicalbox.sqlite3 instance/respaldos/antes-XXX.sqlite3`.
- Entorno del PC: el antivirus/proxy intercepta SSL. Git usa `http.sslBackend=schannel` y
  `credential.helper=manager` (globales); pip necesita truststore. `npm`/`npx` están rotos (no hay Lighthouse).
  Playwright + Chromium están instalados en el venv para capturas (`scripts/capturas.py`).
- `APP_CONFIG=production` → `ProductionConfig` (sin debug, sin simulación de pagos, cookies seguras, exige
  `SECRET_KEY`). Guía de despliegue: `docs/DEPLOY_PYTHONANYWHERE.md`.

## Estructura

```
run.py                     crea `app` (flask --app run ...); inyecta truststore y carga `.env` (dotenv)
app/__init__.py            create_app(): config por APP_CONFIG, blueprints, filtro |cop, context processor
                           (user, purchase_cart), 404, comando crear-admin
app/config.py              Config / DevelopmentConfig / ProductionConfig (MERCADOPAGO_*, SPOTIFY_*, MAIL_*, ACTIVACION_MAX_DIAS)
app/db.py                  db (naming convention), ma, migrate (render_as_batch)
app/correo.py              enviar(): backend consola (.eml en instance/correos/) | smtp | memoria (tests)
app/store/models.py        TODOS los modelos principales + la mayoría de la lógica de negocio
app/store/musicapi.py      cliente de la API de Spotify (client credentials): búsqueda de álbumes y
                           metadatos para sincronizar lanzamientos (SPOTIFY_CLIENT_ID/SECRET)
app/store/views.py         blueprints home, dashboard (admin), releases, artists, purchase, products
app/store/pedidos.py       /pedido/<token> (seguimiento, actualizar envío), simulación (dev)
app/store/mercadopago/     payment brick: create_preference, process_payment, webhook (MP)
app/store/solicitudes.py   pedidos a la medida: formulario, lista admin, cotizar, /solicitud/confirmar/<token>
app/store/carrito.py       carrito en sesión: agregar, cambiar cantidad, resumen con avisos de stock
app/store/catalogo_admin.py rutas extra del panel: tallas, packs, estado de envío, rótulo, redes, listados
app/store/notificaciones.py correos (pedido pagado, activar cuenta) y token de activación (itsdangerous)
app/store/redes.py         modelos Configuracion y PublicacionSocial + selección para el inicio
app/store/imagenes.py      imágenes de producto redimensionadas a WebP con caché (instance/cache_img/)
app/templates/             base.html, _macros.html (field, product_cover, producto_imagen, badge_original),
                           _cards.html (release_card, product_card), _producto_detalle.html (página y modal)
app/static/css/app.css     sistema de diseño (prefijo mb-); js/app.js (autocompletado, panel, vista rápida)
app/static/data/           municipios_colombia.json (DIVIPOLA; la API vieja de datos.gov.co ya no existe)
migrations/versions/       historial de esquema (ver abajo)
scripts/                   migrate_legacy.py (importa BD viejas), capturas.py (Playwright)
tests/                     pytest con BD temporal creada desde las migraciones (no ampliar sin pedirlo)
docs/                      DEPLOY_PYTHONANYWHERE.md, MER_manager.excalidraw.json
```

## Modelo de datos (tablas y relaciones)

- `usuario`: una sola tabla para clientes y admins. `k_rol` ∈ USER, ADMIN, CLIENTE.
  **CLIENTE** = comprador o solicitante **sin login** (contraseña aleatoria). Solo activa su cuenta con el enlace
  firmado que llega a su correo (`/activar/<token>`); registrarse o ingresar con ese correo envía el enlace.
  Correo único, se compara sin distinguir mayúsculas. Contraseñas con **bcrypt** (`app/store/seguridad.py`);
  las cuentas legacy en texto plano autentican y se re-hashean al ingresar.
- `lanzamiento` (el disco) ↔ `artista` (N:M `lanzamiento__artista`) ↔ `genero` (N:M `lanzamiento__genero`).
  `url_social`: post opcional de IG/TikTok, se ve en un modal. `external_id`/`external_url`: álbum de
  Spotify asociado para re-sincronizar metadatos (ver Flujos clave).
- `producto`: pertenece a **un** lanzamiento (1:N, opcional). `categoria` (texto: VINILO, CD, CAMISETA...),
  `tipo` SIMPLE | BUNDLE, `original_mb` (merch propio → sello "Original MB"), `stock` (solo SIMPLE sin tallas),
  `url_imagen` (opcional: link de compartir de Drive o URL directa; se normaliza al servirla y solo se usa
  si no hay fotos subidas; se valida al guardar que responda `image/*`).
- `variante`: talla/color/sku/stock de un producto. Si un producto tiene variantes, el stock vive ahí.
- `producto_componente`: contenido de un pack (bundle → componente [+ variante] × cantidad). Los packs no se anidan.
- `imagen`: foto del producto guardada en la BD (bytes). Se sirve redimensionada en `/products/image_<id>?w=300|600|1200`;
  sin foto redirige a la portada del lanzamiento o al logo.
- `invoice` (= pedido u orden): `estado` de pago PENDIENTE | PAGADO | RECHAZADO; `estado_envio`
  POR PREPARAR | EN PREPARACION | ENVIADO | ENTREGADO; `token_hash` (SHA-256 del token del enlace);
  **copia de los datos de envío** (`n_envio`, `dir_envio`...; no cambia si el usuario edita su perfil); `metodo_pago`.
- `item`: línea de pedido con **id propio**, `k_variante` opcional, `p_item` = precio al comprar.
- `solicitud`: pedido a la medida. Contacto (`cel_contacto` obligatorio, `email_contacto` opcional), `k_usuario` opcional,
  disco en texto y/o `k_producto`; cotización (`precio_cotizado`, `token_hash`, `k_invoice`).
  Estados: ACTIVO, EN PROCESO, COTIZADA, COMPRADA, CANCELADO (ENVIADO/ENTREGADO solo como historial antiguo).
- `configuracion`: clave-valor para ajustes del sitio (hoy `redes.*`). Reutilizarla para nuevos ajustes.
- `publicacion_social`: posts de IG/TikTok para el inicio (url, id_externo, orden, activo, error_embed).

Migraciones (en orden): `5b10cf662d03` línea base → `a36be8d1f63e` checkout sin cuenta →
`3c91f0d79d11` variantes/bundles y reconstrucción de `item` (**solo SQLite**) → `a8429ab90db1` contacto/cotización/envío →
`f8c18145ced0` redes/configuración → `67bf9fe64495` original_mb y url_social → `34fd6248975a` url_imagen en producto →
`5215e71ba6b8` spotify external en lanzamiento.

## Flujos clave

- **Compra sin cuenta**:
  1. Carrito en sesión, con claves `"producto"` o `"producto:variante"`.
  2. `/purchase/checkout` (`CheckoutForm`: nombre, correo, celular, envío, método de pago; sin contraseña).
     `crear_pedido()` crea el pedido PENDIENTE y devuelve un token `secrets.token_urlsafe(32)`.
  3. `/pedido/<token>` carga el payment brick de MercadoPago; al aprobarse el frontend llama a
     `/mercadopago/process_payment` (PSE tarda: lo confirma el webhook `/mercadopago/webhook`).
  4. Ambos caminos llaman a `confirmar_pago()` (models), que es idempotente: descuenta stock (variante o componentes
     del pack), libera las reservas de `ReservaStock`, pasa a PAGADO / POR PREPARAR, marca la solicitud COMPRADA
     y envía el correo una sola vez. Rechazados: `rechazar_pago()` (libera la reserva).
- **Stock**: `stock_disponible()`, `validar_carrito()` (suma la demanda de sueltos + packs por unidad física),
  `descontar_stock()` (nunca queda negativo).
- **Pedido a la medida**:
  1. `/solicitud/`: solo disco + celular (WhatsApp) + correo opcional.
  2. El admin **cotiza**: asocia un producto del catálogo y el precio; se genera el enlace y un botón de WhatsApp.
  3. `/solicitud/confirmar/<token>` reutiliza el checkout, prellenado con la última dirección usada, y cobra el precio
     cotizado **sin revisar stock**.
  4. Al pagarse, la solicitud pasa a COMPRADA.
- **Rótulo de envío**: pertenece a la **orden**. Solo se ve en EN PREPARACION/ENVIADO (`/dashboard/pedido/<id>/rotulo`).
- **Redes en el inicio**: configuración por plataforma (`redes.instagram.*`, `redes.tiktok.*`: modo `ultimas_n` o
  `random_n_de_m`, N, M). Por defecto Instagram 3×3 y TikTok 1 al azar. El sorteo se fija **por sesión** (firma de
  config + conjunto). Los embeds se cargan al llegar a la sección (IntersectionObserver); si no cargan en 10 s, se ocultan.
- **Vista rápida**: `data-quickview="<url>?modal=1"` abre el contenido en `#mbModal` (producto, post del lanzamiento).
  Ctrl+clic abre la página. Usar modal para consultar sin salir; usar página propia para carrito, checkout, pedido y cuenta.
- **Spotify en lanzamientos**: el formulario "Nuevo lanzamiento" busca álbumes en la API de Spotify
  (client credentials; `SPOTIFY_CLIENT_ID`/`SPOTIFY_CLIENT_SECRET`). Al elegir uno, se rellenan nombre, portada,
  fecha y artista (que se crea solo si no existe) y se guardan `external_id`/`external_url`. En la edición del
  lanzamiento, el botón "Actualizar metadatos desde Spotify" refresca nombre/fecha/portada/URL sin tocar géneros
  ni productos y sin degradar una fecha guardada más precisa (día > mes > año). Sin llaves, la búsqueda responde
  con un error amigable.

## Panel admin (`/dashboard`, requiere rol ADMIN)

Resumen con métricas · Solicitudes (cotizar, WhatsApp) · Órdenes (estado de envío, rótulo) · Lanzamientos y
Productos y packs (listados con Editar; tallas y contenido de packs en "Editar producto") · Artistas, géneros y
categorías · Redes en el inicio · Nuevo administrador.
Las secciones con `data-load` se cargan por AJAX dentro de `#admin-content`; las páginas completas extienden
`adminDashboard.html` y rellenan `{% block content %}`.

## Convenciones de código

- Nombres en español, siguiendo el estilo existente (`k_` = clave foránea, `n_` = nombre, `p_` = precio, `f_` = fecha).
  Comentarios cortos en minúscula con `#`.
- Cambios de esquema: modelo → `flask db migrate` → **revisar a mano** (defaults para datos existentes, datos a copiar,
  guardas en el downgrade) → respaldo → `db upgrade` → commit aparte.
- Plantillas: macros `field()` para formularios, precios con `|cop` ($150.000), clases CSS con prefijo `mb-`.
  Reglas genéricas como `.mb-card .cover img` afectan a todo lo que esté dentro: usar selectores específicos
  (ya pasó con el botón de editar y con el logo del sello).
- Macros importados con `{% from ... import ... with context %}` cuando necesitan `user`.
- El carrito, la cuenta y otras vistas se leen de `g.user` / `g.purchase` (lo llena `before_request`).

## Pendientes conocidos

- **Suite de tests desactualizada**: asume el flujo viejo de ePayco (monkey-patchean `consultar_epayco`,
  que ya no existe) → reescribirla sobre `confirmar_pago`/webhook de MP. Solo si se pide.
- **Correo real**: elegir proveedor y `MAIL_*` (`run.py` ya carga `.env`; falta un `.env.example` documentado).
  Hoy el correo se guarda en `instance/correos/`.
- **Despliegue en PythonAnywhere** (guía lista). La migración de `item` para MySQL no está escrita
  (solo si la BD de producción deja de ser SQLite).
- **Estacionados** (fuera de alcance por ahora): miniaturas reales de Instagram (API Meta), carga
  automática de posts, restringir los métodos de MercadoPago según lo elegido en el checkout.

Ya resueltos (no volver a listar): contraseñas con bcrypt + re-hash legacy, CSRF en todo el panel
(exento solo el webhook de MercadoPago), llaves de MP por defecto (hoy placeholders neutros, vienen del
entorno), y reserva de stock entre crear y pagar el pedido (`ReservaStock`, liberada en pago/rechazo y
expiradas al reservar), residuos de ePayco (`referencia_epayco`, flag `EPAYCO_SIMULACION` → `SIMULACION_PAGO`),
e imagen por link externo (`url_imagen` en producto: link de Drive normalizado a URL directa, validado al
guardar, usado solo si no hay fotos subidas; migración `34fd6248975a`).
