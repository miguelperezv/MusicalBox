#from app.store.forms import CreateUsuarioForm, LoginUsuarioForm, newArtistForm, newReleaseForm

from flask.wrappers import Request
from .forms import ActivarCuentaForm, CreateUsuarioForm, LoginUsuarioForm,  newReleaseForm, newProductForm, newCat_Genre_Artist, newAdmin, editReleaseForm, EditUsuarioForm
from flask import Blueprint, Response, current_app, flash, session, request, g, render_template, redirect, url_for, jsonify, make_response
#from app.store.models import create_new_user, get_all_artists, get_user_by_email, create_new_artist
from .models import create_new_user, get_all_artists, get_user_by_email, create_new_artist, get_k_artist_by_name, create_new_release, get_release_by_name, get_releases_with_artists, get_categories, create_new_product, get_k_release_by_name_artista, create_new_category, create_new_genre, create_release_genre, new_admin, get_all_releases, get_artist_by_release, get_categories_by_release, get_release_by_id, get_genres_by_release, get_products_by_release, get_product_by_id, get_artist_by_release, update_release, get_products_with_info, edit_product, create_new_image, get_rawimage_by_product, edit_image, get_items_by_id_factura
from .models import producto_card, lanzamiento_tiene_original, ESTADOS_ENVIO, ESTADOS_CON_ROTULO, opciones_componentes, stock_disponible, get_usuario_por_email, get_artist_by_id, get_releases_cards, get_products_cards, get_admin_stats, edit_user_by_email, get_all_products, get_purchases_by_user, get_all_invoices, get_solicitudes_by_user, validar_carrito, crear_pedido, get_images_by_product, get_first_image_by_product
#import epaycosdk.epayco as epayco
import json
import urllib.parse as urlparse
from urllib.parse import parse_qs
import requests
import datetime
from datetime import timedelta
from functools import wraps
from . import carrito
from .imagenes import imagen_producto
from .redes import seleccion_para_inicio, leer_url
from ..db import db
from .notificaciones import correo_activacion, usuario_de_token


home = Blueprint('home', __name__)
dashboard = Blueprint('dashboard', __name__, url_prefix=  '/dashboard')
releases = Blueprint('releases', __name__, url_prefix=  '/releases')
artists = Blueprint("artists", __name__, url_prefix=  '/artists')
purchase = Blueprint("purchase", __name__, url_prefix=  '/artists' )
products = Blueprint("products", __name__, url_prefix="/products")


@home.before_request
@purchase.before_request
@releases.before_request
@artists.before_request
@dashboard.before_request
@products.before_request
def before_request():
    if "user" in session:
        g.user = session["user"]
    else:
        g.user = None
    if "purchase" in session:
        g.purchase = session["purchase"]
    else:
        # Recuperar carrito de la sesión anterior si existe
        ultimo_carrito = session.get("ultimo_carrito")
        if ultimo_carrito:
            session["purchase"] = ultimo_carrito
            g.purchase = session["purchase"]
        else:
            session["purchase"] = {}
            g.purchase = None
    
    g.datetime = datetime.datetime


def is_admin():
    return bool(g.get("user")) and g.user.get("k_rol") == 'ADMIN'

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_admin():
            flash("Debes ingresar como administrador", "warning")
            return redirect(url_for('home.login'))
        return f(*args, **kwargs)
    return decorated

@dashboard.before_request
@admin_required
def validate_admin():
    pass


    

@home.route("/")
def index():
    return render_template("home.html", releases = get_releases_cards(limit=10), productos = get_products_cards(limit=4),
                           redes = seleccion_para_inicio())

