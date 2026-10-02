#from app.db import db, ma
from flask.wrappers import Response
from werkzeug.utils import secure_filename
from ..db import db, ma
from datetime import datetime, timedelta
from base64 import b64encode
import re
import secrets
import hashlib
import requests
from sqlalchemy.exc import IntegrityError
from .seguridad import hash_password, check_password



class Lanzamiento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    n_lanzamiento = db.Column(db.String(100), nullable = False )
    f_lanzamiento = db.Column(db.Date)
    i_lanzamiento = db.Column(db.String(500))
    #post de Instagram/TikTok sobre el lanzamiento (opcional)
    url_social = db.Column(db.String(300))
    #album externo (Spotify): para re-sincronizar metadatos; ver app/store/musicapi.py
    external_id = db.Column(db.String(100), unique=True)
    external_url = db.Column(db.String(300))
    #paraguas de preorden: si la tirada no ha llegado, todos sus productos sueltos se preordinan
    preorden = db.Column(db.Boolean, nullable=False, default=False, server_default='0')

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
    #stock propio solo para SIMPLE sin variantes; con variantes vive en Variante y en un BUNDLE se calcula
    stock = db.Column(db.Numeric(5,0), nullable=False)
    #imagen externa opcional (link de Google Drive o URL directa a un archivo de imagen);
    #se guarda tal cual la pegó el admin y se normaliza al servirla. Solo se usa si no hay fotos subidas.
    url_imagen = db.Column(db.String(500))
    
    f_producto = db.Column(db.DateTime, default=datetime.now)
    #SIMPLE: se vende tal cual · BUNDLE: pack que descuenta el stock de sus componentes
    tipo = db.Column(db.String(10), nullable=False, default='SIMPLE', server_default='SIMPLE')
    #merch personalizado hecho por Musical Box
    original_mb = db.Column(db.Boolean, nullable=False, default=False, server_default='0')
    #preorden: se vende antes de que llegue la tirada (paga hoy, llega después); solo SIMPLE sin tallas
    preorden = db.Column(db.Boolean, nullable=False, default=False, server_default='0')
    #atributos de la relacion
    lanzamiento = db.relationship("Lanzamiento")
    categoria = db.relationship("Categoria")
    variantes = db.relationship("Variante", back_populates="producto", order_by="Variante.id")
    componentes = db.relationship("ProductoComponente", foreign_keys="ProductoComponente.k_bundle", back_populates="bundle")

TIPOS_PRODUCTO = ['SIMPLE', 'BUNDLE']

class Variante(db.Model):
    #talla/color de un producto (camiseta M negra); cada una con su stock
    id = db.Column(db.Integer, primary_key=True)
    k_producto = db.Column(db.Integer, db.ForeignKey("producto.id"), nullable=False, index=True)
    talla = db.Column(db.String(20))
    color = db.Column(db.String(30))
    sku = db.Column(db.String(40), unique=True)
    stock = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    __table_args__ = (db.UniqueConstraint('k_producto', 'talla', 'color', name='uq_variante_producto_talla_color'),
                      db.CheckConstraint('stock >= 0', name='stock_no_negativo'))
    #atributos de la relacion
    producto = db.relationship("Producto", back_populates="variantes")

    @property
    def nombre(self):
        return " / ".join(x for x in [self.talla, self.color] if x)

class ProductoComponente(db.Model):
    #qué lleva un bundle: producto (y variante, si el componente tiene tallas/colores) y cuántas unidades
    __tablename__ = 'producto_componente'
    id = db.Column(db.Integer, primary_key=True)
    k_bundle = db.Column(db.Integer, db.ForeignKey("producto.id"), nullable=False, index=True)
    k_componente = db.Column(db.Integer, db.ForeignKey("producto.id"), nullable=False)
    k_variante = db.Column(db.Integer, db.ForeignKey("variante.id"))
    cantidad = db.Column(db.Integer, nullable=False, default=1, server_default='1')
    __table_args__ = (db.CheckConstraint('cantidad > 0', name='cantidad_positiva'),
                      db.CheckConstraint('k_bundle <> k_componente', name='no_se_contiene'))
    #atributos de la relacion
    bundle = db.relationship("Producto", foreign_keys=[k_bundle], back_populates="componentes")
    componente = db.relationship("Producto", foreign_keys=[k_componente])
    variante = db.relationship("Variante")

