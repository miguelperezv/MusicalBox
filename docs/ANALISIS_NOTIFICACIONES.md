# Notificaciones por WhatsApp — análisis y propuesta

Rama: `feature/notificaciones`. Estado: análisis + **fase 1 implementada** (avisos al admin por Telegram: A1, A2, A3, A4).

## 1. Estado actual

- **Correo** (única notificación automatizada): `app/correo.py` (`enviar()`, backends `consola` | `smtp` | `memoria`, nunca lanza excepción). Dispara en 2 eventos: pedido pagado (`app/store/notificaciones.py:49`, `correo_pedido_pagado`) y activación de cuenta (`notificaciones.py:62`).
- **WhatsApp**: 100% manual. Solo links `wa.me` que el admin abre en su celular:
  - Cotización lista: `app/store/solicitudes.py:150` arma `https://wa.me/<num>?text=<mensaje>` y el panel lo ofrece como botón "Enviar por WhatsApp" (`solicitudes.html:240,333`).
  - "WhatsApp al comprador" en órdenes: `invoices.html:45`.
  - Formulario de solicitud: el flash "Te escribiremos por WhatsApp" es texto de UI, no un envío (`solicitudes.py:64`).
- **No hay número de admin configurado en ninguna parte** (ni BD ni entorno). La tabla `Configuracion` clave-valor (`app/store/redes.py:17-21`, helpers `get_config`/`set_config`) es el lugar natural para guardarlo.
- Pagos: MercadoPago (brick + webhook). El punto canónico de "pago aprobado" es `confirmar_pago()` (`app/store/models.py:1517`), idempotente, al que llegan brick, webhook y simulación de dev; el flag `pago_nuevo` ya garantiza "una sola vez" (lo usa el correo).

## 2. Puntos del proceso que notificarían al admin

| # | Evento | Enganche (file:line) | Prioridad | Por qué |
|---|--------|----------------------|-----------|---------|
| A1 | **Nueva solicitud a la medida** | `create_solicitud()` `models.py:1026` (vía `/solicitud` en `solicitudes.py:47-70` y `/solicitud/nueva_admin` en `154-183`) | **Alta** | Hoy es totalmente silencioso: el admin solo lo ve si entra al panel. Es el inicio del negocio a la medida. |
| A2 | **Pago aprobado (compra)** | `confirmar_pago()` `models.py:1517` | **Alta** | El admin debe prepararenvío sin depender de que abra el panel. Cubre brick, webhook PSE tardío y simulación. |
| A3 | Pago rechazado | `rechazar_pago()` `models.py:1558` | Media | Avisa de intento fallido (posible seguimiento manual al cliente). También lo genera el rechazo manual del panel. |
| A4 | Orden creada pendiente de pago | `crear_pedido()` `models.py:1433` | Media (opcional) | Permite seguimiento de carritos que pagaron "después" o fueron abandonados. Ruido: un cliente puede crear y no pagar. |
| A5 | Cambio de estado de envío | `actualizar_envio()` `models.py:1792` | Baja | El que actúa es el admin; no necesita que le avisen de su propia acción. |

Confirmación de la intuición inicial: **solicitud + compra (pago aprobado) son los dos imprescindibles**; A3 y A4 son mejoras de baja complejidad (mismo enganche).

## 3. Puntos que notificarían al cliente (por WhatsApp)

| # | Evento | Enganche | Prioridad | Por qué |
|---|--------|----------|-----------|---------|
| C1 | **Solicitud recibida** | `create_solicitud()` `models.py:1026` | **Alta** | El cliente hoy solo ve un flash en la web; sin confirmación puede pensar que no llegó. El celular lo tiene obligatorio (`Solicitud.cel_contacto`). |
| C2 | **Cotización lista** | `cotizar_solicitud()` `models.py:1738` | **Alta** | Hoy el admin copia/pega el link manualmente. Con el mensaje automático + link de confirmación (`/solicitud/confirmar/<token>`) se cierra el ciclo sin dependencia del admin. |
| C3 | **Pedido creado, pendiente de pago** | `crear_pedido()` `models.py:1433` | **Alta** | El mayor abandono del flujo es en el brick. Un link de pago por WhatsApp (`/pedido/<token>`) recupera clientes que cerraron la pestaña. |
| C4 | **Pago confirmado** | `confirmar_pago()` `models.py:1517` | **Alta** | Complementa el correo (que hoy es el único aviso). Muchos clientes revisan WhatsApp antes que el correo. |
| C5 | Pago fallido | `rechazar_pago()` `models.py:1558` | Media | "Tu pago no se aprobó, reintenta aquí" con el link de pago. |
| C6 | **Pedido enviado** | `actualizar_envio()` `models.py:1792` (transición a `ENVIADO`) | **Alta** | Actualización logística clásica. Es el evento donde el cliente MÁS pregunta "¿dónde está mi pedido?". |
| C7 | Entregado / agradecimiento | `actualizar_envio()` a `ENTREGADO` | Baja | Opcional: cierre cálido, pedir reseña o post en redes. |

