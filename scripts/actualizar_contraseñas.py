"""Script para actualizar las contraseñas existentes a bcrypt."""
import sys
import os

# Añadir el directorio raíz al path para poder importar los módulos de la app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.db import db
from app.store.models import Usuario
from app.store.seguridad import hash_password

def actualizar_contraseñas():
    """Actualiza todas las contraseñas existentes para usar bcrypt."""
    app = create_app()
    
    with app.app_context():
        # Obtener todos los usuarios
        usuarios = Usuario.query.all()
        
        print(f"Actualizando contraseñas de {len(usuarios)} usuarios...")
        
        for usuario in usuarios:
            # Verificar si la contraseña ya está cifrada (longitud típica de bcrypt: 60 caracteres)
            if len(usuario.pwd_usuario) < 60:
                print(f"Actualizando contraseña para {usuario.email_usuario}...")
                usuario.pwd_usuario = hash_password(usuario.pwd_usuario)
            else:
                print(f"Contraseña de {usuario.email_usuario} ya está cifrada.")
        
        # Guardar cambios
        db.session.commit()
        print("¡Todas las contraseñas han sido actualizadas!")

if __name__ == "__main__":
    actualizar_contraseñas()