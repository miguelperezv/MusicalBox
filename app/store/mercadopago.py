# Integración con MercadoPago para MusicalBox
import os
import json
import hashlib
import hmac
import uuid
from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for, abort, jsonify
from .forms import CheckoutForm
from .models import crear_pedido, get_pedido_por_token, confirmar_pago, rechazar_pago, validar_carrito
from .views import before_request, purchase
from ..db import db
from .notificaciones import correo_pedido_pagado
import mercadopago

# Definir el blueprint
mercadopago_bp = Blueprint('mercadopago', __name__, url_prefix='/mercadopago')
mercadopago_bp.before_request(before_request)

def get_mercadopago_sdk():
    """Obtiene una instancia del SDK de MercadoPago con las credenciales configuradas."""
    access_token = current_app.config.get("MERCADOPAGO_ACCESS_TOKEN")
    if not access_token or access_token == "YOUR_ACCESS_TOKEN" or access_token == "TEST-ACCESS-TOKEN-HERE":
        raise Exception("Credenciales de MercadoPago no configuradas")
    
    return mercadopago.SDK(access_token)

@mercadopago_bp.route("/button/<token>")
def button(token):
    """Muestra el botón de pago de MercadoPago para un pedido."""
    # Verificar que el pedido exista
    pedido = get_pedido_por_token(token)
    if not pedido:
        abort(404)
    
    # Verificar que el pedido esté pendiente
    if pedido.estado != 'PENDIENTE':
        flash("Este pedido ya fue procesado", "warning")
        return redirect(url_for('pedido.ver', token=token))
    
    try:
        # Crear preferencia de pago
        sdk = get_mercadopago_sdk()
        
        # Datos del pedido
        items = []
        total_amount = 0
        for item in pedido.items:
            # Asegurarse de que unit_price sea entero (sin decimales)
            unit_price = int(float(item.p_item))
            quantity = int(item.cant_item)
            item_total = unit_price * quantity
            total_amount += item_total
            
            items.append({
                "title": f"{item.producto.lanzamiento.n_lanzamiento.title()} - {item.producto.n_producto}" if item.producto and item.producto.lanzamiento else (item.producto.n_producto if item.producto else "Producto"),
                "quantity": quantity,
                "currency_id": "COP",
                "unit_price": unit_price  # Convertido a entero
            })
        
        print(f"DEBUG: Creando preferencia para pedido {pedido.id}")
        print(f"DEBUG: Items: {items}")
        print(f"DEBUG: Total amount: {total_amount}")
        
        # Crear preferencia (versión simplificada para diagnóstico)
        preference_data = {
            "items": items,
            "external_reference": str(pedido.id),
            "notification_url": url_for('mercadopago.webhook', _external=True),
        }
        
        # Loguear la preferencia para debugging
        print("PREFERENCE DATA =>", json.dumps(preference_data, indent=2))
        
        # Crear la preferencia
        preference_response = sdk.preference().create(preference_data)
        
        # Verificar si la creación fue exitosa
        if preference_response.get("status") not in (200, 201):
            raise Exception(f"Error creando preferencia: {preference_response}")
        
        preference = preference_response["response"]
        
        # Verificar que la preferencia tenga id
        if "id" not in preference:
            raise Exception(f"La preferencia no contiene id: {preference}")
        
        print(f"DEBUG: Preferencia creada exitosamente con ID: {preference['id']}")
        
        # Guardar el ID de preferencia en el pedido para futuras referencias
        pedido.ref_payco = preference["id"]  # Usamos este campo para guardar el ID de preferencia
        db.session.commit()
        
        # Renderizar el botón de pago
        return render_template("mercadopago_button.html", 
                             preference_id=preference["id"],
                             public_key=current_app.config.get("MERCADOPAGO_PUBLIC_KEY"),
                             pedido=pedido,
                             token=token)
                              
    except Exception as e:
        print(f"Error creando preferencia de MercadoPago: {str(e)}")
        flash("Hubo un error al procesar el pago con MercadoPago. Por favor, inténtalo más tarde.", "error")
        return redirect(url_for('pedido.ver', token=token))

