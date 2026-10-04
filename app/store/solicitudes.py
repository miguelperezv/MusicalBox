#pedidos a la medida: solicitud (uno o más productos + contacto) -> cotización por ítem -> confirmar compra
import re
from urllib.parse import quote

from flask import Blueprint, flash, request, g, render_template, redirect, url_for, jsonify, abort
from .forms import RegistroSolicitudForm, CheckoutForm, CotizacionRapidaForm
from .models import (create_solicitud, get_all_solicitudes, update_estado_solicitud, get_catalogo_solicitud, get_product_by_id,
                     get_usuario_por_email, cotizar_solicitud, get_solicitud_por_token, datos_envio_previos, crear_pedido,
                     items_efectivos, get_categorias, get_all_releases, buscar_o_crear_lanzamiento,
                     buscar_o_crear_lanzamiento_spotify,
                     ESTADOS_SOLICITUD, Solicitud, SolicitudItem, Lanzamiento)
from .musicapi import buscar_albumes_spotify
from .envio import costo_envio, lineas_desde_cats
from ..db import db
from .views import before_request, admin_required
from .notif_admin import aviso_solicitud, aviso_cotizacion, aviso_pedido_creado


solicitud = Blueprint('solicitud', __name__, url_prefix='/solicitud')
solicitud.before_request(before_request)

_ITEM_RE = re.compile(r"^items\[(\d+)\]\[(\w+)\]$")


def _items_del_formulario():
    #filas del formulario público: items[N][nombre|categoria|cantidad|descripcion|producto_id]
    filas = {}
    for clave, valor in request.form.items():
        m = _ITEM_RE.match(clave)
        if m:
            filas.setdefault(int(m.group(1)), {})[m.group(2)] = (valor or '').strip()
    items = []
    for i in sorted(filas):
        fila = filas[i]
        nombre = (fila.get("nombre") or '').strip()
        if not nombre:
            continue
        k_producto = fila.get("producto_id")
        k_producto = int(k_producto) if (k_producto or '').isdigit() else None
        if k_producto and not get_product_by_id(k_producto):
            k_producto = None
        cantidad = fila.get("cantidad")
        cantidad = int(cantidad) if (cantidad or '').isdigit() else 1
        items.append({"nombre": nombre, "descripcion": fila.get("descripcion"),
                      "categoria": fila.get("categoria"), "cantidad": cantidad, "k_producto": k_producto})
    return items


@solicitud.route("/", methods=["GET", "POST"])
def nueva():
    form = RegistroSolicitudForm()
    if request.method == 'GET' and g.user:
        form.celular.data = g.user.get("cel_usuario")
        form.email.data = g.user.get("email_usuario")

    if form.validate_on_submit():
        items = _items_del_formulario()
        if not items:
            flash("Cuéntanos qué producto buscas", "warning")
        else:
            email = (form.email.data or '').strip().lower() or None
            #se asocia a una cuenta si ya existe; si no, el comprador se crea al confirmar la compra
            usuario = get_usuario_por_email(g.user["email_usuario"]) if g.user else (get_usuario_por_email(email) if email else None)
            s, err = create_solicitud(usuario.id if usuario else None, items, form.celular.data.strip(), email,
                                      lugar=form.ciudad.data)
            if s:
                aviso_solicitud(s)
                flash("¡Recibimos tu solicitud #" + str(s.id) + "! Te escribiremos por WhatsApp con precio y tiempos.", "success")
                return redirect(url_for('home.index'))
            flash("Error registrando la solicitud: " + str(err), "error")
    elif request.method == 'POST':
        flash("Revisa los campos del formulario", "warning")

    return render_template('solicitud.html', form=form, categorias=(get_categorias() or []) + ['OTRO'])


@solicitud.route("/productos")
def productos():
    return jsonify(get_catalogo_solicitud())


@solicitud.route("/solicitudes")
@admin_required
def lista():
    portadas = {}
    for l in Lanzamiento.query.filter(Lanzamiento.i_lanzamiento.isnot(None)).all():
        portadas[str(l.id)] = l.i_lanzamiento
    return render_template('solicitudes.html',
                           solicitudes=[(s, items_efectivos(s)) for s in get_all_solicitudes()],
                           estados=ESTADOS_SOLICITUD, portadas=portadas)


@solicitud.route("/lanzamiento_spotify", methods=["GET", "POST"])
@admin_required
def lanzamiento_spotify():
    #busca álbumes en Spotify y, al elegir uno, lo guarda (o lo recupera) para asociarlo a un ítem
    if request.method == "GET":
        return jsonify(buscar_albumes_spotify(request.args.get("q", "")))
    datos = request.get_json(silent=True) or request.form
    l, nuevo = buscar_o_crear_lanzamiento_spotify({
        "external_id": datos.get("external_id"),
        "n_lanzamiento": datos.get("nombre"),
        "artista": datos.get("artista"),
        "f_lanzamiento": datos.get("fecha"),
        "i_lanzamiento": datos.get("portada"),
        "external_url": datos.get("url")})
    if not l:
        return jsonify({"error": "Elige un álbum de la lista"}), 400
    return jsonify({"id": l.id, "nombre": l.n_lanzamiento, "portada": l.i_lanzamiento, "nuevo": nuevo})