class Imagen(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    k_producto = db.Column(db.Integer, db.ForeignKey("producto.id"), nullable=False)
    img = db.Column(db.Text, nullable=False)
    name = db.Column(db.Text, nullable=False)
    mimetype = db.Column(db.Text, nullable=False)
    orden = db.Column(db.Integer, nullable=False, default=0)
    #atributos de la relacion
    producto = db.relationship("Producto", backref="imagenes")
    
    def __repr__(self):
        return f'<Imagen {self.name} for Producto {self.k_producto}>'
    


class ReservaStock(db.Model):
    """Tabla para almacenar las reservas de stock temporal mientras se procesa un pedido."""
    __tablename__ = 'reserva_stock'
    
    id = db.Column(db.Integer, primary_key=True)
    k_invoice = db.Column(db.Integer, db.ForeignKey("invoice.id"), nullable=False, index=True)
    # Tipo de elemento reservado: 'P' para Producto, 'V' para Variante
    tipo_elemento = db.Column(db.String(1), nullable=False)
    # ID del elemento (producto o variante)
    k_elemento = db.Column(db.Integer, nullable=False)
    # Cantidad reservada
    cantidad = db.Column(db.Integer, nullable=False)
    # Fecha de creación de la reserva
    f_creacion = db.Column(db.DateTime, default=datetime.now, nullable=False)
    # Fecha de expiración de la reserva (por defecto 30 minutos)
    f_expiracion = db.Column(db.DateTime, nullable=False)
    
    # Relaciones
    invoice = db.relationship("Invoice", backref="reservas_stock")
    
    __table_args__ = (
        db.UniqueConstraint('k_invoice', 'tipo_elemento', 'k_elemento', name='uq_reserva_invoice_elemento'),
        db.CheckConstraint("tipo_elemento IN ('P', 'V')", name='chk_tipo_elemento'),
        db.CheckConstraint('cantidad > 0', name='chk_cantidad_positiva')
    )


class Item(db.Model):
    #línea de pedido; id propio para permitir el mismo producto con distintas variantes en un pedido
    id = db.Column(db.Integer, primary_key=True)
    #opcional: las líneas a la medida pueden venderse sin producto de catálogo
    k_producto = db.Column(db.Integer, db.ForeignKey("producto.id"))
    k_factura = db.Column(db.Integer,db.ForeignKey("invoice.id"), nullable=False, index=True)
    k_variante = db.Column(db.Integer, db.ForeignKey("variante.id"))
    #lanzamiento de referencia (portada) y descripción propia cuando no hay producto de catálogo
    k_lanzamiento = db.Column(db.Integer, db.ForeignKey("lanzamiento.id"))
    n_item = db.Column(db.String(150))
    cant_item = db.Column(db.Numeric(3,0), nullable=False)
    p_item = db.Column(db.Numeric(11,2), nullable=False)
    #atributos de la relacion
    producto = db.relationship("Producto")
    factura = db.relationship("Invoice")
    variante = db.relationship("Variante")
    lanzamiento = db.relationship("Lanzamiento")

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    k_usuario = db.Column(db.Integer, db.ForeignKey("usuario.id"), primary_key= False)
    id_factura_payco = db.Column(db.String(100))
    ref_payco = db.Column(db.String(100))
    mp_payment_id = db.Column(db.String(100))  # ID de pago de MercadoPago
    f_compra = db.Column(db.DateTime, default=datetime.now)
    total = db.Column(db.Numeric(13,2), nullable=False)
    #checkout sin cuenta: el pedido existe antes del pago (PENDIENTE) y la pasarela lo confirma o rechaza
    estado = db.Column(db.String(20), nullable=False, default='PENDIENTE', server_default='PENDIENTE')
    #logística, separada del pago: se activa cuando el pedido queda PAGADO
    estado_envio = db.Column(db.String(20))
    metodo_pago = db.Column(db.String(30))
    #enlace /pedido/<token>: solo se guarda el SHA-256 del token, nunca el token
    token_hash = db.Column(db.String(64), unique=True)
    token_creado = db.Column(db.DateTime)
    #datos de envío tal como se escribieron en este pedido (no cambian si el comprador edita su perfil)
    n_envio = db.Column(db.String(100))
    email_envio = db.Column(db.String(100))
    tel_envio = db.Column(db.String(20))
    dir_envio = db.Column(db.String(200))
    lugar_envio = db.Column(db.String(80))
    barrio_envio = db.Column(db.String(30))
    f_actualizacion = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    #campo para indicar si el stock ha sido reservado
    stock_reservado = db.Column(db.Boolean, default=False, server_default='0')
    #nota interna del admin (corrección de dirección, detalles del cliente, etc.)
    nota = db.Column(db.Text)
    #atributos de la relacion
    usuario = db.relationship("Usuario")
    items = db.relationship("Item", viewonly=True, order_by="Item.id")

ESTADOS_PEDIDO = ['PENDIENTE', 'PAGADO', 'RECHAZADO']
ESTADOS_ENVIO = ['POR PREPARAR', 'EN PREPARACION', 'ENVIADO', 'ENTREGADO']
#el rótulo solo tiene sentido cuando el pedido se está preparando o ya salió
ESTADOS_CON_ROTULO = ['EN PREPARACION', 'ENVIADO']
METODOS_PAGO = [('TARJETA', 'Tarjeta de crédito o débito'), ('PSE', 'PSE (débito desde tu banco)'), ('EFECTIVO', 'Efectivo (Efecty, Baloto y otros)')]

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
    #opcional: una solicitud puede llegar solo con celular (el comprador se crea al confirmar la compra)
    k_usuario = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    cel_contacto = db.Column(db.String(20))
    email_contacto = db.Column(db.String(100))
    #cotización: precio acordado, enlace "confirmar compra" (solo se guarda el hash) y la orden que resultó
    precio_cotizado = db.Column(db.Numeric(11,2))
    token_hash = db.Column(db.String(64), unique=True)
    k_invoice = db.Column(db.Integer, db.ForeignKey("invoice.id"))
    #producto del catálogo, o texto libre si el cliente pide algo que no tenemos
    k_producto = db.Column(db.Integer, db.ForeignKey("producto.id"))
    n_producto_solicitado = db.Column(db.String(150))
    d_producto_solicitado = db.Column(db.String(200))
    #unidades pedidas (preórdenes por encargo); 1 = nada especial (legacy: hoy viven en los ítems)
    cantidad = db.Column(db.Integer, nullable=False, default=1, server_default='1')
    #nota del admin sobre la cotización (tiempos, edición, acuerdos); va en el mensaje de WhatsApp
    d_cotizacion = db.Column(db.String(300))
    estado = db.Column(db.String(20), nullable=False, default='ACTIVO')
    f_solicitud = db.Column(db.DateTime, default=datetime.now)
    f_actualizacion = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    #atributos de la relacion
    usuario = db.relationship("Usuario")
    producto = db.relationship("Producto")
    pedido = db.relationship("Invoice")
    items = db.relationship("SolicitudItem", back_populates="solicitud", cascade="all, delete-orphan", order_by="SolicitudItem.id")

    @property
    def n_resumen(self):
        #primer ítem (o el campo legacy) con "+N" si hay más; para listados cortos del panel
        items = self.items or [ItemSolicitudVirtual(self)]
        nombre = items[0].nombre or ''
        return nombre + (f" +{len(items) - 1}" if len(items) > 1 else '')

    @property
    def total_cotizado(self):
        #suma precio por unidad × cantidad de sus líneas; 0 si aún no está cotizada
        return sum(int(it.precio_unit or 0) * int(it.cantidad or 1) for it in items_efectivos(self))

class SolicitudItem(db.Model):
    #línea de una solicitud a la medida: qué pide el cliente y la cotización del admin (precio y asociaciones)
    id = db.Column(db.Integer, primary_key=True)
    k_solicitud = db.Column(db.Integer, db.ForeignKey("solicitud.id"), nullable=False, index=True)
    #opcionales: producto del catálogo y/o lanzamiento (el que da la portada en el mensaje y en la orden)
    k_producto = db.Column(db.Integer, db.ForeignKey("producto.id"))
    k_lanzamiento = db.Column(db.Integer, db.ForeignKey("lanzamiento.id"))
    nombre = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.String(200))
    categoria = db.Column(db.String(30))
    cantidad = db.Column(db.Integer, nullable=False, default=1, server_default='1')
    #precio unitario acordado por el admin
    precio_unit = db.Column(db.Numeric(11,2))
    f_creacion = db.Column(db.DateTime, default=datetime.now)
    #atributos de la relacion
    solicitud = db.relationship("Solicitud", back_populates="items")
    producto = db.relationship("Producto")
    lanzamiento = db.relationship("Lanzamiento")

#ENVIADO/ENTREGADO quedan solo como historial de las solicitudes antiguas (el envío ahora es de la orden)
ESTADOS_SOLICITUD = ['ACTIVO', 'EN PROCESO', 'COTIZADA', 'COMPRADA', 'CANCELADO']

class Categoria(db.Model):
    k_categoria = db.Column(db.String(30), primary_key=True)



#ESQUEMAS schema
class LanzamientoSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Lanzamiento
        fields = ["id", "n_lanzamiento", "f_lanzamiento", "i_lanzamiento", "url_social", "external_id", "external_url"]

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
        fields = ["id", "k_lanzamiento", "k_categoria", "n_producto", "p_producto", "d_producto", 'stock', 'i_producto', 'f_producto', 'tipo']

class ImagenSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Imagen
        fields = ["id", "k_producto", "img_data"]


class ItemSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Item
        fields = ["id", "k_factura", "k_producto", "k_variante", "k_lanzamiento", "n_item", "cant_item", "p_item"]

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
        fields = ["id", "k_usuario", "k_producto", "n_producto_solicitado", "d_producto_solicitado", "cantidad", "d_cotizacion", "estado", "f_solicitud"]

class SolicitudItemSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = SolicitudItem
        fields = ["id", "k_solicitud", "k_producto", "k_lanzamiento", "nombre", "descripcion", "categoria", "cantidad", "precio_unit"]

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
    #las cuentas CLIENTE (compras/solicitudes sin cuenta) no se reclaman aquí: se activan con el enlace del correo
    user = Usuario( k_rol='USER' ,n_usuario =n_usuario,ape_usuario=ape_usuario, email_usuario=email.strip().lower(), pwd_usuario=hash_password(password) )
    try:
        db.session.add(user)
        db.session.commit()
        return user
    except Exception as e:
        print ("No se registró el usuario "+ str(e))
        db.session.rollback()
        return None

def get_usuario_por_email(email):
    return Usuario.query.filter(db.func.lower(Usuario.email_usuario) == (email or '').strip().lower()).first()
    

def create_new_artist(n_artista, pais_artista):
    query_artist = verify_existence_artist(n_artista)
    if query_artist:
        return get_usuario_por_email(n_artista)  # Retornar el artista existente
    else:
        #k_artista = "A"+str(len(get_all_artists())+1)
        artista = Artista(n_artista=n_artista, pais_artista=pais_artista)
    
        db.session.add(artista)

        try:
            db.session.add(artista)
            db.session.commit()
            return (artista)
        except Exception as e:
            db.session.rollback()
            return None
            
    

def create_new_release(k_artista, n_lanzamiento,i_lanzamiento, f_lanzamiento, k_genero, external_id=None, external_url=None):
    #k_lanzamiento = "LANZ"+str(len(get_all_releases())+1)
    lanzamiento = Lanzamiento(n_lanzamiento=n_lanzamiento, i_lanzamiento=i_lanzamiento, f_lanzamiento=f_lanzamiento,
                              external_id=(external_id or '').strip() or None, external_url=(external_url or '').strip() or None)
    try:
        db.session.add(lanzamiento)
        k_lanzamiento = get_release_by_name(lanzamiento.n_lanzamiento)
        lanzamiento_artista = Lanzamiento_Artista(k_lanzamiento =lanzamiento.id, k_artista=k_artista)
        db.session.add(lanzamiento_artista)
        db.session.commit()
        return(k_lanzamiento)
    except Exception as e:
        db.session.rollback()
        return None

