#checkout sin cuenta y seguimiento de pedidos por enlace /pedido/<token>
#el pago lo procesa el blueprint "mercadopago" (app/store/mercadopago/views.py)
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for, abort
from .models import get_pedido_por_token, pasos_envio
from .services.payment_service import confirmar_pago, rechazar_pago
from .views import before_request
from ..db import db
from .notificaciones import notificar_pago_aprobado
from .notif_admin import aviso_pago_rechazado
from .analytics import track_event, Events
from .municipios import canonico, mismo_municipio
from .envio import costo_envio
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired, Email, ValidationError


pedido = Blueprint('pedido', __name__, url_prefix='/pedido')
pedido.before_request(before_request)


class EnvioForm(FlaskForm):
    nombre = StringField('Nombre completo', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    telefono = StringField('Teléfono', validators=[DataRequired()])
    ciudad = StringField('Ciudad', validators=[DataRequired()])
    direccion = StringField('Dirección', validators=[DataRequired()])
    barrio = StringField('Barrio')

    def validate_ciudad(self, field):
        if field.data and not canonico(field.data):
            raise ValidationError("Elige tu municipio de la lista (Municipio, Departamento)")

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


@pedido.route("/<token>/actualizar-envio", methods=["POST"])
def actualizar_envio(token):
    p = _pedido_o_404(token)
    #la dirección y el municipio son la base del costo de envío y del rótulo: una vez que el
    #pedido tiene datos, el cliente no los puede cambiar (lo hace el admin desde el panel).
    #solo se permite completar un pedido viejo que llegó totalmente vacío.
    tiene_datos = any([p.n_envio, p.email_envio, p.tel_envio, p.lugar_envio, p.dir_envio])
    if tiene_datos or p.estado not in ('PENDIENTE', 'PENDIENTE_ABONO', 'RECHAZADO'):
        flash("Los datos de envío de este pedido ya quedaron fijados. "
              "Para cambiarlos, escríbenos por WhatsApp y lo ajustamos.", "warning")
        return redirect(url_for('pedido.ver', token=token))

    form = EnvioForm()
    if form.validate_on_submit():
        ciudad = canonico(form.ciudad.data) or form.ciudad.data
        if p.lugar_envio and not mismo_municipio(ciudad, p.lugar_envio):
            flash("El municipio del envío ya está definido en este pedido. Escríbenos para cambiarlo.", "warning")
            return redirect(url_for('pedido.ver', token=token))
        form.ciudad.data = ciudad
        form.aplicar_a_pedido(p)
        #si el pedido no tenía datos, el envío se cotiza ahora con el municipio que acaba de dejar;
        #pero si ya estaba fijado a mano (o por una cotización), se respeta ese valor
        if not p.envio_manual and 'fijado por la tienda' not in (p.d_envio or '').lower():
            lineas = [(it.producto, it.variante, int(it.cant_item or 1)) for it in p.items]
            env = costo_envio(lineas, p.total, ciudad)
            if env:
                p.p_envio = env["p_envio"]
                p.d_envio = (env.get("detalle") or "")[:100] or None
                p.envio_carrier = env.get("carrier") or None
                p.envio_id_rate = env.get("id_rate") or None
                p.envio_manual = False
        db.session.commit()
        flash("Información de envío actualizada correctamente", "success")
    else:
        flash("Revisa los datos de envío: el municipio debe elegirse de la lista", "warning")

    return redirect(url_for('pedido.ver', token=token))


@pedido.route("/<token>")
def ver(token):
    p = _pedido_o_404(token)
    
    # Track page view
    from .analytics import track_event, Events
    track_event(Events.PRODUCT_VIEW, {'pedido_id': p.id, 'estado': p.estado})
    
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
    
    datos_envio_validos = bool(p.n_envio and p.dir_envio and p.lugar_envio and p.tel_envio and p.email_envio)
    #solo un pedido viejo, vacío y sin pagar puede completar sus datos; después queda bloqueado
    puede_editar_envio = (not datos_envio_validos
                          and not any([p.n_envio, p.email_envio, p.tel_envio, p.lugar_envio, p.dir_envio])
                          and p.estado in ('PENDIENTE', 'PENDIENTE_ABONO', 'RECHAZADO'))
    return render_template("pedido.html", pedido=p, token=token, pasos_envio=pasos_envio(p),
                            simulacion=current_app.config.get("SIMULACION_PAGO"), form_envio=form_envio,
                            datos_envio_validos=datos_envio_validos, puede_editar_envio=puede_editar_envio)


def _pedido_o_404(token):
    p = get_pedido_por_token(token)
    if not p:
        abort(404)
    return p


@pedido.route("/<token>/simular", methods=["POST"])
def simular(token):
    #solo desarrollo: recorre el mismo camino que una confirmación real de MercadoPago
    if not current_app.config.get("SIMULACION_PAGO"):
        abort(404)
    p = _pedido_o_404(token)
    if request.form.get("resultado") == "aprobado":
        etapa = p.etapa_pago
        #id de pago distinto por etapa: si no, el abono y el saldo simulados chocarían como duplicados
        pago_id = "SIMULADO" if etapa in (None, 'TOTAL') else f"SIMULADO-{etapa}"
        p, pago_nuevo = confirmar_pago(p, pago_id, pago_id, "SIM")
        if pago_nuevo:
            notificar_pago_aprobado(p, token, etapa)
        flash("Pago simulado: aprobado", "success")
    else:
        etapa = p.etapa_pago
        rechazar_pago(p, "SIMULADO" if etapa in (None, 'TOTAL') else f"SIMULADO-{etapa}")
        aviso_pago_rechazado(p, token, etapa)
        flash("Pago simulado: rechazado", "error")
    return redirect(url_for('pedido.ver', token=token))


