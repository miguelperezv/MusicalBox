#checkout sin cuenta y seguimiento de pedidos por enlace /pedido/<token>
from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for, abort, jsonify
from decimal import Decimal
import requests
import uuid
from .forms import CheckoutForm
from .models import (METODOS_PAGO, crear_pedido, get_pedido_por_token, referencia_epayco, confirmar_pago,
                     rechazar_pago, validar_carrito, Invoice, Item, Producto, Variante)
from .views import before_request, purchase
from ..db import db
from .notificaciones import correo_pedido_pagado
import mercadopago
from mercadopago import config as mp_config
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired, Email


pedido = Blueprint('pedido', __name__, url_prefix='/pedido')
pedido.before_request(before_request)


class EnvioForm(FlaskForm):
    nombre = StringField('Nombre completo', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    telefono = StringField('Teléfono', validators=[DataRequired()])
    ciudad = StringField('Ciudad', validators=[DataRequired()])
    direccion = StringField('Dirección', validators=[DataRequired()])
    barrio = StringField('Barrio')

    def cargar_desde_pedido(self, pedido):
        """Cargar datos del pedido al formulario"""
        self.nombre.data = pedido.n_envio
        self.email.data = pedido.email_envio
        self.telefono.data = pedido.tel_envio
        self.ciudad.data = pedido.lugar_envio
        self.direccion.data = pedido.dir_envio
        self.barrio.data = pedido.barrio_envio

    def aplicar_a_pedido(self, pedido):
        """Aplicar datos del formulario al pedido"""
        pedido.n_envio = self.nombre.data
        pedido.email_envio = self.email.data
        pedido.tel_envio = self.telefono.data
        pedido.lugar_envio = self.ciudad.data
        pedido.dir_envio = self.direccion.data
        pedido.barrio_envio = self.barrio.data


@pedido.route("/create_preference/<token_hash>", methods=["POST"])
def create_preference(token_hash):
    """
    Payment Brick NO necesita preferenceId.
    Este endpoint solo devuelve contexto del pedido.
    """
    current_app.logger.info(f"[MP] Solicitud create_preference para token_hash: {token_hash}")
    inv = get_invoice_by_token(token_hash)
    if not inv:
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


@pedido.route("/process_payment", methods=["POST"])
def process_payment():
    current_app.logger.info("[MP] Solicitud process_payment recibida")
    payload = request.get_json(silent=True) or {}
    current_app.logger.info(f"[MP] Payload recibido: {payload}")
    if not isinstance(payload, dict):
        current_app.logger.error("[MP] El body no es un JSON objeto válido")
        return jsonify({"error": "El body debe ser un JSON objeto"}), 400
    token_hash = payload.get("token_hash")
    current_app.logger.info(f"[MP] Token hash recibido: {token_hash}")
    if not token_hash:
        current_app.logger.error("[MP] Falta token_hash en el payload")
        return jsonify({"error": "Falta token_hash"}), 400
    inv = get_invoice_by_token(token_hash)
    if not inv:
        current_app.logger.warning(f"[MP] Pedido no encontrado para token_hash: {token_hash}")
        return jsonify({"error": "Pedido no encontrado"}), 404
    current_app.logger.info(f"[MP] Pedido encontrado: {inv.id}, estado: {inv.estado}")
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
    token = payload.get("token")
    payment_method_id = payload.get("payment_method_id")
    installments = int(payload.get("installments", 1))
    issuer_id = payload.get("issuer_id")
    current_app.logger.info(f"[MP] Datos del pago: token={token}, payment_method_id={payment_method_id}, installments={installments}, issuer_id={issuer_id}")
    if not token or not payment_method_id:
        current_app.logger.error("[MP] Faltan campos requeridos (token / payment_method_id)")
        return jsonify({"error": "Faltan campos requeridos (token / payment_method_id)"}), 400
    payment_data = {
        "token": token,
        "transaction_amount": amount,
        "installments": installments,
        "payment_method_id": payment_method_id,
        "payer": {"email": payer_email},
        "external_reference": inv.token_hash,
        "description": f"Musical Box - Pedido {inv.token_hash}",
    }
    if issuer_id:
        payment_data["issuer_id"] = int(issuer_id)
    current_app.logger.info(f"[MP] Datos de pago preparados: {payment_data}")
    # Idempotencia para evitar duplicados si el usuario reintenta
    request_options = mp_config.RequestOptions()
    request_options.custom_headers = {"X-Idempotency-Key": str(uuid.uuid4())}
    current_app.logger.info("[MP] Creando SDK de MercadoPago")
    sdk = get_mp_sdk()
    current_app.logger.info("[MP] Enviando solicitud de pago a MercadoPago")
    mp_resp = sdk.payment().create(payment_data, request_options)
    mp_http_status = mp_resp.get("status", 500)
    mp_body = mp_resp.get("response", {}) or {}
    current_app.logger.info(f"[MP] Respuesta de MercadoPago: status={mp_http_status}, body={mp_body}")
    # Confirmación: si aprobó, cambiar estado
    if mp_body.get("status") == "approved":
        current_app.logger.info(f"[MP] Pago aprobado para pedido {inv.id}")
        try:
            inv.estado = "PAGADO"
            current_app.logger.info(f"[MP] Estado del pedido {inv.id} cambiado a PAGADO")
            # Descontar stock
            current_app.logger.info(f"[MP] Descontando stock para pedido {inv.id}")
            discount_stock(inv)
            current_app.logger.info(f"[MP] Stock descontado para pedido {inv.id}")
            # Enviar correo
            current_app.logger.info(f"[MP] Enviando correo de confirmación para pedido {inv.id}")
            correo_pedido_pagado(inv, token_hash)
            current_app.logger.info(f"[MP] Correo enviado para pedido {inv.id}")
            db.session.commit()
            current_app.logger.info(f"[MP] Transacción confirmada para pedido {inv.id}")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"[MP] Error post-pago para pedido {inv.id}: {e}")
            return jsonify({
                "error": "Pago aprobado, pero falló el post-procesamiento (stock/email). Revisá logs.",
                "mp_status": mp_http_status,
                "mp_response": mp_body,
            }), 500
    current_app.logger.info(f"[MP] Devolviendo respuesta final: status={mp_http_status}")
    return jsonify({
        "mp_status": mp_http_status,
        "mp_response": mp_body,
    }), mp_http_status


