#panel admin: tallas/colores de un producto y contenido de los packs (rutas del blueprint dashboard, ya protegido)
from flask import flash, redirect, request, url_for
from .views import dashboard
from .models import actualizar_variante, agregar_componente, crear_variante, eliminar_componente, eliminar_variante, db, Variante


def _volver(k_producto, err=None, ok=None):
    if err:
        flash(err, "warning")
    elif ok:
        flash(ok, "success")
    return redirect(url_for('dashboard.updateproduct', k_producto=k_producto))


@dashboard.route("/producto/<int:k_producto>/variantes", methods=["POST"])
def variante_nueva(k_producto):
    f = request.form
    _, err = crear_variante(k_producto, f.get("talla", "").strip(), f.get("color", "").strip(), f.get("sku", "").strip(), f.get("stock", type=int))
    return _volver(k_producto, err, "Talla/color agregada")


@dashboard.route("/variante/<int:k_variante>", methods=["POST"])
def variante_editar(k_variante):
    v = db.session.get(Variante, k_variante)
    k_producto = v.k_producto if v else None
    _, err = actualizar_variante(k_variante, request.form.get("stock", type=int), request.form.get("sku", "").strip())
    return _volver(k_producto, err, "Stock actualizado")


@dashboard.route("/variante/<int:k_variante>/eliminar", methods=["POST"])
def variante_eliminar(k_variante):
    v = db.session.get(Variante, k_variante)
    k_producto = v.k_producto if v else None
    _, err = eliminar_variante(k_variante)
    return _volver(k_producto, err, "Talla/color eliminada")


@dashboard.route("/producto/<int:k_bundle>/componentes", methods=["POST"])
def componente_nuevo(k_bundle):
    _, err = agregar_componente(k_bundle, request.form.get("componente"), request.form.get("cantidad", type=int))
    return _volver(k_bundle, err, "Producto agregado al pack")


@dashboard.route("/componente/<int:k_componente>/eliminar", methods=["POST"])
def componente_eliminar(k_componente):
    k_bundle, err = eliminar_componente(k_componente)
    return _volver(k_bundle or request.form.get("k_bundle", type=int), err, "Producto quitado del pack")


#órdenes: estado de envío y rótulo (el rótulo es de la orden, con su copia de datos de envío)
from flask import jsonify, render_template, abort
from .models import ESTADOS_CON_ROTULO, Invoice, actualizar_envio


@dashboard.route("/pedido/<int:k_invoice>/envio", methods=["POST"])
def pedido_envio(k_invoice):
    p = actualizar_envio(k_invoice, request.form.get("estado_envio"))
    if not p:
        return jsonify({"error": "Solo los pedidos pagados tienen estado de envío"}), 400
    return jsonify({"estado_envio": p.estado_envio, "rotulo": p.estado_envio in ESTADOS_CON_ROTULO})


@dashboard.route("/pedido/<int:k_invoice>/rotulo")
def pedido_rotulo(k_invoice):
    p = db.session.get(Invoice, k_invoice)
    if not p or p.estado_envio not in ESTADOS_CON_ROTULO:
        abort(404)
    return render_template("rotulo.html", pedido=p)
