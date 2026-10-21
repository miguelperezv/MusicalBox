#panel admin: tallas/colores de un producto y contenido de los packs (rutas del blueprint dashboard, ya protegido)
from flask import abort, flash, redirect, render_template, request, url_for
from .views import dashboard, render_seccion, datos_paginacion
from .models import actualizar_variante, agregar_componente, crear_variante, eliminar_componente, eliminar_variante, db, Variante
from .auditoria import registrar_evento
from .texto import pesos


def _volver(k_producto, err=None, ok=None):
    if err:
        flash(err, "warning")
    elif ok:
        flash(ok, "success")
    return redirect(url_for('dashboard.updateproduct', k_producto=k_producto))


@dashboard.route("/producto/<int:k_producto>/variantes", methods=["POST"])
def variante_nueva(k_producto):
    f = request.form
    v, err = crear_variante(k_producto, f.get("talla", "").strip(), f.get("color", "").strip(), f.get("sku", "").strip(), f.get("stock", type=int))
    if v:
        registrar_evento("variante.creada", "variante", v.id,
                         f"{v.producto.n_producto if v.producto else 'Producto'}: "
                         f"{v.nombre or 'sin talla'} · stock {v.stock}",
                         datos={"k_producto": k_producto})
    return _volver(k_producto, err, "Talla/color agregada")


@dashboard.route("/variante/<int:k_variante>", methods=["POST"])
def variante_editar(k_variante):
    v = db.session.get(Variante, k_variante)
    k_producto = v.k_producto if v else None
    antes = (v.stock if v else None, v.sku if v else None)
    _, err = actualizar_variante(k_variante, request.form.get("stock", type=int), request.form.get("sku", "").strip())
    if v and not err:
        partes = []
        if v.stock != antes[0]:
            partes.append(f"stock {antes[0]} → {v.stock}")
        if (v.sku or None) != (antes[1] or None):
            partes.append(f"SKU {antes[1] or '—'} → {v.sku or '—'}")
        if partes:
            registrar_evento("variante.editada", "variante", v.id,
                             f"{v.producto.n_producto if v.producto else 'Producto'} / {v.nombre or 'sin talla'}: "
                             + ", ".join(partes),
                             datos={"k_producto": k_producto})
    return _volver(k_producto, err, "Stock actualizado")


@dashboard.route("/variante/<int:k_variante>/stock", methods=["POST"])
def variante_stock(k_variante):
    #edición inline desde el listado de productos: solo el stock de la talla (sin tocar el SKU)
    v = db.session.get(Variante, k_variante) or abort(404)
    valor = request.form.get("stock", type=int)
    if valor is None or not (0 <= valor <= 9999):
        return jsonify({"error": "Stock inválido"}), 400
    antes = v.stock
    v.stock = valor
    db.session.commit()
    if antes != valor:
        registrar_evento("variante.editada", "variante", v.id,
                         f"{v.producto.n_producto if v.producto else 'Producto'} / "
                         f"{v.nombre or 'sin talla'}: stock {antes} → {valor}",
                         datos={"k_producto": v.k_producto, "antes": antes, "despues": valor})
    return jsonify({"stock": int(v.stock), "total": int(stock_disponible(v.producto))})


@dashboard.route("/variante/<int:k_variante>/eliminar", methods=["POST"])
def variante_eliminar(k_variante):
    v = db.session.get(Variante, k_variante)
    k_producto = v.k_producto if v else None
    detalle = (f"{v.producto.n_producto if v and v.producto else 'Producto'} / "
               f"{v.nombre or 'sin talla'}") if v else None
    _, err = eliminar_variante(k_variante)
    if not err:
        registrar_evento("variante.eliminada", "variante", k_variante,
                         f"Talla/color eliminada: {detalle}",
                         datos={"k_producto": k_producto})
    return _volver(k_producto, err, "Talla/color eliminada")