def get_mp_sdk():
    return mercadopago.SDK(current_app.config["MERCADOPAGO_ACCESS_TOKEN"])


def get_invoice_by_token(token_hash: str):
    return Invoice.query.filter_by(token_hash=token_hash).first()


def discount_stock(invoice: Invoice):
    """
    Descontar stock de productos y variantes según los items del pedido.
    """
    for item in invoice.items:
        cantidad = int(item.cant_item)
        if item.k_variante:
            # Descontar stock de variante
            variante = Variante.query.get(item.k_variante)
            if variante and variante.stock >= cantidad:
                variante.stock -= cantidad
            else:
                raise ValueError(f"Stock insuficiente para variante {variante.id if variante else item.k_variante}")
        elif item.producto and item.producto.tipo == 'SIMPLE':
            # Descontar stock de producto simple
            producto = item.producto
            if producto.stock >= cantidad:
                producto.stock -= cantidad
            else:
                raise ValueError(f"Stock insuficiente para producto {producto.id}")
        elif item.producto and item.producto.tipo == 'BUNDLE':
            # Para bundles, descontar stock de componentes
            for componente in item.producto.componentes:
                # Calcular cantidad total necesaria (cantidad del bundle * cantidad del item)
                cantidad_total = int(componente.cantidad) * cantidad
                
                if componente.k_variante:
                    # Descontar stock de variante del componente
                    variante = Variante.query.get(componente.k_variante)
                    if variante and variante.stock >= cantidad_total:
                        variante.stock -= cantidad_total
                    else:
                        raise ValueError(f"Stock insuficiente para variante componente {variante.id if variante else componente.k_variante}")
                else:
                    # Descontar stock de producto del componente
                    producto = componente.componente
                    if producto and producto.stock >= cantidad_total:
                        producto.stock -= cantidad_total
                    else:
                        raise ValueError(f"Stock insuficiente para producto componente {producto.id if producto else componente.k_componente}")


@pedido.route("/<token>/actualizar-envio", methods=["POST"])
def actualizar_envio(token):
    p = _pedido_o_404(token)
    
    # Crear formulario y cargar datos
    form = EnvioForm()
    if form.validate_on_submit():
        # Aplicar cambios al pedido
        form.aplicar_a_pedido(p)
        db.session.commit()
        flash("Información de envío actualizada correctamente", "success")
    else:
        flash("Error al actualizar la información de envío", "error")
    
    return redirect(url_for('pedido.ver', token=token))


