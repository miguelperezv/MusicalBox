from app import create_app
from app.store.models import Invoice

app = create_app()
with app.app_context():
    invoices = Invoice.query.all()
    print('Total invoices: {}'.format(len(invoices)))
    for i in invoices:
        print('{}: {}... estado:{}'.format(i.id, i.token_hash[:20] if i.token_hash else 'None', i.estado))