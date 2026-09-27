#from app.db import db, ma
from flask.wrappers import Response
from werkzeug.utils import secure_filename
from ..db import db, ma
from datetime import datetime
from base64 import b64encode
import secrets



class Lanzamiento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    n_lanzamiento = db.Column(db.String(100), nullable = False )
    f_lanzamiento = db.Column(db.Date)
    i_lanzamiento = db.Column(db.String(500))

class Artista(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    n_artista = db.Column(db.String(50), nullable = False)
    pais_artista = db.Column(db.String(50))

class Lanzamiento_Artista(db.Model):
    k_artista = db.Column(db.Integer, db.ForeignKey("artista.id"), primary_key=True)
    k_lanzamiento = db.Column(db.Integer, db.ForeignKey("lanzamiento.id") ,primary_key=True)
    #atributos de la relacion
    lanzamiento = db.relationship("Lanzamiento")
    artista = db.relationship("Artista")

class Genero(db.Model):
    k_genero = db.Column(db.String(30), primary_key=True)

class Lanzamiento_Genero(db.Model):
    k_genero = db.Column(db.String(30), db.ForeignKey("genero.k_genero"),primary_key=True)
    k_lanzamiento = db.Column(db.Integer, db.ForeignKey("lanzamiento.id"), primary_key=True)
    subgenre = db.Column(db.Boolean)
    #atributos de la relacion
    genero = db.relationship("Genero")
    lanzamiento = db.relationship("Lanzamiento")

class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    k_lanzamiento = db.Column(db.Integer, db.ForeignKey("lanzamiento.id"))
    k_categoria = db.Column(db.String(30), db.ForeignKey("categoria.k_categoria"))
    n_producto = db.Column(db.String(100))
    p_producto = db.Column(db.Numeric(11,2), nullable = False )
    d_producto = db.Column(db.String(200))
    stock = db.Column(db.Numeric(5,0), nullable=False)
    #i_producto = db.Column(db.String(500))
    
    f_producto = db.Column(db.DateTime, default=datetime.now)
    #atributos de la relacion
    lanzamiento = db.relationship("Lanzamiento")
    categoria = db.relationship("Categoria")

class Imagen(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    k_producto = db.Column(db.Integer, db.ForeignKey("producto.id"))
    img = db.Column(db.Text)
    name= db.Column(db.Text, nullable= False)
    mimetype= db.Column(db.Text, nullable= False)
    #atributos de la relacion
    producto = db.relationship("Producto")
    


class Item(db.Model):
    k_producto = db.Column(db.Integer, db.ForeignKey("producto.id"), primary_key=True)
    k_factura = db.Column(db.Integer,db.ForeignKey("invoice.id"), primary_key=True)
    cant_item = db.Column(db.Numeric(3,0), nullable=False)
    p_item = db.Column(db.Numeric(11,2), nullable=False)
    #atributos de la relacion
    producto = db.relationship("Producto")
    factura = db.relationship("Invoice")

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    k_usuario = db.Column(db.Integer, db.ForeignKey("usuario.id"), primary_key= False)
    id_factura_payco = db.Column(db.String(100))
    ref_payco = db.Column(db.String(100))
    f_compra = db.Column(db.DateTime, default=datetime.now)
    total = db.Column(db.Numeric(13,2), nullable=False)
    #atributos de la relacion
    usuario = db.relationship("Usuario")

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    k_rol = db.Column(db.String(20), db.ForeignKey('rol.k_rol'))
    n_usuario = db.Column(db.String(20), nullable=False)
    ape_usuario = db.Column(db.String(20), nullable=False)
    email_usuario = db.Column(db.String(50), unique=True, nullable=False)
    pwd_usuario = db.Column(db.String(100), nullable=False)
    dir_usuario = db.Column(db.String(200))
    lugar_usuario =db.Column(db.String(80))
    #datos de envío que vienen del formulario de solicitudes (antes musical_box_manager)
    tipo_id = db.Column(db.String(4))
    num_id = db.Column(db.String(12))
    barrio_usuario = db.Column(db.String(30))
    cel_usuario = db.Column(db.String(20))
    f_registro = db.Column(db.DateTime, default=datetime.now)
    #atributo de la relacion
    rol = db.relationship("Rol")

class Rol(db.Model):
    k_rol = db.Column(db.String(20), primary_key=True)

ROLES = ['USER', 'ADMIN', 'CLIENTE']

class Solicitud(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    k_usuario = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    #producto del catálogo, o texto libre si el cliente pide algo que no tenemos
    k_producto = db.Column(db.Integer, db.ForeignKey("producto.id"))
    n_producto_solicitado = db.Column(db.String(150))
    d_producto_solicitado = db.Column(db.String(200))
    estado = db.Column(db.String(20), nullable=False, default='ACTIVO')
    f_solicitud = db.Column(db.DateTime, default=datetime.now)
    f_actualizacion = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    #atributos de la relacion
    usuario = db.relationship("Usuario")
    producto = db.relationship("Producto")

ESTADOS_SOLICITUD = ['ACTIVO', 'EN PROCESO', 'ENVIADO', 'ENTREGADO', 'CANCELADO']

class Categoria(db.Model):
    k_categoria = db.Column(db.String(30), primary_key=True)



#ESQUEMAS schema
class LanzamientoSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Lanzamiento
        fields = ["id", "n_lanzamiento", "f_lanzamiento", "i_lanzamiento"]

class ArtistaSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Artista
        fields = ["id", "n_artista", "pais_artista"]

class Lanzamiento_ArtistaSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Lanzamiento_Artista
        fields = ["k_artista", "k_lanzamiento"]

class GeneroSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Genero
        fields = ["k_genero"]

class Lanzamiento_GeneroSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Lanzamiento_Genero
        fields = ["k_lanzamiento", "k_genero", "subgenre"]

class ProductoSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Producto
        fields = ["id", "k_lanzamiento", "k_categoria", "n_producto", "p_producto", "d_producto", 'stock', 'i_producto', 'f_producto']

class ImagenSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Imagen
        fields = ["id", "k_producto", "img_data"]


class ItemSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Item
        fields = ["k_factura", "k_producto", "cant_item", "p_item"]

class InvoiceSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Invoice
        fields = ["id", "k_usuario", "id_factura_payco" ,"ref_payco","f_compra", "total"]

class UsuarioSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Usuario
        fields = ["id", "k_rol", "n_usuario","ape_usuario", "email_usuario", "pwd_usuario", "dir_usuario", "lugar_usuario", "tipo_id", "num_id", "barrio_usuario", "cel_usuario"]

class SolicitudSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Solicitud
        fields = ["id", "k_usuario", "k_producto", "n_producto_solicitado", "d_producto_solicitado", "estado", "f_solicitud"]

class RolSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Rol
        fields = ["k_rol"]

class CategoriaSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Categoria
        fields = ["k_categoria"]

#FOR KEY VALUE :) --- CATEGORY
class CategoriaSchemaJSON(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Categoria
        fields = ["key", "value"] 


#mis consultas 
def create_new_user(n_usuario, ape_usuario, email, password):
    print(email)
    print(password)

    #k_usuario = "U"+str(len(get_all_users())+1)
    #si ya hizo una solicitud sin cuenta (rol CLIENTE), la cuenta se reclama con el mismo email
    user = Usuario.query.filter_by(email_usuario=email, k_rol='CLIENTE').first()
    if user:
        user.k_rol = 'USER'
        user.n_usuario = n_usuario
        user.ape_usuario = ape_usuario
        user.pwd_usuario = password
    else:
        user = Usuario( k_rol='USER' ,n_usuario =n_usuario,ape_usuario=ape_usuario, email_usuario=email, pwd_usuario=password )
    
    try:
        db.session.add(user)
        db.session.commit()
        return user
    except Exception as e:
        print ("No se registró el usuario "+ str(e))
        return None
    

def create_new_artist(n_artista, pais_artista):
    print("ARTISTA: "+ n_artista)
    query_artist = verify_existence_artist(n_artista)
    if query_artist:
        print("El artista ya ha sido registrado!")
        return None
    else:
        #k_artista = "A"+str(len(get_all_artists())+1)
        artista = Artista(n_artista=n_artista, pais_artista=pais_artista)
    
        db.session.add(artista)

        try:
            db.session.add(artista)
            db.session.commit()
            return (artista)
        except Exception as e:
            print("NO SE CREÓ EL artista "+ str(e))
            db.session.rollback()
            return None
            
    

def create_new_release(k_artista, n_lanzamiento,i_lanzamiento, f_lanzamiento, k_genero):
    #k_lanzamiento = "LANZ"+str(len(get_all_releases())+1)
    lanzamiento = Lanzamiento(n_lanzamiento=n_lanzamiento, i_lanzamiento=i_lanzamiento, f_lanzamiento=f_lanzamiento)
    try:
        db.session.add(lanzamiento)
        k_lanzamiento = get_release_by_name(lanzamiento.n_lanzamiento)
        print("EL ID DEL LANZAMIENTO QUEDÓ REGISTRADO ASI : "+str(k_lanzamiento))
        lanzamiento_artista = Lanzamiento_Artista(k_lanzamiento =lanzamiento.id, k_artista=k_artista)
        print(lanzamiento_artista)
        db.session.add(lanzamiento_artista)
        db.session.commit()
        return(k_lanzamiento)
    except Exception as e:
        print("NO SE CREÓ EL lanzamiento "+ str(e))
        db.session.rollback()
        return None

#n_producto, p_producto, d_producto, stock, i_producto, k_categoria
def create_new_product(k_lanzamiento, n_producto, p_producto, d_producto, stock, i_producto, k_categoria):
    product = Producto(k_lanzamiento=k_lanzamiento, n_producto=n_producto, p_producto=p_producto, d_producto=d_producto, stock=stock,k_categoria=k_categoria )
    try:
        db.session.add(product)
        db.session.commit()
        
        db.session.flush
        return (product)
    except Exception as e:
        print("NO SE CREÓ EL producto "+ str(e))
        db.session.rollback()
        return None
   
def create_new_image(producto_key, image_file):
    filename = secure_filename(image_file.filename)
    mimetype = image_file.mimetype

    image = Imagen(img = image_file.read(), mimetype = mimetype, k_producto = producto_key, name=filename)
    try:
        db.session.add(image)
        db.session.commit()
        print("SE CREÓ LA IMAGEN " )
        return image
    except Exception as e:
        print("NO SE CREÓ LA IMAGEN " + str(e))
        db.session.rollback()
        return None

    


def create_new_category(category):
    c = Categoria(k_categoria=category)
    try:
        db.session.add(c)
        db.session.commit()
        return (c)
    except:
        return None

def create_new_genre(genre):
    c = Genero(k_genero=genre)
    try:
        db.session.add(c)
        db.session.commit()
        return (c)
    except:
        return None

def create_release_genre(k_lanzamiento, k_genero):
    r_g = Lanzamiento_Genero(k_lanzamiento=k_lanzamiento, k_genero=k_genero)
    try:
        db.session.add(r_g)
        db.session.commit()
        return (r_g)
    except:
        return None

def create_new_invoice(cart, user_id, id_factura_payco, ref_payco):
    print("creando nueva factura")
    print(cart)
    invoice = Invoice(k_usuario = user_id, total = get_total(cart), id_factura_payco = id_factura_payco, ref_payco = ref_payco )
    print("SOO MY INVOICE WILL BE")
    print(invoice.id)
    try:
        db.session.add(invoice)
        db.session.commit()
        print("SE CREO LA FACTURA!")
        return invoice
    except Exception as e:
        print("ERROR CRITICO NO SE CREO LA FACTURA! "+ str(e))
        db.session.rollback()
        return None
    
def add_items(factura_id, cart):
    for i in cart:
        item = Item(k_producto = i, k_factura = factura_id, p_item = get_product_by_id(i).p_producto, cant_item = cart[i] )
        print("SOOO THE ITEM factura es IS")
        print(item.k_producto)
        try:
            db.session.add(item)
            db.session.commit()
            print("SE CREO el item")
        except:
            print("ERROR CRITICO NO SE CREO el itme :(!")
            db.session.rollback()
    return "ok"

def update_stock(cart):
    
        for i in cart:
            try:
                producto = Producto.query.filter_by(id=i).first()
                print("Producto "+ str(producto))
                producto.stock = producto.stock - cart[i]
                db.session.commit()
            except Exception as e:
                print("ERROR EN UPDATE STOCK "+ str(e)+ " en: " + str(i))

          


def get_total(items):
    total =0
    for p in items:
        total += get_product_by_id(p).p_producto * items[p]
    print("EL TOTAL ES:")
    print(total)
    return total

def new_admin(email, pwd, guser):
    print(guser)
    print(pwd)
    if guser['pwd_usuario'] == pwd:
        
        try:
            Usuario.query.filter_by(email_usuario = email).update({"k_rol": 'ADMIN' })
            db.session.commit()  
            return 'OK'  
        except:
            return None  
    print("No cumple")
    return None  

def get_all_products():
    products_qs = Producto.query.all()
    product_schema = ProductoSchema()
    products=[product_schema.dump(product) for product in products_qs]
    return products

def get_all_users():
    users_qs = Usuario.query.all()
    users_schema = UsuarioSchema()
    users=[users_schema.dump(user) for user in users_qs]
    return users

def get_all_artists():
    artist_qs = Artista.query.all()
    artist_schema = ArtistaSchema()
    artists=[artist_schema.dump(artista) for artista in artist_qs]
    return artists

def get_all_releases():
    release_qs=Lanzamiento.query.order_by(db.desc(Lanzamiento.f_lanzamiento)).all()
    release_Schema=LanzamientoSchema()
    releases=[release_Schema.dump(lanz) for lanz in release_qs]
    return releases

def get_all_genres():

    try:
        genre_qs = Genero.query.all()
        genre_schema = GeneroSchema()
        generos = [genre_schema.dump(genre) for genre in genre_qs]
        return generos
    except Exception as e:
        print(e)
    

def get_release_artist():
    r_a_qs= Lanzamiento_Artista.query.all()
    r_a_schema  = Lanzamiento_ArtistaSchema()
    r_a = [r_a_schema.dump(r_a) for r_a in r_a_qs ]

def get_user_by_email(email):
    usuario_qs = Usuario.query.filter_by(email_usuario = email).first()
    usuario_schema = UsuarioSchema()
    u = usuario_schema.dump(usuario_qs)
    return u

def get_purchases_by_user(email):
    user = get_user_by_email(email)
    invoices = Invoice.query.filter_by(k_usuario = user["id"]).all()
    facturas = []
    for i in invoices:
        items = get_items_by_id_factura(i.id)
        print(items)
        facturas.append([i, items])
    return facturas

def get_items_by_id_factura(id):
    items = Item.query.filter_by(k_factura = id).all()
    return items 

def get_k_artist_by_name(artista):
    artist_qs = Artista.query.filter_by(n_artista = artista).first()
    artist_schema=ArtistaSchema()
    a = artist_schema.dump(artist_qs)
    return a['id']

def get_release_by_name(lanzamiento):
    release_qs = Lanzamiento.query.filter_by(n_lanzamiento = lanzamiento).first()
    release_schema=LanzamientoSchema()
    r = release_schema.dump(release_qs)
    if r:

        return r['id']
    return "No existe!!"

def get_artist_by_id(id):
    artist_qs = Artista.query.filter_by(id = id).first()
    artist_schema=ArtistaSchema()
    a = artist_schema.dump(artist_qs)
    return a

def verify_existence_artist(n_artista):
    artist_qs = Artista.query.filter_by(n_artista =n_artista).first()
    artist_schema=ArtistaSchema()
    a = artist_schema.dump(artist_qs)
    if a:
        return a['n_artista']
    else:
        return None

def get_release_by_id(id):
    release_qs = Lanzamiento.query.filter_by(id = id).first()
    release_schema=LanzamientoSchema()
    r = release_schema.dump(release_qs)
    print("LANZAMIENTO :" + str(r) )
    if r:
        return r
    return  {}

def get_releases_with_artists():
    try:
        release_artist_qs = Lanzamiento_Artista.query.all()
        release_artists_schema = Lanzamiento_ArtistaSchema()
        releases=[release_artists_schema.dump(lanz) for lanz in release_artist_qs]
        r=[]
        for release in releases:
            
            artista = get_artist_by_id(release["k_artista"]).get("n_artista", 'N/A').title()
            lanzamiento = get_release_by_id(release["k_lanzamiento"]).get("n_lanzamiento", "N/A")
            k_lanzamiento = str(release["k_lanzamiento"])
            print(lanzamiento)
            r.append(k_lanzamiento+". "+artista + " - "+  lanzamiento)
        return r
    except Exception as e:
        print("ERROR: "+str(e))
        return None 

def get_products_with_info():
    try:
        product_qs = Producto.query.all()
        products_schema = ProductoSchema()
        products=[products_schema.dump(p) for p in product_qs]
        r=[]
        for product in products:
            
            k_producto = str(product["id"])
            lanzamiento = get_release_by_id(product["k_lanzamiento"])["n_lanzamiento"]
            name = product["n_producto"]
            
            r.append(k_producto+". "+lanzamiento + " - "+  name)
        return r
    except Exception as e:
        print("ERROR: "+str(e))
        return None 

def get_categories():
    category_qs = Categoria.query.all()
    categories_schema= CategoriaSchema()
    categories = [categories_schema.dump(c) for c in category_qs]
    print(categories)
    cat =[]
    for c in categories:
        cat.append((c["k_categoria"],c["k_categoria"]))

    print (cat)
    return cat

def get_releases_artista(k_artista):
    release_qs=Lanzamiento_Artista.query.filter_by(k_artista=k_artista)
    release_Schema=Lanzamiento_ArtistaSchema()
    releases=[release_Schema.dump(lanz) for lanz in release_qs]
    return releases
    

def get_k_release_by_name_artista(n_lanzamiento,n_artista):
    k_artista = get_k_artist_by_name(n_artista)
    k_lanzamiento = get_release_by_name(n_lanzamiento)
    lanz_art = get_releases_artista(k_artista)
    for l in lanz_art:
        if l['k_lanzamiento'] == k_lanzamiento:
            return k_lanzamiento
    return None

def get_image_by_product(k_producto):
    print("el codigo del producto es "+ str(k_producto))
    try:
        #image = Imagen.query.filter_by(k_producto = k_producto).first()
        image = Imagen.query.filter_by(k_producto = k_producto).first()
        print("encontré la imagen ! :) ,  es" + str(image.name))
        
        #print(img)
        return Response(image.img, mimetype=image.mimetype)
    except Exception as e:
        print("no encontré la imagen ! :( " + str(e))
        return None

def get_rawimage_by_product(k_producto):
    try:
        #image = Imagen.query.filter_by(k_producto = k_producto).first()
        image = Imagen.query.filter_by(k_producto = k_producto).first()
        print("encontré la imagen ! :) ,  es" + str(image.name))
        
        #print(img)
        return image.img
    except Exception as e:
        print("no encontré la imagen ! :( " + str(e))
        return None
    

def get_artist_by_release(k_lanzamiento):
    lanz_art = Lanzamiento_Artista.query.filter_by(k_lanzamiento=k_lanzamiento).first()
    if not lanz_art:
        return None
    #print(lanz_art)
    artista = Artista.query.filter_by(id = lanz_art.k_artista ).first()
    #print(artista)
    return artista

def get_categories_by_release(k_lanzamiento):
    #Song.query.filter(Song.artist.has(Artist.genres.any(Genre.name == 'rock')))
    #productos = Producto.query.filter_by(k_lanzamiento=k_lanzamiento).first()
    productos  =Producto.query.filter(Producto.k_lanzamiento == k_lanzamiento ).all()
    pr=[]
    for p in productos:
        pr.append(p.k_categoria)
    pr= sorted(set(pr))
    return pr

def get_genres_by_release(k_lanzamiento):
    genres_qs = Lanzamiento_Genero.query.filter_by(k_lanzamiento=k_lanzamiento).all()
    genre_schema = GeneroSchema()
    
    
    genres=[genre_schema.dump(g) for g in genres_qs]
    print(genres)
    return genres

def get_products_by_release(k_lanzamiento):
    products = Producto.query.filter_by(k_lanzamiento=k_lanzamiento).all()
    return products

def get_product_by_id(k_producto):
    product = Producto.query.filter_by(id=k_producto).first()
    return product

#updatessss
def update_release(k_lanzamiento, n_lanzamiento, i_lanzamiento, k_artista, f_lanzamiento, k_genero):
    lanzamiento = Lanzamiento.query.filter_by(id = k_lanzamiento).first()
    lanzamiento_artista = Lanzamiento_Artista.query.filter_by(k_lanzamiento = k_lanzamiento).first()
    lanz_genero = Lanzamiento_Genero.query.filter_by(k_lanzamiento = k_lanzamiento).first()
    print("models.update_rleease nos dice: ")
    try:
        lanzamiento.n_lanzamiento = n_lanzamiento
        lanzamiento.i_lanzamiento = i_lanzamiento
        lanzamiento.f_lanzamiento = f_lanzamiento
        print(lanzamiento)
        lanzamiento_artista.k_artista = k_artista
        if k_genero != 'N/A':
            lanz_genero.k_genero  =  k_genero
        db.session.commit()
        print("si pude :)")
        return "ok"
    except:
        print("No actualizo ")
        db.session.rollback()
        return None
    
def edit_product(k_producto, n_producto, d_producto, p_producto, i_producto, k_category, stock):
    producto = Producto.query.filter_by(id = k_producto).first()
    try:
        producto.n_producto = n_producto
        producto.d_producto = d_producto
        if p_producto is not None:
            print("CAMBIARÈ EL PRECIO PRODCUTO")
            producto.p_producto = p_producto
        else:
            print("SE ENVIA UN NONE")
            None

        if i_producto:
            print("se debe cmabiar la imagen "+ str(i_producto))
            img_edit = edit_image(k_producto, i_producto)
            if img_edit:
                print("SE ACTUALIZÒ LA IMAGEN")
        else:
            print("No se detectan cambios en la imagen")
        producto.k_categoria = k_category
        producto.stock = stock
        db.session.commit()
        db.session.flush()
        print("si pude :)")
        return "ok"
    except Exception as e:
        print("No actualizo "+ str(e))
        db.session.rollback()
        return None

def edit_image(k_producto, image_file):
    
    image = Imagen.query.filter_by(k_producto = k_producto).first()
    if image:
        print("ACTUALIZANDO IMAGEN ... ")
        filename = secure_filename(image_file.filename)
        mimetype = image_file.mimetype
        print("ANTES ...................")
        print(str(image.name))
        
        try:
            image.img  = image_file.read()
            image.mimetype = mimetype
            image.name = filename
            db.session.commit()
            db.session.flush()
            print("DESPUES.......... ")
            print(str(image.name))
            
            return image
        except Exception as e:
            print("No se actualizò la imagen ! "+str(e))
            db.session.rollback()
            return None
    else:
        print("SE DEBERÀ SUBIR NUEVA IMAGEN asociada la producto")
        return create_new_image(k_producto,image_file)

def edit_user_by_email(email, nombre,apellido,ciudad,direccion, barrio=None, celular=None):
    try:
        user  = Usuario.query.filter_by(email_usuario = email).first()
        print("USUARIO ENCONTRADO "+ str(user))
        user.n_usuario = nombre
        user.ape_usuario = apellido
        user.lugar_usuario = ciudad
        user.dir_usuario = direccion
        user.barrio_usuario = barrio
        user.cel_usuario = celular
        db.session.commit()
        db.session.flush()
        print("EXITO!")
        return user
    except Exception as e:
        print("ERROR " + str(e))
        db.session.rollback()
        return None
    

#solicitudes de pedido (integrado desde musical_box_manager)
def seed_roles():
    for rol in ROLES:
        if not db.session.get(Rol, rol):
            db.session.add(Rol(k_rol=rol))
    db.session.commit()

def get_or_create_cliente(tipo_id, num_id, nombre, apellido, email, direccion, ciudad, barrio, celular):
    #primero por documento, luego por email: así una solicitud queda ligada a la cuenta de la tienda si ya existe
    user = Usuario.query.filter_by(tipo_id=tipo_id, num_id=num_id).first()
    if not user:
        user = Usuario.query.filter(db.func.lower(Usuario.email_usuario) == email.lower()).first()
    try:
        if user:
            #completa solo lo que falte, no pisa datos de la cuenta
            user.tipo_id = user.tipo_id or tipo_id
            user.num_id = user.num_id or num_id
            user.cel_usuario = celular or user.cel_usuario
            user.dir_usuario = direccion or user.dir_usuario
            user.lugar_usuario = ciudad or user.lugar_usuario
            user.barrio_usuario = barrio or user.barrio_usuario
        else:
            #cliente sin cuenta: contraseña aleatoria, puede reclamar la cuenta registrándose con el mismo email
            user = Usuario(k_rol='CLIENTE', n_usuario=nombre, ape_usuario=apellido, email_usuario=email,
                           pwd_usuario=secrets.token_hex(16), tipo_id=tipo_id, num_id=num_id,
                           dir_usuario=direccion, lugar_usuario=ciudad, barrio_usuario=barrio, cel_usuario=celular)
            db.session.add(user)
        db.session.commit()
        return user, None
    except Exception as e:
        print("No se registró el cliente " + str(e))
        db.session.rollback()
        return None, str(e)

def create_solicitud(k_usuario, k_producto, n_producto_solicitado, d_producto_solicitado=None):
    solicitud = Solicitud(k_usuario=k_usuario, k_producto=k_producto, n_producto_solicitado=n_producto_solicitado,
                          d_producto_solicitado=d_producto_solicitado, estado='ACTIVO')
    try:
        db.session.add(solicitud)
        db.session.commit()
        return solicitud, None
    except Exception as e:
        print("No se creó la solicitud " + str(e))
        db.session.rollback()
        return None, str(e)

def get_all_solicitudes():
    return Solicitud.query.order_by(db.desc(Solicitud.f_solicitud)).all()

def get_solicitud_by_id(id):
    return db.session.get(Solicitud, id)

def get_solicitudes_by_user(email):
    user = Usuario.query.filter_by(email_usuario=email).first()
    if not user:
        return []
    return Solicitud.query.filter_by(k_usuario=user.id).order_by(db.desc(Solicitud.f_solicitud)).all()

def update_estado_solicitud(id, estado):
    solicitud = db.session.get(Solicitud, id)
    if not solicitud or estado not in ESTADOS_SOLICITUD:
        return None
    try:
        solicitud.estado = estado
        db.session.commit()
        return solicitud
    except Exception as e:
        print("No se actualizó la solicitud " + str(e))
        db.session.rollback()
        return None

def get_catalogo_solicitud():
    #productos del catálogo con stock para el autocompletado del formulario de solicitud
    productos = Producto.query.all()
    r = []
    for p in productos:
        artista = get_artist_by_release(p.k_lanzamiento) if p.k_lanzamiento else None
        lanzamiento = p.lanzamiento.n_lanzamiento if p.lanzamiento else ''
        nombre = " - ".join(x for x in [artista.n_artista.title() if artista else '', lanzamiento, p.n_producto or ''] if x)
        r.append({"id": p.id, "nombre": nombre, "categoria": p.k_categoria, "stock": int(p.stock or 0)})
    return r

def get_all_invoices():
    return Invoice.query.order_by(db.desc(Invoice.f_compra)).all()


#datos listos para las tarjetas de la interfaz
def _fecha(valor):
    if isinstance(valor, str):
        try:
            return datetime.strptime(valor, '%Y-%m-%d').date()
        except ValueError:
            return None
    return valor

def get_releases_cards(q=None, k_artista=None, limit=None):
    q = (q or '').strip().lower()
    cards = []
    for lanz in Lanzamiento.query.order_by(db.desc(Lanzamiento.f_lanzamiento)).all():
        artista = get_artist_by_release(lanz.id)
        if k_artista and (not artista or artista.id != k_artista):
            continue
        productos = Producto.query.filter_by(k_lanzamiento=lanz.id).all()
        generos = [g.k_genero for g in Lanzamiento_Genero.query.filter_by(k_lanzamiento=lanz.id).all()]
        categorias = sorted({p.k_categoria for p in productos if p.k_categoria})
        texto = " ".join([lanz.n_lanzamiento, artista.n_artista if artista else ''] + generos + categorias).lower()
        if q and q not in texto:
            continue
        fecha = _fecha(lanz.f_lanzamiento)
        cards.append({
            "id": lanz.id,
            "nombre": lanz.n_lanzamiento,
            "portada": lanz.i_lanzamiento,
            "fecha": fecha,
            "artista": artista,
            "generos": generos,
            "categorias": categorias,
            "nuevo": bool(fecha and (datetime.now().date() - fecha).days < 30),
            "agotado": bool(productos) and all((p.stock or 0) <= 0 for p in productos),
            "precio_desde": min((p.p_producto for p in productos), default=None),
        })
        if limit and len(cards) >= limit:
            break
    return cards

def get_products_cards(limit=None):
    query = Producto.query.order_by(db.desc(Producto.f_producto))
    if limit:
        query = query.limit(limit)
    cards = []
    for p in query.all():
        cards.append({
            "id": p.id,
            "nombre": p.n_producto,
            "lanzamiento": p.lanzamiento,
            "artista": get_artist_by_release(p.k_lanzamiento) if p.k_lanzamiento else None,
            "categoria": p.k_categoria,
            "precio": p.p_producto,
            "stock": int(p.stock or 0),
            "descripcion": p.d_producto,
        })
    return cards

def get_admin_stats():
    return {
        "solicitudes_activas": Solicitud.query.filter(Solicitud.estado.in_(['ACTIVO', 'EN PROCESO'])).count(),
        "ordenes": Invoice.query.count(),
        "ventas": sum((i.total or 0) for i in Invoice.query.all()),
        "productos": Producto.query.count(),
        "agotados": Producto.query.filter(Producto.stock <= 0).count(),
        "lanzamientos": Lanzamiento.query.count(),
        "clientes": Usuario.query.filter(Usuario.k_rol.in_(['USER', 'CLIENTE'])).count(),
        "ultimas_solicitudes": Solicitud.query.order_by(db.desc(Solicitud.f_solicitud)).limit(5).all(),
        "ultimas_ordenes": Invoice.query.order_by(db.desc(Invoice.f_compra)).limit(5).all(),
    }