@dashboard.route("/producto/<int:k_bundle>/componentes", methods=["POST"])
def componente_nuevo(k_bundle):
    c, err = agregar_componente(k_bundle, request.form.get("componente"), request.form.get("cantidad", type=int))
    if c:
        registrar_evento("pack.actualizado", "pack", k_bundle,
                         f"Pack: agregado {c.componente.n_producto if c.componente else 'producto'} "
                         f"x{c.cantidad}")
    return _volver(k_bundle, err, "Producto agregado al pack")


@dashboard.route("/componente/<int:k_componente>/eliminar", methods=["POST"])
def componente_eliminar(k_componente):
    from .models import ProductoComponente
    c = db.session.get(ProductoComponente, k_componente)
    detalle = (f"Pack: quitado {c.componente.n_producto if c and c.componente else 'producto'}"
               if c else "Pack actualizado")
    k_bundle, err = eliminar_componente(k_componente)
    if not err:
        registrar_evento("pack.actualizado", "pack", k_bundle, detalle)
    return _volver(k_bundle or request.form.get("k_bundle", type=int), err, "Producto quitado del pack")


#órdenes: estado de envío, rechazo manual, nota interna y rótulo (el rótulo es de la orden, con su copia de datos de envío)
from flask import jsonify, render_template, abort
from .models import ESTADOS_CON_ROTULO, Invoice
from .services.order_service import actualizar_envio
from .services.payment_service import rechazar_pago
from .notificaciones import correo_pedido_enviado


@dashboard.route("/pedido/<int:k_invoice>/envio", methods=["POST"])
def pedido_envio(k_invoice):
    #el admin despacha: cambia el estado y, de paso, guarda guía y transportadora
    antes = db.session.get(Invoice, k_invoice)
    estado_antes = antes.estado_envio if antes else None
    guia_antes = antes.guia if antes else None
    carrier_antes = antes.envio_carrier if antes else None
    p = actualizar_envio(k_invoice, request.form.get("estado_envio"),
                         guia=request.form.get("guia"), carrier=request.form.get("carrier"))
    if not p:
        return jsonify({"error": "Solo los pedidos pagados tienen estado de envío"}), 400
    #al marcar ENVIADO se le avisa al comprador con la guía; si el pedido ya estaba ENVIADO,
    #solo se reenvía cuando el admin lo pide (avisar=1) al guardar la guía
    aviso = False
    if p.estado_envio == 'ENVIADO' and (estado_antes != 'ENVIADO' or request.form.get("avisar") == "1"):
        aviso = correo_pedido_enviado(p)
    if (p.estado_envio, p.guia, p.envio_carrier) != (estado_antes, guia_antes, carrier_antes):
        partes = [f"Pedido #{p.id}: {estado_antes or 'sin estado'} → {p.estado_envio}"]
        if p.guia:
            partes.append(f"guía {p.guia}")
        if p.envio_carrier:
            partes.append(p.envio_carrier)
        registrar_evento("pedido.envio", "pedido", p.id, " · ".join(partes),
                         datos={"antes": estado_antes, "despues": p.estado_envio,
                                "guia": p.guia, "carrier": p.envio_carrier})
    return jsonify({"estado_envio": p.estado_envio, "rotulo": p.estado_envio in ESTADOS_CON_ROTULO,
                    "guia": p.guia or "", "carrier": p.envio_carrier or "", "aviso_enviado": bool(aviso)})


@dashboard.route("/pedido/<int:k_invoice>/rotulo")
def pedido_rotulo(k_invoice):
    p = db.session.get(Invoice, k_invoice)
    if not p or p.estado_envio not in ESTADOS_CON_ROTULO:
        abort(404)
    return render_template("rotulo.html", pedido=p)


