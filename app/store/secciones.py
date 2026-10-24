"""Interruptores de sección de la tienda (feature flags), guardados en la tabla Configuracion.

El admin los prende/apaga desde /dashboard/secciones sin tocar el servidor. Mientras una
sección está apagada, el visitante ve una página "Pronto" (proximamente.html) y el admin
sigue viendo todo el catálogo: es el puente para preparar la tienda sin abrirla del todo.

Sin fila en Configuracion, la sección queda abierta (el comportamiento no cambia hasta que
el admin apague algo). Los endpoints que terminan en "." son prefijos; el resto, nombre exacto.
"""
from .redes import get_config, set_config

#sólo se listan las secciones que se pueden apagar; el resto de la tienda queda siempre abierta
SECCIONES = {
    'lanzamientos': {'nombre': 'Lanzamientos', 'icono': 'bi-vinyl-fill',
                     'endpoints': ('releases.',)},
    'productos': {'nombre': 'Productos y catálogo', 'icono': 'bi-bag-fill',
                  'endpoints': ('products.', 'home.buscar', 'home.sugerencias')},
    'artistas': {'nombre': 'Artistas', 'icono': 'bi-people-fill',
                 'endpoints': ('artists.',)},
}

#endpoints que nunca se apagan aunque su sección esté cerrada: sirven assets usados por
#páginas abiertas (la portada muestra tarjetas de producto con estas imágenes)
EXENTOS = {'products.image'}

#valores de respaldo de la página "Pronto" (también viven en el DEFAULTS de redes.py)
_TITULO = '¡Pronto!'
_MENSAJE = ('Estamos afinando los últimos detalles. Muy pronto podrás explorar todo '
            'el catálogo por aquí.')


def seccion_de(endpoint):
    """Sección a la que pertenece el endpoint, o None si no está sujeta a interruptor."""
    if not endpoint or endpoint in EXENTOS:
        return None
    for slug, cfg in SECCIONES.items():
        exactos = {e for e in cfg['endpoints'] if not e.endswith('.')}
        prefijos = tuple(e for e in cfg['endpoints'] if e.endswith('.'))
        if endpoint in exactos or (prefijos and endpoint.startswith(prefijos)):
            return slug
    return None


def habilitada(slug):
    """¿La sección está abierta al público? Sin fila guardada, sí."""
    return get_config('seccion.' + slug) != '0'


def estado_secciones():
    """[(slug, nombre, icono, habilitada)] en orden, para el panel."""
    return [(s, c['nombre'], c['icono'], habilitada(s)) for s, c in SECCIONES.items()]


def mensaje_pronto():
    """(título, mensaje) de la página "Pronto", editables por el admin."""
    return (get_config('seccion.titulo') or _TITULO,
            get_config('seccion.mensaje') or _MENSAJE)


def guardar_secciones(estados, titulo, mensaje):
    """estados = {slug: valor del checkbox}. Guarda los interruptores y los textos del aviso."""
    valores = {f'seccion.{s}': ('1' if estados.get(s) else '0') for s in SECCIONES}
    valores['seccion.titulo'] = (titulo or '').strip() or _TITULO
    valores['seccion.mensaje'] = (mensaje or '').strip() or _MENSAJE
    set_config(valores)
