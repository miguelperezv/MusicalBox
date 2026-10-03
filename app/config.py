import os

UPLOAD_FOLDER = os.path.abspath("./uploads/")

class Config(object):
    DEBUG = True
    SECRET_KEY = os.getenv("SECRET_KEY", '?\xbf,\xb4\x8d\xa3"<\x9c\xb0@\x0f5\xab,w\xee\x8d$0\x13\x8b83')
    # OJO: PARA CUANDO TRABAJE EN MEMORIA   SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    # las rutas sqlite relativas quedan dentro de la carpeta instance/ (Flask-SQLAlchemy 3)
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///musicalbox.sqlite3")
    #SQLALCHEMY_ECHO=True
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = UPLOAD_FOLDER
    #MercadoPago (llaves de pruebas por defecto; en producción van en variables de entorno)
    MERCADOPAGO_PUBLIC_KEY = os.getenv("MERCADOPAGO_PUBLIC_KEY", "YOUR_PUBLIC_KEY")
    MERCADOPAGO_ACCESS_TOKEN = os.getenv("MERCADOPAGO_ACCESS_TOKEN", "YOUR_ACCESS_TOKEN")
    #Spotify (client credentials; buscar/refrescar metadatos de lanzamientos, ver app/store/musicapi.py)
    SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
    #EnvíoClick Pro (cotización de fletes real; cuenta gratis en envioclick.com, ver app/store/envio.py)
    ENVIOCLICK_TOKEN = os.getenv("ENVIOCLICK_TOKEN")
    #correo (ver app/correo.py): consola en desarrollo, smtp cuando se configure un proveedor
    #Para usar correo real, establece MAIL_BACKEND=smtp y configura las variables MAIL_*
    #Ejemplo para Gmail:
    #MAIL_BACKEND=smtp
    #MAIL_SERVER=smtp.gmail.com
    #MAIL_PORT=587
    #MAIL_USERNAME=tu-correo@gmail.com
    #MAIL_PASSWORD=tu-app-password  # Usa App Password de Google, no la contraseña normal
    #MAIL_USE_TLS=true
    #MAIL_FROM=tu-correo@gmail.com
    MAIL_BACKEND = os.getenv("MAIL_BACKEND", "consola")
    MAIL_SERVER = os.getenv("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_FROM = os.getenv("MAIL_FROM", "Musical Box <pedidos@musicalbox.local>")
    #vigencia del enlace para crear contraseña que llega por correo
    ACTIVACION_MAX_DIAS = 7



class ProductionConfig(Config):
    DEBUG = False
    #en producción la clave secreta es obligatoria y viene del entorno (create_app lo verifica)
    SECRET_KEY = os.getenv("SECRET_KEY")
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    PREFERRED_URL_SCHEME = "https"
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_recycle": 299}


class DevelopmentConfig(Config):
    DEBUG=True
    SIMULACION_PAGO = True
    SECRET_KEY = '\xfd{H\xe5<\x95\xf9\xe3\x96.5\xd1\x01O<!\xd5\xa2\xa0\x9fR"\xa1\xa8'


CONFIGS = {"production": ProductionConfig, "development": DevelopmentConfig}
