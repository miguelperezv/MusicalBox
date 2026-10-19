from flask import Blueprint, abort, current_app, jsonify, request, url_for
from app.db import db
import hashlib
import hmac
import time
import mercadopago
from mercadopago import config as mp_config
from ..models import Invoice, confirmar_pago, rechazar_pago
from ..notificaciones import correo_pedido_pagado
from ..notif_admin import (aviso_pago_aprobado, aviso_pago_rechazado,
                           aviso_pago_de_otro_monto, aviso_pago_no_creado)
from ..analytics import track_event, Events

mercadopago_bp = Blueprint('mercadopago', __name__, url_prefix='/mercadopago')

def get_client_ip():
    """Obtiene la IP real del cliente, considerando proxies/reverse proxies"""
    # Si hay proxy/reverse proxy, X-Forwarded-For suele venir con "ip, proxy1, proxy2"
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr

def get_invoice_by_token(token_hash):
    """Busca un invoice por su token_hash"""
    return Invoice.query.filter_by(token_hash=token_hash).first()

def hash_token(token):
    """Calcula el hash SHA-256 del token, igual que en models.py"""
    return hashlib.sha256(token.encode()).hexdigest()


def _build_callback_url(token_plano):
    """URL a la que el banco devuelve al comprador (PSE).
    Usa PUBLIC_BASE_URL si está configurado (túnel), si no usa url_for normal."""
    base = current_app.config.get("PUBLIC_BASE_URL", "").rstrip("/")
    if base:
        return f"{base}/pedido/{token_plano}"
    return url_for('pedido.ver', token=token_plano, _external=True)


def _url_webhook():
    """URL pública del webhook de MercadoPago que se manda en cada pago."""
    base = current_app.config.get("PUBLIC_BASE_URL", "").rstrip("/")
    if base:
        return f"{base}/mercadopago/webhook"
    return url_for('mercadopago.webhook', _external=True)


def get_mp_sdk():
    return mercadopago.SDK(current_app.config["MERCADOPAGO_ACCESS_TOKEN"])

def monto_pedido(inv):
    #lo que se cobra en la pasarela: el total de la orden + el costo de envío calculado al crearla
    return float((inv.total or 0) + (inv.p_envio or 0))


def _monto_coincide(pago, inv):
    """¿El pago es por el monto del pedido (total + envío)? Devuelve (ok, monto_pagado).

    Si MercadoPago no informa el monto no se bloquea el pago (queda registrado): el monto que se
    cobra sale siempre del pedido en la BD, nunca del navegador, así que no hay nada que falsificar.
    Solo se rechaza cuando viene un monto distinto."""
    bruto = pago.get("transaction_amount")
    if bruto is None:
        current_app.logger.warning("[MP] MercadoPago no informó el monto del pago")
        return True, None
    monto = int(round(float(bruto)))
    return monto == int(round(monto_pedido(inv))), monto

@mercadopago_bp.route("/create_preference/<token>", methods=["POST"])
def create_preference(token):
    """
    Payment Brick NO necesita preferenceId.
    Este endpoint solo devuelve contexto del pedido.
    """
    current_app.logger.info(f"[MP] Solicitud create_preference para token: {token}")
    
    # Calcular el hash del token para buscar en la BD
    token_hash = hash_token(token)
    current_app.logger.info(f"[MP] Buscando invoice con token_hash: {token_hash}")
    
    # Buscar invoice por token_hash
    inv = Invoice.query.filter_by(token_hash=token_hash).first()
    
    if not inv:
        # Log detallado de todos los invoices para debugging
        all_invoices = Invoice.query.all()
        current_app.logger.info(f"[MP] No se encontró invoice. Total invoices en BD: {len(all_invoices)}")
        for i, invoice in enumerate(all_invoices[-5:]):  # Solo los últimos 5
            current_app.logger.info(f"[MP] Invoice {invoice.id}: token_hash={invoice.token_hash[:10] if invoice.token_hash else 'None'}..., estado={invoice.estado}")
        
        current_app.logger.warning(f"[MP] Pedido no encontrado para token_hash: {token_hash}")
        return jsonify({"error": "Pedido no encontrado"}), 404
    
    current_app.logger.info(f"[MP] Pedido encontrado: {inv.id}, estado: {inv.estado}")
    
    if inv.estado != "PENDIENTE":
        current_app.logger.warning(f"[MP] Pedido {inv.id} no está en estado PENDIENTE: {inv.estado}")
        return jsonify({"error": "El pedido no está en estado PENDIENTE"}), 409
    
    current_app.logger.info(f"[MP] Devolviendo contexto para pedido {inv.id}: amount={monto_pedido(inv)}, email={inv.email_envio}")
    
    return jsonify({
        "token_hash": inv.token_hash,
        "amount": monto_pedido(inv),
        "payer_email": inv.email_envio,
    }), 200