@solicitud.route("/<int:id>/estado", methods=["POST"])
@admin_required
def estado(id):
    s = update_estado_solicitud(id, request.form.get("estado"))
    if s:
        return jsonify({"id": s.id, "estado": s.estado})
    return jsonify({"error": "No se pudo actualizar la solicitud"}), 400


def _precio_cop(valor):
    return "${:,}".format(int(valor)).replace(",", ".")


def _respuesta_cotizar(s, token):
    #el enlace solo se puede ver ahora (en la BD queda su hash); se envía al cliente por WhatsApp o correo
    enlace = url_for('solicitud.confirmar', token=token, _external=True)
    items = items_efectivos(s)
    lineas, preview = [], None
    for it in items:
        n = int(it.cantidad or 1)
        if it.producto:
            lanz = it.producto.lanzamiento
            label = " - ".join(x for x in [lanz.n_lanzamiento.title() if lanz else '', it.producto.n_producto or ''] if x) or it.nombre
        else:
            label = it.nombre
        fila = f"• {n} × {label}" + (f" ({it.descripcion})" if it.descripcion else "")
        if n > 1:
            fila += f"\n   {_precio_cop(it.precio_unit)} c/u  →  {_precio_cop(it.precio_unit * n)}"
        lineas.append(fila)
        if not preview:
            l = it.lanzamiento or (it.producto.lanzamiento if it.producto else None)
            if l and l.i_lanzamiento:
                preview = l.i_lanzamiento
    total = sum(int(it.precio_unit or 0) * int(it.cantidad or 1) for it in items)
    partes = ["¡Hola! Tu pedido a la medida en Musical Box quedó así:", "", *lineas, "", f"Total: {_precio_cop(total)}"]
    #si el cliente dejó su municipio, se le estima el envío para que vea el total real
    if s.lugar_solicitud:
        cats = "|".join(f"{(it.producto.k_categoria if it.producto else it.categoria) or 'OTRO'}:{int(it.cantidad or 1)}"
                        for it in items)
        env = costo_envio(lineas_desde_cats(cats), total, s.lugar_solicitud)
        if env:
            if env["p_envio"] == 0:
                partes.append(f"¡Y el envío a {s.lugar_solicitud} es gratis!")
            else:
                partes.append(f"Envío estimado a {s.lugar_solicitud}: {_precio_cop(env['p_envio'])} · total {_precio_cop(total + env['p_envio'])}")
    if s.d_cotizacion:
        partes.append(s.d_cotizacion)
    #el preview de WhatsApp sale de la página de confirmar (portada del disco o logo de Musical Box)
    partes += ["", "Confirma tu compra y datos de envío aquí:", enlace]
    mensaje = "\n".join(partes)
    cel = "".join(c for c in (s.cel_contacto or "") if c.isdigit())
    return {"id": s.id, "enlace": enlace, "preview": preview, "mensaje": mensaje,
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
    s, err = create_solicitud(usuario.id if usuario else None,
                              [{"nombre": nombre_limpio, "cantidad": form.cantidad.data or 1, "k_producto": k_producto}],
                              form.celular.data.strip(), email)
    if not s:
        return jsonify({"error": err or "No se pudo registrar"}), 400
    if form.precio.data:
        it = s.items[0]
        token, cerr = cotizar_solicitud(s.id,
                                        [{"k_producto": it.k_producto,
                                          "k_lanzamiento": it.producto.k_lanzamiento if it.producto else None,
                                          "cantidad": it.cantidad, "precio": form.precio.data}])
        if cerr:
            return jsonify({"error": cerr, "id": s.id, "estado": s.estado}), 400
        aviso_cotizacion(s, token)
        return jsonify(_respuesta_cotizar(s, token))
    return jsonify({"id": s.id, "estado": s.estado})


@solicitud.route("/<int:id>/cotizar", methods=["POST"])
@admin_required
def cotizar(id):
    s = db.session.get(Solicitud, id)
    if not s:
        return jsonify({"error": "La solicitud no existe"}), 400
    items = items_efectivos(s)
    #retirar los ítems que el admin marcó: se quitan de la solicitud y no van en la cotización
    retiros = [i for i in range(len(items)) if request.form.get(f"item_{i}_retirar") == "on"]
    if retiros:
        if any(not isinstance(items[i], SolicitudItem) for i in retiros):
            return jsonify({"error": "No se puede retirar un ítem de una solicitud antigua: cancela la solicitud si ya no le interesa"}), 400
        if len(items) - len(retiros) < 1:
            return jsonify({"error": "Queda al menos un ítem: si el pedido ya no le interesa, marca la solicitud como cancelada"}), 400
        for i in retiros:
            db.session.delete(items[i])
        db.session.commit()
    #una línea por ítem que queda: cantidad, producto del catálogo (opcional), lanzamiento (opcional) y precio
    lineas = []
    for i in range(len(items)):
        if i in retiros:
            continue
        k_producto = (request.form.get(f"item_{i}_producto") or "").split(".")[0].strip()
        #lanzamiento: "id. Nombre" usa el id; un texto libre se busca o crea al vuelo
        k_lanzamiento, _ = buscar_o_crear_lanzamiento(request.form.get(f"item_{i}_lanzamiento"))
        lineas.append({"k_producto": int(k_producto) if k_producto.isdigit() else None,
                       "k_lanzamiento": k_lanzamiento,
                       "cantidad": request.form.get(f"item_{i}_cantidad", type=int),
                       "precio": request.form.get(f"item_{i}_precio", type=int)})
    token, err = cotizar_solicitud(id, lineas, request.form.get("d_cotizacion"))
    if err:
        return jsonify({"error": err}), 400
    aviso_cotizacion(s, token)
    return jsonify(_respuesta_cotizar(s, token))


@solicitud.route("/confirmar/<token>", methods=["GET", "POST"])
def confirmar(token):
    #paso 2 del flujo: el cliente ya recibió precio y tiempos; aquí se piden datos de envío y se paga
    s = get_solicitud_por_token(token)
    if not s:
        abort(404)
    if s.estado == 'COMPRADA':
        flash("Esta solicitud ya fue pagada. Revisa el enlace del pedido que llegó a tu correo.", "info")
        return redirect(url_for('home.index'))
    items = items_efectivos(s)
    if not s.token_hash or not all(it.precio_unit for it in items):
        abort(404)

    form = CheckoutForm()
    previos = datos_envio_previos(s.email_contacto or (s.usuario.email_usuario if s.usuario else None))
    if request.method == 'GET':
        for campo, valor in (previos or {"email": s.email_contacto, "telefono": s.cel_contacto}).items():
            if valor and campo in form:
                form[campo].data = valor
        #si no había datos previos, se sugiere el municipio que dejó en la solicitud
        if not form.ciudad.data and s.lugar_solicitud:
            form.ciudad.data = s.lugar_solicitud

    if form.validate_on_submit():
        datos = {campo: form[campo].data for campo in ["nombre", "email", "telefono", "ciudad", "direccion", "barrio"]}
        #las cantidades las elige el cliente aquí; el precio por unidad es el cotizado por el admin.
        #los ítems marcados "no lo quiero" quedan fuera del pedido
        lineas = []
        for i, it in enumerate(items):
            if request.form.get(f"retirar_{i}") == "on":
                continue
            cantidad = request.form.get(f"cant_{i}", type=int) or int(it.cantidad or 1)
            cantidad = max(1, min(99, cantidad))
            lineas.append({"producto": it.producto, "cantidad": cantidad, "precio": int(it.precio_unit),
                           "k_lanzamiento": it.k_lanzamiento,
                           "n_item": None if it.producto else it.nombre})
        if not lineas:
            flash("Tienes que dejar al menos un ítem: desmarca el que ya no quieres", "warning")
        else:
            pedido, token_pedido, errores = crear_pedido(None, datos, k_usuario=g.user["id"] if g.user else None, cotizacion=lineas)
            if errores:
                for e in errores:
                    flash(e, "warning")
            else:
                s.k_invoice = pedido.id
                db.session.commit()
                aviso_pedido_creado(pedido, token_pedido)
                return redirect(url_for('pedido.ver', token=token_pedido))

    #marcados "no lo quiero" en el último envío (para grisearlos si el formulario se repinta por errores)
    retiros = set()
    if request.method == 'POST':
        for i in range(len(items)):
            if request.form.get(f"retirar_{i}") == "on":
                retiros.add(i)
    lineas_vista, total = [], 0
    for i, it in enumerate(items):
        cantidad, precio = int(it.cantidad or 1), int(it.precio_unit)
        retirado = i in retiros
        total += 0 if retirado else precio * cantidad
        lineas_vista.append({"producto": it.producto, "variante": None, "cantidad": 0 if retirado else cantidad, "precio": precio,
                              "lanzamiento": it.lanzamiento or (it.producto.lanzamiento if it.producto else None),
                              "n_item": None if it.producto else it.nombre, "subtotal": 0 if retirado else precio * cantidad,
                              "idx": i, "retirado": retirado,
                               })
    cats = {}
    for it in items:
        cat = (it.producto.k_categoria if it.producto else "OTRO") or "OTRO"
        cats[cat] = cats.get(cat, 0) + int(it.cantidad or 1)
    return render_template("checkout.html", form=form, lineas=lineas_vista, total=total,
                           accion=url_for('solicitud.confirmar', token=token), previos=previos, solicitud=s,
                           cats="|".join(f"{k}:{v}" for k, v in sorted(cats.items())))
