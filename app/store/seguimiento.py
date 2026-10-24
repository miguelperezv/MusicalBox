# /seguimiento: el comprador perdió su enlace (cerró la pestaña, borró el WhatsApp de la
# cotización) y lo recupera. Pide el correo Y el teléfono con los que compró: los enlaces se
# mandan SOLO a ese correo, nunca se muestran en pantalla. Así nadie más ve un pedido ajeno,
# aunque se sepa el correo de otra persona.
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired, Email, Length

from ..db import db
from .models import Invoice, items_efectivos, pedidos_de, solicitudes_de, token_pedido, token_solicitud
from .notificaciones import correo_enlaces_seguimiento
from .views import before_request
from ..limiter import limiter

seguimiento = Blueprint("seguimiento", __name__, url_prefix="/seguimiento")
seguimiento.before_request(before_request)


class SeguimientoForm(FlaskForm):
    email = StringField("Correo", validators=[DataRequired(), Email(), Length(max=100)])
    telefono = StringField("Teléfono", validators=[DataRequired(), Length(max=20)])


def _resumen_pedido(p):
    cuantos = sum(int(it.cant_item or 0) for it in p.items)
    donde = p.estado_envio if p.estado == 'PAGADO' and p.estado_envio else p.estado
    return "%d producto%s · %s" % (cuantos, "" if cuantos == 1 else "s", donde)


def _fila_pedido(p):
    return {"id": p.id, "estado": p.estado_envio if p.estado == 'PAGADO' and p.estado_envio else p.estado,
            "resumen": _resumen_pedido(p),
            "enlace": url_for("pedido.ver", token=token_pedido(p), _external=True)}


def _fila_solicitud(s):
    #una solicitud cotizada se puede pagar con su enlace; una ya comprada lleva al pedido
    enlace = None
    if s.estado == 'COTIZADA' and s.token_hash:
        enlace = url_for("solicitud.confirmar", token=token_solicitud(s), _external=True)
    elif s.estado == 'COMPRADA' and s.k_invoice:
        pedido = db.session.get(Invoice, s.k_invoice)
        if pedido:
            enlace = url_for("pedido.ver", token=token_pedido(pedido), _external=True)
    items = items_efectivos(s)
    nombres = ", ".join((it.nombre or "")[:40] for it in items[:2])
    if len(items) > 2:
        nombres += " y más"
    return {"id": s.id, "estado": s.estado, "resumen": nombres, "enlace": enlace}


@seguimiento.route("/", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def buscar():
    form = SeguimientoForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        pedidos = [_fila_pedido(p) for p in pedidos_de(email, form.telefono.data)]
        solicitudes = [_fila_solicitud(s) for s in solicitudes_de(email, form.telefono.data)]
        if not pedidos and not solicitudes:
            flash("No encontramos compras con ese correo y ese teléfono. Escribe el teléfono tal como lo "
                  "pusiste al comprar (con o sin indicativo) o escríbenos y lo buscamos.", "warning")
        else:
            correo_enlaces_seguimiento(email, pedidos, solicitudes)
            flash("Te mandamos tus enlaces a %s. Revisa también el correo no deseado (spam)." % email, "success")
            return redirect(url_for("seguimiento.buscar"))
    return render_template("seguimiento.html", form=form)
