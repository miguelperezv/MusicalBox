#solicitudes de pedido y rótulos de envío (integrado desde musical_box_manager)
from flask import Blueprint, flash, request, g, render_template, redirect, url_for, jsonify
from .forms import RegistroSolicitudForm
from .models import get_or_create_cliente, create_solicitud, get_all_solicitudes, get_solicitud_by_id, update_estado_solicitud, get_catalogo_solicitud, get_product_by_id, ESTADOS_SOLICITUD
from .views import before_request, admin_required


solicitud = Blueprint('solicitud', __name__, url_prefix='/solicitud')
solicitud.before_request(before_request)


@solicitud.route("/", methods=["GET", "POST"])
def nueva():
    form = RegistroSolicitudForm()
    if request.method == 'GET' and g.user:
        #si ya tiene cuenta en la tienda, prellenamos sus datos de envío
        form.nombre.data = g.user.get("n_usuario")
        form.apellido.data = g.user.get("ape_usuario")
        form.email.data = g.user.get("email_usuario")
        form.ciudad.data = g.user.get("lugar_usuario")
        form.direccion.data = g.user.get("dir_usuario")
        form.barrio.data = g.user.get("barrio_usuario")
        form.celular.data = g.user.get("cel_usuario")
        form.num_id.data = g.user.get("num_id")
        if g.user.get("tipo_id"):
            form.tipo_id.data = g.user.get("tipo_id")

    if request.method == 'POST':
        if not form.validate():
            flash("Revisa los campos obligatorios del formulario", "warning")
            return render_template('solicitud.html', form=form, user=g.user, purchase_cart=g.purchase)

        user, err = get_or_create_cliente(form.tipo_id.data, form.num_id.data.strip(), form.nombre.data.strip(),
                                          (form.apellido.data or '').strip(), form.email.data.strip(),
                                          form.direccion.data, form.ciudad.data, form.barrio.data, form.celular.data)
        if not user:
            flash("No pudimos registrar tus datos: " + str(err), "error")
            return render_template('solicitud.html', form=form, user=g.user, purchase_cart=g.purchase)

        #producto del catálogo si se eligió del autocompletado, si no queda como texto libre
        k_producto = request.form.get("producto_id", type=int)
        if k_producto and not get_product_by_id(k_producto):
            k_producto = None
        s, err = create_solicitud(user.id, k_producto, form.producto.data.strip(), form.d_producto.data)
        if s:
            flash("¡Recibimos tu solicitud #" + str(s.id) + "! Te contactaremos pronto", "success")
            return redirect(url_for('home.index'))
        flash("Error registrando la solicitud: " + str(err), "error")

    return render_template('solicitud.html', form=form, user=g.user, purchase_cart=g.purchase)


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


@solicitud.route("/<int:id>/rotulo")
@admin_required
def rotulo(id):
    s = get_solicitud_by_id(id)
    if not s:
        return "Solicitud no encontrada", 404
    return render_template('rotulo.html', solicitud=s, usuario=s.usuario)
