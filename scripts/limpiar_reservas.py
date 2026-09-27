"""Script para limpiar las reservas de stock expiradas."""
import sys
import os

# Añadir el directorio raíz al path para poder importar los módulos de la app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.store.models import limpiar_reservas_expiradas

def limpiar_reservas():
    """Limpia las reservas de stock expiradas."""
    app = create_app()
    
    with app.app_context():
        print("Limpiando reservas expiradas...")
        cantidad = limpiar_reservas_expiradas()
        print(f"Se limpiaron {cantidad} reservas expiradas.")

if __name__ == "__main__":
    limpiar_reservas()