@home.route("/login", methods=["GET", 'POST'])
def login():
    from .seguridad import check_password
    form_login = LoginUsuarioForm()

    if request.method == 'POST':
        email = form_login.email_usuario.data
        pwd = form_login.pwd_usuario.data

        existente = get_usuario_por_email(email)
        user = get_user_by_email(existente.email_usuario) if existente else None
        if not user:
            flash("No existe una cuenta con ese correo", "warning")
            return redirect(url_for('home.login'))
        elif check_password(pwd, user['pwd_usuario']):
            if user['k_rol'] == 'CLIENTE':
                #compró o pidió sin cuenta: la contraseña se crea con el enlace que enviamos a su correo
                correo_activacion(existente)
                flash("Aún no tienes contraseña. Te enviamos a tu correo un enlace para crearla.", "info")
                return redirect(url_for('home.login'))
            flash("Bienvenido " + user['n_usuario'])
            session["user"] = user
            if user['k_rol'] == 'ADMIN':
                return redirect(url_for('home.admin'))
            return redirect(url_for('home.index', user=g.user, purchase_cart = g.purchase))
        elif user['k_rol'] == 'CLIENTE':
            #compró o pidió sin cuenta: la contraseña se crea con el enlace que enviamos a su correo
            correo_activacion(existente)
            flash("Aún no tienes contraseña. Te enviamos a tu correo un enlace para crearla.", "info")
            return redirect(url_for('home.login'))
        else:
            flash("Contraseña incorrecta", "warning")
            return redirect(url_for('home.login'))

    resp = make_response(render_template('login.html', form=form_login))
    resp.set_cookie('same-site-cookie', 'foo', samesite='Lax')
    resp.set_cookie('cross-site-cookie', 'bar', samesite='Lax', secure=True)
    return resp
    

@home.route("/signup", methods=["GET", 'POST'])
def signup():
    print("g.user "+ str(g.user))
    if not g.user: 
        form_signup= CreateUsuarioForm()

        if request.method == 'POST' :
            email = (form_signup.email_usuario.data or '').strip()
            pwd = form_signup.pwd_usuario.data
            name = form_signup.name.data
            apellido = form_signup.lastname.data
            existente = get_usuario_por_email(email)
            if existente and existente.k_rol == 'CLIENTE':
                #ya compró o pidió sin cuenta: solo quien controla el correo puede crear la contraseña
                correo_activacion(existente)
                flash("Ya tenemos compras o solicitudes con este correo. Te enviamos un enlace para crear tu contraseña.", "info")
                return redirect(url_for('home.login'))
            if existente:
                flash("Ya existe una cuenta con este correo. Ingresa con tu contraseña.", "warning")
                return redirect(url_for('home.login'))
            result = create_new_user(name,apellido, email, pwd)
            if result:
                flash("¡Cuenta creada! Ya puedes ingresar.")
                return redirect(url_for('home.login'))
            flash("No se pudo crear la cuenta", "error")
            return redirect(url_for('home.signup'))
        return render_template('signup.html', form=form_signup, purchase_cart = g.purchase)
    
    flash("You're already logged in.", "alert-primary")
    return redirect(url_for('home.index', user = g.user, purchase_cart = g.purchase))

@home.route("/activar/<token>", methods=["GET", "POST"])
def activar(token):
    #enlace que llega por correo para crear la contraseña de una cuenta CLIENTE (ver notificaciones.py)
    from .seguridad import hash_password
    usuario = usuario_de_token(token)
    if not usuario:
        return render_template("activar.html", invalido=True), 400
    form = ActivarCuentaForm()
    if form.validate_on_submit():
        usuario.pwd_usuario = hash_password(form.pwd.data)
        usuario.k_rol = 'USER'
        db.session.commit()
        session["user"] = get_user_by_email(usuario.email_usuario)
        flash("¡Listo! Tu contraseña quedó creada.", "success")
        return redirect(url_for('home.account'))
    return render_template("activar.html", form=form, usuario=usuario)

@home.route("/logout", methods=["GET", "POST"])
def logout():
    session.pop("user", None)
    session.pop("purchase", None)
    session.pop("ultimo_carrito", None)
    session.pop("checkout_datos", None)
    flash("You're logged out.", "alert-secondary")

    return redirect(url_for("home.index", user=g.user))

