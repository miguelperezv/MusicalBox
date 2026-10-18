"""Formato de texto para mostrar.

Dos problemas de `str.title()`:
  1. rompe los apóstrofos: "She’s the Best" -> "She’S The Best";
  2. destroza lo que el artista escribió con mayúsculas: "WOR$T GIRL IN AMERICA"
     -> "Wor$T Girl In America", ".mp3" -> ".Mp3".

`titulo()` capitaliza **solo si el dato viene todo en minúsculas**. Si ya trae alguna
mayúscula, se considera intencional (es lo que escribió quien cargó el disco) y se
muestra tal cual, sin tocar nada.

    "she's the best"          -> "She's The Best"
    "She’s the Best"          -> "She’s The Best"   (ya estaba bien)
    "WOR$T GIRL IN AMERICA"   -> "WOR$T GIRL IN AMERICA"
    ".mp3"                    -> ".mp3"
    "TROYE SIVAN"             -> "TROYE SIVAN"
    "spider-man"              -> "Spider-Man"
    "iPhone"                  -> "iPhone"

Uso:
    - En plantillas: `{{ lanzamiento.n_lanzamiento|titulo }}`
    - En Python:     `from .texto import titulo`  ->  `titulo(nombre)`
"""
import re

# palabra = letras, aceptando apóstrofos internos (recto ' o tipográfico ’)
_PALABRA = re.compile(r"[^\W\d_]+(?:['\u2019][^\W\d_]+)*", re.UNICODE)

# caracteres tras los que una palabra NO se capitaliza: apóstrofo (she's) y punto (.mp3)
_SIN_CAPITALIZAR_TRAS = "'\u2019."


def titulo(valor):
    """Capitaliza solo si el dato viene todo en minúsculas; si ya trae mayúsculas, no se toca."""
    if valor is None:
        return ''
    s = str(valor)

    # el dato ya está escrito con mayúsculas: es la fuente de verdad, se muestra tal cual
    if any(c.isupper() for c in s):
        return s

    def _palabra(m):
        # .mp3, r'n'r: no capitalizamos lo que va pegado a un punto o apóstrofo
        if m.start() > 0 and s[m.start() - 1] in _SIN_CAPITALIZAR_TRAS:
            return m.group(0)
        return m.group(0)[:1].upper() + m.group(0)[1:]

    return _PALABRA.sub(_palabra, s)


def pesos(valor):
    """Precio en pesos colombianos: 150000 -> $150.000 (el mismo formato del filtro `cop`)."""
    return "$" + f"{float(valor or 0):,.0f}".replace(",", ".")


#nombre legible de cada categoría del catálogo (barra de confianza, feed de productos, correos)
TIPOS_CATEGORIA = {"VINILO": "Vinilos", "CD": "CDs", "CASSETTE": "Cassettes", "CAMISETA": "Camisetas",
                   "POSTER": "Pósters", "MUG": "Mugs", "ACCESORIO": "Accesorios"}


def categoria_legible(clave):
    """"VINILO" -> "Vinilos"; una categoría nueva se muestra tal como está escrita."""
    return TIPOS_CATEGORIA.get((clave or "").upper(), clave or "")
