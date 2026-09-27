from flask_wtf import FlaskForm
from wtforms.validators import DataRequired, NumberRange, Length, Regexp, EqualTo, Optional
from wtforms import StringField, SelectField, PasswordField, IntegerField, FileField, DateField, EmailField, RadioField, BooleanField
from datetime import date, datetime
from wtforms import widgets as h5widgets
import pycountry
from .models import get_all_genres

class CreateUsuarioForm(FlaskForm):
    name = StringField('Nombre', validators=[DataRequired(message="Ingresa un nombre")])
    lastname = StringField('Apellido', validators= [DataRequired(message = "Ingresa un apellido")])
    email_usuario = StringField('Email', validators=[DataRequired(message = "Ingresa un e-mail válido")])
    pwd_usuario = PasswordField('Contraseña', validators=[DataRequired(message="Ingresa una contraseña.")])

class LoginUsuarioForm(FlaskForm):
    email_usuario =  StringField('Email', validators=[DataRequired()])
    pwd_usuario =  PasswordField('Contraseña', validators=[DataRequired()])

class EditUsuarioForm(FlaskForm):
    name = StringField('Nombre', validators=[DataRequired(message="Ingresa un nombre")])
    lastname = StringField('Apellido', validators= [DataRequired(message = "Ingresa un apellido")])
    email_usuario = StringField('Email', validators=[DataRequired(message = "Ingresa un e-mail válido")])
    pwd_usuario = PasswordField('Contraseña', validators=[DataRequired(message="Ingresa una contraseña.")])
    address = StringField('Dirección', validators=[DataRequired(message="Dirección a donde te enviaremos tus productos")])
    city = StringField('Municipio/Ciudad', id="city", validators=[DataRequired(message="Lugar a donde te enviaremos tus productos")])
    barrio = StringField('Barrio')
    celular = StringField('Celular')
    

class GenreSelectField(SelectField):
    def __init__(self, *args, **kwargs):
        super(GenreSelectField, self).__init__(*args, **kwargs)
        #self.choices = [(country.alpha_2, country.name) for country in pycountry.countries]
        genres = get_all_genres() or []
        genres.append({'k_genero' : 'N/A'})
        print( genres)
        self.choices = [(genre['k_genero']) for genre in genres]
    

class  newReleaseForm(FlaskForm):


    
    #es una mouskerramienta que nos ayudará en la parte de edición del lanzamiento ;)
    #ya que ejemplifico mismo formulario en la vista de edición y quiero evitar conflictos con el otro stringfield
    n_lanzamiento_edit =  StringField("Nombre del lanzamiento", id="n_lanzamiento_edit", validators=[DataRequired()])
    
    
    n_lanzamiento = StringField("Nombre del lanzamiento", id="lanzamiento", validators=[DataRequired()])
    i_lanzamiento = StringField("Imagen del lanzamiento", validators=[DataRequired()])
    k_artista  = StringField("Artista",validators=[DataRequired()], id="artista")
    f_lanzamiento = DateField("Fecha de Lanzamiento", default=date.today)
    k_genero = GenreSelectField("Género", id="k_genero")
    url_social = StringField("Post de Instagram o TikTok (opcional)", render_kw={"placeholder": "https://www.instagram.com/p/... o https://www.tiktok.com/@.../video/..."})
    

    