def buscar_o_crear_lanzamiento(texto):
    #panel: "12. Disco - nombre" usa el id; un nombre libre (sin punto) se crea al vuelo, sin artista ni genero
    #devuelve (id, se_creó_ahora)
    texto = (texto or '').strip()
    if not texto:
        return None, False
    token = texto.split(".")[0].strip()
    if token.isdigit():
        l = db.session.get(Lanzamiento, int(token))
        return (l.id, False) if l else (None, False)
    l = Lanzamiento.query.filter(db.func.upper(Lanzamiento.n_lanzamiento) == texto.upper()).first()
    if l:
        return l.id, False
    nuevo = Lanzamiento(n_lanzamiento=texto)
    try:
        db.session.add(nuevo)
        db.session.commit()
        return nuevo.id, True
    except Exception as e:
        db.session.rollback()
        return None, False

def obtener_artista(n_artista, crear=False):
    #busca al artista por nombre sin distinguir mayusculas; si no existe y crear=True, lo crea tal cual
    n = (n_artista or '').strip()
    if not n:
        return None
    a = Artista.query.filter(db.func.upper(Artista.n_artista) == n.upper()).first()
    if a:
        return a.id
    if not crear:
        return None
    nuevo = Artista(n_artista=n)
    db.session.add(nuevo)
    db.session.commit()
    return nuevo.id

def _fecha_spotify(valor):
    #spotify devuelve la fecha con precision variable (año, mes o día)
    valor = (valor or '').strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(valor, fmt).date()
        except ValueError:
            pass
    return None

def actualizar_lanzamiento_spotify(k_lanzamiento, datos):
    #refresca metadatos desde la API sin tocar generos ni productos
    l = db.session.get(Lanzamiento, k_lanzamiento)
    if not l:
        return False
    try:
        if datos.get("n_lanzamiento"):
            l.n_lanzamiento = datos["n_lanzamiento"]
        #solo actualiza la fecha si spotify es igual o mas precisa que la guardada (dia > mes > año)
        raw = (datos.get("f_lanzamiento") or '').strip()
        nueva = _fecha_spotify(raw) if raw else None
        if nueva and len(raw) >= len(str(l.f_lanzamiento) if l.f_lanzamiento else ''):
            l.f_lanzamiento = nueva
        if datos.get("i_lanzamiento"):
            l.i_lanzamiento = datos["i_lanzamiento"]
        if datos.get("external_url"):
            l.external_url = datos["external_url"]
        db.session.commit()
        return True
    except Exception as e:
        print("No se actualizo el lanzamiento desde Spotify:", str(e))
        db.session.rollback()
        return False

#n_producto, p_producto, d_producto, stock, i_producto, k_categoria
def create_new_product(k_lanzamiento, n_producto, p_producto, d_producto, stock, i_producto, k_categoria, tipo='SIMPLE', url_imagen=None):
    #un pack no tiene stock propio: se calcula con sus componentes
    product = Producto(k_lanzamiento=k_lanzamiento, n_producto=n_producto, p_producto=p_producto, d_producto=d_producto,
                       stock=0 if tipo == 'BUNDLE' else (stock or 0), k_categoria=k_categoria, tipo=tipo if tipo in TIPOS_PRODUCTO else 'SIMPLE',
                       url_imagen=(url_imagen or '').strip() or None)
    try:
        db.session.add(product)
        db.session.commit()
        
        db.session.flush
        return (product)
    except Exception as e:
        db.session.rollback()
        return None
   
def create_new_image(producto_key, image_file):
    filename = secure_filename(image_file.filename)
    mimetype = image_file.mimetype

    image = Imagen(img = image_file.read(), mimetype = mimetype, k_producto = producto_key, name=filename)
    try:
        db.session.add(image)
        db.session.commit()
        return image
    except Exception as e:
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

def new_admin(email, pwd, email_admin):
    #la clave se lee de la BD: la sesion ya no lleva pwd_usuario
    from .seguridad import check_password
    try:
        admin = get_usuario_por_email(email_admin)
        if admin and check_password(pwd, admin.pwd_usuario):
            
            try:
                Usuario.query.filter_by(email_usuario = email).update({"k_rol": 'ADMIN' })
                db.session.commit()  
                return 'OK'  
            except:
                return None  
    except Exception as e:
        return None
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
       pass
    

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
        facturas.append([i, items])
    return facturas

def get_items_by_id_factura(id):
    items = Item.query.filter_by(k_factura = id).all()
    return items 

def get_k_artist_by_name(artista):
    artist_qs = Artista.query.filter_by(n_artista = artista).first()
    artist_schema=ArtistaSchema()
    a = artist_schema.dump(artist_qs)
    return a.get('id')

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
            r.append(k_lanzamiento+". "+artista + " - "+  lanzamiento)
        return r
    except Exception as e:
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
        return None 

def get_categories():
    category_qs = Categoria.query.all()
    categories_schema= CategoriaSchema()
    categories = [categories_schema.dump(c) for c in category_qs]
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

def create_multiple_images(producto_key, image_files):
    """Crea múltiples imágenes para un producto"""
    images = []
    for i, image_file in enumerate(image_files):
        if image_file and image_file.filename:
            try:
                filename = secure_filename(image_file.filename)
                mimetype = image_file.mimetype
                image = Imagen(
                    img=image_file.read(), 
                    mimetype=mimetype, 
                    k_producto=producto_key, 
                    name=filename,
                    orden=i
                )
                db.session.add(image)
                images.append(image)
            except Exception as e:
                db.session.rollback()
                return None
    try:
        db.session.commit()
        return images
    except Exception as e:
        db.session.rollback()
        return None

def create_new_image(producto_key, image_file):
    filename = secure_filename(image_file.filename)
    mimetype = image_file.mimetype

    image = Imagen(img = image_file.read(), mimetype = mimetype, k_producto = producto_key, name=filename, orden=0)
    try:
        db.session.add(image)
        db.session.commit()
        return image
    except Exception as e:
        db.session.rollback()
        return None

def get_rawimage_by_product(k_producto):
    try:
        #image = Imagen.query.filter_by(k_producto = k_producto).first()
        image = Imagen.query.filter_by(k_producto = k_producto).first()
        
        #print(img)
        return image.img
    except Exception as e:
        return None
    

def get_images_by_product(k_producto):
    """Obtiene todas las imágenes de un producto ordenadas por el campo orden"""
    try:
        images = Imagen.query.filter_by(k_producto=k_producto).order_by(Imagen.orden).all()
        for img in images:
           pass
        return images
    except Exception as e:
        return []


def get_first_image_by_product(k_producto):
    """Obtiene la primera imagen de un producto (orden = 0)"""
    try:
        image = Imagen.query.filter_by(k_producto=k_producto, orden=0).first()
        if not image:
            # Si no hay imagen con orden 0, obtener la primera imagen disponible
            image = Imagen.query.filter_by(k_producto=k_producto).order_by(Imagen.orden).first()
        return image
    except Exception as e:
        return None


#link de compartir de Google Drive -> id del archivo
_DRIVE_VIEW = re.compile(r"drive\.google\.com/file/d/([A-Za-z0-9_-]+)")

def normalizar_url_imagen(valor):
    #convierte el link de compartir de Drive en la URL directa que devuelve la imagen
    if not valor:
        return None
    valor = valor.strip()
    m = _DRIVE_VIEW.search(valor)
    if m:
        return f"https://drive.google.com/thumbnail?id={m.group(1)}&sz=w1200"
    return valor or None