@mercadopago_bp.route("/create_preference/<token>", methods=["POST"])
def create_preference(token):
    """Crea una preference para un pedido y la devuelve en formato JSON."""
    try:
        print(f"[MP] === INICIANDO CREACIÓN DE PREFERENCIA ===")
        print(f"[MP] Token recibido: {token}")
        
        # Verificar que el pedido exista
        print(f"[MP] Buscando pedido por token...")
        pedido = get_pedido_por_token(token)
        if not pedido:
            print(f"[MP] ERROR: Pedido no encontrado para token: {token}")
            return jsonify({"error": "Pedido no encontrado"}), 404
        
        print(f"[MP] Pedido encontrado - ID: {pedido.id}, Estado: {pedido.estado}")
        print(f"[MP] Detalles del pedido:")
        print(f"  - Usuario: {pedido.k_usuario}")
        print(f"  - Total: {pedido.total}")
        print(f"  - Fecha compra: {pedido.f_compra}")
        print(f"  - Items count: {len(pedido.items)}")
        
        # Verificar que el pedido esté pendiente
        if pedido.estado != 'PENDIENTE':
            print(f"[MP] ERROR: Pedido no está pendiente. Estado actual: {pedido.estado}")
            return jsonify({"error": f"Este pedido ya ha sido pagado o está rechazado. Estado actual: {pedido.estado}"}), 400
        
        # Verificar que haya items
        if not pedido.items:
            print(f"[MP] ERROR: El pedido no tiene items")
            return jsonify({"error": "El pedido no tiene items"}), 400
        
        # Mostrar detalles de los items
        print(f"[MP] Items del pedido:")
        for i, item in enumerate(pedido.items):
            print(f"  Item {i+1}: Producto ID {item.k_producto}, Variante ID {item.k_variante}, Cantidad {item.cant_item}, Precio {item.p_item}")
            if item.producto:
                print(f"    Producto: {item.producto.n_producto}")
                if item.producto.lanzamiento:
                    print(f"    Lanzamiento: {item.producto.lanzamiento.n_lanzamiento}")
            else:
                print(f"    ADVERTENCIA: Producto no encontrado para este item")
        
        # Crear SDK de MercadoPago
        print(f"[MP] Creando SDK de MercadoPago...")
        sdk = get_mercadopago_sdk()
        
        # Preparar items del pedido
        items = []
        total_amount = 0
        for item in pedido.items:
            # Asegurarse de que unit_price sea entero (sin decimales)
            try:
                unit_price = int(float(item.p_item))
                quantity = int(item.cant_item)
                item_total = unit_price * quantity
                total_amount += item_total
                
                # Crear título descriptivo
                if item.producto and item.producto.lanzamiento:
                    title = f"{item.producto.lanzamiento.n_lanzamiento.title()} - {item.producto.n_producto}"
                elif item.producto:
                    title = item.producto.n_producto
                else:
                    title = f"Producto ID {item.k_producto}"
                
                items.append({
                    "title": title,
                    "quantity": quantity,
                    "currency_id": "COP",
                    "unit_price": unit_price
                })
                print(f"[MP] Item agregado: {title} x{quantity} @ ${unit_price}")
            except Exception as e:
                print(f"[MP] ERROR al procesar item: {e}")
                return jsonify({"error": f"Error al procesar item {item.id}: {str(e)}"}), 400
        
        print(f"[MP] Items preparados: {len(items)} items, total: ${total_amount}")
        
        # Validar que haya items
        if not items:
            print("[MP] ERROR: No se pudieron preparar items válidos")
            return jsonify({"error": "No se pudieron preparar items válidos"}), 400
        
        # Crear preferencia
        preference_data = {
            "items": items,
            "external_reference": str(pedido.id),
            "notification_url": url_for('mercadopago.webhook', _external=True),
        }
        
        print("[MP] PREFERENCE DATA a enviar:")
        import json
        print(json.dumps(preference_data, indent=2, default=str))
        
        # Crear la preferencia
        print("[MP] Llamando a SDK para crear preferencia...")
        preference_response = sdk.preference().create(preference_data)
        print(f"[MP] Respuesta del SDK: {preference_response}")
        
        # Verificar si la creación fue exitosa
        status = preference_response.get("status")
        print(f"[MP] Status de respuesta: {status}")
        
        if status not in (200, 201):
            error_msg = f"Error creando preferencia. Status: {status}, Response: {preference_response}"
            print(f"[MP] {error_msg}")
            return jsonify({"error": error_msg}), 400
        
        preference = preference_response.get("response", {})
        print(f"[MP] Preferencia response: {preference}")
        
        # Verificar que la preferencia tenga id
        if "id" not in preference:
            error_msg = f"La preferencia no contiene id. Response completa: {preference}"
            print(f"[MP] {error_msg}")
            return jsonify({"error": error_msg}), 500
        
        preference_id = preference["id"]
        print(f"[MP] Preferencia creada exitosamente con ID: {preference_id}")
        
        return jsonify({"preferenceId": preference_id})
    except Exception as e:
        print(f"[MP] ERROR GENERAL creando preference: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Error al crear la preferencia de pago: {str(e)}"}), 500

