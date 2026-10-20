"""Rate limiting de endpoints sensibles (login y formularios públicos).

El backend por defecto es memoria del proceso. En producción con varios workers se puede
apuntar a un almacenamiento compartido con RATELIMIT_STORAGE_URI (por ejemplo Redis).
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


limiter = Limiter(key_func=get_remote_address)
