from flask import Flask
from .db import db, ma
from .config import DevelopmentConfig
from .store.views import home, dashboard, releases, artists, purchase, products
from .store.solicitudes import solicitud
from .store.models import seed_roles

ACTIVE_ENDPOINTS = [('/',home), ('/dashboard', dashboard), ('/releases', releases), ('/artists', artists), ('/purchase', purchase), ("/products", products), ("/solicitud", solicitud) ]

def create_app(config=DevelopmentConfig):
    app = Flask(__name__)

    app.config.from_object(config)

    db.init_app(app)
    ma.init_app(app)

    with app.app_context():
        db.create_all()
        seed_roles()

    # register each active blueprint
    for url, blueprint in ACTIVE_ENDPOINTS:
        app.register_blueprint(blueprint, url_prefix=url)

    return app
