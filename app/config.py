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
    #ePayco (llaves de pruebas por defecto; en producción van en variables de entorno)
    EPAYCO_PUBLIC_KEY = os.getenv("EPAYCO_PUBLIC_KEY", "7c0e3cb9905cc6924cfa41bd822306cf")
    EPAYCO_PRIVATE_KEY = os.getenv("EPAYCO_PRIVATE_KEY", "3d1d87bb853a61cd897ff62994f55240")
    EPAYCO_TEST = os.getenv("EPAYCO_TEST", "true").lower() == "true"
    EPAYCO_VALIDATION_URL = "https://secure.epayco.co/validation/v1/reference/"
    #botones para simular pago aprobado/rechazado sin pasar por ePayco (solo desarrollo)
    EPAYCO_SIMULACION = False



class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_recycle": 299}

class DevelopmentConfig(Config):
    DEBUG=True
    EPAYCO_SIMULACION = True
    SECRET_KEY = '\xfd{H\xe5<\x95\xf9\xe3\x96.5\xd1\x01O<!\xd5\xa2\xa0\x9fR"\xa1\xa8'
