"""Script para probar la funcionalidad de reserva de stock."""
import sys
import os

# Añadir el directorio raíz al path para poder importar los módulos de la app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.db import db
from app.store.models import Producto, Variante, Invoice, Item, ReservaStock

def probar_reserva_stock():
    """Prueba la funcionalidad de reserva de stock."""
    app = create_app()
    
    with app.app_context():
        # Crear un producto de prueba
        print("Creando producto de prueba...")
        producto = Producto(
            n_producto="Camiseta de prueba",
            p_producto=50000,
            stock=10,
            k_categoria="CAMISETA"
        )
        db.session.add(producto)
        db.session.commit()
        print(f"Producto creado con ID: {producto.id}")
        
        # Crear un pedido de prueba
        print("Creando pedido de prueba...")
        pedido = Invoice(
            total=100000,
            estado='PENDIENTE',
            n_envio="Cliente de prueba",
            email_envio="cliente@prueba.com",
            tel_envio="3001234567",
            dir_envio="Calle falsa 123",
            lugar_envio="Bogotá D.C., Bogotá D.C."
        )
        db.session.add(pedido)
        db.session.commit()
        print(f"Pedido creado con ID: {pedido.id}")
        
        # Crear un ítem para el pedido
        print("Creando ítem para el pedido...")
        item = Item(
            k_producto=producto.id,
            k_factura=pedido.id,
            cant_item=2,
            p_item=50000
        )
        db.session.add(item)
        db.session.commit()
        print(f"Ítem creado con ID: {item.id}")
        
        # Probar la reserva de stock
        print("Probando reserva de stock...")
        lineas = [(producto, None, 2)]  # (producto, variante, cantidad)
        exito, errores = app.store.models.reservar_stock_pedido(pedido, lineas)
        
        if exito:
            print("¡Reserva de stock exitosa!")
            print(f"Stock actual del producto: {producto.stock}")
            
            # Verificar las reservas creadas
            reservas = ReservaStock.query.filter_by(k_invoice=pedido.id).all()
            print(f"Reservas creadas: {len(reservas)}")
            for reserva in reservas:
                print(f"  - Elemento {reserva.tipo_elemento}{reserva.k_elemento}: {reserva.cantidad} unidades")
        else:
            print("Errores en la reserva de stock:")
            for error in errores:
                print(f"  - {error}")
        
        # Probar liberar la reserva
        print("Probando liberación de reserva...")
        app.store.models.liberar_reserva_stock(pedido.id)
        db.session.refresh(producto)
        print(f"Stock del producto después de liberar: {producto.stock}")
        
        # Limpiar datos de prueba
        print("Limpiando datos de prueba...")
        ReservaStock.query.filter_by(k_invoice=pedido.id).delete()
        Item.query.filter_by(k_factura=pedido.id).delete()
        Invoice.query.filter_by(id=pedido.id).delete()
        Producto.query.filter_by(id=producto.id).delete()
        db.session.commit()
        
        print("¡Prueba completada!")

if __name__ == "__main__":
    probar_reserva_stock()