@mercadopago_bp.route("/success/<token>")
def success(token):
    """Maneja el éxito del pago."""
    pedido = get_pedido_por_token(token)
    if not pedido:
        abort(404)
    
    # Obtener el payment_id de los parámetros
    payment_id = request.args.get('payment_id')
    
    if payment_id:
        try:
            # Verificar el pago con la API de MercadoPago
            sdk = get_mercadopago_sdk()
            payment_response = sdk.payment().get(payment_id)
            payment = payment_response["response"]
            
            # Verificar que el pago sea válido
            if payment and payment.get("status") == "approved":
                # Confirmar el pago en nuestro sistema
                pedido, pago_nuevo = confirmar_pago(pedido, payment_id, payment.get("id"), payment.get("payment_method_id"))
                if pago_nuevo:
                    correo_pedido_pagado(pedido, token)
                flash("¡Pago aprobado! Tu pedido quedó confirmado.", "success")
            elif payment and payment.get("status") == "pending":
                # PSE o transferencia: queda en proceso hasta que MP lo notifique
                flash("Tu pago está en proceso. Te avisaremos cuando se confirme.", "info")
            else:
                flash("El pago no fue aprobado. Por favor, inténtalo nuevamente.", "error")
                
        except Exception as e:
            print(f"Error verificando pago de MercadoPago: {str(e)}")
            flash("Hubo un error al verificar el pago. Te contactaremos pronto.", "warning")
    
    return redirect(url_for('pedido.ver', token=token))

@mercadopago_bp.route("/failure/<token>")
def failure(token):
    """Maneja la falla del pago."""
    pedido = get_pedido_por_token(token)
    if not pedido:
        abort(404)
    
    # Rechazar el pago en nuestro sistema
    rechazar_pago(pedido, "MERCADOPAGO_FAILURE")
    
    flash("El pago no fue aprobado. Por favor, inténtalo nuevamente.", "error")
    return redirect(url_for('pedido.ver', token=token))

@mercadopago_bp.route("/pending/<token>")
def pending(token):
    """Maneja el pago pendiente."""
    pedido = get_pedido_por_token(token)
    if not pedido:
        abort(404)
    
    flash("Tu pago está en proceso. Te avisaremos cuando se confirme.", "info")
    return redirect(url_for('pedido.ver', token=token))

