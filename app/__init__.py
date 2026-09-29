from flask import Flask, g, render_template
from flask_wtf.csrf import CSRFProtect
from .db import db, ma, migrate
import os

import click
from .config import CONFIGS, DevelopmentConfig
from .store.views import home, dashboard, releases, artists, purchase, products
from .store.solicitudes import solicitud
from .store.pedidos import pedido
from .store.mercadopago import views as mercadopago_views
from .store import catalogo_admin  # noqa: F401 (rutas de tallas y packs en el panel)

ACTIVE_ENDPOINTS = [('/',home), ('/dashboard', dashboard), ('/releases', releases), ('/artists', artists), ('/purchase', purchase), ("/products", products), ("/solicitud", solicitud), ("/pedido", pedido), ("/mercadopago", mercadopago_views.mercadopago_bp) ]

def create_app(config=None):
    app = Flask(__name__)

    #APP_CONFIG=production en el servidor (ver docs/DEPLOY_PYTHONANYWHERE.md); por defecto, desarrollo
    config = config or CONFIGS.get(os.getenv("APP_CONFIG", "development"), DevelopmentConfig)
    app.config.from_object(config)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("Falta la variable de entorno SECRET_KEY")

    # Inicializar protección CSRF
    # csrf = CSRFProtect()
    # csrf.init_app(app)
    
    # Exportar csrf para que otros módulos puedan usarlo
    # app.csrf = csrf

    db.init_app(app)
    ma.init_app(app)
    #el esquema lo manejan las migraciones: flask --app run db upgrade
    migrate.init_app(app, db)

    # register each active blueprint
    for url, blueprint in ACTIVE_ENDPOINTS:
        app.register_blueprint(blueprint, url_prefix=url)

    # Eximir los endpoints de MercadoPago de CSRF
    # csrf.exempt(mercadopago_views.mercadopago_bp)  # Comentada porque csrf está desactivado

    @app.cli.command("crear-admin")
    @click.argument("email")
    @click.option("--nombre", default="Admin", help="Nombre del administrador")
    @click.password_option(help="Contraseña (se pide sin mostrarla)")
    def crear_admin(email, nombre, password):
        """Crea un administrador, o convierte en admin una cuenta existente: flask --app run crear-admin correo@x.com"""
        from .store.models import Usuario, get_usuario_por_email
        from .store.seguridad import hash_password
        user = get_usuario_por_email(email)
        if user:
            user.k_rol, user.pwd_usuario = 'ADMIN', hash_password(password)
            accion = "actualizado a administrador"
        else:
            db.session.add(Usuario(k_rol='ADMIN', n_usuario=nombre[:20], ape_usuario='', email_usuario=email.strip().lower(), pwd_usuario=hash_password(password)))
            accion = "creado"
        db.session.commit()
        click.echo(f"Administrador {email} {accion}.")

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
