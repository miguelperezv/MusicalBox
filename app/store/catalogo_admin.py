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
