"""Paso 4: stock por variante, bundles y líneas de pedido con variante."""
import pytest

from app.db import db
from app.store import pedidos
from app.store.models import (Invoice, Item, Producto, ProductoComponente, Variante, confirmar_pago,
                              referencia_epayco, stock_disponible, validar_bundle, validar_carrito)
from conftest import DATOS_ENVIO


@pytest.fixture
def catalogo(app):
    """Camiseta (id 2) con tallas M/L y un pack vinilo + camiseta M (id 3)."""
    with app.app_context():
        m = Variante(id=10, k_producto=2, talla="M", color="Negro", stock=3)
        l = Variante(id=11, k_producto=2, talla="L", color="Negro", stock=1)
        pack = Producto(id=3, k_lanzamiento=1, k_categoria="VINILO", n_producto="Pack vinilo + camiseta",
                        p_producto=160000, stock=0, tipo="BUNDLE")
        db.session.add_all([m, l, pack])
        db.session.flush()
        db.session.add_all([ProductoComponente(k_bundle=3, k_componente=1, cantidad=1),
                            ProductoComponente(k_bundle=3, k_componente=2, k_variante=10, cantidad=1)])
        db.session.commit()
    return app


def poner_carrito(client, carrito):
    with client.session_transaction() as s:
        s["purchase"] = carrito


def test_stock_por_variante_y_total(catalogo):
    with catalogo.app_context():
        camiseta = db.session.get(Producto, 2)
        assert stock_disponible(camiseta, db.session.get(Variante, 10)) == 3
        assert stock_disponible(camiseta, db.session.get(Variante, 11)) == 1
        assert stock_disponible(camiseta) == 4  #suma, para mostrar "agotado" o no


def test_stock_del_bundle_es_el_minimo_de_sus_componentes(catalogo):
    with catalogo.app_context():
        pack = db.session.get(Producto, 3)
        assert validar_bundle(pack) == []
        assert stock_disponible(pack) == 3  #vinilo 5, camiseta M 3
        db.session.get(Variante, 10).stock = 0
        assert stock_disponible(pack) == 0


def test_bundle_mal_armado_no_se_puede_vender(catalogo):
    with catalogo.app_context():
        comp = ProductoComponente.query.filter_by(k_bundle=3, k_componente=2).one()
        comp.k_variante = None  #camiseta sin talla
        db.session.flush()
        pack = db.session.get(Producto, 3)
        assert validar_bundle(pack) == ["Indica la talla/color de Camiseta"]
        assert stock_disponible(pack) == 0


def test_carrito_exige_elegir_variante(catalogo):
    with catalogo.app_context():
        lineas, total, errores = validar_carrito({"2": 1})
        assert lineas == [] and errores == ["Negro Swan - Camiseta: elige talla o color"]
        lineas, total, errores = validar_carrito({"2:10": 2})
        assert errores == [] and total == 120000 and lineas[0][1].talla == "M"


def test_carrito_rechaza_variante_de_otro_producto(catalogo):
    with catalogo.app_context():
        assert validar_carrito({"1:10": 1})[2] == ["Un producto de tu carrito ya no está disponible"]


def test_demanda_combinada_de_sueltos_y_packs(catalogo):
    with catalogo.app_context():
        #camiseta M: 3 en stock; 2 sueltas + 2 packs = 4
        lineas, total, errores = validar_carrito({"2:10": 2, "3": 2})
        assert lineas == []
        assert errores == ["Negro Swan - Camiseta (M / Negro): entre productos sueltos y packs pides 4, solo quedan 3"]
        assert validar_carrito({"2:10": 1, "3": 2})[2] == []


def test_mismo_producto_en_dos_tallas_en_un_pedido(client, catalogo):
    poner_carrito(client, {"2:10": 1, "2:11": 1})
    resp = client.post("/purchase/checkout", data=DATOS_ENVIO)
    assert resp.status_code == 302 and "/pedido/" in resp.headers["Location"]
    with catalogo.app_context():
        items = Item.query.order_by(Item.id).all()
        assert [(i.k_producto, i.k_variante) for i in items] == [(2, 10), (2, 11)]
        assert Invoice.query.one().total == 120000


def test_pago_descuenta_variante_y_componentes_del_pack(client, catalogo, monkeypatch):
    poner_carrito(client, {"2:11": 1, "3": 2})
    token = client.post("/purchase/checkout", data=DATOS_ENVIO).headers["Location"].rsplit("/", 1)[1]
    with catalogo.app_context():
        p = Invoice.query.one()
        ref, monto = referencia_epayco(p), str(p.total)
    monkeypatch.setattr(pedidos, "consultar_epayco", lambda r: {"x_response": "Aceptada", "x_id_invoice": ref, "x_amount": monto})
    client.get(f"/pedido/{token}/respuesta?ref_payco=x")
    with catalogo.app_context():
        assert Invoice.query.one().estado == "PAGADO"
        assert db.session.get(Variante, 11).stock == 0   #camiseta L suelta
        assert db.session.get(Variante, 10).stock == 1   #2 packs usan 2 camisetas M
        assert db.session.get(Producto, 1).stock == 3    #2 packs usan 2 vinilos
        assert db.session.get(Producto, 3).stock == 0    #el pack no tiene stock propio
        assert db.session.get(Producto, 2).stock == 2    #el stock propio de la camiseta no se toca


def test_confirmar_pago_nunca_deja_stock_negativo(catalogo):
    with catalogo.app_context():
        pedido = Invoice(k_usuario=50, total=60000, estado="PENDIENTE", token_hash="x" * 64)
        db.session.add(pedido)
        db.session.flush()
        db.session.add(Item(k_producto=2, k_factura=pedido.id, k_variante=11, cant_item=5, p_item=60000))
        db.session.commit()
        confirmar_pago(pedido, "ref")
        assert db.session.get(Variante, 11).stock == 0