@home.route("/account", methods=["GET", "POST"])
def account():
    if not g.user:
        return redirect(url_for('home.login'))

    edit_usuario = EditUsuarioForm()
    if request.method == "POST":
        nombre = edit_usuario.name.data
        apellido  =edit_usuario.lastname.data
        ciudad = edit_usuario.city.data
        direccion = edit_usuario.address.data
        result = edit_user_by_email(session["user"]["email_usuario"], nombre,apellido,ciudad,direccion, edit_usuario.barrio.data, edit_usuario.celular.data)
        if result:
            flash("Usuario modificado correctamente")
            #g.user = result
            session["user"] = get_user_by_email(session["user"]["email_usuario"])
            return redirect(request.referrer)
        else:
            flash("No se pudo actualizar el usuario")
            return redirect(request.referrer)
    if request.method == "GET":
        
        print("USER: " + str(session["user"]))
        edit_usuario.name.data = session["user"]["n_usuario"]
        edit_usuario.lastname.data = session["user"]["ape_usuario"]
        edit_usuario.email_usuario.data = session["user"]["email_usuario"]
        edit_usuario.email_usuario.render_kw = {'disabled': 'disabled'}
        
        edit_usuario.city.data = session["user"]["lugar_usuario"]
        edit_usuario.address.data = session["user"]["dir_usuario"]
        edit_usuario.barrio.data = session["user"].get("barrio_usuario")
        edit_usuario.celular.data = session["user"].get("cel_usuario")

        compras = get_purchases_by_user(session["user"]["email_usuario"])
        solicitudes = get_solicitudes_by_user(session["user"]["email_usuario"])

    return render_template("account.html",  user=g.user, purchase_cart = g.purchase, form = edit_usuario, compras = compras, solicitudes = solicitudes, get_product_by_id = get_product_by_id, get_release_by_id = get_release_by_id )

@home.route("/dashboard", methods=["GET", "POST"])
@admin_required
def admin():
    return render_template("adminDashboard.html", stats = get_admin_stats())

LOCALIDADES_BOGOTA = ["Usaquén", "Chapinero", "Santa Fe", "San Cristóbal", "Usme", "Tunjuelito", "Bosa", "Kennedy",
    "Fontibón", "Engativá", "Suba", "Barrios Unidos", "Teusaquillo", "Los Mártires", "Antonio Nariño", "Puente Aranda",
    "La Candelaria", "Rafael Uribe Uribe", "Ciudad Bolívar", "Sumapaz"]

@home.route("/colombia", methods=["GET"])
def colombia():
    #municipios DIVIPOLA (datos.gov.co gdxc-w37w) guardados en static/data; Bogotá se reemplaza por sus localidades (del manager)
    with current_app.open_resource("static/data/municipios_colombia.json") as f:
        municipios = set(json.load(f))
    municipios.discard("Bogotá, D.C., Bogotá, D.C.")
    municipios.update(l + ", Bogotá D.C." for l in LOCALIDADES_BOGOTA)
    return jsonify(sorted(municipios))


#routes del panel de administración

@dashboard.route( "/newrelease" ,methods=["GET", "POST"])
def newrelease():
    

    form_new_release=newReleaseForm()

    if request.method == 'POST':
        n_lanzamiento = form_new_release.n_lanzamiento.data
        i_lanzamiento = form_new_release.i_lanzamiento.data
        k_artista =  get_k_artist_by_name((form_new_release.k_artista.data or '').strip().upper())
        if not k_artista:
            flash("El artista no existe: créalo primero en Género / categoría / artista", "warning")
            return redirect(url_for('home.admin'))
        f_lanzamiento = form_new_release.f_lanzamiento.data
        k_genero = form_new_release.k_genero.data
        print(k_genero)
        k_lanzamiento= create_new_release(k_artista, n_lanzamiento, i_lanzamiento, f_lanzamiento, k_genero)
        print("EL LANZAMIENTO ES: "+str(k_lanzamiento)+" , "+ n_lanzamiento)
        if k_lanzamiento :
            guardar_url_social(k_lanzamiento, form_new_release.url_social.data)
            release_genre = create_release_genre(k_lanzamiento,  k_genero)
            if release_genre:
                flash("Lanzamiento Registrado! "+ str(n_lanzamiento) +" - "+ str(k_genero))
                return redirect(url_for('home.admin'))
        else:
            flash("No se pudo registrar")
        return redirect(url_for('home.admin'))
    return render_template("newRelease.html", form = form_new_release, artistas = sorted(a['n_artista'] for a in get_all_artists()))

