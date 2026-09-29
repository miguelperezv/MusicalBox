from flask import Blueprint, current_app, jsonify, request, url_for
import uuid
import hashlib
import mercadopago
from mercadopago import config as mp_config
from ..models import Invoice, Item, Producto, Variante
from ...db import db
from ..notificaciones import correo_pedido_pagado
from ..pedidos import discount_stock

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

def get_mp_sdk():
    return mercadopago.SDK(current_app.config["MERCADOPAGO_ACCESS_TOKEN"])

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
    
    current_app.logger.info(f"[MP] Devolviendo contexto para pedido {inv.id}: amount={float(inv.total)}, email={inv.email_envio}")
    
    return jsonify({
        "token_hash": inv.token_hash,
        "amount": float(inv.total),
        "payer_email": inv.email_envio,
    }), 200

@mercadopago_bp.route("/process_payment", methods=["POST"])
def process_payment():
    current_app.logger.info("[MP] === INICIO PROCESS_PAYMENT ===")
    current_app.logger.info(f"[MP] Headers recibidos: {dict(request.headers)}")
    current_app.logger.info(f"[MP] Remote address: {request.remote_addr}")
    
    payload = request.get_json(silent=True) or {}
    current_app.logger.info(f"[MP] Payload recibido: {payload}")
    
    if not isinstance(payload, dict):
        current_app.logger.error("[MP] El body no es un JSON objeto válido")
        return jsonify({"error": "El body debe ser un JSON objeto"}), 400
    
    token = payload.get("token_hash")  # El frontend envía el token original como token_hash
    current_app.logger.info(f"[MP] Token recibido: {token}")
    
    if not token:
        current_app.logger.error("[MP] Falta token en el payload")
        return jsonify({"error": "Falta token"}), 400
    
    # Hashear el token para buscar en la BD (igual que en create_preference)
    token_hash = hash_token(token)
    current_app.logger.info(f"[MP] Token hash calculado: {token_hash}")
    
    inv = get_invoice_by_token(token_hash)
    if not inv:
        current_app.logger.warning(f"[MP] Pedido no encontrado para token_hash: {token_hash}")
        # Log detallado para debugging
        all_invoices = Invoice.query.all()
        current_app.logger.info(f"[MP] Total de invoices en BD: {len(all_invoices)}")
        for i, invoice in enumerate(all_invoices[-10:]):  # Últimos 10
            current_app.logger.info(f"[MP] Invoice {invoice.id}: hash={invoice.token_hash[:20] if invoice.token_hash else 'None'}, estado={invoice.estado}")
        return jsonify({"error": "Pedido no encontrado"}), 404
    
    current_app.logger.info(f"[MP] Pedido encontrado: {inv.id}, estado: {inv.estado}")
    current_app.logger.info(f"[MP] Datos del pedido: total={inv.total}, email={inv.email_envio}")
    
    if inv.estado != "PENDIENTE":
        current_app.logger.warning(f"[MP] Pedido {inv.id} no está en estado PENDIENTE: {inv.estado}")
        return jsonify({"error": "El pedido no está en estado PENDIENTE"}), 409
    
    # Seguridad: monto desde BD (no confiar en frontend)
    amount = float(inv.total)
    payer_email = inv.email_envio
    current_app.logger.info(f"[MP] Datos del pedido: amount={amount}, payer_email={payer_email}")
    
    if not payer_email:
        current_app.logger.error(f"[MP] El pedido {inv.id} no tiene email_envio")
        return jsonify({"error": "El pedido no tiene email_envio"}), 400
    
    # Validación por tipo de pago
    payment_method_id = payload.get("payment_method_id")
    current_app.logger.info(f"[MP] Método de pago seleccionado: {payment_method_id}")
    
    # Detectar si es PSE
    if payment_method_id == "pse":
        current_app.logger.info("[MP] Procesando pago PSE")
        # Flujo PSE: no requiere token, pero necesita IP, entity_type e identification
        ip = get_client_ip()
        current_app.logger.info(f"[MP] IP del cliente detectada: {ip}")
        
        if not ip:
            current_app.logger.error("[MP] No se pudo detectar la IP del comprador para PSE")
            return jsonify({"error": "No se pudo detectar la IP del comprador"}), 400
            
        # Obtener datos del pagador del payload
        pse_payer = payload.get("payer") or {}
        current_app.logger.info(f"[MP] Datos del pagador PSE: {pse_payer}")
        
        ident = pse_payer.get("identification") or {}
        id_type = ident.get("type")
        id_number = ident.get("number")
        current_app.logger.info(f"[MP] Identificación PSE: type={id_type}, number={id_number}")
        
        # Para PSE, estos datos son obligatorios
        if not id_type or not id_number:
            current_app.logger.error("[MP] Faltan payer.identification.type/number para PSE")
            return jsonify({"error": "Falta payer.identification.type/number para PSE"}), 400
            
        payment_data = {
            "transaction_amount": float(inv.total),  # Usar siempre el monto de la BD por seguridad
            "payment_method_id": "pse",
            "payer": {
                "email": payer_email,  # Email desde Invoice.email_envio
                "entity_type": "individual",  # Requerido para PSE
                "identification": {
                    "type": id_type,
                    "number": str(id_number)
                }
            },
            "external_reference": inv.token_hash,
            "description": f"Musical Box - Pedido {inv.token_hash}",
            "additional_info": {
                "ip_address": ip
            },
            # PSE requiere callback_url específicamente, usar una URL válida
            "callback_url": "https://httpbin.org/post"
        }
        
        # Agregar otros campos que puedan venir en el payload de PSE
        for key, value in payload.items():
            if key not in ["token_hash", "payment_method_id", "transaction_amount", "payer", "external_reference", "description", "additional_info"] and value is not None:
                # Si es un diccionario, navegar adentro; si no, asignar directo
                if not isinstance(value, dict):
                    payment_data[key] = value
                elif key not in payment_data:
                    payment_data[key] = value
                    
        current_app.logger.info(f"[MP] Datos de pago PSE preparados: {payment_data}")
        
    elif payload.get("token"):
        current_app.logger.info("[MP] Procesando pago con tarjeta/débito")
        # Flujo tarjeta/débito/crédito
        token = payload.get("token")
        payment_method_id = payload.get("payment_method_id")
        installments = int(payload.get("installments", 1))
        issuer_id = payload.get("issuer_id")
        current_app.logger.info(f"[MP] Datos del pago tarjeta: token={token}, payment_method_id={payment_method_id}, installments={installments}, issuer_id={issuer_id}")
        
        if not token or not payment_method_id:
            current_app.logger.error("[MP] Faltan campos requeridos (token / payment_method_id)")
            return jsonify({"error": "Faltan campos requeridos (token / payment_method_id)"}), 400
            
        payment_data = {
            "token": token,
            "transaction_amount": float(inv.total),  # Usar siempre el monto de la BD por seguridad
            "installments": installments,
            "payment_method_id": payment_method_id,
            "payer": {"email": payer_email},
            "external_reference": inv.token_hash,
            "description": f"Musical Box - Pedido {inv.token_hash}",
        }
        if issuer_id:
            payment_data["issuer_id"] = int(issuer_id)
            
        current_app.logger.info(f"[MP] Datos de pago tarjeta preparados: {payment_data}")
    else:
        current_app.logger.info("[MP] Procesando pago con otro medio")
        # Otros medios de pago (wallet, ticket, etc.)
        current_app.logger.info("[MP] Procesando pago con otro medio, payload: %s", payload)
        # Usar los campos que vienen en el payload, pero asegurar los mínimos requeridos
        payment_data = {
            "transaction_amount": float(inv.total),  # Usar siempre el monto de la BD por seguridad
            "payer": {"email": payer_email},
            "external_reference": inv.token_hash,
            "description": f"Musical Box - Pedido {inv.token_hash}",
        }
        
        # Agregar campos del payload
        for key, value in payload.items():
            if key not in ["token_hash"] and value is not None:
                payment_data[key] = value
                
        current_app.logger.info(f"[MP] Datos de pago otros medios preparados: {payment_data}")
    
    # Idempotencia para evitar duplicados si el usuario reintenta
    request_options = mp_config.RequestOptions()
    request_options.custom_headers = {"X-Idempotency-Key": str(uuid.uuid4())}
    current_app.logger.info("[MP] Creando SDK de MercadoPago")
    
    sdk = get_mp_sdk()
    current_app.logger.info("[MP] Enviando solicitud de pago a MercadoPago")
    current_app.logger.info(f"[MP] Datos enviados a MP: {payment_data}")
    
    mp_resp = sdk.payment().create(payment_data, request_options)
    mp_http_status = mp_resp.get("status", 500)
    mp_body = mp_resp.get("response", {}) or {}
    current_app.logger.info(f"[MP] Respuesta de MercadoPago: status={mp_http_status}")
    current_app.logger.info(f"[MP] Body de MercadoPago: {mp_body}")
    
    # Confirmación: si aprobó, cambiar estado
    if mp_body.get("status") == "approved":
        current_app.logger.info(f"[MP] Pago aprobado para pedido {inv.id}")
        try:
            # Guardar el pago y marcar el pedido como PAGADO primero (siempre)
            inv.estado = "PAGADO"
            inv.mp_payment_id = str(mp_body.get("id") or "")
            current_app.logger.info(f"[MP] Estado del pedido {inv.id} cambiado a PAGADO, payment_id: {inv.mp_payment_id}")
            db.session.commit()  # Commit del estado/pago primero
            current_app.logger.info(f"[MP] Transacción de estado confirmada para pedido {inv.id}")
            
            # Ejecutar stock y email después, con manejo de errores separado
            try:
                current_app.logger.info(f"[MP] Descontando stock para pedido {inv.id}")
                discount_stock(inv)
                db.session.commit()
                current_app.logger.info(f"[MP] Stock descontado para pedido {inv.id}")
            except Exception as e:
                current_app.logger.exception(f"[MP] Fallo descuento de stock para pedido {inv.id}: {e}")
                # No hacer rollback, el pago ya se procesó
            
            try:
                current_app.logger.info(f"[MP] Enviando correo de confirmación para pedido {inv.id}")
                correo_pedido_pagado(inv, inv.token_hash)
                current_app.logger.info(f"[MP] Correo enviado para pedido {inv.id}")
            except Exception as e:
                current_app.logger.exception(f"[MP] Fallo envío de email para pedido {inv.id}: {e}")
                
            current_app.logger.info(f"[MP] Post-procesamiento completado para pedido {inv.id}")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"[MP] Error post-pago para pedido {inv.id}: {e}")
            return jsonify({
                "error": "Pago aprobado, pero falló el post-procesamiento. Revisá logs.",
                "mp_status": mp_http_status,
                "mp_response": mp_body,
            }), 500
    elif mp_body.get("status") == "rejected":
        current_app.logger.info(f"[MP] Pago rechazado para pedido {inv.id}")
        # Registrar el motivo del rechazo para debugging
        rejection_reason = mp_body.get("status_detail", "Sin detalles")
        current_app.logger.info(f"[MP] Motivo de rechazo: {rejection_reason}")
    elif payment_method_id == "pse" and mp_body.get("status") == "in_process":
        current_app.logger.info(f"[MP-PSE] Pago PSE en proceso para pedido {inv.id}")
        # Para PSE, el estado puede quedar en "in_process" temporalmente
        current_app.logger.info(f"[MP-PSE] Esperando confirmación del banco")
    
    current_app.logger.info(f"[MP] === FIN PROCESS_PAYMENT ===")
    current_app.logger.info(f"[MP] Devolviendo respuesta final: status={mp_http_status}")
    return jsonify({
        "mp_status": mp_http_status,
        "mp_response": mp_body,
    }), mp_http_status