@mercadopago_bp.route("/webhook", methods=["POST"])
def webhook():
    """Webhook para recibir notificaciones de MercadoPago."""
    try:
        # Verificar la firma de la notificación
        x_signature = request.headers.get('x-signature', '')
        x_request_id = request.headers.get('x-request-id', '')
        
        # Obtener el cuerpo de la solicitud
        data = request.get_data()
        
        # Verificar firma (opcional pero recomendado)
        # Esta es una verificación básica, en producción deberías implementar
        # la verificación completa según la documentación de MercadoPago
        
        # Procesar la notificación
        data = request.get_json()
        print(f'[MP] Datos de notificación: {data}')
        
        # Si es una notificación de tipo payment
        if data.get("type") == "payment":
            payment_id = data.get("data", {}).get("id")
            if payment_id:
                print(f'[MP] Procesando notificación de pago ID: {payment_id}')
                
                # Obtener información del pago
                sdk = get_mercadopago_sdk()
                payment_response = sdk.payment().get(payment_id)
                payment = payment_response["response"]
                print(f'[MP] Información del pago: {payment}')
                
                # Buscar el pedido asociado usando external_reference
                external_reference = payment.get("external_reference")
                if external_reference and external_reference.isdigit():
                    pedido_id = int(external_reference)
                    print(f'[MP] Pedido encontrado: {pedido_id}')
                    
                    # Aquí actualizas el estado del pedido en tu base de datos
                    from .models import Invoice, db
                    pedido = Invoice.query.get(pedido_id)
                    if pedido:
                        print(f'[MP] Actualizando estado del pedido {pedido_id}')
                        
                        # Actualizar el estado del pedido según el estado del pago
                        payment_status = payment.get("status")
                        if payment_status == "approved":
                            # Pago aprobado - confirmar el pago en el sistema
                            pedido, pago_nuevo = confirmar_pago(
                                pedido, 
                                payment_id, 
                                payment.get("id"), 
                                payment.get("payment_method_id")
                            )
                            if pago_nuevo:
                                # Necesitamos obtener el token_hash para enviar el correo
                                print(f'[MP] Enviando correo para pedido aprobado {pedido_id}')
                                correo_pedido_pagado(pedido, pedido.token_hash)
                            print(f'[MP] Pago aprobado para pedido {pedido_id}')
                            
                        elif payment_status in ["rejected", "cancelled"]:
                            # Pago rechazado o cancelado
                            rechazar_pago(pedido, f"MERCADOPAGO_{payment_status.upper()}")
                            print(f'[MP] Pago rechazado/cancelado para pedido {pedido_id}')
                            
                        elif payment_status == "pending":
                            # Pago pendiente (PSE, transferencia, etc.)
                            print(f'[MP] Pago pendiente para pedido {pedido_id}')
                            
                        # Guardar las referencias de pago
                        pedido.ref_payco = str(payment.get("id"))  # ID de MercadoPago
                        pedido.id_factura_payco = str(payment.get("payment_method_id"))
                        
                        # También guardar información adicional del pago
                        print(f'[MP] Guardando referencias - ref_payco: {pedido.ref_payco}, id_factura_payco: {pedido.id_factura_payco}')
                        
                        db.session.commit()
                        print(f'[MP] Pedido {pedido_id} actualizado en la base de datos')
                    else:
                        print(f'[MP] Pedido {pedido_id} no encontrado en la base de datos')
                else:
                    print(f'[MP] No se encontró external_reference válido: {external_reference}')
        
        return "", 200
    except Exception as e:
        print(f"[MP] Error procesando webhook de MercadoPago: {str(e)}")
        import traceback
        traceback.print_exc()
        return "", 500
        print(f"Error procesando webhook de MercadoPago: {str(e)}")
        return "", 500