@dashboard.route("/newrelease_artists")
def newrelease_artists():
    artists= get_all_artists()
    selectfieldartist =[]
    for artist in artists:
        #selectfieldartist.append((artist['k_artista'], artist['n_artista']))
        selectfieldartist.append((artist['n_artista']))
    return jsonify(selectfieldartist)

@dashboard.route("/newproduct", methods=["GET", "POST"])
def newproduct():
    categories =  get_categories()
    form_new_product = newProductForm(categories_choices=categories)
    if request.method=="POST":
        #n_lanzamiento = form_new_product.n_lanzamiento.data.split(" - ")[-1]
        #n_artista = form_new_product.n_lanzamiento.data.split(" - ")[0].upper()
        n_producto = form_new_product.n_producto.data
        p_producto  =form_new_product.p_producto.data
        d_producto = form_new_product.d_producto.data
        stock = form_new_product.stock.data
        i_producto = form_new_product.i_producto.data
        k_categoria = dict(form_new_product.k_category.choices).get(form_new_product.k_category.data)
        
        #k_lanzamiento = get_k_release_by_name_artista(n_lanzamiento,n_artista)
        k_lanzamiento = form_new_product.n_lanzamiento.data.split(".")[0]
        print("K_LANZAMIENTO ES "+ k_lanzamiento)
        print("imagefile")
        image_files = request.files.getlist('inputImages')
        # Filtrar archivos vacíos
        image_files = [f for f in image_files if f and f.filename]
        product = create_new_product(int(k_lanzamiento), n_producto, p_producto, d_producto, stock, i_producto, k_categoria, form_new_product.tipo.data)
        if product:
            product.original_mb = bool(form_new_product.original_mb.data)
            db.session.commit()
            if image_files:
                create_multiple_images(product.id, image_files)
            #a la edición, para configurar tallas/colores o el contenido del pack
            flash("Producto creado: configura sus tallas o el contenido del pack si aplica", "success")
            return redirect(url_for('dashboard.updateproduct', k_producto=product.id))
        else:
            flash("No se pudo registrar")
        return redirect(url_for('home.admin'))
    return render_template("newProduct.html", form=form_new_product, lanzamientos=get_releases_with_artists() or [],
                           preseleccion=request.args.get("lanzamiento", ""))

@dashboard.route("/newproduct_releases")
def newproduct_releases():
    release_artist = get_releases_with_artists()
    return jsonify(release_artist)

@dashboard.route("/editproduct_productList")
def editproduct_productList():
    product_info = get_products_with_info()
    return jsonify(product_info)

@dashboard.route("/newproduct_categories")
def newproduct_categories():
    categories = get_categories()
    return jsonify(categories)

@dashboard.route("/newgenre_category_artist", methods=["GET", "POST"])
def newgenre_category_artist():
    form_cat_genre = newCat_Genre_Artist()
    if request.method=='POST':
        return "Soy el Post de esta vista"
    return render_template("newCatGenreArtist.html", form = form_cat_genre) 

@dashboard.route("/newgenre", methods=["GET", "POST"])
def newgenre():
    if request.method =='POST':
        form_cat_genre = newCat_Genre_Artist()
        genre = form_cat_genre.genre.data.upper()
        result = create_new_genre(genre)
        if result:
            flash("Genero registrado!")
            return redirect(url_for('home.admin'))
        flash("No se agregó el género! Posiblemente ya exista ;)")
        return redirect(url_for('home.admin'))

@dashboard.route("/newcategory", methods=["GET", "POST"])
def newcategory():
    if request.method =='POST':
        form_cat_genre = newCat_Genre_Artist()
        category = form_cat_genre.category.data.upper()
        result = create_new_category(category)
        if result:
            flash("Cateogría registrada!")
            return redirect(url_for('home.admin'))
        flash("No se agregó la categoría! Posiblemente ya exista ;)")
        return redirect(url_for('home.admin'))