@mercadopago_bp.route("/webhook", methods=["POST"])
def webhook():
    """Webhook para recibir notificaciones de MercadoPago"""
    try:
        data = request.get_json()
        current_app.logger.info(f"[MP-WEBHOOK] Notificación recibida: {data}")
        current_app.logger.info(f"[MP-WEBHOOK] Headers: {dict(request.headers)}")
        current_app.logger.info(f"[MP-WEBHOOK] Remote addr: {request.remote_addr}")
        
        # Verificar que sea una notificación válida
        if not data or "type" not in data:
            current_app.logger.warning("[MP-WEBHOOK] Notificación inválida recibida")
            return jsonify({"status": "invalid"}), 400
        
        # Procesar diferentes tipos de notificaciones
        if data.get("type") == "payment":
            return process_payment_notification(data)
        elif data.get("type") == "merchant_order":
            return process_merchant_order_notification(data)
        else:
            current_app.logger.info(f"[MP-WEBHOOK] Tipo de notificación no manejado: {data.get('type')}")
            return jsonify({"status": "not_handled"}), 200
            
    except Exception as e:
        current_app.logger.error(f"[MP-WEBHOOK] Error procesando notificación: {str(e)}")
        current_app.logger.exception("[MP-WEBHOOK] Traceback completo:")
        return jsonify({"error": "Error interno"}), 500


