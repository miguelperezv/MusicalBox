"""Script para probar la configuración de correo."""
import sys
import os

# Añadir el directorio raíz al path para poder importar los módulos de la app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.correo import enviar

def probar_correo():
    """Prueba el envío de correo con la configuración actual."""
    app = create_app()
    
    with app.app_context():
        # Verificar configuración
        backend = app.config.get("MAIL_BACKEND", "consola")
        print(f"Usando backend de correo: {backend}")
        
        if backend == "smtp":
            print("Configuración SMTP:")
            print(f"  Servidor: {app.config.get('MAIL_SERVER')}")
            print(f"  Puerto: {app.config.get('MAIL_PORT')}")
            print(f"  Usuario: {app.config.get('MAIL_USERNAME')}")
            print(f"  TLS: {app.config.get('MAIL_USE_TLS')}")
            print(f"  Desde: {app.config.get('MAIL_FROM')}")
        
        # Enviar correo de prueba
        destino = "test@example.com"
        asunto = "Prueba de configuración de correo"
        texto = "Este es un correo de prueba para verificar la configuración."
        html = "<p>Este es un <strong>correo de prueba</strong> para verificar la configuración.</p>"
        
        print(f"\nEnviando correo de prueba a {destino}...")
        resultado = enviar(destino, asunto, texto, html)
        
        if resultado:
            print("¡Correo enviado exitosamente!")
            if backend == "consola":
                print("El correo se guardó en instance/correos/")
            elif backend == "memoria":
                print("El correo se guardó en memoria (pruebas)")
        else:
            print("Error al enviar el correo. Revisa la configuración.")

if __name__ == "__main__":
    probar_correo()