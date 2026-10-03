# Propuesta: costo de envío con cotización real de EnvíoClick Pro (verificada con key del dueño)

Fecha: 2026-10-03 · Estado: **en revisión, iteración 6** (API probada en vivo con tarifas reales) · Nada se implementa hasta la confirmación del dueño.

## Lo ya decidido

- **Proveedor: EnvíoClick Pro** (`api.envioclickpro.com.co`) — gratis: cuenta en envioclick.com → API key en "Mi cuenta → Información del API". La key ya está en `.env` como `ENVIOCLICK_TOKEN`.
- **Cotización real, gratis y en producción** (verificada hoy, 2026-10-03):

  Bogotá→Medellín, 1 kg, caja 30×31×5 cm, valor $200.000 →
  **Envía $14.696 / 2 días · Coordinadora $17.682 / 1 día · TCC $19.261 / 3 días.**

- Orden de decisión del costo: **manual del admin > reglas automáticas > cotización EnvíoClick (criterio: menor `flete`, configurable) > tarifa por zona (fallback si la API falla)**.
- El municipio es **desplegable completado y estricto** (solo valores del listado oficial).
- El **admin decide por pedido** si se cobra envío y cuánto (con el sugerido visible).
- El **estimado se ve en la cotización y en el checkout**, y al confirmar se convierte en el cargo real (MP lo cobra).

## El contrato (verificado)

- `POST https://api.envioclickpro.com.co/api/v2/quotation` · Headers: `Authorization: <API key>` (UUID, no Bearer), `Content-Type: application/json`. **Ojo**: Cloudflare bloquea UA no-navegador (403/1010); usar User-Agent de navegador.
- Body (todo obligatorio salvo los COD):
  ```json
  {
    "description": "Vinilo (musica fisica)",
    "contentValue": 200000,
    "packages": [ { "weight": 1.0, "height": 5, "width": 30, "length": 31,
                    "codValue": 0, "includeGuideCost": false, "codPaymentMethod": "cash" } ],
    "origin":      { "daneCode": "11001000", "address": "Carrera 15 # 85-40" },
    "destination": { "daneCode": "05001000", "address": "Carrera 50 # 50-50" }
  }
  ```
  - `packages` es **lista** (1 paquete por llamado). `weight` en kg (mín 1.0), medidas en cm, `contentValue` COP.
  - `daneCode` es el **código DANE de 8 dígitos** (Bogotá `11001000`, Medellín `05001000`).
  - Errores típicos: 422 con el campo en `status_messages` ("El campo X es obligatorio" / "debe ser una lista de objetos").
- Respuesta: `status=OK` + `data.rates[]` → `{carrier, product, flete, deliveryDays, idRate, quotationType, minimumInsurance, ...}`. `idRate` se guarda si queremos generar guía después (fase 2: `POST /shipment`).
- Demás endpoints: `/shipment` (guía; exige saldo en monedero en prod), `/shipment_sandbox` (guía de prueba), `/track`, `/track-by-orders`, `/cancellation/batch/order`.

## Qué existe hoy (resumen)

- `CheckoutForm.ciudad`: autocompletado en vivo contra `/colombia` (DIVIPOLA + 20 localidades "X, Bogotá D.C."). `mbAutocomplete` corregido (2+ letras, multi-campo, teclado) pero **sin validación estricta**.
- `Invoice`: solo `total` (productos). MP cobra `invoice.total`.
- Cotización (`solicitudes.py`): WhatsApp con total de ítems; sin municipio ni envío.
- Peso por producto: no existe (lo exige la cotización real).
- Códigos DANE: no hay tabla local (los resuelve el mapa propuesto abajo).

## Diseño

### A. Municipio: desplegable "completable" y estricto

- `mbAutocomplete` gana modo **estricto** (`data-strict`): solo acepta valores del listado; texto libre no reconocido → inválido ("Escribe un municipio válido"). El backend valida igual (doble guarda).
- Opción **"Otro municipio…"** al final: texto libre (casos exóticos/exterior). El pedido se acepta; el envío va a manual o fallback.
- **Mapeo a DANE local** en tabla nueva `ubicacion` (nombre normalizado, departamento, `daneCode` 8 dígitos): se llena **una vez** (comando `sincronizar-ubicaciones` + botón en panel) usando el endpoint **gratis y sin token** `POST https://api.envia.com/locate` (verificado hoy: Medellín→`05001000`) contra nuestra lista de ~1.100 municipios; los que no resuelvan se parchan a mano. Las 20 localidades de Bogotá → `11001000`.
- **Nuevo**: el formulario público de solicitud gana campo opcional "Municipio de destino" → permite el estimado en la cotización.
- Formato guardado sin cambios: `lugar_envio` ("Municipio, Departamento").

