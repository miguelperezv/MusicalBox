"""Funciones de seguridad para el manejo de contraseñas."""
import bcrypt


def hash_password(password):
    """Genera un hash bcrypt de una contraseña."""
    if isinstance(password, str):
        password = password.encode('utf-8')
    return bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')


def check_password(password, hashed):
    """Verifica si una contraseña coincide con su hash."""
    if isinstance(password, str):
        password = password.encode('utf-8')
    if isinstance(hashed, str):
        hashed = hashed.encode('utf-8')
    return bcrypt.checkpw(password, hashed)