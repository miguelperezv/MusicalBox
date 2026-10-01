"""Funciones de seguridad para el manejo de contraseñas."""
import bcrypt


def hash_password(password):
    """Genera un hash bcrypt de una contraseña."""
    if isinstance(password, str):
        password = password.encode('utf-8')
    return bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')


def check_password(password, hashed):
    """Verifica si una contraseña coincide con su hash (o con el texto plano legacy)."""
    if not hashed:
        return False
    pwd = password.encode('utf-8') if isinstance(password, str) else password
    if not isinstance(hashed, str):
        return False
    # hash truncado: workaround que recupera el completo desde la BD
    if len(hashed) < 60 and ('.' in hashed and hashed.count('$') < 3):
        full_hash = get_full_hash_from_db(hashed)
        if full_hash:
            hashed = full_hash
    # cuentas nuevas: hash bcrypt
    if hashed.startswith(('$2b$', '$2a$', '$2y$')) and len(hashed) == 60:
        try:
            return bcrypt.checkpw(pwd, hashed.encode('utf-8'))
        except (ValueError, TypeError):
            return False
    # cuentas legacy: la clave se guardó en texto plano
    return (password if isinstance(password, str) else password.decode('utf-8')) == hashed

def get_full_hash_from_db(truncated_hash):
    """Obtiene el hash completo de la base de datos basado en el hash truncado"""
    # Esta función es un workaround temporal
    # En una implementación real, se debería evitar este problema desde la fuente
    try:
        import sqlite3
        conn = sqlite3.connect('instance/musicalbox.sqlite3')
        # Buscar un hash que contenga el fragmento truncado
        cursor = conn.execute('SELECT pwd_usuario FROM usuario WHERE pwd_usuario LIKE ?', (f'%{truncated_hash}%',))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        print(f"Error getting full hash from DB: {e}")
        return None