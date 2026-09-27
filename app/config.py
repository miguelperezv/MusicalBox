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



class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_recycle": 299}

class DevelopmentConfig(Config):
    DEBUG=True
    SECRET_KEY = '\xfd{H\xe5<\x95\xf9\xe3\x96.5\xd1\x01O<!\xd5\xa2\xa0\x9fR"\xa1\xa8'