@dashboard.route("/newartist", methods=["GET", "POST"])
def newartist():
    if request.method=='POST':
        form_cat_genre = newCat_Genre_Artist()
        artist = form_cat_genre.n_artist.data.upper()
        country = form_cat_genre.country.data
        print(country)
        result = create_new_artist(artist, country)
        if result:
            flash("Artista registrado!: " + artist)
            return redirect(url_for('home.admin'))
        flash("No se agregó el artista! Posiblemente ya exista ;)")
        return redirect(url_for('home.admin'))

@dashboard.route("/newadmin", methods=['GET', 'POST'])
def newadmin():
    form_new_admin= newAdmin()
    if request.method=='POST':
        
        email = form_new_admin.email.data
        pwd = form_new_admin.pwd.data
        result = new_admin(email, pwd, session["user"])
        print("result "+ str(result))
        if result:
            flash("Nuevo administrador con el correo "+ email)
            return redirect(url_for("home.admin"))
        else:
            flash("Contraseña o email incorrectos! ")
            return redirect(url_for("home.admin"))
        
    return render_template("newAdmin.html", form = form_new_admin)

@dashboard.route("/invoices", methods=["GET", "POST"])
def invoices():

    return render_template("invoices.html", invoices = get_all_invoices(), get_items_by_id_factura = get_items_by_id_factura, estados_envio = ESTADOS_ENVIO, con_rotulo = ESTADOS_CON_ROTULO)  

@dashboard.route("/editrelease", methods=["GET", "POST"])
def editrelease():
    
    form_edit_release = newReleaseForm()
    lanzamiento = None
    if request.method == 'POST':
        seleccion = (form_edit_release.n_lanzamiento.data or '').split(".")[0].strip()
        if not seleccion.isdigit():
            flash("Elige una opción de la lista", "warning")
            return redirect(url_for('dashboard.editrelease'))
        k_lanzamiento = int(seleccion)
        print("SOY POST")
        lanzamiento = get_release_by_id(k_lanzamiento)
        print(lanzamiento)
        if get_genres_by_release(k_lanzamiento):
            form_edit_release.k_genero.data = get_genres_by_release(k_lanzamiento)[0].get("k_genero")
            
        else:
            form_edit_release.k_genero.data = "N/A"
    return render_template("editRelease.html", form = form_edit_release, get_artist_by_release = get_artist_by_release,  lanzamiento = lanzamiento, artistas = sorted(a['n_artista'] for a in get_all_artists()))


@dashboard.route("/updaterelease_<string:k_lanzamiento>", methods=["GET", "POST"])
def updaterelease(k_lanzamiento):
    form_edit_release = newReleaseForm()
    lanzamiento = None
    if request.method == 'POST':
        k_lanzamiento = int (k_lanzamiento)
        n_lanzamiento = form_edit_release.n_lanzamiento_edit.data
        i_lanzamiento = form_edit_release.i_lanzamiento.data
        k_artista =  get_k_artist_by_name((form_edit_release.k_artista.data or '').strip().upper())
        if not k_artista:
            flash("El artista no existe: créalo primero en Género / categoría / artista", "warning")
            return redirect(url_for('dashboard.updaterelease', k_lanzamiento=k_lanzamiento))
        f_lanzamiento = form_edit_release.f_lanzamiento.data
        k_genero = form_edit_release.k_genero.data
        print(k_genero)
        
        result = update_release(k_lanzamiento, n_lanzamiento, i_lanzamiento, k_artista, f_lanzamiento, k_genero)
        if result:
            guardar_url_social(k_lanzamiento, form_edit_release.url_social.data)
        if result:
            flash("Se actualizó el lanzamiento ["+str(k_lanzamiento)+"-"+str(n_lanzamiento)+"]")
        else:
            flash("No se pudo actualizar ["+str(k_lanzamiento)+"-"+str(n_lanzamiento)+"]")
    
    if request.method ==  'GET':
        
        k_lanzamiento = int (k_lanzamiento)
        lanzamiento = get_release_by_id(k_lanzamiento)
        print(lanzamiento)
        if get_genres_by_release(k_lanzamiento):
            form_edit_release.k_genero.data = get_genres_by_release(k_lanzamiento)[0].get("k_genero")
            
        else:
            form_edit_release.k_genero.data = "N/A"
        
    
    return render_template("editRelease.html", form = form_edit_release, get_artist_by_release = get_artist_by_release,  lanzamiento = lanzamiento, artistas = sorted(a['n_artista'] for a in get_all_artists()))