Datos de contacto ya disponibles: `Invoice.tel_envio` (copia inmutable del checkout), `Solicitud.cel_contacto`, `Usuario.cel_usuario`. La normalización para `wa.me` (prefijo `57` + 10 dígitos) ya existe en `solicitudes.py:150`.

## 4. Cómo enviar WhatsApp: opciones

| Opción | Costo | Pros | Contras |
|--------|-------|------|---------|
| **1. `wa.me` manual** (estado actual) | 0 | Sin APIs, sin approval, sin riesgo | El admin manda todo a mano desde su celular; no llega nada al admin sin que alguien lo dispare; no media/rich |
| **2. Meta Cloud API (oficial)** | Pago por mensaje (categoría *utility* más barata que *marketing*; free tier de conversaciones de servicio, verificar términos) | Oficial, sin riesgo de ban, número de negocio, webhooks para recibir respuestas del cliente, accesibles | Plantillas pre-aprobadas para mensajes del negocio al cliente; ventana de 24 h para chat libre; el número debe ser exclusivo de la API (no puede estar en la app normal); setup de business verification |
| **3. Twilio WhatsApp** | USD por mensaje, vía Twilio | API muy simple, documentación buena | Mismo régimen de plantillas que Meta (usa la oficial por debajo), costo en USD |
| **4. Evolution API (no oficial, self-hosted Docker)** | 0 (huberlo en un VPS ~$5/mes) | Entra con el número propio del negocio por QR, escribe a cualquier número sin plantillas, soporta media, REST + webhooks, muy usado en LATAM | Va contra ToS de WhatsApp: riesgo de ban del número si hay volumen o automatización; requiere VPS (PythonAnywhere no corre Docker) |
| **5. Telegram bot (solo para el admin)** | 0 | El admin recibe alertas A1-A4 en su celular gratis y sin approval; API trivial (1 `sendMessage`) | No es WhatsApp; solo sirve para el lado admin |

### Recomendación

Faseada, para no frenar el feature:

1. **Fase 0 (esta rama, costo 0)**: arquitectura de notificaciones + backends `consola`/`memoria` para desarrollo. El envío real sigue siendo manual por `wa.me`, pero **el contenido queda generado por la app** en cada evento (msg + link), visible en el panel con botón de enviar (como ya existe en cotización). El admin configura su número y qué eventos activar.
2. **Fase 1 (alertas al admin)**: Telegram bot (gratis) o Evolution API en VPS (WhatsApp real).
3. **Fase 2 (clientes automatizados)**: Meta Cloud API con plantillas *utility*: C1, C2, C3, C4, C5, C6. (Evolución queda como alternativa si el costo de la oficial no convence, aceptando el riesgo de ban con un número dedicado.)

## 5. Modo desarrollador: cómo se proban las notificaciones

### 5.1 Local (la app)

Imitar el patrón que ya usa el correo (`MAIL_BACKEND=consola`):

- `WSP_BACKEND=consola` (default en dev): cada notificación se imprime y se guarda en `instance/wsp/` como `.txt` (con fecha, evento, destino, mensaje). Nunca lanza excepción: si algo falla, el flujo de compra sigue (mismo contrato que `app/correo.py:8`).
- `WSP_BACKEND=memoria`: apila en `app.extensions["wsp_enviados"]` para tests.
- `SIMULACION_PAGO=True` (dev) dispara A2/C4/C5 desde `/pedido/<token>/simular`; `/mercadopago/webhook-test` cubre la ruta PSE tardía.
- Para links absolutos en mensajes (seguimiento, pago) fuera de contexto de request (webhook): agregar `URL_BASE` a config; hoy el correo desde webhook ya sufre un problema parecido (usa `p.token_hash` como token, `mercadopago/views.py:409-410`).

### 5.2 Meta Cloud API en modo de prueba (después)

1. Meta developer account → crear app (tipo "Business") → agregar producto **WhatsApp** → modo **test**.
2. En test mode: un número de prueba de Meta, token temporal, y hasta **5 números de testeo** agregados a la app. Solo esos números pueden recibir mensajes; no hace falta public review ni business verification.
3. Crear plantillas (*utility*) de prueba y enviarlas con `POST /v{ver}/<phone-number-id>/messages` (token en `X-POST-Bearer`).
4. Pasar a producción: verificar el negocio, número dedicado, token permanente y webhook para recibir respuestas del cliente (con eso se abre el chat de 24 h).

## 6. Arquitectura propuesta en el código (Fase 0)

