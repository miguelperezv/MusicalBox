"""Salir en otras páginas: el catálogo listo para buscadores y marketplaces.

Ojo: esto NO son anuncios dentro de la tienda (eso era la otra mitad del issue #18) — es lo
contrario. Aquí sacamos el catálogo de acá para que Musical Box aparezca en otras páginas:

    /feed/productos.csv     feed público del catálogo, para enchufar a Google Merchant
                            Center y al catálogo de Meta (Instagram/Facebook). Es el mismo
                            catálogo en dos dialectos: ?destino=google (por defecto) o
                            ?destino=meta (availability con espacio, cantidad para Meta)
    /dashboard/promocion    página del panel: URLs del feed, exportaciones para cargar
                            inventario en marketplaces, datos del negocio y tareas
    datos del negocio       teléfono/dirección/ciudad que usa el schema.org Store del inicio
                            (búsquedas locales tipo "vinilos en Bogotá")

Sólo lee el catálogo: no toca precios, stock ni nada de la tienda.
"""
import csv
import io
from urllib.parse import quote_plus

from flask import Blueprint, Response, flash, g, redirect, render_template, request, url_for

from .models import Producto, get_artist_by_release, stock_disponible
from .redes import get_config, set_config
from .texto import TIPOS_CATEGORIA as TIPOS, categoria_legible, titulo

#el feed se sirve en /feed/productos.csv (ver ACTIVE_ENDPOINTS en app/__init__.py)
promo = Blueprint("promo", __name__)

#el mismo catálogo, dos dialectos: Google quiere availability "in_stock" y Meta "in stock"
DESTINOS = {"google": "google", "merchant": "google", "meta": "meta", "facebook": "meta",
            "instagram": "meta"}

#formatos de Discogs para la hoja de trabajo de Discogs
FORMATOS_DISCOGS = {"VINILO": "Vinyl", "CD": "CD", "CASSETTE": "Cassette", "CAMISETA": "T-Shirt",
                    "POSTER": "Poster", "MUG": "Mug", "ACCESORIO": "Accessory"}

CAMPOS_GOOGLE = ["id", "title", "description", "link", "image_link", "availability",
                 "availability_date", "price", "condition", "brand", "identifier_exists",
                 "item_group_id", "size", "color", "product_type", "sku", "mpn"]
CAMPOS_META = CAMPOS_GOOGLE + ["quantity_to_sell_on_facebook"]


# ---------------------------------------------------------------- datos de una fila
def precio(valor):
    """Google y Meta quieren el precio con la moneda: "120000.00 COP"."""
    return "%.2f COP" % float(valor or 0)


def disponibilidad(stock, preorden, destino):
    if preorden:
        estado = "preorder"
    else:
        estado = "in_stock" if int(stock or 0) > 0 else "out_of_stock"
    return estado.replace("_", " ") if destino == "meta" else estado


def identificador(producto, variante=None):
    """id propio de la tienda (no hay GTIN): MB-12 para el producto, MB-12-3 para una talla."""
    return "MB-%d%s" % (producto.id, "-%d" % variante.id if variante else "")


def _limpio(texto):
    #una sola línea, sin saltos ni tabulaciones (Google no los quiere en title/description)
    return " ".join(str(texto or "").split())


def _artista(producto):
    artista = get_artist_by_release(producto.k_lanzamiento)
    return titulo(artista.n_artista) if artista else ""


def _categoria(producto):
    return producto.categoria.k_categoria if producto.categoria else ""


def titulo_fila(producto, variante=None, artista=""):
    partes = [producto.n_producto, titulo(producto.lanzamiento.n_lanzamiento) if producto.lanzamiento else ""]
    if artista:
        partes.append(artista)
    if variante:
        partes.append(variante.nombre)
    categoria = TIPOS.get(_categoria(producto), _categoria(producto))
    return _limpio(" – ".join(p for p in partes if p) + (" (%s)" % categoria if categoria else ""))


def descripcion_fila(producto, variante=None, artista="", categoria=""):
    """Descripción honesta y sin texto promocional (Google lo prohíbe en el feed)."""
    lanzamiento = titulo(producto.lanzamiento.n_lanzamiento) if producto.lanzamiento else ""
    propias = _limpio(producto.d_producto)
    if propias and not propias.endswith((".", "!", "?")):
        propias += "."
    partes = [propias]
    if not propias:
        #sin descripción del producto se arma con lo que sí sabemos (no se repite el nombre)
        partes.append("%s%s." % (" de ".join(x for x in [producto.n_producto, artista] if x),
                                 " (%s)" % lanzamiento if lanzamiento else ""))
    if lanzamiento and lanzamiento not in propias:
        partes.append("%s: %s." % (artista or "Musical Box", lanzamiento))
    if variante:
        partes.append("Opción: %s." % variante.nombre)
    if categoria:
        partes.append("Categoría: %s." % TIPOS.get(categoria, categoria))
    partes.append("Vendido por Musical Box, tienda de música física en Bogotá, Colombia; "
                  "se despacha a todo el país.")
    return _limpio(" ".join(p for p in partes if p))