@dashboard.route("/pedido/<int:k_invoice>/rechazar", methods=["POST"])
def pedido_rechazar(k_invoice):
    p = db.session.get(Invoice, k_invoice) or abort(404)
    if p.estado not in ('PENDIENTE', 'PENDIENTE_ABONO', 'ABONADO'):
        return jsonify({"error": "Solo se pueden rechazar los pedidos pendientes de pago"}), 400
    rechazar_pago(p, "rechazo manual")
    registrar_evento("pedido.rechazado", "pedido", p.id,
                     f"Pedido #{p.id} rechazado manualmente")
    return jsonify({"estado": p.estado})


@dashboard.route("/recordar-saldo", methods=["POST"])
def recordar_saldo():
    """Recordatorio del saldo de una preorden abonada: por correo (uno o masivo) o devuelve el
    enlace de WhatsApp para que el admin lo mande. El historial queda en abono_pago."""
    from .models import AbonoPago, token_pedido
    from .services.payment_service import marcar_recordatorio
    from .notificaciones import correo_saldo_pendiente
    metodo = (request.form.get("metodo") or "email").strip().lower()
    if request.form.get("masivo"):
        pendientes = AbonoPago.query.filter(AbonoPago.estado_abono == 'PAGADO',
                                            AbonoPago.estado_saldo != 'PAGADO').all()
        enviados = 0
        for ab in pendientes:
            p = db.session.get(Invoice, ab.k_invoice)
            if p and correo_saldo_pendiente(p, ab):
                marcar_recordatorio(ab)
                enviados += 1
        registrar_evento("pago.recordatorio_masivo", None, None,
                         f"Recordatorios de saldo por correo: {enviados} enviados")
        flash(f"Recordatorios de saldo enviados: {enviados}", "success")
        return redirect(url_for('dashboard.invoices'))
    k_invoice = request.form.get("k_invoice", type=int)
    p = db.session.get(Invoice, k_invoice) if k_invoice else None
    ab = p.abono if p else None
    if not p or not ab or ab.estado_abono != 'PAGADO' or ab.estado_saldo == 'PAGADO':
        flash("Ese pedido no tiene un saldo pendiente", "warning")
        return redirect(request.referrer or url_for('dashboard.invoices'))
    if metodo == "whatsapp":
        tel = (p.tel_envio or "").strip()
        if not tel:
            return jsonify({"error": "El pedido no tiene celular"}), 400
        from .promocion import whatsapp_enlace
        saldo_total = p.saldo_total
        mensaje = (f"Musical Box: tu pedido #{p.id} está abonado y le queda un saldo de "
                   f"${int(saldo_total):,}".replace(",", ".") +
                   f" (incluye envío). Puedes pagarlo aquí: {url_for('pedido.ver', token=token_pedido(p), _external=True)}")
        marcar_recordatorio(ab)
        registrar_evento("pago.recordatorio", "pedido", p.id,
                         f"Pedido #{p.id}: recordatorio de saldo por WhatsApp")
        return jsonify({"enlace": whatsapp_enlace(tel, mensaje), "saldo": float(saldo_total)})
    if correo_saldo_pendiente(p, ab):
        marcar_recordatorio(ab)
        registrar_evento("pago.recordatorio", "pedido", p.id,
                         f"Pedido #{p.id}: recordatorio de saldo por correo")
        flash(f"Recordatorio enviado a {p.email_envio}", "success")
    else:
        flash("No se pudo enviar el recordatorio (revisa el correo del pedido)", "warning")
    return redirect(request.referrer or url_for('dashboard.invoices'))


@dashboard.route("/pedido/<int:k_invoice>/nota", methods=["POST"])
def pedido_nota(k_invoice):
    p = db.session.get(Invoice, k_invoice) or abort(404)
    antes = p.nota
    p.nota = (request.form.get("nota") or "").strip() or None
    db.session.commit()
    if (antes or None) != (p.nota or None):
        registrar_evento("pedido.nota", "pedido", p.id,
                         f"Pedido #{p.id}: nota interna {'actualizada' if p.nota else 'borrada'}",
                         datos={"antes": antes, "despues": p.nota})
    return jsonify({"nota": p.nota or ""})