@dashboard.route("/editproduct",  methods=["GET", "POST"])
def editproduct():
    categories =  get_categories()
    form_edit_product = newProductForm(categories_choices=categories)
    producto= None
    if request.method == 'POST':
        seleccion = (form_edit_product.n_producto.data or '').split(".")[0].strip()
        if not seleccion.isdigit():
            flash("Elige una opción de la lista", "warning")
            return redirect(url_for('dashboard.editproduct'))
        k_producto = int(seleccion)
        producto = get_product_by_id(k_producto)
        # Asegurarse de que las imágenes se carguen correctamente
        imagenes = get_images_by_product(k_producto)
        producto.imagenes = imagenes
        print("Cargando producto:", k_producto, "con", len(imagenes), "imágenes")
        for img in imagenes:
            print(f"  Imagen ID: {img.id}, Orden: {img.orden}, Nombre: {img.name}")
        print(producto.p_producto)
        form_edit_product.n_producto_edit.data = producto.n_producto
        form_edit_product.p_producto.data = int(producto.p_producto or 0)
        form_edit_product.stock.data = producto.stock
        form_edit_product.d_producto.data  = producto.d_producto
        form_edit_product.i_producto.data = get_rawimage_by_product(producto.id)
        form_edit_product.k_category.data = producto.k_categoria
        # En lugar de renderizar el mismo template, redirigir a updateproduct
        return redirect(url_for('dashboard.updateproduct', k_producto=k_producto))
    return render_template("editProduct.html", form = form_edit_product, producto = producto, opciones_componentes = opciones_componentes, stock_disponible = stock_disponible)

@dashboard.route("/updateproduct/<string:k_producto>",  methods=["GET", "POST"])
def updateproduct(k_producto):
    print("ESTOY EN EL PRODUCTO "+ k_producto)
    form = newProductForm()
    if request.method == 'POST':
        k_producto = int(k_producto)
        n_producto = form.n_producto_edit.data
        #i_producto =  form.i_producto.data
        d_producto =  form.d_producto.data
        p_producto =  form.p_producto.data
        k_category = form.k_category.data
        stock = form.stock.data
        #print("i_producto "+ str(i_producto))
        print("p_producto "+ str(p_producto))
        image_files = None
        try:
            image_files = request.files.getlist('inputImages')
            # Filtrar archivos vacíos
            image_files = [f for f in image_files if f and f.filename]
            print("obtuve las imágenes a editar: " + str(len(image_files)))
        except Exception as e:
            print("ERROR OBTENIENDO LAS IMÁGENES "+ str(e))

        # Manejar reordenación de imágenes existentes
        imagen_ordenes = request.form.get('imagen_ordenes')
        if imagen_ordenes:
            try:
                ordenes = json.loads(imagen_ordenes)
                reorder_images(k_producto, ordenes)
            except Exception as e:
                print("Error actualizando ordenes: " + str(e))

        result = edit_product(k_producto, n_producto, d_producto, p_producto, image_files, k_category, stock)
        if result:
            get_product_by_id(k_producto).original_mb = request.form.get("original_mb") == "y"
            db.session.commit()
        if result:
            flash("Se actualizó el producto")

        else:
            flash("No se pudo actualizar el producto!")

    if request.method == 'GET':

        categories =  get_categories()
        form_edit_product = newProductForm(categories_choices=categories)
        k_producto = int(k_producto)
        producto = get_product_by_id(k_producto)
        # Asegurarse de que las imágenes se carguen correctamente
        imagenes = get_images_by_product(k_producto)
        producto.imagenes = imagenes
        print("Cargando producto:", k_producto, "con", len(imagenes), "imágenes")
        for img in imagenes:
            print(f"  Imagen ID: {img.id}, Orden: {img.orden}, Nombre: {img.name}")
        print(producto.p_producto)
        form_edit_product.n_producto_edit.data = producto.n_producto
        form_edit_product.p_producto.data = int(producto.p_producto or 0)
        form_edit_product.stock.data = producto.stock
        form_edit_product.d_producto.data  = producto.d_producto
        form_edit_product.i_producto.data = None
        form_edit_product.k_category.data = producto.k_categoria
        form_edit_product.original_mb.data = producto.original_mb
        return render_template("editProduct.html", form = form_edit_product, producto = producto, opciones_componentes = opciones_componentes, stock_disponible = stock_disponible)
    return redirect(url_for('dashboard.editproduct'))


