from flask import Flask, g, render_template
from .db import db, ma, migrate
from .config import DevelopmentConfig
from .store.views import home, dashboard, releases, artists, purchase, products
from .store.solicitudes import solicitud

ACTIVE_ENDPOINTS = [('/',home), ('/dashboard', dashboard), ('/releases', releases), ('/artists', artists), ('/purchase', purchase), ("/products", products), ("/solicitud", solicitud) ]

def create_app(config=DevelopmentConfig):
    app = Flask(__name__)

    app.config.from_object(config)

    db.init_app(app)
    ma.init_app(app)
    #el esquema lo manejan las migraciones: flask --app run db upgrade
    migrate.init_app(app, db)

    # register each active blueprint
    for url, blueprint in ACTIVE_ENDPOINTS:
        app.register_blueprint(blueprint, url_prefix=url)

    @app.template_filter('cop')
    def cop(valor):
        #precio en pesos colombianos: 150000 -> $150.000
        return "$" + f"{float(valor or 0):,.0f}".replace(",", ".")

    @app.errorhandler(404)
    def no_encontrado(e):
        return render_template("404.html"), 404

    @app.context_processor
    def usuario_y_carrito():
        #disponibles en todas las plantillas (navbar)
        return {"user": g.get("user"), "purchase_cart": g.get("purchase")}

    return app