#sección Redes del inicio
from . import redes


def _volver_redes(err=None, ok=None):
    flash(err or ok, "warning" if err else "success")
    return redirect(url_for('dashboard.redes_admin'))


@dashboard.route("/redes")
def redes_admin():
    cfg = redes.config_redes()
    avisos = []
    for plat, nombre in redes.PLATAFORMAS.items():
        visibles, c = len(redes.publicaciones_visibles(plat)), cfg[plat]
        if c["n"] > visibles:
            avisos.append(f"{nombre}: pediste mostrar {c['n']} pero solo hay {visibles} visibles; se mostrarán {visibles}.")
        elif c["modo"] == 'random_n_de_m' and c["m"] > visibles:
            avisos.append(f"{nombre}: el sorteo es entre las últimas {c['m']}, pero solo hay {visibles}.")
    pubs = redes.PublicacionSocial.query.order_by(redes.PublicacionSocial.orden, redes.PublicacionSocial.id.desc()).all()
    return render_seccion("redes_admin.html", cfg=cfg, pubs=pubs, avisos=avisos, plataformas=redes.PLATAFORMAS, modos=redes.MODOS)


@dashboard.route("/redes/config", methods=["POST"])
def redes_config():
    f = request.form
    por_plat = {p: (f.get(f"{p}_modo"), f.get(f"{p}_n", type=int), f.get(f"{p}_m", type=int)) for p in redes.PLATAFORMAS}
    err = redes.guardar_config_redes(f.get("activa") == "1", por_plat)
    if not err:
        registrar_evento("ajuste.redes", None, None,
                         "Configuración de redes del inicio actualizada")
    return _volver_redes(err, "Configuración guardada")


@dashboard.route("/redes/nueva", methods=["POST"])
def redes_nueva():
    pub, err = redes.crear_publicacion(request.form.get("plataforma"), request.form.get("url"))
    if pub:
        registrar_evento("ajuste.redes", None, None,
                         f"Publicación agregada: {pub.plataforma}")
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
    registrar_evento("ajuste.redes", None, None,
                     f"Publicación editada: {pub.plataforma}")
    return _volver_redes(pub.error_embed, "Publicación actualizada")


@dashboard.route("/redes/<int:k>/activo", methods=["POST"])
def redes_activo(k):
    pub = db.session.get(redes.PublicacionSocial, k) or abort(404)
    pub.activo = not pub.activo
    db.session.commit()
    registrar_evento("ajuste.redes", None, None,
                     f"Publicación {'activada' if pub.activo else 'desactivada'}: {pub.plataforma}")
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


# Notificaciones admin
from .redes import Configuracion

NOTIF_OPCIONES = {
    'avisos.pago_aprobado': ('Pago aprobado', 'Siempre activo: avisa cuando el pago se aprueba (webhook o process_payment)', True),
    'avisos.pago_rechazado': ('Pago rechazado', 'Avisar cuando el pago es rechazado', False),
    'avisos.pedido_creado': ('Nuevo pedido (antes de pagar)', 'Avisar al crear el pedido, aunque aún no ha pagado', False),
}


def _volver_notif(err=None, ok=None):
    flash(err or ok, "warning" if err else "success")
    return redirect(url_for('dashboard.notificaciones_admin'))


@dashboard.route("/notificaciones")
def notificaciones_admin():
    cfg = {}
    for clave, (label, help_text, always_on) in NOTIF_OPCIONES.items():
        row = db.session.get(Configuracion, clave)
        cfg[clave] = {
            'label': label,
            'help': help_text,
            'always_on': always_on,
            'valor': (row.valor if row else '0') == '1',
        }
    return render_seccion("notificaciones_admin.html", cfg=cfg)


