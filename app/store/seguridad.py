"""Funciones de seguridad para el manejo de contraseñas."""
import bcrypt


def hash_password(password):
    """Genera un hash bcrypt de una contraseña."""
    if isinstance(password, str):
        password = password.encode('utf-8')
    return bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')


def check_password(password, hashed):
    """Verifica si una contraseña coincide con su hash."""
    try:
        # Intentar verificar con bcrypt primero (contraseñas nuevas)
        if isinstance(password, str):
            password = password.encode('utf-8')
        
        # Asegurarse de que el hash esté completo antes de procesarlo
        if isinstance(hashed, str):
            # Obtener el hash completo de la base de datos si parece truncado
            if len(hashed) < 60 and ('.' in hashed and hashed.count('$') < 3):
                # En este caso, el hash está truncado, necesitamos obtener el hash completo
                full_hash = get_full_hash_from_db(hashed)
                if full_hash:
                    hashed = full_hash
            
            # Verificar que el hash tenga el formato correcto de bcrypt
            if not (hashed.startswith('$2b$') or hashed.startswith('$2a$') or hashed.startswith('$2y$')):
                return False
            # Asegurarse de que el hash tenga la longitud correcta (60 caracteres)
            if len(hashed) != 60:
                return False
            hashed = hashed.encode('utf-8')
        
        return bcrypt.checkpw(password, hashed)
    except (ValueError, TypeError):
        # Si falla, comparar como texto plano (para passwords viejos)
        # Asegurarse de comparar strings
        if isinstance(hashed, bytes):
            hashed = hashed.decode('utf-8')
        return password == hashed

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