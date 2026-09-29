from app import create_app
from app.store.models import Invoice

app = create_app()
with app.app_context():
    # Buscar los últimos 5 pedidos ordenados por ID descendente
    invoices = Invoice.query.order_by(Invoice.id.desc()).limit(5).all()
    print('Últimos 5 pedidos:')
    for inv in invoices:
        print('ID: {}, token_hash: {}..., estado: {}'.format(
            inv.id, 
            inv.token_hash[:20] if inv.token_hash else 'None', 
            inv.estado
        ))