- **`app/wsp.py`** (nuevo, espejo de `app/correo.py`): `enviar_wsp(destino, mensaje, tipo, evento)` con backends `consola` | `memoria` | `wame` (genera link `wa.me` y lo guarda/lo devuelve para envío manual) — y más adelante `meta` | `evolution`. Punto único, nunca rompe el flujo.
- **Configuración** en `Configuracion` (`app/store/redes.py`):
  - `wsp.admin_cel` — número del admin (formato 57XXXXXXXXXX).
  - `wsp.evento.<clave>` — on/off por evento (`solicitud_nueva`, `pago_aprobado`, `pago_rechazado`, `pedido_creado`, `envio`, `solicitud_cliente`, `cotizacion`, `pendiente_pago`).
  - Sección de ajustes en el panel (estilo de la sección de redes, `catalogo_admin.py:109-170`).
- **Ganchos** (llamadas de 1 línea al final de cada función, envueltas en try/except):

| Enganche | Notifica a | Eventos |
|----------|-----------|---------|
| `create_solicitud()` | admin + cliente | A1, C1 |
| `crear_pedido()` | admin + cliente | A4, C3 |
| `confirmar_pago()` | admin + cliente | A2, C4 (con el flag `pago_nuevo`, igual que el correo: una sola vez entre brick/webhook/simulación) |
| `rechazar_pago()` | admin + cliente | A3, C5 |
| `cotizar_solicitud()` | cliente (link que hoy se arma en `solicitudes.py:121-151` se mueve aquí) | C2 |
| `actualizar_envio()` | cliente (solo transición a `ENVIADO`) | C6 |

- **Anti-duplicación**: flags en los modelos (`Invoice.notificado_pago`, `notificado_envio`; `Solicitud.notificada_creacion`, `notificada_cotizacion`) o reutilizar `pago_nuevo`; el webhook y el brick pueden llegar casi a la vez.
- **Plantillas de mensaje** en `app/store/notificaciones.py` (o `plantillas_wsp.py`), en español, tono de la tienda, con `{total}` ya formateado (`|cop`).

## 7. Ejemplos de mensaje

**Al admin**
- A1: `Nueva solicitud #12: 2 x Disco a la medida "Dark Side of the Moon". Contacto: 300 123 4567. Panel: <url>/solicitud/solicitudes`
- A2: `Pago aprobado: pedido #45 por $320.000 (Tarjeta). Cliente: X YZ, 300 123 4567, <ciudad>. Prepara el pedido.`
- A3: `Pago rechazado: pedido #45 ($320.000, cliente X YZ). Quizás deba reintentar.`
- A4: `Nueva orden pendiente de pago: #45, $320.000, X YZ.`

**Al cliente**
- C1: `Hola, recibimos tu solicitud para 2 x "Dark Side of the Moon". Te escribimos por este medio con precio y tiempos.`
- C2: `Hola, tu cotización está lista: 2 x ... por $320.000. Confirma y paga aquí: <url>/solicitud/confirmar/<token>`
- C3: `Tu pedido #45 ($320.000) está listo para pagar: <url>/pedido/<token>`
- C4: `Gracias por tu compra. Pedido #45 confirmado por $320.000. Estado y seguimiento: <url>/pedido/<token>`
- C5: `Tu pago del pedido #45 no se aprobó. Puedes reintentar aquí: <url>/pedido/<token>`
- C6: `Tu pedido #45 fue enviado por <transportadora>. Seguimiento: <url>/pedido/<token>`

## 8. Riesgos y detalles finos

- `wa.me?text=` no incrusta imágenes ni media (límite conocido, ya documentado en `docs/PROPUESTA_COTIZACIONES.md`); longitud de mensaje razonable (< ~800 caracteres).
- Meta: solo se puede iniciar conversación al cliente con plantilla aprobada (cat. *utility*); el chat libre libre solo dentro de las 24 h desde que el cliente escribe. El número en API no puede usarse en la app de WhatsApp normal.
- Evolution API: ban del número por uso automatizado; si se usa, con número dedicado y sin reenvíos masivos.
- El webhook de MP llega sin contexto de request: los links absolutos requieren `URL_BASE` en config (o se resigna a link relativo). Cuidado con no replicar el bug del token en el correo de webhook (`mercadopago/views.py:409-410`).
- Todos los ganchos van en try/except: **una notificación fallida jamás rompe la compra** (contrato del correo, `app/correo.py:8`).
- El celular del checkout (`tel_envio`) puede venir con formato 0XX o +57: normalizar antes de `wa.me` (57 + 10 dígitos).

## 9. Siguiente paso concreto (Fase 0, en esta rama)

1. `app/wsp.py` con backends `consola` y `memoria` + config `WSP_BACKEND` (default `consola`).
2. `URL_BASE` en `app/config.py` y `.env.example`.
3. Claves `wsp.*` en `Configuracion` + sección de ajustes en el panel.
4. Ganchos en las 6 funciones de la sección 6 + plantillas de mensajes (sección 7).
5. Flags anti-duplicación + migración de esquema.
6. Backend `wame`: guardar link `wa.me` generado y ofrecer botones "Enviar por WhatsApp" en solicitudes y órdenes (ya existe en solicitudes; extender a C3/C4/C5/C6 y A1/A2).