@mercadopago_bp.route("/process_payment", methods=["POST"])
def process_payment():
    """Crea el pago en MercadoPago (tarjeta o PSE).

    Del navegador solo se aceptan los datos del medio de pago: el monto y la referencia salen
    siempre del pedido en la BD (`monto_pedido`), así nadie puede pagar menos ni apuntar a otro pedido.
    """
    payload = request.get_json(silent=True) or {}

    if not isinstance(payload, dict):
        current_app.logger.error("[MP] el body no es un JSON objeto")
        return jsonify({"error": "El body debe ser un JSON objeto"}), 400

    # El frontend envía el token original del pedido como token_hash (no confundir con el token de tarjeta)
    token_pedido = payload.get("token_hash")
    if not token_pedido:
        current_app.logger.error("[MP] falta token en el payload")
        return jsonify({"error": "Falta token"}), 400

    inv = get_invoice_by_token(hash_token(token_pedido))
    if not inv:
        current_app.logger.warning("[MP] pedido no encontrado para el token recibido")
        return jsonify({"error": "Pedido no encontrado"}), 404

    current_app.logger.info("[MP] pedido %s (%s) · medio %s · total %s + envío %s",
                            inv.id, inv.estado, payload.get("payment_method_id"),
                            inv.total, inv.p_envio)
    if inv.estado != "PENDIENTE":
        current_app.logger.warning("[MP] el pedido %s no está PENDIENTE: %s", inv.id, inv.estado)
        return jsonify({"error": "El pedido no está en estado PENDIENTE"}), 409

    # Seguridad: monto desde la BD (no confiar en el frontend)
    payer_email = inv.email_envio
    if not payer_email:
        current_app.logger.error("[MP] el pedido %s no tiene email_envio", inv.id)
        return jsonify({"error": "El pedido no tiene email_envio"}), 400

    # Validación por tipo de pago
    payment_method_id = payload.get("payment_method_id")
    
    # ===== PSE: REUTILIZAR PAGO PENDIENTE SI EXISTE =====
    if payment_method_id == "pse" and inv.mp_payment_id:
        current_app.logger.info(f"[MP] PSE: Verificando pago existente {inv.mp_payment_id}")
        # Consultar estado del pago en MercadoPago
        sdk = get_mp_sdk()
        mp_resp = sdk.payment().get(inv.mp_payment_id)
        if mp_resp.get("status") == 200:
            mp_body = mp_resp.get("response", {})
            mp_status = mp_body.get("status")
            current_app.logger.info(f"[MP] Estado pago existente: {mp_status}")
            if mp_status in ("pending", "in_process"):
                # Pago pendiente: reutilizar, devolver URL existente
                external_url = mp_body.get("transaction_details", {}).get("external_resource_url") or inv.mp_external_resource_url
                if external_url:
                    current_app.logger.info(f"[MP] Reutilizando pago pendiente {inv.mp_payment_id}, redirect: {external_url}")
                    return jsonify({
                        "mp_status": 200,
                        "mp_response": mp_body,
                        "redirect_url": external_url,
                        "reused": True
                    }), 200
                # Si no hay URL, seguir para crear uno nuevo
            elif mp_status == "approved":
                # Ya pagado: se confirma solo si el monto es el del pedido (igual que en el webhook)
                ok, monto = _monto_coincide(mp_body, inv)
                if not ok:
                    current_app.logger.warning("[MP] pago %s con monto distinto al del pedido %s: %s vs %s",
                                               inv.mp_payment_id, inv.id, monto, monto_pedido(inv))
                    return jsonify({"error": "El monto no coincide con el pedido"}), 409
                current_app.logger.info("[MP] pago ya aprobado, confirmando el pedido %s", inv.id)
                inv.mp_payment_id = str(mp_body.get("id") or "")
                p, nuevo = confirmar_pago(inv, inv.mp_payment_id, inv.mp_payment_id, "pse")
                if nuevo:
                    try:
                        correo_pedido_pagado(p, token_pedido)
                    except Exception as e:
                        current_app.logger.exception(f"[MP] Fallo envío de email para pedido {inv.id}: {e}")
                    aviso_pago_aprobado(p, token_pedido)
                return jsonify({"mp_status": 200, "mp_response": mp_body, "approved": True}), 200
            elif mp_status in ("rejected", "cancelled", "expired"):
                # Pago fallido: limpiar para crear uno nuevo
                current_app.logger.info(f"[MP] Pago previo {mp_status}, creando uno nuevo")
                inv.mp_payment_id = None
                inv.mp_external_resource_url = None
                db.session.commit()
        else:
            current_app.logger.warning(f"[MP] Error consultando pago existente: {mp_resp}")
    # ===== FIN REUTILIZACIÓN PSE =====
    
    # Detectar si es PSE
    if payment_method_id == "pse":
        # PSE (Avanza) no usa token: se arma con los datos del pedido y los que manda el Brick
        current_app.logger.info("[MP] procesando pago PSE (Avanza)")
        ip = get_client_ip()
        if not ip:
            current_app.logger.error("[MP] no se pudo detectar la IP del comprador para PSE")
            return jsonify({"error": "No se pudo detectar la IP del comprador"}), 400

        pse_payer = payload.get("payer") or {}
        ident = pse_payer.get("identification") or {}
        id_type, id_number = ident.get("type"), ident.get("number")
        if not id_type or not id_number:
            current_app.logger.error("[MP] faltan payer.identification.type/number para PSE")
            return jsonify({"error": "Falta payer.identification.type/number para PSE"}), 400

        # El banco lo elige el comprador en el Brick: viaja en transaction_details.financial_institution.
        # MercadoPago lo exige anidado (en la raíz responde 400 "the name of the parameters is wrong").
        financial_institution = ((payload.get("transaction_details") or {}).get("financial_institution")
                                 or payload.get("financial_institution")
                                 or pse_payer.get("financial_institution"))
        if not financial_institution:
            current_app.logger.error("[MP] el comprador no eligió banco para PSE")
            return jsonify({"error": "Falta elegir el banco para pagar con PSE"}), 400
        
        # nombre y apellido del pedido (PSE pide entre 1 y 32 caracteres en cada uno)
        partes = (inv.n_envio or "Cliente MusicalBox").strip().split(" ", 1)
        first_name = (partes[0] or "Cliente")[:32]
        last_name = (partes[1] if len(partes) > 1 else "MusicalBox")[:32]

        # teléfono: 3 dígitos de área + hasta 7 del número, como los valida PSE
        digitos = "".join(c for c in (inv.tel_envio or "") if c.isdigit()) or "3000000000"
        area_code = digitos[:3].ljust(3, "0")
        number = (digitos[3:10] or "0000000").ljust(7, "0")

        # Campos que exige PSE; el monto y la referencia salen del pedido en la BD, no del navegador
        payment_data = {
            "transaction_amount": monto_pedido(inv),
            "payment_method_id": "pse",
            "description": f"Musical Box - Pedido {inv.token_hash}",
            "external_reference": inv.token_hash,
            "payer": {
                "email": payer_email,
                "entity_type": "individual",
                "first_name": first_name,
                "last_name": last_name,
                "identification": {"type": id_type, "number": str(id_number)},
                # PSE exige la dirección del pagador (el zip code, exactamente 5 dígitos)
                "address": {
                    "zip_code": "110111",
                    "street_name": (inv.dir_envio or "Calle desconocida")[:18],
                    "street_number": "S/N",
                    "neighborhood": (inv.barrio_envio or "Sin barrio")[:18],
                    "city": (inv.lugar_envio or "Bogotá")[:18],
                },
                "phone": {"area_code": area_code, "number": number},
            },
            "additional_info": {"ip_address": ip},
            "transaction_details": {"financial_institution": str(financial_institution)},
        }
        # el comprador vuelve aquí desde el banco (callback) y MercadoPago avisa al webhook
        payment_data["callback_url"] = _build_callback_url(token_pedido)
        payment_data["notification_url"] = _url_webhook()

        current_app.logger.info("[MP] datos PSE preparados · banco %s · monto %s",
                                financial_institution, payment_data["transaction_amount"])

    elif payload.get("token"):
        # Flujo tarjeta/débito/crédito
        token = payload.get("token")
        payment_method_id = payload.get("payment_method_id")
        installments = int(payload.get("installments", 1))
        issuer_id = payload.get("issuer_id")

        if not token or not payment_method_id:
            current_app.logger.error("[MP] faltan campos requeridos (token / payment_method_id)")
            return jsonify({"error": "Faltan campos requeridos (token / payment_method_id)"}), 400

        payment_data = {
            "token": token,
            "transaction_amount": monto_pedido(inv),  # Usar siempre el monto de la BD por seguridad
            "installments": installments,
            "payment_method_id": payment_method_id,
            "payer": {"email": payer_email},
            "external_reference": inv.token_hash,
            "description": f"Musical Box - Pedido {inv.token_hash}",
        }
        if issuer_id:
            payment_data["issuer_id"] = int(issuer_id)

        current_app.logger.info("[MP] datos de tarjeta preparados · %s · %s cuota(s) · monto %s",
                                payment_method_id, installments, payment_data["transaction_amount"])
    else:
        # Otros medios de pago (wallet, ticket, etc.)
        current_app.logger.info("[MP] procesando pago con otro medio: %s",
                                [k for k in payload if k not in ("token_hash", "payer")])
        # Usar los campos que vienen en el payload, pero asegurar los mínimos requeridos
        payment_data = {
            "transaction_amount": monto_pedido(inv),  # Usar siempre el monto de la BD por seguridad
            "payer": {"email": payer_email},
            "external_reference": inv.token_hash,
            "description": f"Musical Box - Pedido {inv.token_hash}",
        }
        
        # Agregar campos del payload, menos los que manda el pedido en la BD: así nadie puede
        # pagar menos ni apuntar el pago a otro pedido desde el navegador
        reservados = {"token_hash", "intento", "transaction_amount", "external_reference", "description"}
        for key, value in payload.items():
            if key not in reservados and value is not None:
                payment_data[key] = value

        current_app.logger.info("[MP] datos de otro medio preparados · %s · monto %s",
                                payment_method_id, payment_data["transaction_amount"])

    # Idempotencia: clave ESTABLE por intento de pago (no UUID aleatorio)
    # Usamos hash del token + método de pago + contador de intentos para permitir reintentos legítimos
    # pero evitar duplicados por reenvío de request del frontend
    intento_num = payload.get("intento", 1)
    idem_base = f"{inv.token_hash}_{payment_method_id}_attempt{intento_num}"
    idempotency_key = hashlib.sha256(idem_base.encode()).hexdigest()[:32]
    request_options = mp_config.RequestOptions()
    request_options.custom_headers = {"X-Idempotency-Key": idempotency_key}
    # PSE en sandbox requiere x-test-token
    if payment_method_id == "pse" and current_app.config.get("SIMULACION_PAGO"):
        request_options.custom_headers["x-test-token"] = "true"
    
    # Track checkout start
    track_event(Events.CHECKOUT_START, {
        'pedido_id': inv.id,
        'amount': monto_pedido(inv),
        'payment_method': payment_method_id,
        'token_hash': inv.token_hash
    })
    
    sdk = get_mp_sdk()

    # Reintentos para los errores transitorios de MercadoPago (424 en PSE, 500 internal_error)
    max_retries = 3
    retry_delay = 1  # segundos; se duplica en cada intento

    mp_http_status, mp_body = 500, {}
    for attempt in range(max_retries):
        try:
            mp_resp = sdk.payment().create(payment_data, request_options)
        except Exception as e:
            current_app.logger.error("[MP] error de conexión en el intento %s: %s", attempt + 1, e)
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            aviso_pago_no_creado(inv, f"No se pudo hablar con MercadoPago: {e}", token_pedido)
            return jsonify({
                "error": "No pudimos conectar con MercadoPago. Intenta de nuevo en unos minutos."
            }), 500

        mp_http_status = mp_resp.get("status", 500)
        mp_body = mp_resp.get("response", {}) or {}
        current_app.logger.info("[MP] intento %s · HTTP %s · pago %s · %s (%s)",
                                attempt + 1, mp_http_status, mp_body.get("id"),
                                mp_body.get("status"), mp_body.get("status_detail"))

        # 424 (BankTransfers Api fail) y 500 (internal_error) suelen ser transitorios: se reintenta
        if mp_http_status in (424, 500) and attempt < max_retries - 1:
            current_app.logger.warning("[MP] HTTP %s en el intento %s · cause %s",
                                       mp_http_status, attempt + 1, str(mp_body.get("cause"))[:200])
            time.sleep(retry_delay)
            retry_delay *= 2
            continue
        break

    # Confirmación: confirmar_pago() es idempotente y completa el pedido de un solo paso
    # (estado_envio POR PREPARAR, solicitud→COMPRADA, liberar reservas y stock)
    if mp_body.get("status") == "approved":
        ok, monto = _monto_coincide(mp_body, inv)
        if not ok:
            current_app.logger.warning("[MP] pago %s del pedido %s con monto distinto: %s vs %s",
                                       mp_body.get("id"), inv.id, monto, monto_pedido(inv))
            return jsonify({"error": "El monto no coincide con el pedido"}), 409
        inv.mp_payment_id = str(mp_body.get("id") or "")
        p, nuevo = confirmar_pago(inv, inv.mp_payment_id, inv.mp_payment_id, payment_method_id)
        if nuevo:
            try:
                #el payload manda el token plano como "token_hash": es el que va en el enlace del correo
                correo_pedido_pagado(p, token_pedido)
            except Exception as e:
                current_app.logger.exception("[MP] falló el correo del pedido %s: %s", inv.id, e)
            aviso_pago_aprobado(p, token_pedido)
            current_app.logger.info("[MP] pedido %s confirmado, stock y solicitud actualizados", inv.id)
        # Track purchase
        track_event(Events.PURCHASE, {
            'pedido_id': inv.id,
            'payment_id': mp_body.get("id"),
            'amount': monto_pedido(inv),
            'payment_method': payment_method_id,
            'token_hash': inv.token_hash
        })
    elif mp_body.get("status") == "rejected":
        current_app.logger.info("[MP] pago rechazado para el pedido %s: %s", inv.id, mp_body.get("status_detail"))
        rechazar_pago(inv, str(mp_body.get("id") or ""))
        aviso_pago_rechazado(inv, token_pedido)
    elif mp_http_status == 424:
        # Error específico de BankTransfers Api fail: el pedido queda PENDIENTE para reintentar
        current_app.logger.error("[MP] error 424 (BankTransfers Api fail) en el pedido %s · %s",
                                 inv.id, str(mp_body.get("cause"))[:200])
        aviso_pago_no_creado(inv, "MercadoPago no pudo iniciar el pago PSE (error 424 · BankTransfers Api fail)", token_pedido)
        return jsonify({
            "error": "No pudimos iniciar el pago con PSE. Intenta de nuevo en unos minutos o paga con tarjeta.",
            "mp_status": mp_http_status,
            "mp_response": mp_body,
            "retryable": True
        }), 424
    elif mp_http_status == 500:
        # Error interno de MercadoPago (común en sandbox)
        current_app.logger.error("[MP] error 500 (internal_error) en el pedido %s · %s",
                                 inv.id, str(mp_body.get("cause"))[:200])
        aviso_pago_no_creado(inv, "MercadoPago devolvió un error interno (500)", token_pedido)
        return jsonify({
            "error": "MercadoPago está fallando ahora mismo. Intenta de nuevo en unos minutos.",
            "mp_status": mp_http_status,
            "mp_response": mp_body,
            "retryable": True
        }), 500
    elif payment_method_id == "pse" and mp_body.get("status") in ("in_process", "pending"):
        # Para PSE el banco confirma después: se guarda el pago para reutilizar el mismo al volver
        external_url = (mp_body.get("transaction_details") or {}).get("external_resource_url")
        payment_id = str(mp_body.get("id") or "")
        current_app.logger.info("[MP-PSE] pedido %s en %s · pago %s · banco %s · con URL: %s",
                                inv.id, mp_body.get("status"), payment_id,
                                (mp_body.get("transaction_details") or {}).get("financial_institution"),
                                bool(external_url))
        if payment_id:
            inv.mp_payment_id = payment_id
            if external_url:
                inv.mp_external_resource_url = external_url
            db.session.commit()
        # Track PSE redirect
        track_event(Events.PSE_REDIRECT, {
            'pedido_id': inv.id,
            'payment_id': payment_id,
            'amount': monto_pedido(inv),
            'bank': (mp_body.get("transaction_details") or {}).get("financial_institution"),
            'token_hash': inv.token_hash
        })
    elif payment_method_id == "pse":
        current_app.logger.info("[MP-PSE] pedido %s quedó en %s (no in_process/pending)",
                                inv.id, mp_body.get("status"))

    current_app.logger.info("[MP] fin · pedido %s · HTTP %s · %s", inv.id, mp_http_status, mp_body.get("status"))
    resp = {
        "mp_status": mp_http_status,
        "mp_response": mp_body,
    }
    # Para PSE in_process/pending, incluir URL de redirección al banco
    if payment_method_id == "pse" and mp_body.get("status") in ("in_process", "pending"):
        external_url = (mp_body.get("transaction_details") or {}).get("external_resource_url")
        if external_url:
            resp["redirect_url"] = external_url
    return jsonify(resp), mp_http_status