@mercadopago_bp.route("/process_payment", methods=["POST"])
def process_payment():
    """Procesa el pago realizado a través del Payment Brick."""
    try:
        print('[MP] === INICIANDO PROCESO DE PAGO ===')
        
        # Obtener los datos del pago del request (solo el payload interno)
        payload = request.get_json()
        print(f"[MP] Datos recibidos: {payload}")
        
        # Diagnóstico: imprimir las keys que nos llegan
        print("[MP] payload keys:", list(payload.keys()) if payload else "None")
        if isinstance(payload, dict) and payload.get("payer"):
            print("[MP] payer keys:", list(payload["payer"].keys()))
        
        # Validar que tengamos datos
        if not payload:
            print('[MP] ERROR: No se recibieron datos en el payload')
            return jsonify({"error": "No se recibieron datos"}), 400
        
        # Obtener el monto del payload
        amount = (
            payload.get("transaction_amount")
            or payload.get("transactionAmount")
            or payload.get("amount")
        )
        
        if amount is None:
            print('[MP] ERROR: No se encontró monto en el payload')
            return jsonify({"error": "missing amount in payload"}), 400
        
        print(f"[MP] Monto encontrado: {amount}")
        
        # Obtener payment_method_id de varias posibles variantes
        payment_method_id = (
            payload.get("payment_method_id")
            or payload.get("paymentMethodId")
            or payload.get("payment_method")
        )
        
        if payment_method_id is None:
            print('[MP] ERROR: No se encontró payment_method_id en el payload')
            print('[MP] Payload completo:', payload)
            return jsonify({"error": "missing payment_method_id in payload"}), 400
        
        print(f"[MP] Payment method ID encontrado: {payment_method_id}")
        
        # Filtrar solo los campos válidos para la API de MercadoPago
        # Referencia: https://www.mercadopago.com.co/developers/es/docs/checkout-bricks/payment-brick/payment-submission/cards
        payment_data = {
            "token": payload.get("token"),
            "transaction_amount": float(amount),
            "installments": int(payload.get("installments", 1)),
            "payment_method_id": payment_method_id,  # Usar el payment_method_id encontrado
        }
        
        # Agregar issuer_id si viene
        if payload.get("issuer_id"):
            payment_data["issuer_id"] = payload.get("issuer_id")
        
        # Agregar payer con email
        if isinstance(payload.get("payer"), dict) and payload["payer"].get("email"):
            payment_data["payer"] = {
                "email": payload["payer"]["email"]
            }
            
            # Agregar identification si viene
            if payload["payer"].get("identification"):
                payment_data["payer"]["identification"] = payload["payer"]["identification"]
        
        print(f"[MP] Datos filtrados para MercadoPago: {payment_data}")
        
        # Crear el pago usando el SDK de MercadoPago
        print('[MP] Obteniendo SDK de MercadoPago')
        sdk = get_mercadopago_sdk()
        
        # Agregar idempotency key para evitar pagos duplicados
        import uuid
        from mercadopago import config
        request_options = config.RequestOptions()
        request_options.custom_headers = {"x-idempotency-key": str(uuid.uuid4())}
        print(f'[MP] Idempotency key generado: {request_options.custom_headers["x-idempotency-key"]}')
        
        # Loguear el payload completo antes de enviarlo
        print('[MP] PAYLOAD a enviar a MercadoPago:')
        import json
        print(json.dumps(payment_data, indent=2, default=str))
        
        # Crear el pago
        print('[MP] Creando pago con SDK...')
        mp_resp = sdk.payment().create(payment_data, request_options)
        print(f'[MP] Respuesta completa del SDK: {mp_resp}')
        
        # Verificar si la llamada al SDK fue exitosa
        status = mp_resp.get("status")
        print(f'[MP] Status de respuesta: {status}')
        
        if status not in (200, 201):
            error_response = mp_resp.get("response", {})
            print(f'[MP] ERROR del SDK de MercadoPago - Status: {status}, Response: {error_response}')
            return jsonify({
                "mp_status": status,
                "mp_error": error_response,
            }), 400
        
        payment = mp_resp["response"]
        print(f"[MP] Pago creado - ID: {payment.get('id')}, Status: {payment.get('status')}")
        
        # Validar que tengamos un pago válido
        if not payment or "id" not in payment:
            print('[MP] ERROR: No se recibió un pago válido de MercadoPago')
            return jsonify({"error": "No se recibió un pago válido"}), 500
        
        # Devolver la información del pago para que el frontend pueda mostrar el status
        result = {
            "paymentId": payment.get("id"),
            "status": payment.get("status"),
            "status_detail": payment.get("status_detail"),
        }
        print(f'[MP] Resultado a enviar: {result}')
        return jsonify(result), 200
        
    except Exception as e:
        print(f"[MP] Error procesando pago: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# Desactivar CSRF protection para el endpoint de process_payment
# ya que el Payment Brick no envía el token CSRF
# process_payment.csrf_exempt = True  # Esta forma no funciona, usamos @csrf.exempt en la ruta