def validar_url_imagen(url, timeout=15):
    #confirma que la URL responda con una imagen; las paginas de compartir no pasan
    try:
        r = requests.get(url, timeout=timeout, allow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and (r.headers.get("Content-Type") or "").startswith("image/"):
            return True, None
        return False, "Ese link no devuelve una imagen directa (parece una página). Usá el link de compartir de Drive o una URL directa a la foto."
    except Exception:
        return False, "No se pudo abrir el link. Revisá que sea una URL válida."

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
    try:
        lanzamiento.n_lanzamiento = n_lanzamiento
        lanzamiento.i_lanzamiento = i_lanzamiento
        lanzamiento.f_lanzamiento = f_lanzamiento
        lanzamiento_artista.k_artista = k_artista
        if k_genero != 'N/A':
            lanz_genero.k_genero  =  k_genero
        db.session.commit()
        return "ok"
    except:
        db.session.rollback()
        return None
    
def reorder_images(k_producto, ordenes):
    """Reordena las imágenes de un producto según el diccionario de ordenes {imagen_id: nuevo_orden}"""
    try:
        for imagen_id, nuevo_orden in ordenes.items():
            imagen = Imagen.query.get(int(imagen_id))
            if imagen and imagen.k_producto == int(k_producto):
                imagen.orden = int(nuevo_orden)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        return False


def edit_product(k_producto, n_producto, d_producto, p_producto, image_files, k_category, stock, url_imagen=None):
    producto = Producto.query.filter_by(id = k_producto).first()
    try:
        producto.n_producto = n_producto
        producto.d_producto = d_producto
        producto.url_imagen = (url_imagen or '').strip() or None
        if p_producto is not None:
            producto.p_producto = p_producto
        else:
            None

        if image_files:
            # Agregar nuevas imágenes sin eliminar las existentes
            # Obtener el siguiente número de orden disponible
            max_orden = db.session.query(db.func.max(Imagen.orden)).filter_by(k_producto=k_producto).scalar() or 0
            nuevas_imagenes = []
            
            for i, image_file in enumerate(image_files):
                if image_file and image_file.filename:
                    try:
                        filename = secure_filename(image_file.filename)
                        mimetype = image_file.mimetype
                        image = Imagen(
                            img=image_file.read(), 
                            mimetype=mimetype, 
                            k_producto=k_producto, 
                            name=filename,
                            orden=max_orden + i + 1  # Continuar desde el último orden
                        )
                        db.session.add(image)
                        nuevas_imagenes.append(image)
                    except Exception as e:
                       pass
            
        else:
           pass
        producto.k_categoria = k_category
        producto.stock = stock
        db.session.commit()
        db.session.flush()
        return "ok"
    except Exception as e:
        db.session.rollback()
        return None

def edit_image(k_producto, image_file):
    """Edita la primera imagen de un producto (orden = 0)"""
    image = Imagen.query.filter_by(k_producto=k_producto, orden=0).first()
    if not image:
        # Si no hay imagen con orden 0, obtener la primera imagen disponible
        image = Imagen.query.filter_by(k_producto=k_producto).order_by(Imagen.orden).first()
    
    if image:
        filename = secure_filename(image_file.filename)
        mimetype = image_file.mimetype
        
        try:
            image.img  = image_file.read()
            image.mimetype = mimetype
            image.name = filename
            db.session.commit()
            db.session.flush()
            return image
        except Exception as e:
            db.session.rollback()
            return None
    else:
        # Si no existe ninguna imagen, crear una nueva con orden 0
        # Crear una nueva imagen con orden 0
        filename = secure_filename(image_file.filename)
        mimetype = image_file.mimetype
        image = Imagen(
            img=image_file.read(), 
            mimetype=mimetype, 
            k_producto=k_producto, 
            name=filename,
            orden=0
        )
        try:
            db.session.add(image)
            db.session.commit()
            return image
        except Exception as e:
            db.session.rollback()
            return None

def edit_user_by_email(email, nombre,apellido,ciudad,direccion, barrio=None, celular=None):
    try:
        user  = Usuario.query.filter_by(email_usuario = email).first()
        user.n_usuario = nombre
        user.ape_usuario = apellido
        user.lugar_usuario = ciudad
        user.dir_usuario = direccion
        user.barrio_usuario = barrio
        user.cel_usuario = celular
        db.session.commit()
        db.session.flush()
        return user
    except Exception as e:
        db.session.rollback()
        return None
    

#solicitudes de pedido (integrado desde musical_box_manager)
def create_solicitud(k_usuario, items, cel=None, email=None):
    #items: lista de {nombre, descripcion, categoria, cantidad, k_producto} (uno o más por solicitud)
    validos = []
    for it in (items or []):
        nombre = (it.get("nombre") or '').strip()
        if not nombre:
            continue
        validos.append(SolicitudItem(
            nombre=nombre[:150],
            descripcion=(it.get("descripcion") or '').strip()[:200] or None,
            categoria=(it.get("categoria") or '').strip()[:30] or None,
            cantidad=max(1, min(99, int(it.get("cantidad") or 1))),
            k_producto=it.get("k_producto")))
    if not validos:
        return None, "Agrega al menos un producto"
    solicitud = Solicitud(k_usuario=k_usuario, estado='ACTIVO',
                          cel_contacto=cel, email_contacto=(email or '').strip().lower() or None)
    for it in validos:
        solicitud.items.append(it)
    try:
        db.session.add(solicitud)
        db.session.commit()
        return solicitud, None
    except Exception as e:
        db.session.rollback()
        return None, str(e)


class ItemSolicitudVirtual:
    #una solicitud antigua (sin solicitud_item) se sirve como un ítem único desde sus campos legacy
    def __init__(self, s):
        self.solicitud = s
        self.k_producto = s.k_producto
        self.k_lanzamiento = None
        self.producto = s.producto
        self.lanzamiento = None
        self.nombre = s.n_producto_solicitado or ''
        self.descripcion = s.d_producto_solicitado
        self.categoria = None
        self.cantidad = s.cantidad or 1
        self.precio_unit = s.precio_cotizado


def items_efectivos(s):
    #líneas de una solicitud: las suyas si las tiene; si no, un ítem virtual con los campos legacy
    return s.items if s.items else [ItemSolicitudVirtual(s)]

def get_all_solicitudes():
    return Solicitud.query.order_by(db.desc(Solicitud.f_solicitud)).all()

def get_solicitudes_by_user(email):
    #las del usuario y las que dejó solo con su correo de contacto
    user = get_usuario_por_email(email)
    filtro = db.func.lower(Solicitud.email_contacto) == (email or '').lower()
    if user:
        filtro = db.or_(Solicitud.k_usuario == user.id, filtro)
    return Solicitud.query.filter(filtro).order_by(db.desc(Solicitud.f_solicitud)).all()

def update_estado_solicitud(id, estado):
    solicitud = db.session.get(Solicitud, id)
    if not solicitud or estado not in ESTADOS_SOLICITUD:
        return None
    try:
        solicitud.estado = estado
        db.session.commit()
        return solicitud
    except Exception as e:
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
        r.append({"id": p.id, "nombre": nombre, "categoria": 'PACK' if p.tipo == 'BUNDLE' else p.k_categoria, "stock": stock_disponible(p)})
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

def get_releases_cards(q=None, k_artista=None, limit=None, genero=None, categoria=None, orden='recientes'):
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
        if genero and genero not in generos:
            continue
        if categoria and categoria not in categorias:
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
            "agotado": bool(productos) and all(stock_disponible(p) <= 0 for p in productos),
            "preorden": bool(lanz.preorden),
            "precio_desde": min((p.p_producto for p in productos), default=None),
            "original": any(es_original(p) for p in productos),
        })
        if limit and len(cards) >= limit:
            break
    if orden == 'antiguos':
        cards.sort(key=lambda c: c['fecha'] or datetime.min.date())
    elif orden == 'nombre':
        cards.sort(key=lambda c: (c['nombre'] or '').lower())
    elif orden == 'precio':
        cards.sort(key=lambda c: (c['precio_desde'] is None, c['precio_desde'] or 0))
    return cards

def get_generos():
    return [r[0] for r in db.session.query(Lanzamiento_Genero.k_genero).distinct().order_by(Lanzamiento_Genero.k_genero).all()]

def get_categorias():
    return [r[0] for r in db.session.query(Producto.k_categoria).distinct().filter(Producto.k_categoria.isnot(None)).order_by(Producto.k_categoria).all()]

