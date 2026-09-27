#checkout sin cuenta y seguimiento de pedidos por enlace /pedido/<token>
from decimal import Decimal
import requests
from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for, abort
from .forms import CheckoutForm
from .models import (METODOS_PAGO, crear_pedido, get_pedido_por_token, referencia_epayco, confirmar_pago,
                     rechazar_pago, validar_carrito)
from .views import before_request, purchase
from ..db import db


pedido = Blueprint('pedido', __name__, url_prefix='/pedido')
pedido.before_request(before_request)


@purchase.route("/checkout", methods=["GET", "POST"])
def checkout():
    lineas, total, errores = validar_carrito(session.get("purchase"))
    if errores:
        for e in errores:
            flash(e, "warning")
        return redirect(url_for('purchase.summary'))

    form = CheckoutForm()
    form.metodo_pago.choices = METODOS_PAGO
    if request.method == 'GET':
        #prellenado: cuenta con sesión, o los datos de la última compra en este navegador
        previo = session.get("checkout_datos") or {}
        if g.user:
            previo = {"nombre": f"{g.user.get('n_usuario', '')} {g.user.get('ape_usuario', '')}".strip(),
                      "email": g.user.get("email_usuario"), "telefono": g.user.get("cel_usuario"),
                      "ciudad": g.user.get("lugar_usuario"), "direccion": g.user.get("dir_usuario"),
                      "barrio": g.user.get("barrio_usuario"), **{k: v for k, v in previo.items() if v and k == "metodo_pago"}}
        for campo, valor in previo.items():
            if valor and campo in form:
                form[campo].data = valor

    if form.validate_on_submit():
        datos = {campo: form[campo].data for campo in ["nombre", "email", "telefono", "ciudad", "direccion", "barrio", "metodo_pago"]}
        nuevo, token, errores = crear_pedido(session.get("purchase"), datos, k_usuario=g.user["id"] if g.user else None)
        if errores:
            for e in errores:
                flash(e, "warning")
            return redirect(url_for('purchase.summary'))
        session["purchase"] = {}
        session["checkout_datos"] = datos
        return redirect(url_for('pedido.ver', token=token))

    return render_template("checkout.html", form=form, lineas=lineas, total=total)


def _pedido_o_404(token):
    p = get_pedido_por_token(token)
    if not p:
        abort(404)
    return p


@pedido.route("/<token>")
def ver(token):
    p = _pedido_o_404(token)
    return render_template("pedido.html", pedido=p, token=token, referencia=referencia_epayco(p),
                           simulacion=current_app.config.get("EPAYCO_SIMULACION"))


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
        confirmar_pago(p, ref_payco, data.get("x_id_factura"), data.get("x_franchise"))
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
        confirmar_pago(p, "SIMULADO", "SIMULADO", "SIM")
        flash("Pago simulado: aprobado", "success")
    else:
        rechazar_pago(p, "SIMULADO")
        flash("Pago simulado: rechazado", "error")
    return redirect(url_for('pedido.ver', token=token))