@dashboard.route("/editgenre_category_artist")
def editgenre_category_artist():
    None

@dashboard.route("/editadmin")
def editadmin():
    None

@releases.route('/', methods=["GET", "POST"])
def home_releases():
    if request.method == "POST":
        None
    if request.method == 'GET':
        q = request.args.get("q", "")
        return render_template("releases.html", releases = get_releases_cards(q=q), q = q)

@releases.route("/<int:k_lanzamiento>", methods=["GET", "POST"])
def release(k_lanzamiento):
    if request.method == 'GET':
        artista = get_artist_by_release(k_lanzamiento)
        lanzamiento = get_release_by_id(k_lanzamiento)
        generos = get_genres_by_release(k_lanzamiento)
        productos = get_products_by_release(k_lanzamiento)
        if not lanzamiento:
            return render_template("404.html"), 404
        cards = get_products_cards(k_lanzamiento=k_lanzamiento)
        return render_template("singleRelease.html", artista=artista, lanzamiento=lanzamiento, generos = generos, productos=productos,
                               packs=[c for c in cards if c["tipo"] == 'BUNDLE'], sueltos=[c for c in cards if c["tipo"] != 'BUNDLE'],
                               social=post_social(lanzamiento.get("url_social")), original=any(c["original"] for c in cards))


def guardar_url_social(k_lanzamiento, url):
    #solo se guarda si es un post válido de Instagram/TikTok (vacío = quitarlo)
    from .models import Lanzamiento
    lanz = db.session.get(Lanzamiento, int(k_lanzamiento)) if str(k_lanzamiento).isdigit() else None
    if not lanz:
        return
    url = (url or "").strip()
    social = post_social(url) if url else None
    if url and not social:
        flash("El link de redes no es un post de Instagram o TikTok; no se guardó", "warning")
        return
    lanz.url_social = social["url"] if social else None
    db.session.commit()


def post_social(url):
    #{"plataforma", "url", "id"} si el link del lanzamiento es un post válido de Instagram/TikTok
    for plataforma in ('instagram', 'tiktok'):
        limpia, id_externo, err = leer_url(plataforma, url)
        if not err:
            return {"plataforma": plataforma, "url": limpia, "id": id_externo}
    return None


@releases.route("/<int:k_lanzamiento>/post")
def post_lanzamiento(k_lanzamiento):
    #contenido del modal con el post de redes del lanzamiento
    social = post_social((get_release_by_id(k_lanzamiento) or {}).get("url_social"))
    if not social:
        return "", 404
    return render_template("_post_social.html", social=social)


@artists.route("/<int:k_artista>", methods=["GET", "POST"])
def artist(k_artista):
    if request.method == 'GET':
        artista = get_artist_by_id(k_artista)
        if not artista:
            return render_template("404.html"), 404
        return render_template("releases.html", releases = get_releases_cards(k_artista=k_artista), artista = artista)

@purchase.route("/", methods=["GET"])
def summary():
    #el stock por variante y de los packs se revisa aquí, antes de ir a pagar
    lineas, total, errores = carrito.resumen(session.get("purchase"))
    return render_template("purchase.html", lineas=lineas, total=total, errores=errores)


