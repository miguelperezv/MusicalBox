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


#sección Redes del inicio
from . import redes


def _volver_redes(err=None, ok=None):
    flash(err or ok, "warning" if err else "success")
    return redirect(url_for('dashboard.redes_admin'))


@dashboard.route("/redes")
def redes_admin():
    cfg = redes.config_redes()
    visibles = len(redes.publicaciones_visibles())
    avisos = []
    if cfg["n"] > visibles:
        avisos.append(f"Pediste mostrar {cfg['n']} publicaciones pero solo hay {visibles} activas sin error: se mostrarán {visibles}.")
    if cfg["modo"] == 'random_n_de_m' and cfg["m"] > visibles:
        avisos.append(f"El sorteo es entre las últimas {cfg['m']}, pero solo hay {visibles} disponibles.")
    pubs = redes.PublicacionSocial.query.order_by(redes.PublicacionSocial.orden, redes.PublicacionSocial.id.desc()).all()
    return render_template("redes_admin.html", cfg=cfg, pubs=pubs, avisos=avisos, plataformas=redes.PLATAFORMAS, modos=redes.MODOS)


@dashboard.route("/redes/config", methods=["POST"])
def redes_config():
    f = request.form
    err = redes.guardar_config_redes(f.get("activa") == "1", f.get("modo"), f.get("n", type=int), f.get("m", type=int))
    return _volver_redes(err, "Configuración guardada")


@dashboard.route("/redes/nueva", methods=["POST"])
def redes_nueva():
    pub, err = redes.crear_publicacion(request.form.get("plataforma"), request.form.get("url"))
    if pub and pub.error_embed:
        return _volver_redes(f"Guardada, pero no se mostrará: {pub.error_embed}")
    return _volver_redes(err, "Publicación agregada")


@dashboard.route("/redes/<int:k>/editar", methods=["POST"])
def redes_editar(k):
    pub = db.session.get(redes.PublicacionSocial, k) or abort(404)
    url, id_externo, err = redes.leer_url(request.form.get("plataforma"), request.form.get("url"))
    if err:
        return _volver_redes(err)
    pub.plataforma, pub.url, pub.id_externo = request.form.get("plataforma"), url, id_externo
    redes.verificar_embed(pub)
    db.session.commit()
    return _volver_redes(pub.error_embed, "Publicación actualizada")


@dashboard.route("/redes/<int:k>/activo", methods=["POST"])
def redes_activo(k):
    pub = db.session.get(redes.PublicacionSocial, k) or abort(404)
    pub.activo = not pub.activo
    db.session.commit()
    return _volver_redes(ok="Publicación " + ("activada" if pub.activo else "desactivada"))


@dashboard.route("/redes/<int:k>/mover/<direccion>", methods=["POST"])
def redes_mover(k, direccion):
    redes.mover_publicacion(db.session.get(redes.PublicacionSocial, k) or abort(404), direccion)
    return redirect(url_for('dashboard.redes_admin'))


@dashboard.route("/redes/<int:k>/verificar", methods=["POST"])
def redes_verificar(k):
    pub = db.session.get(redes.PublicacionSocial, k) or abort(404)
    redes.verificar_embed(pub)
    db.session.commit()
    return _volver_redes(pub.error_embed, "El post se ve bien")