### B. Motor de cotejo (`app/store/envio.py`)

- `calcular_envio(lineas, lugar_envio)` → `(costo, detalle, oferta)`:
  1. **Reglas** activas (por `orden`) → su costo y fin.
  2. Si no, **EnvíoClick**: `POST /quotation` con origen fijo (config: bodega en Bogotá) y el destino por `ubicacion`; elige por **menor `flete`** (criterio configurable: precio/tiempo) → `detalle` = "Envía Normal: $14.696 (2 días)".
  3. Si falla / no hay peso → **tarifa por zona** (`configuracion`: `envio.zona_bogota` / `envio.zona_nacional`) → `detalle` = "Tarifa: nacional".
- **Peso del pedido**: campo nuevo `peso_gramos` en `Producto` (y opcional en `Variante`; el bundle suma componentes × cantidad) en "Editar producto". Pedido sin peso → fallback por zona con nota.
- **Caja por defecto** en `configuracion`: `envio.ancho_cm`/`largo_cm`/`alto_cm` (default: vinilo 31×30×5). `contentValue` = total del pedido + costo de envío.
- **Cache de cotizaciones**: tabla `cotizacion_cache` (origen+destino+peso a 0.5 kg+caja → oferta, TTL 24 h) para no llamar a la API con cada pulsación y para que el estimado no se mueva entre el WhatsApp y el confirmar. Timeout ~8 s; nunca bloquea el checkout.

### C. Reglas automáticas (encima de todo)

Tabla `regla_envio` (CRUD mínimo en panel) evaluada primero:

- Campos: `tipo`, `k_categoria`, `cantidad_min`, `total_min`, `costo` (0 = gratis), `orden`, `activo`.
- Tipos:
  - `SOLO_CATEGORIA`: el pedido contiene **exclusivamente** esa categoría → `costo` (ej.: solo vinilos → 0).
  - `CANTIDAD_CATEGORIA`: hay `cantidad_min`+ unidades de la categoría → `costo` (ej.: 4 o más CDs → 0; min=1 = "con 1+ vinilos, gratis").
  - `TOTAL_MIN`: subtotal ≥ `total_min` → `costo`.
  - `SIEMPRE`: siempre → `costo` (paraguas global).
- La primera que aplique (por `orden`) gana; su detalle queda registrado ("Regla: 4 o más CDs → envío gratis").

### D. El costo vive en la orden

Columnas nuevas en `Invoice` (aditivas, default 0/null):

- `p_envio` (Numeric(11,2), default 0) — lo que se cobra.
- `d_envio` (String(100)) — qué se aplicó: "Envía Normal: $14.696 (2 días)", "Regla: solo vinilos", "Manual (admin)", "Tarifa: nacional".
- `envio_manual` (bool) — el admin lo tocó.
- `envio_id_rate` (String(30)) + `envio_carrier` (String(30)) — `idRate` y carrier elegidos, listos para `/shipment` en fase 2.

Flujos:

- **Checkout público**: al elegir municipio (y con el carrito) se pinta "Envío: $X · ~N días (carrier) · se confirma al pagar" (debounce + cache). Al crear el pedido, `p_envio` = recálculo servidor. La orden muestra `Productos / Envío / Total`.
- **MercadoPago**: `amount = total + p_envio` (único cambio de comportamiento; neutro con `p_envio = 0`).
- **Cotización (énfasis)**:
  - El modal del admin muestra: subtotal de ítems + "Envío (cotejado a <municipio>): $Y · ~N días" (y las 3 ofertas como referencia si el dueño quiere comparar) + total. Si la solicitud no trae municipio, el admin lo elige ahí.
  - El mensaje de WhatsApp incluye: "Total productos: $X · **Envío estimado: $Y** (se confirma en tu enlace)".
  - En `confirmar` el cliente ya ve el envío con su municipio; `crear_pedido` guarda `p_envio` (recalculado; desde cache si aplica).
- **Panel de órdenes**: campo "Envío" con el sugerido automático ("auto: $X — <detalle>") y botón **Aplicar**; el admin puede escribir otro valor (incluido 0 = gratis) → manual. Editable hasta que el pedido pasa a ENVIADO.

### E. Configuración

- `.env`: ya hay `ENVIOCLICK_TOKEN` (nada más por ahora).
- `configuracion`: `envio.habilitado` (switch general; en `false` no se muestra ni cobra nada), `envio.criterio` (menor precio / menor tiempo), `envio.zona_bogota`, `envio.zona_nacional` (fallback), dimensiones de caja por defecto. Formulario "Envíos" en el panel.

## Aditivo vs. rompedor

