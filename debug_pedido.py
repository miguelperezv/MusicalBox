from app import create_app
from app.store.models import Invoice

app = create_app()
with app.app_context():
    token_hash = '75jA341OZeY_GIgz-e00YdS4fTYkGQ8_IK3p5ZEbjyQ'
    inv = Invoice.query.filter_by(token_hash=token_hash).first()
    print('Pedido encontrado: {}'.format(inv is not None))
    if inv:
        print('ID: {}'.format(inv.id))
        print('Estado: {}'.format(inv.estado))
        print('Total: {}'.format(inv.total))
        print('Email: {}'.format(inv.email_envio))
    else:
        print('No existe pedido con ese token_hash')