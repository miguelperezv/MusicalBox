"""Los rankings del panel con ítems que no salen del catálogo.

Una línea de pedido puede quedar con `k_producto` nulo (el modelo lo permite y hay ítems a la
medida). Los rankings le hacían `db.session.get(Producto, None)` y SQLAlchemy soltaba un
`SAWarning` por cada uno; el ítem se descartaba igual, así que el `.limit()` también se gastaba
un puesto en una fila que iba a tirar.
"""
import warnings

from sqlalchemy.exc import SAWarning

from app.db import db
from app.store.models import Invoice, Item, get_admin_stats, get_productos_mas_vendidos
from conftest import comprar, simular_pago
from test_checkout_invitado import token_de


def test_los_items_sin_producto_no_ensucian_los_rankings(client, app):
    token = token_de(comprar(client, {1: 2}))
    simular_pago(client, app, token)

    with app.app_context():
        pedido = Invoice.query.one()
        assert pedido.estado == "PAGADO"
        #el caso que disparaba el aviso: un ítem sin producto en un pedido pagado
        db.session.add(Item(k_factura=pedido.id, k_producto=None, n_item="A la medida",
                            cant_item=1, p_item=50000))
        db.session.commit()

        with warnings.catch_warnings(record=True) as avisos:
            warnings.simplefilter("always")
            vendidos = get_productos_mas_vendidos(limit=10, dias=30)
            stats = get_admin_stats(dias=30)

        sueltos = [str(a.message) for a in avisos if issubclass(a.category, SAWarning)]
        assert sueltos == []
        assert [v["producto"].id for v in vendidos] == [1]   #el ítem sin producto no aparece
        assert vendidos[0]["u"] == 2
        assert [t["u"] for t in stats["top5"]] == [2]
