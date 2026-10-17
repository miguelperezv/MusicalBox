"""Temáticas de temporada del logotipo (vinilo vivo).

El logotipo se "disfraza" unos días al año **sin tocar el boceto**: sólo se le montan
adornos encima (el gorro de la nota, murciélagos, chispas, corazones, discos chiquitos).
El disco, los surcos, la etiqueta y la nota siguen siendo exactamente los del boceto
`musicalbox.png`, así que la marca nunca deja de ser reconocible.

El tema activo sale de la fecha en hora de Bogotá y se puede cambiar sin tocar código:

    Panel      /dashboard/tema  -> el admin ve todos los temas, los previsualiza en vivo
                                    y marca el que quiera (o lo apaga, o lo deja automático)
    ?tema=...  en la URL        -> ?tema=navidad (también ?tema=ninguno para apagarlo)
    Entorno    MUSICALBOX_TEMA=navidad

Manda la URL, después el entorno, después lo que dejó el admin en el panel, y si no hay
nada de eso, la fecha. La elección del panel queda en la tabla Configuracion como
'tema.modo' (auto | forzado | apagado) y 'tema.forzado' (la clave).

Ventanas de fechas (fáciles de mover aquí abajo; VENTANAS es sólo el texto que muestra
el panel):

    halloween        20 oct - 1 nov
    record_store_day el 3er sábado de abril ± 3 días (Record Store Day)
    pride            mes del orgullo (junio) y la primera marcha de julio en Bogotá
    amor_amistad     12 - 22 de septiembre (día del Amor y la Amistad en Colombia)
    navidad          1 - 25 de diciembre
    ano_nuevo        26 de diciembre - 6 de enero

Uso:
    - Plantillas: `{% if tema == 'navidad' %}` (el contexto inyecta `tema`)
    - Python:     `from .temporadas import tema_activo`  ->  `tema_activo(request.args)`
"""
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

#la elección del panel vive en la tabla de configuración del sitio (app/store/redes.py)
from .redes import get_config, set_config

BOGOTA = ZoneInfo("America/Bogota")

# clave -> nombre para mostrar (títulos del hero o de redes, si se necesitan)
NOMBRES = {
    "halloween": "Halloween",
    "record_store_day": "Record Store Day",
    "pride": "Orgullo",
    "amor_amistad": "Amor y amistad",
    "navidad": "Navidad",
    "ano_nuevo": "Año nuevo",
}

# orden en que se dibujan (no se solapan, pero deja el set completo en un solo sitio)
TEMAS = tuple(NOMBRES)

# los tres modos que puede dejar el admin en el panel
MODOS = {"auto": "Automático (según la fecha)",
         "forzado": "Forzado (el que yo marque)",
         "apagado": "Apagado (sin adornos en el logotipo)"}

# texto de las ventanas para el panel: la lógica de verdad es tema_por_fecha()
VENTANAS = {
    "halloween": "20 de octubre – 1 de noviembre",
    "record_store_day": "3er sábado de abril, ± 3 días",
    "pride": "junio y hasta la primera marcha de julio",
    "amor_amistad": "12 – 22 de septiembre",
    "navidad": "1 – 25 de diciembre",
    "ano_nuevo": "26 de diciembre – 6 de enero",
}

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")


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


def _primer_domingo(anio, mes):
    """Primer domingo del mes: la marcha del orgullo en Bogotá cae ahí."""
    for dia in range(1, 8):
        if date(anio, mes, dia).weekday() == 6:
            return date(anio, mes, dia)


def tema_por_fecha(d):
    """La clave del tema que toca ese día (o None si es un día normal)."""
    if (d.month == 10 and d.day >= 20) or (d.month == 11 and d.day == 1):
        return "halloween"
    if abs((d - _tercer_sabado(d.year, 4)).days) <= 3:
        return "record_store_day"
    if d.month == 6 or (d.month == 7 and d <= _primer_domingo(d.year, 7)):
        return "pride"
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
    if clave in ("pride", "lgbt", "lgbtq", "lgbtiq", "orgullo", "arcoiris", "arcoíris"):
        return "pride"
    return clave if clave in TEMAS else None


def fecha_larga(d):
    """'20 de octubre de 2026', para los textos del panel."""
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def config_tema():
    """Lo que dejó el admin en el panel: (modo, clave forzada).

    modo: 'auto' | 'forzado' | 'apagado'. Si algo quedó corrupto, se cae a 'auto'.
    """
    modo = str(get_config("tema.modo") or "auto").strip().lower()
    if modo not in MODOS:
        modo = "auto"
    clave = str(get_config("tema.forzado") or "").strip().lower()
    return modo, (clave if clave in TEMAS else "")


def guardar_config_tema(modo, forzado=""):
    """Guarda la elección del panel. Devuelve None si quedó bien, o el error para avisar."""
    modo = str(modo or "").strip().lower()
    if modo not in MODOS:
        return "Modo no válido"
    if modo == "forzado":
        clave = _normalizar(forzado)
        if not clave:  # None = desconocido, "" = ninguno/auto
            return "Elige un tema para forzar"
    else:
        clave = ""
    set_config({"tema.modo": modo, "tema.forzado": clave})
    return None


def proximo_tema(ahora=None):
    """(clave, fecha, días que faltan) del próximo tema que empiece, o (None, None, None)."""
    hoy = (ahora or datetime.now(BOGOTA)).date()
    actual = tema_por_fecha(hoy)
    for salto in range(1, 400):
        d = hoy + timedelta(days=salto)
        t = tema_por_fecha(d)
        if t and t != actual:
            return t, d, salto
    return None, None, None


def tema_activo(args=None, ahora=None):
    """Tema de hoy (clave), o None si es un día normal.

    Manda la URL (?tema=), después MUSICALBOX_TEMA, después lo que dejó el admin en el
    panel, y si no hay nada de eso, la fecha.
    """
    for candidato in ((args or {}).get("tema"), os.getenv("MUSICALBOX_TEMA")):
        clave = _normalizar(candidato)
        if clave is not None:
            return clave or None
    modo, forzado = config_tema()
    if modo == "apagado":
        return None
    if modo == "forzado":
        return forzado
    return tema_por_fecha((ahora or datetime.now(BOGOTA)).date())