def url_producto(producto, nombre=None):
    """URL canónica de la ficha (con slug): Google no quiere que el link del feed redirija."""
    from .models import slugify
    return url_for("products.detalle", k_producto=producto.id,
                   slug=slugify(nombre if nombre is not None else producto.n_producto),
                   _external=True)


def fila_feed(producto, variante=None, destino="google"):
    artista, categoria = _artista(producto), _categoria(producto)
    stock = stock_disponible(producto, variante)
    #preorden: el lanzamiento entero puede estar en preorden y sus productos sueltos también
    preorden = bool(producto.preorden) or bool(producto.lanzamiento and producto.lanzamiento.preorden)
    fila = {
        "id": identificador(producto, variante),
        "title": titulo_fila(producto, variante, artista),
        "description": descripcion_fila(producto, variante, artista, categoria),
        "link": url_producto(producto),
        "image_link": url_for("products.image", k_producto=producto.id, w=800, _external=True),
        "availability": disponibilidad(stock, preorden, destino),
        "availability_date": "",
        "price": precio(producto.p_producto),
        "condition": "new",
        "brand": artista or "Musical Box",
        "identifier_exists": "no",  # no manejamos GTIN: Google lo pide explícito
        "item_group_id": identificador(producto) if producto.variantes else "",
        "size": (variante.talla or "") if variante else "",
        "color": (variante.color or "") if variante else "",
        "product_type": TIPOS.get(categoria, categoria),
        "sku": (variante.sku if variante and variante.sku else identificador(producto, variante)),
        "mpn": identificador(producto, variante),
    }
    if preorden and producto.lanzamiento and producto.lanzamiento.f_lanzamiento:
        fila["availability_date"] = producto.lanzamiento.f_lanzamiento.isoformat()
    if destino == "meta":
        fila["quantity_to_sell_on_facebook"] = max(int(stock or 0), 0)
    return fila


def filas_feed(destino="google"):
    """Una fila por cosa vendible: el producto suelto, o cada talla/color si tiene variantes."""
    filas = []
    for producto in Producto.query.order_by(Producto.id).all():
        if producto.variantes:
            filas += [fila_feed(producto, v, destino) for v in producto.variantes]
        else:
            filas.append(fila_feed(producto, None, destino))
    return filas


def a_csv(filas, campos, separador=","):
    buffer = io.StringIO()
    escritor = csv.DictWriter(buffer, fieldnames=campos, extrasaction="ignore", lineterminator="\n")
    escritor.writeheader()
    for fila in filas:
        escritor.writerow({c: fila.get(c, "") for c in campos})
    return buffer.getvalue()


# ---------------------------------------------------------------- exportaciones
def filas_generico():
    """Hoja de trabajo con todo el catálogo: sirve para cualquier marketplace o un Sheets."""
    filas = []
    for producto in Producto.query.order_by(Producto.id).all():
        artista, categoria = _artista(producto), _categoria(producto)
        variantes = producto.variantes or [None]
        for variante in variantes:
            stock = stock_disponible(producto, variante)
            filas.append({
                "id": identificador(producto, variante),
                "categoria": categoria,
                "producto": _limpio(producto.n_producto),
                "artista": artista,
                "lanzamiento": titulo(producto.lanzamiento.n_lanzamiento) if producto.lanzamiento else "",
                "descripcion": _limpio(producto.d_producto),
                "precio": "%.2f" % float(producto.p_producto or 0),
                "moneda": "COP",
                "stock": int(stock or 0),
                "condicion": "Nuevo",
                "variante": variante.nombre if variante else "",
                "sku": (variante.sku if variante and variante.sku else identificador(producto, variante)),
                "imagen": url_for("products.image", k_producto=producto.id, w=800, _external=True),
                "url": url_producto(producto),
            })
    return filas


