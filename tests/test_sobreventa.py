"""Sobreventa: no se puede vender stock que otro pedido acaba de apartar."""
from datetime import datetime

from app.db import db
from app.store.models import Invoice, Producto, Variante, reservar_stock_pedido


def test_no_se_reserva_stock_que_otro_pedido_ya_se_llevo(app):
    #este proceso leyó el producto cuando había 5 unidades
    with app.app_context():
        producto = db.session.get(Producto, 1)
        assert int(producto.stock) == 5

        #mientras tanto, otro proceso vendió las 5 (su propia sesión, ya confirmada)
        with app.app_context():
            otro = db.session.get(Producto, 1)
            otro.stock = 0
            db.session.commit()

        #este proceso no se enteró: su comprobación pasa (5 en memoria) pero el descuento no
        pedido = Invoice(total=120000, estado="PENDIENTE", token_hash="hash-de-prueba",
                         token_creado=datetime.now())
        db.session.add(pedido)
        db.session.flush()
        ok, errores = reservar_stock_pedido(pedido, [(producto, None, 5)])

        assert ok is False
        assert "otro pedido se llevó las últimas unidades" in errores[0]
        assert pedido.stock_reservado in (False, None)
        #y no queda un pedido a medias con reservas de stock
        db.session.rollback()

    with app.app_context():
        assert int(db.session.get(Producto, 1).stock) == 0  #no bajó de cero
        assert Invoice.query.filter_by(token_hash="hash-de-prueba").count() == 0


def test_la_ultima_unidad_se_vende_una_sola_vez(client, app):
    #dos carritos con la última unidad: el primero la aparta, el segundo recibe el aviso
    with app.app_context():
        p = db.session.get(Producto, 1)
        p.stock = 1
        db.session.commit()

    from conftest import comprar
    primero = comprar(client, {1: 1}, {"nombre": "Uno", "email": "uno@correo.com", "telefono": "3001111111",
                                       "ciudad": "Suba, Bogotá D.C.", "direccion": "Cra 1 # 2-3", "barrio": "Niza"})
    assert primero.status_code == 302 and "/pedido/" in primero.headers["Location"]

    otro = app.test_client()
    segundo = comprar(otro, {1: 1}, {"nombre": "Dos", "email": "dos@correo.com", "telefono": "3002222222",
                                     "ciudad": "Suba, Bogotá D.C.", "direccion": "Cra 1 # 2-3", "barrio": "Niza"})
    assert segundo.status_code == 302 and segundo.headers["Location"].endswith("/purchase/")
    with app.app_context():
        assert Invoice.query.count() == 1  #solo quedó el pedido del primero
        assert int(db.session.get(Producto, 1).stock) == 0


def test_la_variante_tambien_se_protege(app):
    #la talla es la que se agota: la reserva se hace contra el stock de la variante
    with app.app_context():
        db.session.add(Variante(id=10, k_producto=2, talla="M", color="Negro", stock=2))
        db.session.commit()
        camiseta = db.session.get(Producto, 2)
        v = db.session.get(Variante, 10)

        with app.app_context():
            otra = db.session.get(Variante, 10)
            otra.stock = 0
            db.session.commit()

        pedido = Invoice(total=60000, estado="PENDIENTE", token_hash="hash-variante",
                         token_creado=datetime.now())
        db.session.add(pedido)
        db.session.flush()
        ok, errores = reservar_stock_pedido(pedido, [(camiseta, v, 2)])
        assert ok is False and "otro pedido" in errores[0]
        db.session.rollback()