class newProductForm(FlaskForm):

    #es una mouskerramienta que nos ayudará en la parte de edición del lanzamiento ;)
    #ya que ejemplifico mismo formulario en la vista de edición y quiero evitar conflictos con el otro stringfield
    n_producto_edit =  StringField("Nombre del producto", id="n_producto_edit", validators=[])
    
    n_lanzamiento = StringField("Lanzamiento asociado", id="lanzamiento", render_kw={"placeholder": "Lanzamiento al que se registra el producto"})
    n_producto = StringField("Nombre del producto", id="producto" , render_kw={"placeholder": "Opcional. Amplía el nombre (ej: +VinylBox Set)"})
    p_producto = IntegerField("Precio", widget=h5widgets.NumberInput(min=0, max=1000000, step=50), validators=[NumberRange(min=0, max=10000), DataRequired()])
    d_producto = StringField("Descripción", render_kw={"placeholder": "Opcional. Información adicional"})
    stock = IntegerField("Stock", widget=h5widgets.NumberInput(min=0, max=1000), validators=[DataRequired()])
    i_producto = FileField("Imagen del producto")
    k_category = SelectField("Categoría", id="category", choices=[])
    original_mb = BooleanField("Merch original Musical Box (personalizado por nosotros)")
    tipo = SelectField("Tipo", choices=[('SIMPLE', 'Producto individual'), ('BUNDLE', 'Pack (arma sus productos después)')], default='SIMPLE')

    def __init__(self, categories_choices: list = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if categories_choices:
            self.k_category.choices = categories_choices


class CountrySelectField(SelectField):
    def __init__(self, *args, **kwargs):
        super(CountrySelectField, self).__init__(*args, **kwargs)
        #self.choices = [(country.alpha_2, country.name) for country in pycountry.countries]
        self.choices = [(country.name) for country in pycountry.countries]

class newCat_Genre_Artist(FlaskForm):
    genre = StringField("Nombre del género")
    category = StringField("Nombre de la categoría")
    n_artist = StringField('Nombre del Artista', validators=[DataRequired()])
    country = CountrySelectField("País de origen", default="Colombia")

class newAdmin(FlaskForm):
    email = StringField("Ingresa el email del nuevo usuario ADMINISTRADOR")
    pwd = PasswordField("Ingresa tu contraseña")

class editReleaseForm(FlaskForm):
    
    n_lanzamiento = StringField("Lanzamiento asociado", id="lanzamiento", render_kw={"placeholder": "Lanzamiento al que se registra el producto"})



TIPOS_DOCUMENTO = [
    ('cc', 'Cédula de Ciudadanía'),
    ('ce', 'Cédula de Extranjería'),
    ('ti', 'Tarjeta de Identidad'),
    ('rc', 'Registro Civil'),
    ('pa', 'Pasaporte'),
    ('nit', 'NIT'),  # Número de Identificación Tributaria
]

class RegistroSolicitudForm(FlaskForm):
    #solo lo necesario para buscar el disco y contactar; los datos de envío se piden al confirmar la compra
    producto = StringField('¿Qué disco buscas?', validators=[DataRequired(message="Cuéntanos qué disco buscas"), Length(max=150)], render_kw={"placeholder": "Busca en el catálogo o escribe artista y disco"})
    d_producto = StringField('Detalles', validators=[Length(max=200)], render_kw={"placeholder": "Opcional. Edición, color, formato..."})
    celular = StringField('Celular (WhatsApp)', validators=[DataRequired(message="Déjanos tu celular"), Length(max=20)])
    email = EmailField('Correo', validators=[Optional(), Length(max=100), Regexp(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", message="Revisa el correo")])


def _limpiar(valor):
    return valor.strip() if isinstance(valor, str) else valor


class CheckoutForm(FlaskForm):
    #compra sin cuenta: solo lo necesario para enviar el pedido y cobrarlo
    nombre = StringField('Nombre completo', validators=[DataRequired(message="Escribe tu nombre"), Length(max=100)], filters=[_limpiar])
    email = EmailField('Correo', validators=[DataRequired(message="Escribe tu correo"), Length(max=100),
                                             Regexp(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", message="Revisa el correo")], filters=[_limpiar])
    telefono = StringField('Celular', validators=[DataRequired(message="Escribe un celular de contacto"), Length(max=20)], filters=[_limpiar])
    ciudad = StringField('Municipio | Ciudad, Departamento', validators=[DataRequired(message="Escribe el municipio"), Length(max=80)], filters=[_limpiar])
    direccion = StringField('Dirección', validators=[DataRequired(message="Escribe la dirección"), Length(max=200)], filters=[_limpiar])
    barrio = StringField('Barrio', validators=[Length(max=30)], filters=[_limpiar])
    metodo_pago = RadioField('Método de pago', validators=[DataRequired(message="Elige un método de pago")])


class ActivarCuentaForm(FlaskForm):
    pwd = PasswordField('Contraseña', validators=[DataRequired(message="Escribe una contraseña"), Length(min=8, message="Usa al menos 8 caracteres")])
    confirmar = PasswordField('Repite la contraseña', validators=[DataRequired(message="Repite la contraseña"), EqualTo('pwd', message="Las contraseñas no coinciden")])