def filas_mercadolibre():
    """Para la carga masiva de Mercado Libre: queda listo salvo la categoría de cada ítem
    (Mercado Libre la exige por publicación y no se puede adivinar sin su API)."""
    filas = []
    for fila in filas_generico():
        producto = None
        titulo_ml = " ".join(x for x in [fila["producto"], fila["variante"], fila["artista"],
                                         fila["lanzamiento"]] if x)
        filas.append({
            "titulo": _limpio(titulo_ml)[:60],  # Mercado Libre corta el título en 60
            "descripcion": " ".join(x for x in [fila["descripcion"], "Música física original.",
                                                "Envíos desde Bogotá a todo Colombia."] if x),
            "precio": fila["precio"],
            "moneda": fila["moneda"],
            "cantidad_disponible": fila["stock"],
            "condicion": "new",
            "categoria": "",  # a definir en Mercado Libre (su buscador de categorías la sugiere)
            "fotos": fila["imagen"],
            "sku": fila["sku"],
            "marca": fila["artista"] or "Musical Box",
        })
    return filas


def filas_discogs():
    """Hoja de trabajo para Discogs: su carga masiva exige release_id (que no tenemos en el
    catálogo) y la condición de cada disco, así que se dejan las dos para llenar y se aporta
    el enlace de búsqueda ya armado para encontrarlos rápido."""
    filas = []
    for fila in filas_generico():
        consulta = quote_plus(" ".join(x for x in [fila["artista"], fila["producto"],
                                                   fila["lanzamiento"]] if x))
        filas.append({
            "release_id": "",  # llenar con el de Discogs
            "media_condition": "",  # llenar: M / NM / VG+ ...
            "precio": fila["precio"],
            "moneda": fila["moneda"],
            "artista": fila["artista"],
            "titulo": fila["producto"],
            "formato": FORMATOS_DISCOGS.get(fila["categoria"], fila["categoria"]),
            "sku": fila["sku"],
            "buscar_en_discogs": "https://www.discogs.com/search/?q=%s&type=release" % consulta,
        })
    return filas


EXPORTACIONES = {
    "generico": ("catálogo completo para cualquier destino", "musicalbox-catalogo.csv", filas_generico),
    "mercadolibre": ("Mercado Libre (carga masiva)", "musicalbox-mercadolibre.csv", filas_mercadolibre),
    "discogs": ("Discogs (hoja de trabajo)", "musicalbox-discogs.csv", filas_discogs),
}


def csv_descarga(nombre, filas):
    """Descarga en CSV con BOM para que Excel muestre bien los acentos."""
    texto = a_csv(filas, list(filas[0].keys()) if filas else [])
    respuesta = Response(texto.encode("utf-8-sig"), mimetype="text/csv")
    respuesta.headers["Content-Disposition"] = "attachment; filename=%s" % nombre
    return respuesta


# ---------------------------------------------------------------- datos del negocio
def datos_negocio():
    """Datos del negocio para el schema.org Store, la barra de confianza y el pie del sitio.
    Se leen una sola vez por petición y lo que esté vacío no se publica: nunca se inventa
    teléfono ni dirección (si no hay teléfono, no se muestra un WhatsApp falso)."""
    cache = getattr(g, "_datos_negocio", None)
    if cache is None:
        #la dirección real ya vive en el código: es el origen de los envíos (app/store/envio.py)
        from .envio import ORIGEN_DIRECCION
        cache = {"telefono": (get_config("negocio.telefono") or "").strip(),
                 "direccion": (get_config("negocio.direccion") or "").strip(),
                 "ciudad": (get_config("negocio.ciudad") or "Bogotá").strip(),
                 "pais": "CO",
                 "sugerencia_direccion": ORIGEN_DIRECCION}
        g._datos_negocio = cache
    return cache


def whatsapp_enlace(numero, texto=None):
    """Enlace de WhatsApp a partir del teléfono del panel (acepta "+57 300 123 4567").
    Un número de 10 dígitos se toma como colombiano y se le pone el 57; sin número, no hay enlace."""
    digitos = "".join(c for c in (numero or "") if c.isdigit())
    if not digitos:
        return ""
    if len(digitos) == 10:
        digitos = "57" + digitos
    return "https://wa.me/%s%s" % (digitos, "?text=" + quote_plus(texto) if texto else "")


def guardar_datos_negocio(telefono, direccion, ciudad):
    telefono = _limpio(telefono)[:30]
    set_config({"negocio.telefono": telefono,
                "negocio.direccion": _limpio(direccion)[:120],
                "negocio.ciudad": _limpio(ciudad)[:60] or "Bogotá"})
    return None