def get_products_cards(limit=None, k_lanzamiento=None, categoria=None, orden='recientes'):
    query = Producto.query
    if k_lanzamiento:
        query = query.filter_by(k_lanzamiento=k_lanzamiento)
    if categoria:
        query = query.filter(Producto.k_categoria == categoria)
    if orden == 'precio_asc':
        query = query.order_by(Producto.p_producto.asc())
    elif orden == 'precio_desc':
        query = query.order_by(Producto.p_producto.desc())
    elif orden == 'nombre':
        query = query.order_by(Producto.n_producto.asc())
    else:
        query = query.order_by(db.desc(Producto.f_producto))
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
            "stock": stock_disponible(p),
            "descripcion": p.d_producto,
            "tipo": p.tipo,
            "variantes": [{"id": v.id, "nombre": v.nombre, "stock": int(v.stock or 0)} for v in p.variantes] if p.tipo != 'BUNDLE' else [],
            "incluye": [f"{c.cantidad} × {c.componente.n_producto}" + (f" ({c.variante.nombre})" if c.variante else "") for c in p.componentes] if p.tipo == 'BUNDLE' else [],
            "original": es_original(p),
            "preorden": es_preorden(p),
            #pack: imágenes de sus productos para armar el collage (máx. 4)
            "collage": [{"id": c.componente.id, "nombre": c.componente.n_producto, "respaldo": c.componente.lanzamiento.i_lanzamiento if c.componente.lanzamiento else ''}
                        for c in p.componentes][:4] if p.tipo == 'BUNDLE' else [],
            # Cargar imágenes del producto
            "imagenes": get_images_by_product(p.id),
        })
    return cards

def get_admin_stats():
    #el resumen responde "¿qué hago hoy?": ventas del mes, lo que va saliendo, stock crítico y pendientes
    ahora = datetime.now()
    inicio_mes = datetime(ahora.year, ahora.month, 1)
    inicio_prev = datetime(ahora.year - 1, 12, 1) if ahora.month == 1 else datetime(ahora.year, ahora.month - 1, 1)
    hace_30 = ahora - timedelta(days=30)
    pagados_mes = Invoice.query.filter(Invoice.estado == 'PAGADO', Invoice.f_compra >= inicio_mes)
    pagados_prev = Invoice.query.filter(Invoice.estado == 'PAGADO',
                                       Invoice.f_compra >= inicio_prev, Invoice.f_compra < inicio_mes)
    #top 5 de los últimos 30 días por unidades vendidas
    col_unidades = db.func.sum(Item.cant_item).label("u")
    filas_top = (db.session.query(Item.k_producto, col_unidades)
                 .join(Invoice, Invoice.id == Item.k_factura)
                 .filter(Invoice.estado == 'PAGADO', Invoice.f_compra >= hace_30)
                 .group_by(Item.k_producto).order_by(col_unidades.desc()).limit(5).all())
    top5 = []
    for k_prod, unidades in filas_top:
        p = db.session.get(Producto, k_prod)
        if p:
            top5.append({"nombre": p.n_producto or '(sin nombre)',
                         "lanzamiento": p.lanzamiento.n_lanzamiento.title() if p.lanzamiento else '',
                         "u": int(unidades)})
    stock_baja = []
    for p in Producto.query.order_by(Producto.id).all():
        s = stock_disponible(p)
        if s <= 3:
            stock_baja.append({"p": p, "stock": s})
    stock_baja.sort(key=lambda f: f["stock"])
    #preórdenes comprometidas por lanzamiento (pagadas y sin entregar): el número para decidir la tirada
    preordenes = {}
    #incluye los marcados a nivel de producto y los heredados del lanzamiento (paraguas)
    pre_ids = [p.id for p in Producto.query.filter(Producto.tipo == 'SIMPLE').all() if es_preorden(p)]
    if pre_ids:
        filas_pre = (db.session.query(Item.k_producto, db.func.sum(Item.cant_item))
                     .join(Invoice, Invoice.id == Item.k_factura)
                     .filter(Invoice.estado == 'PAGADO', Item.k_producto.in_(pre_ids),
                             db.or_(Invoice.estado_envio.is_(None), Invoice.estado_envio != 'ENTREGADO'))
                     .group_by(Item.k_producto).all())
        for k_prod, unidades in filas_pre:
            p = db.session.get(Producto, k_prod)
            if p and p.lanzamiento:
                preordenes[p.lanzamiento.n_lanzamiento] = preordenes.get(p.lanzamiento.n_lanzamiento, 0) + int(unidades)
    preordenes_lista = [{"lanzamiento": n.title(), "u": u} for n, u in preordenes.items()]
    preordenes_lista.sort(key=lambda f: -f["u"])
    return {
        "solicitudes_activas": Solicitud.query.filter(Solicitud.estado.in_(['ACTIVO', 'EN PROCESO'])).count(),
        "solicitudes_cotizadas": Solicitud.query.filter_by(estado='COTIZADA').count(),
        "ordenes": Invoice.query.filter_by(estado='PAGADO').count(),
        "pendientes": Invoice.query.filter_by(estado='PENDIENTE').count(),
        "ventas": sum((i.total or 0) for i in Invoice.query.filter_by(estado='PAGADO').all()),
        "ventas_mes": float(sum((i.total or 0) for i in pagados_mes.all())),
        "ordenes_mes": pagados_mes.count(),
        "ventas_prev": float(sum((i.total or 0) for i in pagados_prev.all())),
        "top5": top5,
        "stock_baja": stock_baja,
        "pendientes_envio": Invoice.query.filter(Invoice.estado == 'PAGADO',
                                                Invoice.estado_envio.in_(['POR PREPARAR', 'EN PREPARACION'])).count(),
        "productos": Producto.query.count(),
        "agotados": Producto.query.filter(Producto.stock <= 0).count(),
        "lanzamientos": Lanzamiento.query.count(),
        "clientes": Usuario.query.filter(Usuario.k_rol.in_(['USER', 'CLIENTE'])).count(),
        "ultimas_solicitudes": Solicitud.query.order_by(db.desc(Solicitud.f_solicitud)).limit(5).all(),
        "preordenes": preordenes_lista,
        "ultimas_ordenes": Invoice.query.order_by(db.desc(Invoice.f_compra)).limit(5).all(),
        "rotulo_estados": ESTADOS_CON_ROTULO,
    }


#pedidos sin cuenta (checkout de invitado)
def hash_token(token):
    #en la BD solo queda el SHA-256: con una copia de la BD no se pueden armar los enlaces /pedido/<token>
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def get_or_create_comprador(nombre, email, telefono, direccion, ciudad, barrio):
    #un comprador por correo (sin distinguir mayúsculas); si no existe queda como CLIENTE, sin login
    email = email.strip().lower()
    
    # Buscar un cliente existente con el mismo email
    user = Usuario.query.filter(
        db.func.lower(Usuario.email_usuario) == email,
        Usuario.k_rol == 'CLIENTE'
    ).first()
    
    if user:
        # Si ya existe un cliente con ese email, actualizar sus datos
        user.cel_usuario = user.cel_usuario or telefono
        user.dir_usuario = user.dir_usuario or direccion
        user.lugar_usuario = user.lugar_usuario or ciudad
        user.barrio_usuario = user.barrio_usuario or barrio
        return user
    
    # Si no existe un cliente con ese email, verificar si hay algún usuario con ese email
    existing_user = Usuario.query.filter(db.func.lower(Usuario.email_usuario) == email).first()
    
    if existing_user:
        # Si existe un usuario con ese email pero no es cliente, crear un cliente con email modificado
        # para evitar conflictos de unicidad
        counter = 1
        base_email = email
        while Usuario.query.filter(db.func.lower(Usuario.email_usuario) == email).first():
            # Crear un email único para el cliente
            email = f"{base_email.split('@')[0]}+guest{counter}@{base_email.split('@')[1]}"
            counter += 1
    
    # Crear nuevo usuario cliente
    partes = nombre.strip().split(maxsplit=1)
    user = Usuario(k_rol='CLIENTE', n_usuario=partes[0][:20], ape_usuario=(partes[1] if len(partes) > 1 else '')[:20],
                   email_usuario=email, pwd_usuario=hash_password(secrets.token_hex(16)), cel_usuario=telefono,
                   dir_usuario=direccion, lugar_usuario=ciudad, barrio_usuario=barrio)
    db.session.add(user)
    db.session.flush()
    return user