def process_payment_notification(data):
    """Procesar notificación de pago"""
    try:
        payment_id = data.get("data", {}).get("id")
        if not payment_id:
            current_app.logger.warning("[MP-WEBHOOK] ID de pago no encontrado en notificación")
            return jsonify({"error": "ID de pago no encontrado"}), 400
        
        current_app.logger.info(f"[MP-WEBHOOK] Procesando notificación de pago: {payment_id}")
        
        # Obtener detalles del pago
        current_app.logger.info(f"[MP-WEBHOOK] Obteniendo detalles del pago {payment_id} desde MercadoPago API")
        sdk = get_mp_sdk()
        payment_response = sdk.payment().get(payment_id)
        payment = payment_response.get("response", {})
        
        if not payment:
            current_app.logger.warning(f"[MP-WEBHOOK] No se pudieron obtener detalles del pago: {payment_id}")
            current_app.logger.info(f"[MP-WEBHOOK] Respuesta de API: {payment_response}")
            return jsonify({"error": "No se pudieron obtener detalles del pago"}), 400
        
        current_app.logger.info(f"[MP-WEBHOOK] Detalles del pago obtenidos: {payment}")
        
        # Buscar el pedido asociado
        external_reference = payment.get("external_reference")
        if not external_reference:
            current_app.logger.warning(f"[MP-WEBHOOK] Referencia externa no encontrada para pago: {payment_id}")
            current_app.logger.info(f"[MP-WEBHOOK] Campos disponibles en payment: {list(payment.keys())}")
            return jsonify({"error": "Referencia externa no encontrada"}), 400
        
        current_app.logger.info(f"[MP-WEBHOOK] Buscando pedido con external_reference: {external_reference}")
        inv = get_invoice_by_token(external_reference)
        if not inv:
            current_app.logger.warning(f"[MP-WEBHOOK] Pedido no encontrado para referencia: {external_reference}")
            # Listar algunos invoices recientes para debugging
            recent_invoices = Invoice.query.order_by(Invoice.id.desc()).limit(5).all()
            for invoice in recent_invoices:
                current_app.logger.info(f"[MP-WEBHOOK] Invoice reciente: ID={invoice.id}, token_hash={invoice.token_hash[:20] if invoice.token_hash else 'None'}, estado={invoice.estado}")
            return jsonify({"error": "Pedido no encontrado"}), 404
        
        current_app.logger.info(f"[MP-WEBHOOK] Pedido encontrado: {inv.id}, estado actual: {inv.estado}")
        current_app.logger.info(f"[MP-WEBHOOK] Datos del pedido: total={inv.total}, email={inv.email_envio}")
        
        # Procesar según el estado del pago
        payment_status = payment.get("status")
        payment_method_id = payment.get("payment_method_id")
        current_app.logger.info(f"[MP-WEBHOOK] Estado del pago: {payment_status}, método: {payment_method_id}")
        
        # Log detallado de todos los campos del pago
        current_app.logger.info(f"[MP-WEBHOOK] Campos completos del pago: {payment.keys()}")
        if "status_detail" in payment:
            current_app.logger.info(f"[MP-WEBHOOK] Detalle del status: {payment['status_detail']}")
        if "payment_method" in payment:
            current_app.logger.info(f"[MP-WEBHOOK] Método de pago detallado: {payment['payment_method']}")
        
        if payment_status == "approved" and inv.estado == "PENDIENTE":
            # Pago aprobado, confirmar el pedido
            current_app.logger.info(f"[MP-WEBHOOK] Pago aprobado para pedido pendiente {inv.id}")
            inv.estado = "PAGADO"
            inv.estado_envio = inv.estado_envio or 'POR PREPARAR'
            inv.mp_payment_id = str(payment.get("id", ""))
            
            # Descontar stock y enviar correo
            try:
                current_app.logger.info(f"[MP-WEBHOOK] Descontando stock para pedido {inv.id}")
                discount_stock(inv)
                current_app.logger.info(f"[MP-WEBHOOK] Stock descontado para pedido {inv.id}")
                
                current_app.logger.info(f"[MP-WEBHOOK] Enviando correo de confirmación para pedido {inv.id}")
                correo_pedido_pagado(inv, external_reference)
                current_app.logger.info(f"[MP-WEBHOOK] Correo enviado para pedido {inv.id}")
                
                db.session.commit()
                current_app.logger.info(f"[MP-WEBHOOK] Pedido {inv.id} confirmado exitosamente")
                return jsonify({"status": "processed"}), 200
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"[MP-WEBHOOK] Error confirmando pedido {inv.id}: {str(e)}")
                current_app.logger.exception("[MP-WEBHOOK] Traceback completo del error:")
                return jsonify({"error": "Error confirmando pedido"}), 500
                
        elif payment_status in ["rejected", "cancelled", "refunded"]:
            # Pago rechazado o cancelado
            current_app.logger.info(f"[MP-WEBHOOK] Pago {payment_status} para pedido {inv.id}")
            if inv.estado == "PENDIENTE":
                inv.estado = "RECHAZADO"
                inv.mp_payment_id = str(payment.get("id", ""))
                db.session.commit()
                current_app.logger.info(f"[MP-WEBHOOK] Pedido {inv.id} marcado como rechazado")
                return jsonify({"status": "processed"}), 200
            else:
                current_app.logger.info(f"[MP-WEBHOOK] Pedido {inv.id} ya procesado, estado: {inv.estado}")
                return jsonify({"status": "already_processed"}), 200
                
        elif payment_status == "in_process" and payment_method_id == "pse":
            # Pago en proceso (típico para PSE)
            current_app.logger.info(f"[MP-WEBHOOK] Pago PSE en proceso para pedido {inv.id}")
            current_app.logger.info(f"[MP-WEBHOOK] Detalles adicionales PSE: {payment.get('payment_method', {})}")
            return jsonify({"status": "processing"}), 200
            
        elif payment_status == "in_process":
            # Otros pagos en proceso
            current_app.logger.info(f"[MP-WEBHOOK] Pago en proceso para pedido {inv.id}, método: {payment_method_id}")
            return jsonify({"status": "processing"}), 200
            
        else:
            current_app.logger.info(f"[MP-WEBHOOK] Estado de pago no manejado: {payment_status}, pedido estado: {inv.estado}")
            return jsonify({"status": "not_handled"}), 200
            
    except Exception as e:
        current_app.logger.error(f"[MP-WEBHOOK] Error procesando notificación de pago: {str(e)}")
        current_app.logger.exception("[MP-WEBHOOK] Traceback completo:")
        return jsonify({"error": "Error interno"}), 500


def process_merchant_order_notification(data):
    """Procesar notificación de orden de merchant"""
    current_app.logger.info("[MP-WEBHOOK] Procesando notificación de orden de merchant")
    # Implementar si se necesita manejar órdenes de merchant
    return jsonify({"status": "received"}), 200


@mercadopago_bp.route("/webhook-test", methods=["POST"])
def webhook_test():
    """Endpoint para pruebas de webhook en desarrollo"""
    if current_app.config.get("ENV") == "development":
        data = request.get_json()
        current_app.logger.info(f"[MP-WEBHOOK-TEST] Test notification received: {data}")
        return jsonify({"status": "test_received"}), 200
    else:
        abort(404)