# ---------------------------------------------------------------- schema.org
#lo que leen Google y los buscadores: la ficha del producto y la del negocio. Se arma aquí
#(y no en la plantilla) para poder probarlo.
def schema_producto(p, url=None):
    """schema.org Product de una ficha del catálogo (dict de producto_card)."""
    artista = p.get("artista")
    nombre_artista = titulo(artista.n_artista) if artista else "Musical Box"
    lanzamiento = titulo(p["lanzamiento"].n_lanzamiento) if p.get("lanzamiento") else ""
    categoria = TIPOS.get(p.get("categoria"), p.get("categoria") or "")
    #Google exige descripción: si el producto no tiene, se arma una honesta con lo que sí sabemos
    descripcion = _limpio(p.get("descripcion")) or _limpio(
        "%s de %s%s. %s original de Musical Box, desde Bogotá, Colombia." % (
            p.get("nombre"), nombre_artista, " (%s)" % lanzamiento if lanzamiento else "",
            categoria or "Música física"))
    if p.get("preorden"):
        disponibilidad_schema = "PreOrder"
    else:
        disponibilidad_schema = "InStock" if int(p.get("stock") or 0) > 0 else "OutOfStock"
    datos = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": _limpio(p.get("nombre")),
        "description": descripcion,
        "sku": "MB-%s" % p.get("id"),
        "image": [url_for("products.image", k_producto=p.get("id"), w=800, _external=True)],
        "brand": {"@type": "Brand", "name": nombre_artista},
        "offers": {
            "@type": "Offer",
            "url": url or url_for("products.detalle", k_producto=p.get("id"), _external=True),
            "priceCurrency": "COP",
            "price": "%.2f" % float(p.get("precio") or 0),
            "availability": "https://schema.org/%s" % disponibilidad_schema,
            "itemCondition": "https://schema.org/NewCondition",
            "seller": {"@type": "Organization", "name": "Musical Box"},
        },
    }
    if categoria:
        datos["category"] = categoria
    return datos


def schema_tienda():
    """schema.org Store del inicio, con los datos del negocio que haya (lo vacío no se publica)."""
    negocio = datos_negocio()
    direccion = {"@type": "PostalAddress", "addressLocality": negocio["ciudad"] or "Bogotá",
                 "addressCountry": negocio["pais"]}
    if negocio["direccion"]:
        direccion["streetAddress"] = negocio["direccion"]
    tienda = {
        "@context": "https://schema.org",
        "@type": "Store",
        "name": "Musical Box",
        "url": request.host_url,
        "image": url_for("static", filename="imgs/musicalbox.png", _external=True),
        "currenciesAccepted": "COP",
        "areaServed": {"@type": "Country", "name": "Colombia"},
        "address": direccion,
        "sameAs": ["https://facebook.com/musicalboxcol/", "https://www.instagram.com/musicalboxcol/",
                   "https://twitter.com/musicalboxcol", "https://tiktok.com/@musicalboxcol"],
    }
    if negocio["telefono"]:
        tienda["telephone"] = negocio["telefono"]
    return tienda


# ---------------------------------------------------------------- rutas
@promo.route("/productos.csv")
def feed_productos():
    """Feed público del catálogo (Google Merchant Center / catálogo de Meta)."""
    destino = DESTINOS.get((request.args.get("destino") or "google").strip().lower(), "google")
    campos = CAMPOS_META if destino == "meta" else CAMPOS_GOOGLE
    respuesta = Response(a_csv(filas_feed(destino), campos), mimetype="text/csv")
    respuesta.headers["Content-Disposition"] = 'inline; filename="musicalbox-productos.csv"'
    #los buscadores refrescan el feed cada rato: basta con cachear unos minutos
    respuesta.headers["Cache-Control"] = "public, max-age=600"
    return respuesta


#las de abajo viven en el panel (blueprint dashboard, ya protegido por admin)
from .views import dashboard  # noqa: E402


@dashboard.route("/promocion")
def promocion_admin():
    negocio = datos_negocio()
    intentos = [{"url": url_for("promo.feed_productos", _external=True),
                 "destino": "Google Merchant Center",
                 "nota": "el que se pega en Merchant Center/Facebook Commerce"},
                {"url": url_for("promo.feed_productos", destino="meta", _external=True),
                 "destino": "catálogo de Meta",
                 "nota": "mismo catálogo, con los valores que pide Meta"}]
    return render_template("promocion_admin.html", negocio=negocio, feeds=intentos,
                           exportaciones=EXPORTACIONES)


@dashboard.route("/promocion/negocio", methods=["POST"])
def promocion_negocio():
    guardar_datos_negocio(request.form.get("telefono"), request.form.get("direccion"),
                          request.form.get("ciudad"))
    flash("Datos del negocio guardados", "success")
    return redirect(url_for("dashboard.promocion_admin"))


@dashboard.route("/export/catalogo.csv")
def export_catalogo():
    formato = (request.args.get("formato") or "generico").strip().lower()
    if formato not in EXPORTACIONES:
        formato = "generico"
    _, nombre, construir = EXPORTACIONES[formato]
    return csv_descarga(nombre, construir())
