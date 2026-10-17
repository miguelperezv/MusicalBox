"""Formato de texto para mostrar.

`str.title()` rompe los apóstrofos: "She’s the Best" -> "She’S The Best".
`titulo()` capitaliza igual que `.title()` (cada palabra, respetando guiones:
"spider-man" -> "Spider-Man") pero trata el apóstrofo como parte de la palabra,
así "she’s" -> "She’s", "don't" -> "Don't" y "rock'n'roll" -> "Rock'n'roll".

Uso:
    - En plantillas: `{{ lanzamiento.n_lanzamiento|titulo }}`
    - En Python:     `from .texto import titulo`  ->  `titulo(nombre)`
"""
import re

# palabra = letras, aceptando apóstrofos internos (recto ' o tipográfico ’)
_PALABRA = re.compile(r"[^\W\d_]+(?:['\u2019][^\W\d_]+)*", re.UNICODE)


def titulo(valor):
    """str.title() sin destrozar los apóstrofos."""
    if valor is None:
        return ''
    return _PALABRA.sub(lambda m: m.group(0)[:1].upper() + m.group(0)[1:].lower(), str(valor))
