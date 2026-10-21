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
    
    needs_shipping_modal = not (p.n_envio and p.dir_envio and p.lugar_envio and p.tel_envio and p.email_envio)
    return render_template("pedido.html", pedido=p, token=token, pasos_envio=pasos_envio(p),
                            simulacion=current_app.config.get("SIMULACION_PAGO"), form_envio=form_envio)


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


