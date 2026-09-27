"""Paso 5a: carrito con variantes y packs; stock visible antes de pagar."""
from test_variantes_bundles import catalogo, poner_carrito  # noqa: F401 (fixture)


def carrito_de(client):
    with client.session_transaction() as s:
        return dict(s.get("purchase") or {})


def agregar(client, producto, cantidad=1, variante=None):
    data = {"product_id": str(producto), "quantity": str(cantidad)}
    if variante:
        data["variante_id"] = str(variante)
    return client.post("/purchase/addtocart", data=data, headers={"Referer": "http://localhost/releases/1"})


def test_agregar_con_variante_usa_clave_producto_variante(client, catalogo):
    agregar(client, 2, 1, variante=10)
    agregar(client, 2, 1, variante=11)
    agregar(client, 2, 1, variante=10)  #suma a la misma línea
    assert carrito_de(client) == {"2:10": 2, "2:11": 1}


def test_no_se_puede_agregar_sin_elegir_talla(client, catalogo):
    agregar(client, 2, 1)
    assert carrito_de(client) == {}


def test_agregar_no_pasa_del_stock_de_la_variante(client, catalogo):
    agregar(client, 2, 5, variante=11)  #talla L: 1 en stock
    assert carrito_de(client) == {"2:11": 1}
    agregar(client, 2, 1, variante=11)
    assert carrito_de(client) == {"2:11": 1}


def test_variante_de_otro_producto_se_rechaza(client, catalogo):
    agregar(client, 1, 1, variante=10)
    assert carrito_de(client) == {}


def test_pack_se_agrega_hasta_su_stock(client, catalogo):
    agregar(client, 3, 9)  #pack: mínimo de vinilo 5 y camiseta M 3
    assert carrito_de(client) == {"3": 3}


def test_carrito_muestra_talla_y_avisa_antes_de_pagar(client, catalogo):
    poner_carrito(client, {"2:10": 2, "3": 2})  #4 camisetas M, hay 3
    html = client.get("/purchase/").get_data(as_text=True)
    assert "M / Negro" in html and "PACK" in html
    assert "entre productos sueltos y packs pides 4, solo quedan 3" in html
    assert 'href="/purchase/checkout"' not in html  #botón de pago deshabilitado
    #el checkout también lo impide
    assert client.get("/purchase/checkout").headers["Location"].endswith("/purchase/")


def test_carrito_marca_linea_sin_stock_suficiente(client, catalogo):
    poner_carrito(client, {"2:11": 3})
    html = client.get("/purchase/").get_data(as_text=True)
    assert "Solo quedan 1" in html


def test_cambiar_cantidad_respeta_stock_y_quita_en_cero(client, catalogo):
    poner_carrito(client, {"2:11": 1})
    client.get("/purchase/updatesingle2:11_up", headers={"Referer": "/purchase/"})
    assert carrito_de(client) == {"2:11": 1}
    client.get("/purchase/updatesingle2:11_down", headers={"Referer": "/purchase/"})
    assert carrito_de(client) == {}


def test_quitar_linea(client, catalogo):
    poner_carrito(client, {"2:10": 1, "1": 1})
    client.get("/purchase/remove/2:10", headers={"Referer": "/purchase/"})
    assert carrito_de(client) == {"1": 1}


def test_carrito_con_productos_simples_sigue_igual(client, catalogo):
    agregar(client, 1, 2)
    assert carrito_de(client) == {"1": 2}
    html = client.get("/purchase/").get_data(as_text=True)
    assert "$240.000" in html and 'href="/purchase/checkout"' in html