| Cambio | Tipo |
|---|---|
| `mbAutocomplete` estricto + "Otro municipio" | Aditivo |
| `peso_gramos` en `Producto`/`Variante` | Aditivo (sin peso = fallback zona) |
| Columnas `p_envio`, `d_envio`, `envio_manual`, `envio_id_rate`, `envio_carrier` en `Invoice` | Aditivas, defaults neutros |
| Tablas `ubicacion`, `regla_envio`, `cotizacion_cache` + claves `envio.*` | Aditivas |
| Campo municipio opcional en `/solicitud/` | Aditivo |
| `amount` de MP = `total + p_envio` | Comportamiento; neutro mientras `p_envio = 0` |
| Llamada a EnvíoClick (gratis) con cache + fallback | No bloquea nada |

**No rompe nada**: con `envio.habilitado=false` el sitio se comporta igual que hoy. Una migración aditiva (5 columnas + 3 tablas) revisada a mano + respaldo antes del `db upgrade`.

## Preguntas para el dueño (restan poquitas)

1. **Criterio por defecto**: ¿menor costo (gana Envía en la prueba) o menor tiempo (gana Coordinadora, 1 día)? (Es configurable en `envio.criterio`.)
2. "Vinilos no tienen costo": ¿solo pedido *exclusivo* de vinilos, o con 1+ vinilo? (`SOLO_CATEGORIA` vs `CANTIDAD_CATEGORIA` min=1.)
3. ¿Reglas editables **en el panel** (CRUD mínimo) o las creo yo en BD/código para v1?
4. **Tarifas fallback por zona** (solo si la API falla): Bogotá $___ / resto $___ (o una sola).
5. ¿Municipio opcional en `/solicitud/` público? (Proyecto: sí.)
6. ¿El admin puede corregir `p_envio` tras el pago? (Proyecto: hasta que pase a ENVIADO; el cambio no afecta el cobro ya hecho en MP.)
7. **Fase 2 (fuera de esta feature)**: `/shipment` = generar guía al pasar a ENVIADO (cobra del monedero de EnvíoClick) + tracking en `/pedido/<token>`. ¿Se anota para después?

## Pasos propuestos (v1)

1. Rama `feature/costo-envio` desde `main`.
2. Migración aditiva: columnas de `Invoice` + `ubicacion` + `regla_envio` + `cotizacion_cache` + `peso_gramos` + respaldo + `db upgrade`.
3. `sincronizar-ubicaciones` (desde `/locate` de Envía, gratis y sin token) + mapeo de Bogotá localities → `11001000`.
4. `app/store/envio.py`: reglas + cliente EnvíoClick (UA de navegador, cache, criterio) + fallback por zona.
5. `mbAutocomplete` estricto + "Otro municipio"; validación backend; campo opcional en `/solicitud/`.
6. Peso por producto/variante en "Editar producto" + caja por defecto.
7. Checkout: estimado en vivo + `p_envio` en `crear_pedido` + `amount` de MP con envío.
8. Cotización: cotejo (con las 3 ofertas de referencia) en el modal del admin, línea en el WhatsApp, recálculo en `confirmar`.
9. Panel de órdenes: sugerido + "Aplicar" manual + bloqueo tras ENVIADO; CRUD de reglas; formulario "Envíos".
10. Verificación rápida en :5010 (pedido de prueba + captura del panel) → "estamos" → commit + push → sugerir merge a `main`.

## Alternativas documentadas (por si a la vez)

- **MiPaquete** (verificado en vivo 2026-10-02, dev): `POST /quoteShipping` país `170` + DANE 8 dígitos; key por `generateapikey` (JWT sin expiración). Bogotá→Medellín 1 kg: TCC $10.400/2d, Coordinadora $16.696/4d, Servientrega $19.488/4d.
- **Skydropx** (`api.skydropx.com.co` + `help.skydropx.com.co`): token vía plataforma; rate válido 24 h; prepago por créditos; backend 502 el 2026-10-03.
- **Envía** (`docs.envia.com`): sandbox gratis self-service; `/ship/rate/` multi-carrier; `/locate` gratis sin token (el mismo que usamos para llenar `ubicacion`).
- **Tarifa por zona propia**: el fallback que cubre si todo externo se cae.

## Evidencia de la verificación

- EnvíoClick con key del dueño: script `Temp\opencode\envioclick_cotizar2.py`, respuesta completa en `envioclick_quote.json` (HTTP 200, 3 rates).
- Contrato extraído de `apidoc.envioclickpro.com.co` (`api_data.js`/`api_project.js` en `Temp\opencode\envioclick_*`).
- `/locate` de Envía sin token: `Medellin/AN/CO` → `05001000` (sandbox y producción).
- MiPaquete/Skydropx: ver "Alternativas" y `Temp\opencode\mp_cotizar*.ps1`, `skydropx_api.yaml`.
