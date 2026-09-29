from app import create_app
from app.store.models import Invoice, Usuario

app = create_app()
with app.app_context():
    # Buscar el pedido por token_hash
    pedido = Invoice.query.filter_by(token_hash='a48176a85427658ffd26077d4d0f845ccb70a39b4b782929e3ecdf39c78c82da').first()
    if pedido:
        print(f'Pedido ID: {pedido.id}')
        print(f'Usuario ID: {pedido.k_usuario}')
        print(f'Estado: {pedido.estado}')
        print(f'Total: {pedido.total}')
        usuario = Usuario.query.get(pedido.k_usuario)
        if usuario:
            print(f'Usuario nombre: {usuario.n_usuario} {usuario.ape_usuario}')
            print(f'Usuario email: {usuario.email_usuario}')
            print(f'Usuario rol: {usuario.k_rol}')
        print(f'Datos envío - Nombre: {pedido.n_envio}')
        print(f'Datos envío - Email: {pedido.email_envio}')
        print(f'Datos envío - Teléfono: {pedido.tel_envio}')
        print(f'Datos envío - Dirección: {pedido.dir_envio}')
        print(f'Datos envío - Ciudad: {pedido.lugar_envio}')
        print(f'Datos envío - Barrio: {pedido.barrio_envio}')
    else:
        print("Pedido no encontrado")
        
    # Listar todos los pedidos recientes para ver cuál es el correcto
    print("\n--- Últimos 5 pedidos ---")
    pedidos = Invoice.query.order_by(Invoice.id.desc()).limit(5).all()
    for p in pedidos:
        print(f"ID: {p.id}, Token hash: {p.token_hash[:20]}..., Usuario: {p.k_usuario}, Nombre: {p.n_envio}")