@pedido.route("/<token>")
def ver(token):
    p = _pedido_o_404(token)
    
    # Crear formulario para actualizar información de envío
    form_envio = EnvioForm()
    
    # Si el pedido no tiene información de envío, prellenar con datos de sesión o dejar vacío
    if not p.n_envio or not p.dir_envio:
        # Intentar prellenar con datos de la sesión si existen
        datos_checkout = session.get("checkout_datos", {})
        if datos_checkout:
            form_envio.nombre.data = datos_checkout.get("nombre")
            form_envio.email.data = datos_checkout.get("email")
            form_envio.telefono.data = datos_checkout.get("telefono")
            form_envio.ciudad.data = datos_checkout.get("ciudad")
            form_envio.direccion.data = datos_checkout.get("direccion")
            form_envio.barrio.data = datos_checkout.get("barrio")
    
    # Restaurar el carrito si el usuario vuelve a la tienda
    if session.get("ultimo_carrito") and not session.get("purchase"):
        session["purchase"] = session["ultimo_carrito"]
    
    return render_template("pedido.html", pedido=p, token=token, referencia=referencia_epayco(p),
                           simulacion=current_app.config.get("EPAYCO_SIMULACION"), form_envio=form_envio)


def _pedido_o_404(token):
    p = get_pedido_por_token(token)
    if not p:
        abort(404)
    return p


def consultar_epayco(ref_payco):
    #valida la transacción directamente con ePayco (no se confía en los parámetros que llegan en la URL)
    r = requests.get(current_app.config["EPAYCO_VALIDATION_URL"] + ref_payco, timeout=15)
    return (r.json() or {}).get("data") or {}


@pedido.route("/<token>/respuesta", methods=["GET", "POST"])
def respuesta(token):
    #URL de respuesta (navegador) y de confirmación (servidor a servidor) de ePayco
    p = _pedido_o_404(token)
    ref_payco = request.values.get("ref_payco") or request.values.get("x_ref_payco")
    if not ref_payco:
        flash("No recibimos la referencia del pago", "warning")
        return redirect(url_for('pedido.ver', token=token))
    try:
        data = consultar_epayco(ref_payco)
    except Exception as e:
        print("No se pudo validar con ePayco " + str(e))
        flash("No pudimos confirmar el pago con ePayco todavía. Revisa este enlace en unos minutos.", "warning")
        return redirect(url_for('pedido.ver', token=token))

    #la transacción debe ser de este pedido y por su valor exacto
    if data.get("x_id_invoice") != referencia_epayco(p) or Decimal(str(data.get("x_amount") or 0)) != Decimal(p.total):
        print(f"Respuesta de ePayco no corresponde al pedido {p.id}: {data.get('x_id_invoice')} {data.get('x_amount')}")
        flash("La respuesta del pago no corresponde a este pedido", "error")
        return redirect(url_for('pedido.ver', token=token))

    estado = data.get("x_response")
    if estado == "Aceptada":
        p, pago_nuevo = confirmar_pago(p, ref_payco, data.get("x_id_factura"), data.get("x_franchise"))
        if pago_nuevo:
            correo_pedido_pagado(p, token)
        flash("¡Pago aprobado! Tu pedido quedó confirmado.", "success")
    elif estado in ("Rechazada", "Fallida", "Abandonada", "Cancelada"):
        rechazar_pago(p, ref_payco)
        flash("El pago no fue aprobado. Puedes intentarlo de nuevo.", "error")
    else:
        #Pendiente (p. ej. PSE o efectivo): queda PENDIENTE hasta que ePayco confirme
        p.ref_payco = ref_payco
        db.session.commit()
        flash("Tu pago está en proceso. Te avisaremos cuando se confirme.", "info")
    return redirect(url_for('pedido.ver', token=token))


@pedido.route("/<token>/simular", methods=["POST"])
def simular(token):
    #solo desarrollo: recorre el mismo camino que una respuesta real de ePayco
    if not current_app.config.get("EPAYCO_SIMULACION"):
        abort(404)
    p = _pedido_o_404(token)
    if request.form.get("resultado") == "aprobado":
        p, pago_nuevo = confirmar_pago(p, "SIMULADO", "SIMULADO", "SIM")
        if pago_nuevo:
            correo_pedido_pagado(p, token)
        flash("Pago simulado: aprobado", "success")
    else:
        rechazar_pago(p, "SIMULADO")
        flash("Pago simulado: rechazado", "error")
    return redirect(url_for('pedido.ver', token=token))


