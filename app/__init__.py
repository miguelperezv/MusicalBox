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
from .store import envios_admin  # noqa: F401 (sección "Envíos" del panel y costo por orden)
from .store import suscriptores  # noqa: F401 (suscriptores de drops: form del footer y lista del panel)
from .whatsapp import whatsapp_bp

ACTIVE_ENDPOINTS = [('/',home), ('/dashboard', dashboard), ('/releases', releases), ('/artists', artists), ('/purchase', purchase), ("/products", products), ("/solicitud", solicitud), ("/pedido", pedido), ("/mercadopago", mercadopago_views.mercadopago_bp), ("/whatsapp", whatsapp_bp) ]

def create_app(config=None):
    app = Flask(__name__)

    #APP_CONFIG=production en el servidor (ver docs/DEPLOY_PYTHONANYWHERE.md); por defecto, desarrollo
    config = config or CONFIGS.get(os.getenv("APP_CONFIG", "development"), DevelopmentConfig)
    app.config.from_object(config)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("Falta la variable de entorno SECRET_KEY")

    # Inicializar protección CSRF
    csrf = CSRFProtect()
    csrf.init_app(app)
    
    # Exportar csrf para que otros módulos puedan usarlo
    app.csrf = csrf

    db.init_app(app)
    ma.init_app(app)
    #el esquema lo manejan las migraciones: flask --app run db upgrade
    migrate.init_app(app, db)

    # register each active blueprint
    for url, blueprint in ACTIVE_ENDPOINTS:
        app.register_blueprint(blueprint, url_prefix=url)

    # Eximir solo los webhooks de MercadoPago y WhatsApp (peticiones externas, sin navegador)
    csrf.exempt(mercadopago_views.mercadopago_bp)
    csrf.exempt(whatsapp_bp)
    # el resto del panel usa tokens CSRF: {{ form.csrf_token }} / hidden input / header X-CSRFToken

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

    @app.context_processor
    def form_suscriptor():
        #formulario del footer (avisos de drops); el panel sobreescribe el bloque footer
        from .store.forms import SuscriptorForm
        return {"suscriptor_form": SuscriptorForm()}

    @app.context_processor
    def textos_envio():
        #textos de envío (zonas y procesado) disponibles en todas las plantillas
        from .store.redes import envio
        return {"envio_cfg": envio()}

    @app.context_processor
    def seo_defaultes():
        #canonical y OG por defecto; las plantillas pueden sobreescribir los bloques og_*
        from flask import request as _request, url_for as _url_for
        endpoint, view_args = _request.endpoint, dict(_request.view_args or {})
        seo_canonical = None
        if endpoint and endpoint != 'static':
            try:
                seo_canonical = _url_for(endpoint, **view_args, _external=True)
            except Exception:
                seo_canonical = None
        return {"seo_canonical": seo_canonical}

    return app
