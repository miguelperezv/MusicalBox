"""Temáticas de temporada del logotipo (vinilo vivo).

El logotipo se "disfraza" unos días al año **sin tocar el boceto**: sólo se le montan
adornos encima (el gorro de la nota, murciélagos, chispas, corazones, discos chiquitos).
El disco, los surcos, la etiqueta y la nota siguen siendo exactamente los del boceto
`musicalbox.png`, así que la marca nunca deja de ser reconocible.

El tema activo sale de la fecha en hora de Bogotá. Se puede forzar para previsualizar
(o para grabar los videos de redes) de dos maneras:

    ?tema=navidad            en la URL (también ?tema=ninguno para apagarlo)
    MUSICALBOX_TEMA=navidad  en el entorno

Ventanas de fechas (fáciles de mover aquí abajo):

    halloween        20 oct - 1 nov
    record_store_day el 3er sábado de abril ± 3 días (Record Store Day)
    amor_amistad     12 - 22 de septiembre (día del Amor y la Amistad en Colombia)
    navidad          1 - 25 de diciembre
    ano_nuevo        26 de diciembre - 6 de enero

Uso:
    - Plantillas: `{% if tema == 'navidad' %}` (el contexto inyecta `tema`)
    - Python:     `from .temporadas import tema_activo`  ->  `tema_activo(request.args)`
"""
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

BOGOTA = ZoneInfo("America/Bogota")

# clave -> nombre para mostrar (títulos del hero o de redes, si se necesitan)
NOMBRES = {
    "halloween": "Halloween",
    "record_store_day": "Record Store Day",
    "amor_amistad": "Amor y amistad",
    "navidad": "Navidad",
    "ano_nuevo": "Año nuevo",
}

# orden en que se dibujan (no se solapan, pero deja el set completo en un solo sitio)
TEMAS = tuple(NOMBRES)


def _tercer_sabado(anio, mes):
    """El tercer sábado del mes: Record Store Day cae ahí todos los años."""
    sabados = [date(anio, mes, dia) for dia in range(1, 32)
               if _existe(anio, mes, dia) and date(anio, mes, dia).weekday() == 5]
    return sabados[2]


def _existe(anio, mes, dia):
    try:
        date(anio, mes, dia)
        return True
    except ValueError:
        return False


def tema_por_fecha(d):
    """La clave del tema que toca ese día (o None si es un día normal)."""
    if (d.month == 10 and d.day >= 20) or (d.month == 11 and d.day == 1):
        return "halloween"
    if abs((d - _tercer_sabado(d.year, 4)).days) <= 3:
        return "record_store_day"
    if d.month == 9 and 12 <= d.day <= 22:
        return "amor_amistad"
    if d.month == 12 and 1 <= d.day <= 25:
        return "navidad"
    if (d.month == 12 and d.day >= 26) or (d.month == 1 and d.day <= 6):
        return "ano_nuevo"
    return None


def _normalizar(valor):
    """Devuelve la clave pedida, '' si piden apagarlo, o None si no es un tema conocido."""
    if valor is None:
        return None
    clave = str(valor).strip().lower().replace("-", "_").replace(" ", "_")
    if not clave:
        return None
    if clave in ("ninguno", "ninguna", "auto", "no", "off", "0"):
        return ""
    if clave in ("ano_nuevo", "añonuevo", "ano_feliz"):
        return "ano_nuevo"
    return clave if clave in TEMAS else None


def tema_activo(args=None, ahora=None):
    """Tema de hoy (clave), forzado por ?tema= o MUSICALBOX_TEMA, o None si es un día normal."""
    for candidato in ((args or {}).get("tema"), os.getenv("MUSICALBOX_TEMA")):
        clave = _normalizar(candidato)
        if clave is not None:
            return clave or None
    return tema_por_fecha((ahora or datetime.now(BOGOTA)).date())
