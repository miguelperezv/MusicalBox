import os
from datetime import timedelta

UPLOAD_FOLDER = os.path.abspath("./uploads/")

#Claves que quedaron escritas en este archivo y, como el repositorio es público, son públicas.
#No sirven para nada: create_app se niega a arrancar si alguna vuelve a aparecer (ver app/__init__.py).
LLAVES_PUBLICADAS = {
    '?\xbf,\xb4\x8d\xa3"<\x9c\xb0@\x0f5\xab,w\xee\x8d$0\x13\x8b83',
    '\xfd{H\xe5<\x95\xf9\xe3\x96.5\xd1\x01O<!\xd5\xa2\xa0\x9fR"\xa1\xa8',
}


class Config(object):
    DEBUG = True
    #sin respaldo escrito aquí: la clave sale siempre del entorno (SECRET_KEY) y create_app
    #verifica que exista, así nunca queda en uso una clave que esté en el repositorio
    SECRET_KEY = os.getenv("SECRET_KEY")
    # OJO: PARA CUANDO TRABAJE EN MEMORIA   SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    # las rutas sqlite relativas quedan dentro de la carpeta instance/ (Flask-SQLAlchemy 3)
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///musicalbox.sqlite3")
    #SQLALCHEMY_ECHO=True
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = UPLOAD_FOLDER
    #MercadoPago (llaves de pruebas por defecto; en producción van en variables de entorno)
    MERCADOPAGO_PUBLIC_KEY = os.getenv("MERCADOPAGO_PUBLIC_KEY", "YOUR_PUBLIC_KEY")
    MERCADOPAGO_ACCESS_TOKEN = os.getenv("MERCADOPAGO_ACCESS_TOKEN", "YOUR_ACCESS_TOKEN")
    #firma del webhook de MercadoPago (Panel de MP > Webhooks > clave secreta); si está, se exige
    MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET", "")
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
    #los administradores quedan con la sesión abierta; se renueva con cada visita.
    #Para cambiarla: ADMIN_SESSION_DIAS=30 en el entorno (0 o negativo no se recomienda).
    PERMANENT_SESSION_LIFETIME = timedelta(days=int(os.getenv("ADMIN_SESSION_DIAS", "7")))
    #límites de intentos en login y formularios públicos (ver app/limiter.py)
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True
    #avisos al admin por Telegram (ver app/telegram.py): sin credenciales cae a consola
    TG_BACKEND = os.getenv("TG_BACKEND", "real")
    TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
    TG_ADMIN_CHAT_ID = os.getenv("TG_ADMIN_CHAT_ID", "")
    #bot de cotización: secreto del webhook entrante (ver app/telegram.py)
    TG_WEBHOOK_SECRET = os.getenv("TG_WEBHOOK_SECRET", "")  #opcional: candado extra del webhook del bot
    #URL base pública para callbacks de pagos (PSE, etc.); en local usa tunnel (ngrok, cloudflared)
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")



class ProductionConfig(Config):
    DEBUG = False
    #en producción la clave secreta es obligatoria y viene del entorno (create_app lo verifica)
    SECRET_KEY = os.getenv("SECRET_KEY")
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    PREFERRED_URL_SCHEME = "https"
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_recycle": 299}


class DevelopmentConfig(Config):
    DEBUG = True
    SIMULACION_PAGO = True
    #la clave secreta se toma del entorno (SECRET_KEY), igual que en producción: ver docs/DEPLOY_PYTHONANYWHERE.md


CONFIGS = {"production": ProductionConfig, "development": DevelopmentConfig}