def _firma_ok(data):
    """Valida la firma del webhook cuando MP_WEBHOOK_SECRET está configurado.

    Esquema de MercadoPago: la cabecera x-signature trae ts=<ts>,v1=<hmac>; el manifiesto
    es 'id:<data.id>;request-id:<x-request-id>;ts:<ts>;' firmado con HMAC-SHA256 y la clave
    secreta (Panel de MercadoPago > Webhooks)."""
    secreto = (current_app.config.get("MP_WEBHOOK_SECRET") or "").strip()
    if not secreto:
        return True  #sin clave no hay nada que comparar: el candado real es consultar el pago en la API
    partes = dict(p.split("=", 1) for p in (request.headers.get("x-signature") or "").split(",") if "=" in p)
    ts, v1 = partes.get("ts"), partes.get("v1")
    if not ts or not v1:
        return False
    data_id = str((data.get("data") or {}).get("id") or "").lower()
    manifiesto = f"id:{data_id};request-id:{request.headers.get('x-request-id', '')};ts:{ts};"
    calculado = hmac.new(secreto.encode(), manifiesto.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calculado, v1)


@mercadopago_bp.route("/webhook", methods=["POST"])
def webhook():
    """Notificación de MercadoPago.

    Nunca se confía en el cuerpo: con el id se consulta el pago en la API de MP (que responde
    solo por los pagos de esta cuenta) y recién ahí se confirma por el camino único e idempotente.
    Si MP_WEBHOOK_SECRET está configurado, además se exige la firma.
    """
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or "type" not in data:
            current_app.logger.warning("[MP-WEBHOOK] notificación inválida: %s", str(data)[:200])
            return jsonify({"status": "invalid"}), 400
        if not _firma_ok(data):
            current_app.logger.warning("[MP-WEBHOOK] firma inválida · tipo=%s · id=%s",
                                       data.get("type"), (data.get("data") or {}).get("id"))
            return jsonify({"error": "Firma inválida"}), 401
        tipo = data.get("type")
        current_app.logger.info("[MP-WEBHOOK] %s · id=%s", tipo, (data.get("data") or {}).get("id"))
        if tipo == "payment":
            return process_payment_notification(data)
        if tipo == "merchant_order":
            return process_merchant_order_notification(data)
        current_app.logger.info("[MP-WEBHOOK] tipo no manejado: %s", tipo)
        return jsonify({"status": "not_handled"}), 200
    except Exception as e:
        #5xx: MercadoPago reintenta la notificación más tarde
        current_app.logger.exception("[MP-WEBHOOK] error procesando la notificación: %s", e)
        return jsonify({"error": "Error interno"}), 500


