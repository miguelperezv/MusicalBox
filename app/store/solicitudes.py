#pedidos a la medida: solicitud (disco + contacto) -> cotización por WhatsApp/correo -> confirmar compra (checkout normal)
from urllib.parse import quote

from flask import Blueprint, flash, request, g, render_template, redirect, url_for, jsonify, session, abort
from .forms import RegistroSolicitudForm, CheckoutForm, CotizacionRapidaForm
from .models import (create_solicitud, get_all_solicitudes, update_estado_solicitud, get_catalogo_solicitud, get_product_by_id,
                     get_usuario_por_email, cotizar_solicitud, get_solicitud_por_token, datos_envio_previos, crear_pedido,
                     ESTADOS_SOLICITUD, METODOS_PAGO, Solicitud)
from ..db import db
from .views import before_request, admin_required


solicitud = Blueprint('solicitud', __name__, url_prefix='/solicitud')
solicitud.before_request(before_request)


@solicitud.route("/", methods=["GET", "POST"])
def nueva():
    form = RegistroSolicitudForm()
    if request.method == 'GET' and g.user:
        form.celular.data = g.user.get("cel_usuario")
        form.email.data = g.user.get("email_usuario")

    if form.validate_on_submit():
        email = (form.email.data or '').strip().lower() or None
        #se asocia a una cuenta si ya existe; si no, el comprador se crea al confirmar la compra
        usuario = get_usuario_por_email(g.user["email_usuario"]) if g.user else (get_usuario_por_email(email) if email else None)
        k_producto = request.form.get("producto_id", type=int)
        if k_producto and not get_product_by_id(k_producto):
            k_producto = None
        s, err = create_solicitud(usuario.id if usuario else None, k_producto, form.producto.data.strip(), form.d_producto.data,
                                  form.celular.data.strip(), email)
        if s:
            flash("¡Recibimos tu solicitud #" + str(s.id) + "! Te escribiremos por WhatsApp con precio y tiempos.", "success")
            return redirect(url_for('home.index'))
        flash("Error registrando la solicitud: " + str(err), "error")
    elif request.method == 'POST':
        flash("Revisa los campos del formulario", "warning")

    return render_template('solicitud.html', form=form)


@solicitud.route("/productos")
def productos():
    return jsonify(get_catalogo_solicitud())


@solicitud.route("/solicitudes")
@admin_required
def lista():
    return render_template('solicitudes.html', solicitudes=get_all_solicitudes(), estados=ESTADOS_SOLICITUD)


@solicitud.route("/<int:id>/estado", methods=["POST"])
@admin_required
def estado(id):
    s = update_estado_solicitud(id, request.form.get("estado"))
    if s:
        return jsonify({"id": s.id, "estado": s.estado})
    return jsonify({"error": "No se pudo actualizar la solicitud"}), 400


def _respuesta_cotizar(s, token):
    #el enlace solo se puede ver ahora (en la BD queda su hash); se envía al cliente por WhatsApp o correo
    enlace = url_for('solicitud.confirmar', token=token, _external=True)
    disco = s.producto.lanzamiento.n_lanzamiento.title() + " - " if s.producto.lanzamiento else ""
    mensaje = (f"¡Hola! Conseguimos tu pedido en Musical Box: {disco}{s.producto.n_producto} por ${int(s.precio_cotizado):,}".replace(",", ".")
               + f". Confirma tu compra y datos de envío aquí: {enlace}")
    cel = "".join(c for c in (s.cel_contacto or "") if c.isdigit())
    return {"id": s.id, "enlace": enlace,
            "whatsapp": f"https://wa.me/{'57' + cel if len(cel) == 10 else cel}?text={quote(mensaje)}",
            "estado": s.estado}


@solicitud.route("/nueva_admin", methods=["POST"])
@admin_required
def nueva_admin():
    #pedido a la medida que nace en el panel (la conversación empezó en el sitio, Instagram o WhatsApp)
    form = CotizacionRapidaForm()
    if not form.validate():
        return jsonify({"error": "Revisa los campos: mínimo el WhatsApp y el disco"}), 400
    texto = (form.producto.data or "").strip()
    k_producto = int(texto.split(".")[0]) if texto.split(".")[0].strip().isdigit() else None
    if k_producto and not get_product_by_id(k_producto):
        k_producto = None
    #si vino del catálogo, el nombre limpio es lo que va después de "id."
    nombre_limpio = texto.split(". ", 1)[1].strip() if k_producto else texto
    email = (form.email.data or "").strip().lower() or None
    usuario = get_usuario_por_email(email) if email else None
    s, err = create_solicitud(usuario.id if usuario else None, k_producto, nombre_limpio, None,
                              form.celular.data.strip(), email)
    if not s:
        return jsonify({"error": err or "No se pudo registrar"}), 400
    if k_producto and form.precio.data:
        token, cerr = cotizar_solicitud(s.id, k_producto, form.precio.data)
        if cerr:
            return jsonify({"error": cerr, "id": s.id, "estado": s.estado}), 400
        return jsonify(_respuesta_cotizar(s, token))
    return jsonify({"id": s.id, "estado": s.estado})


@solicitud.route("/<int:id>/cotizar", methods=["POST"])
@admin_required
def cotizar(id):
    k_producto = request.form.get("producto", "").split(".")[0].strip()
    token, err = cotizar_solicitud(id, int(k_producto) if k_producto.isdigit() else None, request.form.get("precio", type=int))
    if err:
        return jsonify({"error": err}), 400
    s = db.session.get(Solicitud, id)
    return jsonify(_respuesta_cotizar(s, token))


@solicitud.route("/confirmar/<token>", methods=["GET", "POST"])
def confirmar(token):
    #paso 2 del flujo: el cliente ya recibió precio y tiempos; aquí se piden datos de envío y se paga
    s = get_solicitud_por_token(token)
    if not s or not s.producto or not s.precio_cotizado:
        abort(404)
    if s.estado == 'COMPRADA':
        flash("Esta solicitud ya fue pagada. Revisa el enlace del pedido que llegó a tu correo.", "info")
        return redirect(url_for('home.index'))

    form = CheckoutForm()
    form.metodo_pago.choices = METODOS_PAGO
    previos = datos_envio_previos(s.email_contacto or (s.usuario.email_usuario if s.usuario else None))
    if request.method == 'GET':
        for campo, valor in (previos or {"email": s.email_contacto, "telefono": s.cel_contacto}).items():
            if valor and campo in form:
                form[campo].data = valor

    if form.validate_on_submit():
        datos = {campo: form[campo].data for campo in ["nombre", "email", "telefono", "ciudad", "direccion", "barrio", "metodo_pago"]}
        pedido, token_pedido, errores = crear_pedido(None, datos, k_usuario=g.user["id"] if g.user else None,
                                                     cotizacion=(s.producto, s.precio_cotizado))
        if errores:
            for e in errores:
                flash(e, "warning")
        else:
            s.k_invoice = pedido.id
            db.session.commit()
            return redirect(url_for('pedido.ver', token=token_pedido))

    return render_template("checkout.html", form=form, lineas=[(s.producto, None, 1, s.precio_cotizado)], total=s.precio_cotizado,
                           accion=url_for('solicitud.confirmar', token=token), previos=previos, solicitud=s)