#stock con variantes y bundles
def requiere_variante(producto):
    return producto.tipo != 'BUNDLE' and bool(producto.variantes)

def stock_disponible(producto, variante=None):
    """Unidades que se pueden vender ya.
    SIMPLE sin variantes: producto.stock · con variantes: la variante (o la suma, si no se indica una)
    BUNDLE: el mínimo, entre sus componentes, de stock_componente // cantidad."""
    if producto.tipo == 'BUNDLE':
        if not producto.componentes:
            return 0
        posibles = []
        for c in producto.componentes:
            #un componente con tallas/colores debe indicar cuál; los bundles no se anidan
            if c.componente.tipo == 'BUNDLE' or (requiere_variante(c.componente) and not c.variante):
                return 0
            posibles.append(stock_disponible(c.componente, c.variante) // c.cantidad)
        return min(posibles)
    if producto.variantes:
        if variante is not None:
            return int(variante.stock or 0)
        return sum(int(v.stock or 0) for v in producto.variantes)
    return int(producto.stock or 0)

def unidades_de_stock(producto, variante, cantidad):
    """De qué unidades físicas sale una línea: {('P', id) o ('V', id): cantidad}. Un bundle se expande."""
    if producto.tipo == 'BUNDLE':
        demanda = {}
        for c in producto.componentes:
            for clave, n in unidades_de_stock(c.componente, c.variante, c.cantidad * cantidad).items():
                demanda[clave] = demanda.get(clave, 0) + n
        return demanda
    if variante is not None:
        return {('V', variante.id): cantidad}
    return {('P', producto.id): cantidad}

def descontar_stock(producto, variante, cantidad):
    #nunca deja stock negativo; devuelve avisos si no alcanzaba
    if es_preorden(producto):
        return []  #la tirada llega después: el stock entra cuando se reciba
    avisos = []
    for (tipo, k), n in unidades_de_stock(producto, variante, cantidad).items():
        objeto = db.session.get(Variante if tipo == 'V' else Producto, k)
        if objeto.stock < n:
            avisos.append(f"stock insuficiente en {'variante' if tipo == 'V' else 'producto'} {k}")
        objeto.stock = max(0, objeto.stock - n)
    return avisos

def validar_bundle(bundle):
    errores = []
    if not bundle.componentes:
        errores.append("El pack no tiene productos")
    for c in bundle.componentes:
        if c.componente.tipo == 'BUNDLE':
            errores.append("Un pack no puede contener otro pack")
        elif requiere_variante(c.componente) and not c.variante:
            errores.append(f"Indica la talla/color de {c.componente.n_producto}")
        elif c.variante and c.variante.k_producto != c.k_componente:
            errores.append(f"La variante no corresponde a {c.componente.n_producto}")
    return errores

def nombre_linea(producto, variante=None):
    nombre = (producto.lanzamiento.n_lanzamiento.title() + " - " if producto.lanzamiento else "") + (producto.n_producto or "")
    return nombre + (f" ({variante.nombre})" if variante is not None and variante.nombre else "")

def clave_carrito(k_producto, k_variante=None):
    return f"{int(k_producto)}:{int(k_variante)}" if k_variante else str(int(k_producto))

def validar_carrito(cart):
    """Devuelve (lineas, total, errores) con lineas = [(producto, variante, cantidad)].
    Claves del carrito: "producto" o "producto:variante". El stock se revisa sumando lo que pide todo el
    carrito (un bundle cuenta contra el stock de sus componentes) y otra vez al confirmar el pago."""
    lineas, errores, total, demanda = [], [], 0, {}
    for clave, cantidad in (cart or {}).items():
        partes = str(clave).split(":")
        producto = db.session.get(Producto, int(partes[0])) if partes[0].isdigit() else None
        variante = db.session.get(Variante, int(partes[1])) if len(partes) > 1 and partes[1].isdigit() else None
        cantidad = int(cantidad)
        if not producto or cantidad < 1 or (variante is not None and variante.k_producto != producto.id):
            errores.append("Un producto de tu carrito ya no está disponible")
            continue
        if requiere_variante(producto) and variante is None:
            errores.append(f"{nombre_linea(producto)}: elige talla o color")
            continue
        if es_preorden(producto):
            #la tirada aún no llega: se paga hoy y se envía después, sin tocar el stock
            lineas.append((producto, None, cantidad))
            total += producto.p_producto * cantidad
            continue
        if pack_lleva_preorden(producto):
            errores.append(f"{nombre_linea(producto)}: el pack incluye un producto en preorden; quítalo del carrito")
            continue
        disponible = stock_disponible(producto, variante)
        if cantidad > disponible:
            errores.append(f"{nombre_linea(producto, variante)}: solo quedan {disponible} disponibles")
            continue
        for unidad, n in unidades_de_stock(producto, variante, cantidad).items():
            demanda[unidad] = demanda.get(unidad, 0) + n
        lineas.append((producto, variante, cantidad))
        total += producto.p_producto * cantidad
    #lo pedido en total (sueltos + packs) no puede superar el stock de cada unidad física
    for (tipo, k), n in demanda.items():
        objeto = db.session.get(Variante if tipo == 'V' else Producto, k)
        if n > int(objeto.stock or 0):
            p, v = (objeto.producto, objeto) if tipo == 'V' else (objeto, None)
            errores.append(f"{nombre_linea(p, v)}: entre productos sueltos y packs pides {n}, solo quedan {int(objeto.stock or 0)}")
    if errores:
        return [], 0, errores
    if not lineas:
        errores.append("Tu carrito está vacío")
    return lineas, total, errores

def crear_pedido(cart, datos, k_usuario=None, cotizacion=None):
    """Crea el pedido PENDIENTE con sus líneas. Devuelve (pedido, token, errores).
    El token se entrega una sola vez (enlace de seguimiento); en la BD queda su hash.
    cotizacion: lista de líneas de un pedido a la medida ya acordado, cada una
    {producto, cantidad, precio, k_lanzamiento, n_item}; no revisa stock (se consigue por encargo)."""
    if cotizacion:
        lineas, total, errores = [], 0, []
        for l in cotizacion:
            try:
                cantidad, precio = int(l.get("cantidad") or 1), int(l.get("precio"))
            except (TypeError, ValueError):
                cantidad, precio = 1, None
            if not precio or precio <= 0:
                return None, None, ["Revisa la cotización: falta el precio de un ítem"]
            cantidad = max(1, min(99, cantidad))
            lineas.append((l.get("producto"), None, cantidad, precio, l.get("k_lanzamiento"), l.get("n_item")))
            total += precio * cantidad
    else:
        lineas, total, errores = validar_carrito(cart)
        #misma forma que la cotizacion: (producto, variante, cantidad, precio, k_lanzamiento, n_item)
        lineas = [(*l, None, None, None) for l in lineas]
    if errores:
        return None, None, errores
    
    # Validar que los datos de envío no estén vacíos
    nombre_envio = datos["nombre"].strip()
    email_envio = datos["email"].strip().lower()
    telefono_envio = datos["telefono"].strip()
    direccion_envio = datos["direccion"].strip()
    ciudad_envio = datos["ciudad"].strip()
    barrio_envio = (datos.get("barrio") or "").strip() or None
    
    # Verificar si los datos de envío son válidos
    datos_validos = bool(nombre_envio and email_envio and telefono_envio and direccion_envio and ciudad_envio)
    
    for intento in range(2):
        try:
            comprador = db.session.get(Usuario, k_usuario) if k_usuario else None
            if not comprador:
                comprador = get_or_create_comprador(nombre_envio, email_envio, telefono_envio,
                                                    direccion_envio, ciudad_envio, barrio_envio)
            #token_urlsafe(32): 32 bytes (256 bits) del generador criptográfico del sistema operativo
            token = secrets.token_urlsafe(32)
            
            # Solo guardar datos de envío si son válidos
            pedido = Invoice(k_usuario=comprador.id, total=total, estado='PENDIENTE', metodo_pago=datos.get("metodo_pago"),
                             token_hash=hash_token(token), token_creado=datetime.now(),
                             n_envio=nombre_envio if datos_validos else None,
                             email_envio=email_envio if datos_validos else None,
                             tel_envio=telefono_envio if datos_validos else None,
                             dir_envio=direccion_envio if datos_validos else None,
                             lugar_envio=ciudad_envio if datos_validos else None,
                             barrio_envio=barrio_envio if datos_validos and barrio_envio else None)
            db.session.add(pedido)
            db.session.flush()
            for producto, variante, cantidad, precio, k_lanzamiento, n_item in lineas:
                item = Item(k_producto=producto.id if producto else None, k_factura=pedido.id,
                            k_variante=variante.id if variante is not None else None,
                            k_lanzamiento=k_lanzamiento, n_item=n_item,
                            cant_item=cantidad, p_item=precio if precio is not None else producto.p_producto)
                db.session.add(item)
            
            # Reservar stock para el pedido
            if not cotizacion:  # No reservar stock para pedidos a la medida
                exito, errores_reserva = reservar_stock_pedido(pedido, [(producto, variante, cantidad) for producto, variante, cantidad, *_resto in lineas])
                if not exito:
                    db.session.rollback()
                    return None, None, errores_reserva
            
            db.session.commit()
            return pedido, token, []
        except IntegrityError as e:
            #dos compras simultáneas con el mismo correo nuevo: el segundo intento reutiliza el comprador ya creado
            db.session.rollback()
        except Exception as e:
            db.session.rollback()
            return None, None, [f"Error interno: {str(e)}"]
    return None, None, ["No pudimos crear tu pedido, intenta de nuevo"]

def get_pedido_por_token(token):
    if not token or len(token) > 100:
        return None
    return Invoice.query.filter_by(token_hash=hash_token(token)).first()

def confirmar_pago(pedido, ref_payco, id_factura_payco=None, franquicia=None):
    #idempotente: el stock se descuenta una sola vez, en el paso a PAGADO. Devuelve (pedido, pago_nuevo)
    if pedido.estado == 'PAGADO':
        return pedido, False
    
    # Si el stock ya estaba reservado, simplemente marcamos el pedido como pagado
    # y eliminamos las reservas (el stock ya fue descontado al crear el pedido)
    if pedido.stock_reservado:
        pedido.estado = 'PAGADO'
        pedido.estado_envio = pedido.estado_envio or 'POR PREPARAR'
        pedido.ref_payco = ref_payco
        
        # Eliminar las reservas de stock (el stock ya fue descontado)
        ReservaStock.query.filter_by(k_invoice=pedido.id).delete()
        
        for s in Solicitud.query.filter_by(k_invoice=pedido.id).all():
            s.estado = 'COMPRADA'
            s.k_usuario = s.k_usuario or pedido.k_usuario
        pedido.id_factura_payco = id_factura_payco
        if franquicia:
            pedido.metodo_pago = f"{pedido.metodo_pago or ''} ({franquicia})".strip()[:30]
        db.session.commit()
        return pedido, True
    
    # Si no había reserva de stock, descontamos el stock normalmente
    pedido.estado = 'PAGADO'
    pedido.estado_envio = pedido.estado_envio or 'POR PREPARAR'
    pedido.ref_payco = ref_payco
    for s in Solicitud.query.filter_by(k_invoice=pedido.id).all():
        s.estado = 'COMPRADA'
        s.k_usuario = s.k_usuario or pedido.k_usuario
    pedido.id_factura_payco = id_factura_payco
    if franquicia:
        pedido.metodo_pago = f"{pedido.metodo_pago or ''} ({franquicia})".strip()[:30]
    for item in Item.query.filter_by(k_factura=pedido.id).all():
        if item.producto:
            for aviso in descontar_stock(item.producto, item.variante, int(item.cant_item)):
               pass
    db.session.commit()
    return pedido, True

def rechazar_pago(pedido, ref_payco):
    if pedido.estado != 'PAGADO':
        pedido.estado = 'RECHAZADO'
        pedido.ref_payco = ref_payco
        # Liberar la reserva de stock si existe
        if pedido.stock_reservado:
            liberar_reserva_stock(pedido.id)
        db.session.commit()
    return pedido


def limpiar_reservas_expiradas():
    """Limpia las reservas de stock que han expirado y libera el stock correspondiente."""
    from datetime import datetime, timedelta

    # Obtener todas las reservas expiradas
    reservas_expiradas = ReservaStock.query.filter(
        ReservaStock.f_expiracion < datetime.now()
    ).all()
    
    # Liberar el stock de cada reserva expirada
    for reserva in reservas_expiradas:
        liberar_reserva_stock(reserva.k_invoice)
    
    return len(reservas_expiradas)


def reservar_stock_pedido(pedido, lineas):
    """Reserva el stock necesario para un pedido y crea registros de reserva."""
    from datetime import datetime, timedelta

    # libera antes las reservas de pedidos abandonados que ya expiraron
    limpiar_reservas_expiradas()

    # Verificar que el pedido aún no tenga stock reservado
    if pedido.stock_reservado:
        return True, []
    
    # Calcular la cantidad total de cada elemento que se necesita
    demanda_total = {}
    for producto, variante, cantidad in lineas:
        if es_preorden(producto):
            continue  #no se aparta stock para preórdenes
        # Para cada línea, calcular las unidades físicas necesarias
        for (tipo, k), n in unidades_de_stock(producto, variante, cantidad).items():
            clave = (tipo, k)
            demanda_total[clave] = demanda_total.get(clave, 0) + n
    
    # Verificar disponibilidad de stock para toda la demanda
    errores = []
    for (tipo, k), cantidad_necesaria in demanda_total.items():
        if tipo == 'P':  # Producto
            elemento = db.session.get(Producto, k)
            nombre_elemento = elemento.n_producto if elemento else f"Producto {k}"
        else:  # Variante
            elemento = db.session.get(Variante, k)
            nombre_elemento = elemento.nombre if elemento else f"Variante {k}"
        
        if not elemento:
            errores.append(f"Elemento no encontrado: {nombre_elemento}")
            continue
            
        stock_disponible = int(elemento.stock or 0)
        if stock_disponible < cantidad_necesaria:
            errores.append(f"No hay suficiente stock de {nombre_elemento}: se necesitan {cantidad_necesaria}, disponibles {stock_disponible}")
    
    # Si hay errores, no reservar nada
    if errores:
        return False, errores
    
    # Reservar el stock y crear registros de reserva
    try:
        for (tipo, k), cantidad_necesaria in demanda_total.items():
            # Descontar el stock disponible
            elemento = db.session.get(Variante if tipo == 'V' else Producto, k)
            elemento.stock = int(elemento.stock or 0) - cantidad_necesaria
            
            # Crear registro de reserva
            reserva = ReservaStock(
                k_invoice=pedido.id,
                tipo_elemento=tipo,
                k_elemento=k,
                cantidad=cantidad_necesaria,
                f_expiracion=datetime.now() + timedelta(minutes=30)  # Expira en 30 minutos
            )
            db.session.add(reserva)
        
        # Marcar el pedido como con stock reservado (solo si de verdad se reservó algo;
        # un carrito solo de preórdenes no aparta nada)
        if demanda_total:
            pedido.stock_reservado = True
        db.session.commit()
        
        return True, []
    except Exception as e:
        # En caso de error, revertir los cambios
        db.session.rollback()
        return False, [f"Error al reservar stock: {str(e)}"]


#admin de tallas/colores y packs
def crear_variante(k_producto, talla, color, sku, stock):
    producto = db.session.get(Producto, k_producto)
    if not producto or producto.tipo == 'BUNDLE':
        return None, "Solo los productos individuales tienen tallas o colores"
    if not (talla or color):
        return None, "Indica talla, color o ambos"
    v = Variante(k_producto=k_producto, talla=talla or None, color=color or None, sku=sku or None, stock=max(0, stock or 0))
    try:
        db.session.add(v)
        db.session.commit()
        return v, None
    except IntegrityError:
        db.session.rollback()
        return None, "Ya existe esa talla/color o ese SKU"

def actualizar_variante(k_variante, stock, sku):
    v = db.session.get(Variante, k_variante)
    if not v:
        return None, "No existe la variante"
    try:
        v.stock = max(0, stock or 0)
        v.sku = sku or None
        db.session.commit()
        return v, None
    except IntegrityError:
        db.session.rollback()
        return None, "Ese SKU ya está en uso"

def eliminar_variante(k_variante):
    v = db.session.get(Variante, k_variante)
    if not v:
        return None, "No existe la variante"
    if Item.query.filter_by(k_variante=v.id).first() or ProductoComponente.query.filter_by(k_variante=v.id).first():
        return None, "No se puede borrar: ya está en pedidos o packs (déjala en stock 0)"
    k_producto = v.k_producto
    db.session.delete(v)
    db.session.commit()
    return k_producto, None

def opciones_componentes(excluir=None):
    #[(valor "producto" o "producto:variante", texto)] de productos individuales, para armar packs
    opciones = []
    for p in Producto.query.filter(Producto.tipo != 'BUNDLE').order_by(Producto.k_lanzamiento, Producto.id).all():
        if p.id == excluir:
            continue
        base = nombre_linea(p)
        if p.variantes:
            opciones += [(f"{p.id}:{v.id}", f"{base} ({v.nombre})") for v in p.variantes]
        else:
            opciones.append((str(p.id), base))
    return opciones

def agregar_componente(k_bundle, valor, cantidad):
    bundle = db.session.get(Producto, k_bundle)
    partes = str(valor or "").split(":")
    componente = db.session.get(Producto, int(partes[0])) if partes[0].isdigit() else None
    variante = db.session.get(Variante, int(partes[1])) if len(partes) > 1 and partes[1].isdigit() else None
    if not bundle or bundle.tipo != 'BUNDLE':
        return None, "Solo los packs tienen componentes"
    if not componente or componente.tipo == 'BUNDLE' or componente.id == bundle.id:
        return None, "Elige un producto individual"
    if requiere_variante(componente) and (variante is None or variante.k_producto != componente.id):
        return None, "Elige la talla/color del producto"
    c = ProductoComponente(k_bundle=bundle.id, k_componente=componente.id, k_variante=variante.id if variante else None, cantidad=max(1, cantidad or 1))
    db.session.add(c)
    db.session.commit()
    return c, None

def eliminar_componente(k_componente):
    c = db.session.get(ProductoComponente, k_componente)
    if not c:
        return None, "No existe"
    k_bundle = c.k_bundle
    db.session.delete(c)
    db.session.commit()
    return k_bundle, None


#pedidos a la medida: cotización -> enlace "confirmar compra" -> pedido normal
def cotizar_solicitud(k_solicitud, lineas, d_cotizacion=None):
    #lineas: [{k_producto, k_lanzamiento, cantidad, precio}, ...] alineadas con los ítems de la solicitud
    s = db.session.get(Solicitud, k_solicitud)
    if not s or s.estado == 'COMPRADA':
        return None, "La solicitud no existe o ya se compró"
    #una línea legacy (sin ítems) se materializa para poder guardarle precio y asociaciones
    if not s.items:
        v = ItemSolicitudVirtual(s)
        s.items.append(SolicitudItem(k_solicitud=s.id, k_producto=v.k_producto, nombre=v.nombre,
                                     descripcion=v.descripcion, categoria=v.categoria, cantidad=v.cantidad))
        db.session.flush()
    items = list(s.items)
    if not lineas or len(lineas) != len(items):
        return None, "Revisa las líneas de la cotización"
    for it, linea in zip(items, lineas):
        try:
            precio = int(linea.get("precio"))
        except (TypeError, ValueError):
            precio = None
        if not precio or precio <= 0:
            return None, "Indica el precio de cada ítem"
        it.precio_unit = precio
        it.cantidad = max(1, min(99, int(linea.get("cantidad") or it.cantidad or 1)))
        k_producto = linea.get("k_producto")
        it.k_producto = db.session.get(Producto, k_producto).id if k_producto else None
        k_lanzamiento = linea.get("k_lanzamiento")
        it.k_lanzamiento = db.session.get(Lanzamiento, k_lanzamiento).id if k_lanzamiento else None
    token = secrets.token_urlsafe(32)
    s.d_cotizacion = (d_cotizacion or '').strip()[:300] or None
    s.token_hash, s.estado = hash_token(token), 'COTIZADA'
    db.session.commit()
    return token, None

def get_solicitud_por_token(token):
    if not token or len(token) > 100:
        return None
    return Solicitud.query.filter_by(token_hash=hash_token(token)).first()

def datos_envio_previos(email):
    #última dirección usada con ese correo (copia del pedido) o la del perfil, para reutilizarla
    if not email:
        return None
    email = email.strip().lower()
    p = (Invoice.query.filter(db.func.lower(Invoice.email_envio) == email, Invoice.dir_envio.isnot(None))
         .order_by(db.desc(Invoice.f_compra)).first())
    if p:
        return {"nombre": p.n_envio, "email": p.email_envio, "telefono": p.tel_envio, "ciudad": p.lugar_envio,
                "direccion": p.dir_envio, "barrio": p.barrio_envio}
    u = get_usuario_por_email(email)
    if u and u.dir_usuario and u.lugar_usuario:
        return {"nombre": f"{u.n_usuario} {u.ape_usuario}".strip(), "email": u.email_usuario, "telefono": u.cel_usuario,
                "ciudad": u.lugar_usuario, "direccion": u.dir_usuario, "barrio": u.barrio_usuario}
    return None

def actualizar_envio(k_invoice, estado):
    p = db.session.get(Invoice, k_invoice)
    if not p or p.estado != 'PAGADO' or estado not in ESTADOS_ENVIO:
        return None
    p.estado_envio = estado
    db.session.commit()
    return p


#merch original Musical Box
def es_original(producto):
    #un pack es original si él o alguno de sus productos lo es
    if producto.original_mb:
        return True
    return producto.tipo == 'BUNDLE' and any(c.componente.original_mb for c in producto.componentes)


#preorden: se vende antes de que llegue la tirada (paga hoy, llega después); solo SIMPLE sin tallas
def es_preorden(producto):
    #se hereda del lanzamiento: si el disco está en preorden, todos sus sueltos también
    bajo = bool(producto.preorden or (producto.lanzamiento is not None and producto.lanzamiento.preorden))
    return bajo and producto.tipo != 'BUNDLE' and not producto.variantes


def pack_lleva_preorden(producto):
    return producto.tipo == 'BUNDLE' and any(es_preorden(c.componente) for c in producto.componentes)

def lanzamiento_tiene_original(k_lanzamiento):
    return any(es_original(p) for p in Producto.query.filter_by(k_lanzamiento=k_lanzamiento).all())


def producto_card(k_producto):
    #una sola tarjeta (página y modal del producto)
    p = db.session.get(Producto, k_producto)
    if not p:
        return None
    # Obtener las imágenes del producto
    p.imagenes = get_images_by_product(k_producto)
    return next((c for c in get_products_cards(k_lanzamiento=p.k_lanzamiento) if c["id"] == p.id), None) if p.k_lanzamiento         else next((c for c in get_products_cards() if c["id"] == p.id), None)


def liberar_reserva_stock(k_invoice):
    """Libera el stock reservado para un pedido y elimina las reservas."""
    from datetime import datetime, timedelta
    
    # Obtener todas las reservas para este pedido
    reservas = ReservaStock.query.filter_by(k_invoice=k_invoice).all()
    
    # Liberar el stock reservado
    for reserva in reservas:
        if reserva.tipo_elemento == 'P':  # Producto
            producto = db.session.get(Producto, reserva.k_elemento)
            if producto:
                producto.stock = (producto.stock or 0) + reserva.cantidad
        elif reserva.tipo_elemento == 'V':  # Variante
            variante = db.session.get(Variante, reserva.k_elemento)
            if variante:
                variante.stock = (variante.stock or 0) + reserva.cantidad
        
        # Eliminar la reserva
        db.session.delete(reserva)
    
    # Marcar el pedido como no reservado
    pedido = db.session.get(Invoice, k_invoice)
    if pedido:
        pedido.stock_reservado = False
    
    db.session.commit()



