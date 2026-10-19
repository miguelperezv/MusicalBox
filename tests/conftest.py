import os
import sys

import pytest
from flask_migrate import upgrade

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import create_app
from app.config import DevelopmentConfig
from app.db import db
from app.store.models import Artista, Categoria, Lanzamiento, Lanzamiento_Artista, Producto, Usuario


@pytest.fixture
def app(tmp_path):
    class TestConfig(DevelopmentConfig):
        TESTING = True
        WTF_CSRF_ENABLED = False
        SIMULACION_PAGO = False
        SECRET_KEY = "clave-solo-para-las-pruebas"  #las pruebas no dependen del .env
        MAIL_BACKEND = "memoria"
        TG_BACKEND = "memoria"  #los avisos al admin quedan en app.extensions["telegram_enviados"]
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + str(tmp_path / "test.sqlite3").replace("\\", "/")

    app = create_app(TestConfig)
    with app.app_context():
        #el esquema de pruebas sale de las mismas migraciones que usa la app
        upgrade(directory=os.path.join(ROOT, "migrations"))
        db.session.add_all([Categoria(k_categoria="VINILO"), Categoria(k_categoria="CAMISETA")])
        disco = Lanzamiento(id=1, n_lanzamiento="negro swan")
        artista = Artista(id=1, n_artista="BLOOD ORANGE")
        db.session.add_all([disco, artista, Lanzamiento_Artista(k_artista=1, k_lanzamiento=1)])
        db.session.add_all([
            Producto(id=1, k_lanzamiento=1, k_categoria="VINILO", n_producto="Vinilo", p_producto=120000, stock=5),
            Producto(id=2, k_lanzamiento=1, k_categoria="CAMISETA", n_producto="Camiseta", p_producto=60000, stock=2),
        ])
        db.session.add(Usuario(id=50, k_rol="USER", n_usuario="Ana", ape_usuario="Cuenta", email_usuario="ana@cuenta.com", pwd_usuario="clave"))
        db.session.commit()
        yield app
        db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()


DATOS_ENVIO = {
    "nombre": "Laura Invitada Pérez",
    "email": "Laura@Correo.com",
    "telefono": "3001234567",
    "ciudad": "Suba, Bogotá D.C.",
    "direccion": "Cra 1 # 2-3",
    "barrio": "Niza",
    "metodo_pago": "PSE",
}


def comprar(client, carrito, datos=None):
    """Agrega al carrito y envía el checkout. Devuelve la respuesta del POST.
    Por defecto elige el abono cuando la preorden lo permite; pasa pago_parcial='total'
    para probar el pago completo."""
    for k_producto, cantidad in carrito.items():
        client.post("/purchase/addtocart", data={"product_id": str(k_producto), "quantity": str(cantidad)},
                    headers={"Referer": "/products/"})
    datos = dict(datos or DATOS_ENVIO)
    datos.setdefault("pago_parcial", "abono")
    return client.post("/purchase/process_checkout", data=datos)


def simular_pago(client, app, token, resultado="aprobado"):
    """Confirma (o rechaza) el pago por el mismo camino que usa MercadoPago en producción.

    /pedido/<token>/simular existe solo en desarrollo, pero por dentro llama a confirmar_pago()
    igual que el webhook real, así que sirve para probar el descuento de stock, el correo y la
    idempotencia sin hablar con MercadoPago."""
    antes = app.config.get("SIMULACION_PAGO")
    app.config["SIMULACION_PAGO"] = True
    try:
        return client.post(f"/pedido/{token}/simular", data={"resultado": resultado})
    finally:
        app.config["SIMULACION_PAGO"] = antes