@dashboard.route("/notificaciones/guardar", methods=["POST"])
def notificaciones_guardar():
    for clave, (_, _, always_on) in NOTIF_OPCIONES.items():
        if always_on:
            continue  # no se toca, siempre activo
        activado = request.form.get(clave) == "1"
        row = db.session.get(Configuracion, clave)
        if activado:
            if not row:
                row = Configuracion(clave=clave, valor='1')
                db.session.add(row)
            else:
                row.valor = '1'
        else:
            if row:
                row.valor = '0'
    db.session.commit()
    registrar_evento("ajuste.notificaciones", None, None,
                     "Preferencias de avisos del panel actualizadas")
    return _volver_notif(ok="Configuración de notificaciones guardada")


#listados del catálogo: ver todo y entrar a editar con un clic (en vez de buscar escribiendo)
from .models import Producto, Lanzamiento, get_artist_by_release, stock_disponible, es_original, es_preorden


@dashboard.route("/productos")
def productos_admin():
    q = Producto.query
    f_lanzamiento = request.args.get("lanzamiento", type=int)
    if f_lanzamiento:
        q = q.filter_by(k_lanzamiento=f_lanzamiento)
    f_categoria = request.args.get("categoria", "").strip()
    if f_categoria:
        q = q.filter_by(k_categoria=f_categoria)
    qtext = request.args.get("q", "").strip()
    if qtext:
        like = f"%{qtext}%"
        q = (q.outerjoin(Lanzamiento, Producto.k_lanzamiento == Lanzamiento.id)
             .filter(db.or_(Producto.n_producto.ilike(like), Lanzamiento.n_lanzamiento.ilike(like))))
    q = q.order_by(Producto.k_lanzamiento, Producto.id)

    def fila(p):
        return {"p": p, "artista": get_artist_by_release(p.k_lanzamiento) if p.k_lanzamiento else None,
                "stock": stock_disponible(p), "original": es_original(p),
                "preorden": es_preorden(p)}

    f_stock = request.args.get("stock", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 50
    if f_stock:
        #el stock se calcula (packs/variantes): hay que filtrar antes de paginar
        filas = [fila(p) for p in q.all()]
        if f_stock == "agotado":
            filas = [f for f in filas if f["stock"] <= 0]
        elif f_stock == "bajo":
            filas = [f for f in filas if f["stock"] <= 3]
        pag = datos_paginacion("dashboard.productos_admin", page, len(filas), per_page)
        inicio = (pag["page"] - 1) * per_page
        filas = filas[inicio:inicio + per_page]
    else:
        total = q.count()
        pag = datos_paginacion("dashboard.productos_admin", page, total, per_page)
        inicio = (pag["page"] - 1) * per_page
        filas = [fila(p) for p in q.offset(inicio).limit(per_page).all()]
    categorias = sorted({p.k_categoria for p in Producto.query.all() if p.k_categoria})
    return render_seccion("productos_admin.html", filas=filas, categorias=categorias,
                           lanzamientos=Lanzamiento.query.order_by(Lanzamiento.n_lanzamiento).all(),
                           f_lanzamiento=f_lanzamiento or "", f_categoria=f_categoria,
                           f_stock=f_stock, q=qtext, pag=pag)


@dashboard.route("/lanzamientos")
def lanzamientos_admin():
    qtext = request.args.get("q", "").strip()
    q = Lanzamiento.query
    if qtext:
        q = q.filter(Lanzamiento.n_lanzamiento.ilike(f"%{qtext}%"))
    q = q.order_by(db.desc(Lanzamiento.f_lanzamiento))
    per_page = 50
    pag = datos_paginacion("dashboard.lanzamientos_admin", request.args.get("page", 1, type=int), q.count(), per_page)
    inicio = (pag["page"] - 1) * per_page
    filas = [{"l": l, "artista": get_artist_by_release(l.id),
              "productos": Producto.query.filter_by(k_lanzamiento=l.id).count()}
             for l in q.offset(inicio).limit(per_page).all()]
    return render_seccion("lanzamientos_admin.html", filas=filas, q=qtext, pag=pag)


#edición rápida desde los listados: stock/precio de producto y campos de lanzamiento,
#sin abrir la página de edición completa (lo estructural sigue por "Editar")
from datetime import date as fecha_date


@dashboard.route("/producto/<int:k_producto>/stock", methods=["POST"])
def producto_stock(k_producto):
    p = db.session.get(Producto, k_producto) or abort(404)
    if p.tipo == 'BUNDLE' or p.variantes:
        return jsonify({"error": "Tiene tallas o es un pack: el stock se cambia en Editar"}), 400
    valor = request.form.get("stock", type=int)
    if valor is None or not (0 <= valor <= 9999):
        return jsonify({"error": "Stock inválido"}), 400
    antes = p.stock
    p.stock = valor
    db.session.commit()
    if antes != valor:
        registrar_evento("producto.stock", "producto", p.id,
                         f"{p.n_producto}: stock {antes} → {valor}",
                         datos={"antes": antes, "despues": valor})
    return jsonify({"stock": int(p.stock)})


@dashboard.route("/producto/<int:k_producto>/precio", methods=["POST"])
def producto_precio(k_producto):
    p = db.session.get(Producto, k_producto) or abort(404)
    valor = request.form.get("precio", type=int)
    if valor is None or not (1 <= valor <= 99999999):
        return jsonify({"error": "Precio inválido (en pesos, sin puntos)"}), 400
    antes = p.p_producto or 0
    p.p_producto = valor
    db.session.commit()
    if antes != valor:
        registrar_evento("producto.precio", "producto", p.id,
                         f"{p.n_producto}: {pesos(antes)} → {pesos(valor)}",
                         datos={"antes": int(antes), "despues": valor})
    return jsonify({"precio": int(p.p_producto)})


CAMPOS_LANZAMIENTO = {
    "f_lanzamiento": "Fecha",
    "i_lanzamiento": "Portada (URL)",
    "url_social": "Post (URL)",
}


@dashboard.route("/producto/<int:k_producto>/preorden", methods=["POST"])
def producto_preorden(k_producto):
    p = db.session.get(Producto, k_producto) or abort(404)
    if p.tipo == 'BUNDLE' or p.variantes:
        return jsonify({"error": "El preorden directo solo aplica a sueltos sin tallas"}), 400
    p.preorden = not p.preorden
    db.session.commit()
    registrar_evento("producto.preorden", "producto", p.id,
                     f"{p.n_producto}: preorden {'activada' if p.preorden else 'desactivada'}")
    return jsonify({"preorden": p.preorden, "es_preorden": es_preorden(p)})


@dashboard.route("/lanzamiento/<int:k_lanzamiento>/preorden", methods=["POST"])
def lanzamiento_preorden(k_lanzamiento):
    l = db.session.get(Lanzamiento, k_lanzamiento) or abort(404)
    l.preorden = not l.preorden
    db.session.commit()
    registrar_evento("lanzamiento.preorden", "lanzamiento", l.id,
                     f"{l.n_lanzamiento}: preorden {'activada' if l.preorden else 'desactivada'}")
    return jsonify({"preorden": l.preorden})


@dashboard.route("/lanzamiento/<int:k_lanzamiento>/<campo>", methods=["POST"])
def lanzamiento_campo(k_lanzamiento, campo):
    if campo not in CAMPOS_LANZAMIENTO:
        abort(404)
    l = db.session.get(Lanzamiento, k_lanzamiento) or abort(404)
    valor = (request.form.get("valor") or "").strip()
    antes = l.f_lanzamiento if campo == "f_lanzamiento" else getattr(l, campo)
    if campo == "f_lanzamiento":
        if valor:
            try:
                l.f_lanzamiento = fecha_date.fromisoformat(valor)
            except ValueError:
                return jsonify({"error": "Fecha inválida (se espera AAAA-MM-DD)"}), 400
        else:
            l.f_lanzamiento = None
    else:
        setattr(l, campo, valor or None)
    db.session.commit()
    if campo == "f_lanzamiento":
        detalle = f"{l.n_lanzamiento}: fecha {antes or '—'} → {l.f_lanzamiento or '—'}"
    else:
        detalle = f"{l.n_lanzamiento}: {CAMPOS_LANZAMIENTO[campo].lower()} actualizada"
    registrar_evento("lanzamiento.campo", "lanzamiento", l.id, detalle,
                     datos={"campo": campo, "antes": str(antes or ''), "despues": str(valor)})
    return jsonify({campo: (l.f_lanzamiento.isoformat() if campo == "f_lanzamiento" else getattr(l, campo) or "")})


#sección Tema de temporada del logotipo (ver app/store/temporadas.py)
from datetime import datetime as _datetime

from . import temporadas


def _volver_tema(err=None, ok=None):
    flash(err or ok, "warning" if err else "success")
    return redirect(url_for('dashboard.tema_admin'))


@dashboard.route("/tema")
def tema_admin():
    modo, forzado = temporadas.config_tema()
    hoy = _datetime.now(temporadas.BOGOTA).date()
    tema_hoy = temporadas.tema_por_fecha(hoy)
    proximo, fecha_proximo, dias = temporadas.proximo_tema()
    if modo == "forzado":
        activo = forzado
    elif modo == "apagado":
        activo = None
    else:
        activo = tema_hoy
    return render_seccion("tema_admin.html", modo=modo, forzado=forzado, activo=activo,
                           tema_hoy=tema_hoy, temas=list(temporadas.TEMAS), nombres=temporadas.NOMBRES,
                           ventanas=temporadas.VENTANAS,
                           proximo=(proximo, temporadas.fecha_larga(fecha_proximo) if fecha_proximo else None, dias))


@dashboard.route("/tema/config", methods=["POST"])
def tema_config():
    err = temporadas.guardar_config_tema(request.form.get("modo"), request.form.get("forzado"))
    if not err:
        registrar_evento("ajuste.tema", None, None,
                         f"Tema de temporada: {request.form.get('modo') or 'sin modo'}")
    return _volver_tema(err, "Listo, quedó guardado")


@dashboard.route("/tema/marcar/<clave>", methods=["POST"])
def tema_marcar(clave):
    #el botón de cada recuadro: forzar ese tema (o dejar sin tema, que es apagarlo)
    if clave == "ninguno":
        err, ok = temporadas.guardar_config_tema("apagado"), "Listo: el logotipo queda sin adornos"
    else:
        err = temporadas.guardar_config_tema("forzado", clave)
        ok = f"Listo: se muestra {temporadas.NOMBRES.get(clave, clave)} (míralo en la tienda)"
    if not err:
        registrar_evento("ajuste.tema", None, None,
                         f"Tema: {temporadas.NOMBRES.get(clave, 'sin adornos')}")
    return _volver_tema(err, ok)


@dashboard.route("/tema/auto", methods=["POST"])
def tema_auto():
    temporadas.guardar_config_tema("auto")
    registrar_evento("ajuste.tema", None, None, "Tema: automático por fecha")
    return _volver_tema(ok="Listo: vuelve a automático, según la fecha")


@dashboard.route("/tema/vista/<clave>")
def tema_vista(clave):
    #vista previa mínima (logotipo del navbar + vinilo) para los recuadros del panel
    if clave == "ninguno":
        return render_template("_tema_vista.html", clave=None, nombre="Sin tema")
    if clave not in temporadas.TEMAS:
        abort(404)
    return render_template("_tema_vista.html", clave=clave, nombre=temporadas.NOMBRES[clave])