def process_payment_notification(data):
    """Procesa una notificación de pago ya verificada."""
    try:
        payment_id = (data.get("data") or {}).get("id")
        if not payment_id:
            current_app.logger.warning("[MP-WEBHOOK] notificación sin id de pago")
            return jsonify({"error": "ID de pago no encontrado"}), 400

        # Los datos del pago se piden a la API de MercadoPago (nunca se confía en quien llama)
        sdk = get_mp_sdk()
        payment = (sdk.payment().get(payment_id) or {}).get("response") or {}
        if not payment:
            current_app.logger.warning("[MP-WEBHOOK] la API no devolvió el pago %s", payment_id)
            return jsonify({"error": "No se pudieron obtener detalles del pago"}), 400

        external_reference = payment.get("external_reference")
        inv = get_invoice_by_token(external_reference) if external_reference else None
        if not inv:
            current_app.logger.warning("[MP-WEBHOOK] pago %s sin pedido para la referencia %r",
                                       payment_id, external_reference)
            return jsonify({"error": "Pedido no encontrado"}), 404

        payment_status = payment.get("status")
        payment_method_id = payment.get("payment_method_id")
        current_app.logger.info("[MP-WEBHOOK] pago %s · pedido %s (%s) · estado %s · medio %s · monto %s",
                                payment_id, inv.id, inv.estado, payment_status, payment_method_id,
                                payment.get("transaction_amount"))

        if payment_status == "approved" and inv.estado == "PENDIENTE":
            #el pago tiene que ser por el monto que se cobró (total + envío): si no cuadra no se
            #confirma nada, se avisa al admin y se responde 200 (reintentar no lo va a arreglar)
            ok, monto = _monto_coincide(payment, inv)
            if not ok:
                current_app.logger.warning("[MP-WEBHOOK] monto distinto en el pedido %s: pagó %s y vale %s",
                                           inv.id, monto, monto_pedido(inv))
                try:
                    aviso_pago_de_otro_monto(inv, monto, monto_pedido(inv))
                except Exception:
                    current_app.logger.exception("[MP-WEBHOOK] no se pudo avisar el monto distinto")
                return jsonify({"status": "monto_incorrecto"}), 200
            # Pago aprobado: confirmar por el camino único idempotente
            inv.mp_payment_id = str(payment.get("id", ""))
            p, nuevo = confirmar_pago(inv, inv.mp_payment_id, inv.mp_payment_id, payment_method_id)
            if nuevo:
                try:
                    #aquí solo hay el hash del token: el enlace del correo puede no resolver (caso PSE tardío)
                    correo_pedido_pagado(p, p.token_hash)
                except Exception as e:
                    current_app.logger.exception("[MP-WEBHOOK] falló el correo del pedido %s: %s", inv.id, e)
                aviso_pago_aprobado(p, p.token_hash)
                current_app.logger.info("[MP-WEBHOOK] pedido %s confirmado", inv.id)
            else:
                current_app.logger.info("[MP-WEBHOOK] pedido %s ya estaba confirmado", inv.id)
            return jsonify({"status": "processed"}), 200

        if payment_status in ("rejected", "cancelled", "refunded"):
            if inv.estado == "PENDIENTE":
                inv.mp_payment_id = str(payment.get("id", ""))
                rechazar_pago(inv, inv.mp_payment_id)
                aviso_pago_rechazado(inv, inv.token_hash)
                current_app.logger.info("[MP-WEBHOOK] pedido %s marcado como rechazado", inv.id)
                return jsonify({"status": "processed"}), 200
            current_app.logger.info("[MP-WEBHOOK] pedido %s ya estaba en %s", inv.id, inv.estado)
            return jsonify({"status": "already_processed"}), 200

        if payment_status in ("in_process", "pending"):
            #típico de PSE: la confirmación llega después con otra notificación
            current_app.logger.info("[MP-WEBHOOK] pago %s en proceso para el pedido %s (%s)",
                                    payment_id, inv.id, payment.get("status_detail"))
            return jsonify({"status": "processing"}), 200

        current_app.logger.info("[MP-WEBHOOK] estado no manejado: %s (pedido %s en %s)",
                                payment_status, inv.id, inv.estado)
        return jsonify({"status": "not_handled"}), 200

    except Exception as e:
        #5xx: MercadoPago reintenta la notificación más tarde
        current_app.logger.exception("[MP-WEBHOOK] error procesando el pago: %s", e)
        return jsonify({"error": "Error interno"}), 500

def process_merchant_order_notification(data):
    """Procesar notificación de orden de merchant"""
    current_app.logger.info("[MP-WEBHOOK] Procesando notificación de orden de merchant")
    # Implementar si se necesita manejar órdenes de merchant
    return jsonify({"status": "received"}), 200


@mercadopago_bp.route("/webhook-test", methods=["POST"])
def webhook_test():
    """Endpoint para pruebas de webhook: solo existe con SIMULACION_PAGO (desarrollo)."""
    if not current_app.config.get("SIMULACION_PAGO"):
        abort(404)
    data = request.get_json(silent=True)
    current_app.logger.info("[MP-WEBHOOK-TEST] notificación de prueba: %s", data)
    return jsonify({"status": "test_received"}), 200