@purchase.route("/addtocart" ,methods=["POST"])
def addtocart():
    k_producto = request.form.get("product_id", type=int)
    k_variante = request.form.get("variante_id", type=int)
    cantidad = request.form.get("quantity", default=1, type=int) or 1
    session["purchase"], mensaje, categoria = carrito.agregar(session.get("purchase"), k_producto, k_variante, cantidad)
    flash(mensaje, categoria)
    return redirect(request.referrer or url_for('purchase.summary'))


@purchase.route("/remove/<string:k_producto>", methods=["POST", "GET"]) 
def remove(k_producto):
    cart = dict(session.get("purchase") or {})
    cart.pop(k_producto, None)
    session["purchase"] = cart
    return redirect(request.referrer or url_for('purchase.summary'))


@purchase.route("/updatesingle<string:k_producto>_<string:opc>", methods=["GET", "POST"])
def updatesingle(k_producto, opc):
    session["purchase"], aviso = carrito.cambiar_cantidad(session.get("purchase"), k_producto, 1 if opc == 'up' else -1)
    if aviso:
        flash(aviso, "warning")
    return redirect(request.referrer or url_for('purchase.summary'))


@purchase.route('/process_checkout', methods=["POST"])
def process_checkout():
    # Obtener datos del formulario
    datos = {
        "nombre": request.form.get("nombre", "").strip(),
        "email": request.form.get("email", "").strip().lower(),
        "telefono": request.form.get("telefono", "").strip(),
        "ciudad": request.form.get("ciudad", "").strip(),
        "direccion": request.form.get("direccion", "").strip(),
        "barrio": request.form.get("barrio", "").strip(),
        "metodo_pago": "TARJETA"  # Valor por defecto
    }
    
    # Validar que los datos no estén vacíos
    if not all([datos["nombre"], datos["email"], datos["telefono"], datos["ciudad"], datos["direccion"]]):
        flash("Por favor completa todos los campos obligatorios", "warning")
        return redirect(url_for('purchase.summary'))
    
    # Validar carrito
    lineas, total, errores = validar_carrito(session.get("purchase"))
    if errores:
        for e in errores:
            flash(e, "warning")
        return redirect(url_for('purchase.summary'))
    
    # Crear pedido con los datos proporcionados
    pedido, token, errores = crear_pedido(session.get("purchase"), datos)
    if errores:
        for e in errores:
            flash(e, "warning")
        return redirect(url_for('purchase.summary'))
    
    # Guardar datos para futuros checkouts
    session["checkout_datos"] = datos
    # Limpiar carrito
    session["purchase"] = {}
    
    # Ir a la página de pedido
    return redirect(url_for('pedido.ver', token=token))
        

@purchase.route('/success')
def thankyou():
    return render_template('thankyou.html', purchase_cart = g.purchase, user=g.user )

@products.route("/image_<int:k_producto>")
def image(k_producto): 
    # Obtener el parámetro de orden si existe
    orden = request.args.get("orden", type=int)
    
    if orden is not None:
        # Obtener imagen específica por orden
        imagen = Imagen.query.filter_by(k_producto=k_producto, orden=orden).first()
        if imagen:
            return Response(imagen.img, mimetype=imagen.mimetype)
    
    # Comportamiento original: obtener la primera imagen
    respuesta = imagen_producto(k_producto, request.args.get("w", default=600, type=int))
    if respuesta:
        return respuesta
    #sin foto: portada del lanzamiento o logo (evita un 404 por cada tarjeta)
    producto = get_product_by_id(k_producto)
    portada = producto.lanzamiento.i_lanzamiento if producto and producto.lanzamiento else None
    return redirect(portada or url_for('static', filename='imgs/musicalbox.png'))

@products.route("/<int:k_producto>")
def detalle(k_producto):
    #página del producto; con ?modal=1 devuelve solo el contenido para la vista rápida
    p = producto_card(k_producto)
    if not p:
        return render_template("404.html"), 404
    if request.args.get("modal"):
        return render_template("_producto_detalle.html", p=p, modal=True)
    return render_template("producto.html", p=p)

@products.route("/", methods=["POST", "GET"])
def home_products():
    if request.method == "GET":
        products = get_all_products()
    if request.method == "POST":
        None
    return render_template("products.html", productos = get_products_cards())