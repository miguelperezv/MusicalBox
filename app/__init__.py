from flask import Flask, g, render_template
from flask_wtf.csrf import CSRFProtect
from .db import db, ma, migrate
import os

from dotenv import load_dotenv

# Cargar variables de entorno desde .env ANTES de importar config
# Esto asegura que las variables de entorno (incluyendo MERCADOPAGO_PUBLIC_KEY) estén disponibles
# Ruta relativa al repo: app/__init__.py -> app/ -> raíz (funciona en local y en producción)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path, override=True)

import click
from .config import CONFIGS, DevelopmentConfig, LLAVES_PUBLICADAS
from .store.views import home, dashboard, releases, artists, purchase, products
from .store.solicitudes import solicitud
from .store.pedidos import pedido
from .store.mercadopago import views as mercadopago_views
from .store import catalogo_admin  # noqa: F401 (rutas de tallas y packs en el panel)
from .store import envios_admin  # noqa: F401 (sección "Envíos" del panel y costo por orden)
from .store import suscriptores  # noqa: F401 (suscriptores de drops: form del footer y lista del panel)
from .store.promocion import promo
from .telegram import telegram_bp
from .store.seguimiento import seguimiento

import logging
logging.getLogger("mb.tgbot").setLevel(logging.INFO)  #logs del bot para el error log (ver app/telegram.py)

ACTIVE_ENDPOINTS = [('/',home), ('/dashboard', dashboard), ('/releases', releases), ('/artists', artists), ('/purchase', purchase), ("/products", products), ("/solicitud", solicitud), ("/pedido", pedido), ("/seguimiento", seguimiento), ("/mercadopago", mercadopago_views.mercadopago_bp), ("/telegram-bot", telegram_bp), ("/feed", promo) ]

def create_app(config=None):
    app = Flask(__name__)

    #APP_CONFIG=production en el servidor (ver docs/DEPLOY_PYTHONANYWHERE.md); por defecto, desarrollo
    config = config or CONFIGS.get(os.getenv("APP_CONFIG", "development"), DevelopmentConfig)
    app.config.from_object(config)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("Falta SECRET_KEY: ponla en .env (local) o en las variables de entorno del servidor")
    if app.config["SECRET_KEY"] in LLAVES_PUBLICADAS:
        #el repositorio es público: con esa clave cualquiera puede firmar una sesión y entrar como admin
        raise RuntimeError("La SECRET_KEY está publicada en el repositorio. Genera una nueva: "
                           "python -c \"import secrets; print(secrets.token_urlsafe(48))\"")

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

    # Eximir solo los webhooks de MercadoPago y del bot de Telegram (peticiones externas, sin navegador)
    csrf.exempt(mercadopago_views.mercadopago_bp)
    csrf.exempt(telegram_bp)
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
        from .store.texto import pesos
        return pesos(valor)

    @app.template_filter('fecha_co')
    def fecha_co(valor, fmt='%d/%m/%Y %H:%M'):
        #fecha en formato colombiano: 2026-10-06 15:30 -> 06/10/2026 15:30
        if not valor:
            return ''
        if hasattr(valor, 'strftime'):
            return valor.strftime(fmt)
        return str(valor)

    @app.template_filter('schema_producto')
    def _filtro_schema_producto(p, url=None):
        #schema.org Product de la ficha (ver app/store/promocion.py)
        from .store.promocion import schema_producto
        return schema_producto(p, url)

    @app.template_global('schema_tienda')
    def _global_schema_tienda():
        #schema.org Store del inicio, con los datos del negocio del panel (ver /dashboard/promocion)
        from .store.promocion import schema_tienda
        return schema_tienda()

    @app.template_global('negocio_datos')
    def _global_negocio_datos():
        #teléfono/dirección/ciudad que dejó el admin (barra de confianza y pie del sitio)
        from .store.promocion import datos_negocio
        return datos_negocio()

    @app.template_global('whatsapp_enlace')
    def _global_whatsapp_enlace(numero, texto=None):
        #enlace wa.me a partir del teléfono del panel (ver app/store/promocion.py)
        from .store.promocion import whatsapp_enlace
        return whatsapp_enlace(numero, texto)

    @app.template_global('envio_gratis_texto')
    def _global_envio_gratis_texto():
        #frase con la regla de envío gratis activa (la misma que aplica el pedido)
        from .store.envio import envio_gratis_texto
        return envio_gratis_texto()

    @app.template_global('productos_recomendados')
    def _global_productos_recomendados(limit=4):
        #tarjetas para el carrito vacío y el 404; solo se consultan si la plantilla las pide
        from .store.models import get_products_cards
        try:
            return get_products_cards(orden='vendidos', limit=limit)
        except Exception:
            return []

    @app.template_global('minutos_reserva')
    def _global_minutos_reserva():
        #minutos reales de la reserva de stock (una sola fuente: app/store/models.py)
        from .store.models import MINUTOS_RESERVA
        return MINUTOS_RESERVA

    @app.template_filter('titulo')
    def _filtro_titulo(valor):
        #capitaliza nombres sin romper apóstrofos: "She’s the Best" -> "She’s The Best"
        from .store.texto import titulo
        return titulo(valor)

    @app.errorhandler(404)
    def no_encontrado(e):
        return render_template("404.html"), 404

    @app.context_processor
    def usuario_y_carrito():
        #disponibles en todas las plantillas (navbar)
        return {"user": g.get("user"), "purchase_cart": g.get("purchase")}

    @app.context_processor
    def tema_de_temporada():
        #tema de temporada del logotipo (gorro, murciélagos, chispas...): por fecha en hora
        #de Bogotá, forzado con ?tema=navidad (o MUSICALBOX_TEMA), o el que dejó el admin
        #en el panel /dashboard/tema. Además se expone el modo para que el panel lo muestre.
        from flask import request as _request
        from .store.temporadas import config_tema, tema_activo
        modo, forzado = config_tema()
        return {"tema": tema_activo(_request.args), "tema_modo": modo, "tema_forzado": forzado}

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

    @app.context_processor
    def url_helpers():
        # Helpers para URLs textuales
        from .store.models import url_for_release, url_for_artist, url_for_product
        return {
            "url_for_release": url_for_release,
            "url_for_artist": url_for_artist,
            "url_for_product": url_for_product
        }

    return app
