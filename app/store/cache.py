"""Caché en memoria, pequeña y explícita.

No reemplaza a Redis: sirve para no repetir cálculos caros entre peticiones
seguidas (listas de categorías/géneros, resúmenes del panel). En pruebas se
desactiva para que cada test vea sus propios datos.
"""
import threading
import time

_CACHE = {}
_LOCK = threading.Lock()


def cache_ttl(key, seconds, fn):
    from flask import current_app, has_app_context

    if has_app_context() and current_app.config.get("TESTING"):
        return fn()

    ahora = time.time()
    with _LOCK:
        guardado = _CACHE.get(key)
        if guardado and guardado[0] > ahora:
            return guardado[1]

    valor = fn()
    with _LOCK:
        _CACHE[key] = (ahora + seconds, valor)
    return valor


def cache_clear(prefix=None):
    with _LOCK:
        if prefix:
            for clave in list(_CACHE):
                if clave.startswith(prefix):
                    _CACHE.pop(clave, None)
        else:
            _CACHE.clear()
