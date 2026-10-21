"""Catálogo propio de colores y acabados para los mockups.

La idea es tener una base amplia sin copiar assets de VinylMockup ni de las
prensadoras: acá solo viven nombres comerciales, códigos PMS y colores RGB
aproximados. El disco se sigue dibujando con Pillow en `mockups.py`.

Los 34 colores base salen del catálogo público de Citizen Vinyl: 20 opacos,
5 translúcidos y 9 clear. Los acabados son nuestros y se pueden combinar con
cualquier color, así que el catálogo queda abierto sin replicar 426 variantes.
"""
from __future__ import annotations

from typing import Iterable


# tipo -> cómo se muestra en el panel
TIPOS = ("Opaco", "Translúcido", "Clear")

COLORES = [
    # 20 opacos
    {"slug": "opaque-black", "nombre": "Negro opaco", "nombre_en": "Opaque Black",
     "tipo": "Opaco", "pms": "Process Black C", "rgb": (18, 18, 18), "alpha": 255},
    {"slug": "opaque-blue", "nombre": "Azul opaco", "nombre_en": "Opaque Blue",
     "tipo": "Opaco", "pms": "286 C", "rgb": (6, 77, 152), "alpha": 255},
    {"slug": "opaque-brown", "nombre": "Marrón opaco", "nombre_en": "Opaque Brown",
     "tipo": "Opaco", "pms": "4625 C", "rgb": (132, 92, 34), "alpha": 255},
    {"slug": "opaque-tan", "nombre": "Arena opaco", "nombre_en": "Opaque Tan",
     "tipo": "Opaco", "pms": "729 C", "rgb": (200, 143, 48), "alpha": 255},
    {"slug": "opaque-gold", "nombre": "Dorado opaco", "nombre_en": "Opaque Gold",
     "tipo": "Opaco", "pms": "871 C", "rgb": (170, 142, 67), "alpha": 255},
    {"slug": "opaque-bright-orange", "nombre": "Naranja brillante", "nombre_en": "Opaque Bright Orange",
     "tipo": "Opaco", "pms": "Orange 021 C", "rgb": (211, 101, 21), "alpha": 255},
    {"slug": "opaque-pink", "nombre": "Rosa opaco", "nombre_en": "Opaque Pink",
     "tipo": "Opaco", "pms": "233 C", "rgb": (197, 99, 137), "alpha": 255},
    {"slug": "opaque-deep-purple", "nombre": "Púrpura profundo", "nombre_en": "Opaque Deep Purple",
     "tipo": "Opaco", "pms": "2695 C", "rgb": (38, 23, 59), "alpha": 255},
    {"slug": "opaque-red", "nombre": "Rojo opaco", "nombre_en": "Opaque Red",
     "tipo": "Opaco", "pms": "200 C", "rgb": (156, 10, 39), "alpha": 255},
    {"slug": "opaque-maroon", "nombre": "Borgoña opaco", "nombre_en": "Opaque Maroon",
     "tipo": "Opaco", "pms": "4975 C", "rgb": (97, 48, 33), "alpha": 255},
    {"slug": "opaque-turquoise", "nombre": "Turquesa opaco", "nombre_en": "Opaque Turquoise",
     "tipo": "Opaco", "pms": "7474 C", "rgb": (50, 122, 140), "alpha": 255},
    {"slug": "opaque-white", "nombre": "Blanco opaco", "nombre_en": "Opaque White",
     "tipo": "Opaco", "pms": "White", "rgb": (244, 244, 244), "alpha": 255},
    {"slug": "opaque-yellow", "nombre": "Amarillo opaco", "nombre_en": "Opaque Yellow",
     "tipo": "Opaco", "pms": "123 C", "rgb": (224, 155, 35), "alpha": 255},
    {"slug": "opaque-green", "nombre": "Verde opaco", "nombre_en": "Opaque Green",
     "tipo": "Opaco", "pms": "348 C", "rgb": (54, 135, 65), "alpha": 255},
    {"slug": "opaque-lime-green", "nombre": "Verde lima", "nombre_en": "Opaque Lime Green",
     "tipo": "Opaco", "pms": "375 C", "rgb": (141, 180, 60), "alpha": 255},
    {"slug": "opaque-jade-blue", "nombre": "Azul jade", "nombre_en": "Opaque Jade Blue",
     "tipo": "Opaco", "pms": "7474 C", "rgb": (63, 140, 140), "alpha": 255},
    {"slug": "opaque-peach", "nombre": "Durazno opaco", "nombre_en": "Opaque Peach",
     "tipo": "Opaco", "pms": "715 C", "rgb": (214, 133, 80), "alpha": 255},
    {"slug": "opaque-sky-blue", "nombre": "Azul cielo", "nombre_en": "Opaque Sky Blue",
     "tipo": "Opaco", "pms": "551 C", "rgb": (164, 198, 200), "alpha": 255},
    {"slug": "opaque-silver", "nombre": "Plateado opaco", "nombre_en": "Opaque Silver",
     "tipo": "Opaco", "pms": "877 C", "rgb": (159, 157, 154), "alpha": 255},
    {"slug": "opaque-bright-yellow", "nombre": "Amarillo brillante", "nombre_en": "Opaque Bright Yellow",
     "tipo": "Opaco", "pms": "3945 C", "rgb": (227, 190, 33), "alpha": 255},

    # 5 translúcidos
    {"slug": "translucent-orange", "nombre": "Naranja translúcido", "nombre_en": "Translucent Orange",
     "tipo": "Translúcido", "pms": "1495 C", "rgb": (212, 118, 22), "alpha": 205},
    {"slug": "translucent-natural", "nombre": "Natural translúcido", "nombre_en": "Translucent Natural",
     "tipo": "Translúcido", "pms": "Natural", "rgb": (190, 187, 179), "alpha": 185},
    {"slug": "translucent-violet", "nombre": "Violeta translúcido", "nombre_en": "Translucent Violet",
     "tipo": "Translúcido", "pms": "2577 C", "rgb": (131, 94, 113), "alpha": 195},
    {"slug": "translucent-seaglass-blue", "nombre": "Azul mar translúcido", "nombre_en": "Translucent Seaglass Blue",
     "tipo": "Translúcido", "pms": "563 C", "rgb": (128, 185, 176), "alpha": 195},
    {"slug": "translucent-emerald-green", "nombre": "Esmeralda translúcido", "nombre_en": "Translucent Emerald Green",
     "tipo": "Translúcido", "pms": "3288 C", "rgb": (20, 139, 111), "alpha": 205},

    # 9 clear
    {"slug": "clear-blue", "nombre": "Azul clear", "nombre_en": "Clear Blue",
     "tipo": "Clear", "pms": "300 C", "rgb": (22, 80, 141), "alpha": 160},
    {"slug": "clear-black", "nombre": "Negro clear", "nombre_en": "Clear Black",
     "tipo": "Clear", "pms": "Black 6 C", "rgb": (80, 74, 58), "alpha": 180},
    {"slug": "clear", "nombre": "Clear", "nombre_en": "Clear",
     "tipo": "Clear", "pms": "Clear", "rgb": (223, 223, 223), "alpha": 105},
    {"slug": "clear-green", "nombre": "Verde clear", "nombre_en": "Clear Green",
     "tipo": "Clear", "pms": "347 C", "rgb": (36, 141, 91), "alpha": 160},
    {"slug": "clear-bottle-green", "nombre": "Verde botella clear", "nombre_en": "Clear Bottle Green",
     "tipo": "Clear", "pms": "7499 C", "rgb": (168, 201, 170), "alpha": 145},
    {"slug": "clear-orange", "nombre": "Naranja clear", "nombre_en": "Clear Orange",
     "tipo": "Clear", "pms": "137 C", "rgb": (231, 165, 37), "alpha": 160},
    {"slug": "clear-pink", "nombre": "Rosa clear", "nombre_en": "Clear Pink",
     "tipo": "Clear", "pms": "706 C", "rgb": (207, 156, 175), "alpha": 150},
    {"slug": "clear-red", "nombre": "Rojo clear", "nombre_en": "Clear Red",
     "tipo": "Clear", "pms": "201 C", "rgb": (161, 32, 58), "alpha": 160},
    {"slug": "clear-yellow", "nombre": "Amarillo clear", "nombre_en": "Clear Yellow",
     "tipo": "Clear", "pms": "604 C", "rgb": (220, 199, 44), "alpha": 150},
]

COLORES_POR_SLUG = {c["slug"]: c for c in COLORES}
for _color in COLORES:
    _color["hex"] = "#%02x%02x%02x" % _color["rgb"]


EFECTOS = {
    "estandar": {
        "nombre": "Estándar",
        "slug": "estandar",
        "descripcion": "Color liso, sin efecto.",
        "acentos": [],
    },
    "splatter": {
        "nombre": "Splatter",
        "slug": "splatter",
        "descripcion": "Salpicaduras de color sobre la base.",
        "acentos": ["opaque-red", "opaque-bright-yellow", "opaque-blue"],
    },
    "swirl": {
        "nombre": "Swirl",
        "slug": "swirl",
        "descripcion": "Espirales de color mezcladas con la base.",
        "acentos": ["opaque-white", "opaque-pink"],
    },
    "marble": {
        "nombre": "Mármol",
        "slug": "marble",
        "descripcion": "Vetas onduladas, tipo mármol.",
        "acentos": ["opaque-white", "opaque-blue"],
    },
    "smoke": {
        "nombre": "Humo",
        "slug": "smoke",
        "descripcion": "Nubes suaves y translúcidas.",
        "acentos": ["opaque-white", "opaque-silver"],
    },
    "color_in_color": {
        "nombre": "Color en color",
        "slug": "color-in-color",
        "descripcion": "Manchas grandes de otro color.",
        "acentos": ["opaque-red", "opaque-bright-yellow"],
    },
    "half_and_half": {
        "nombre": "Mitad y mitad",
        "slug": "half-and-half",
        "descripcion": "Dos colores repartidos en el disco.",
        "acentos": ["opaque-white"],
    },
    "pinwheel": {
        "nombre": "Pinwheel",
        "slug": "pinwheel",
        "descripcion": "Cuñas de color que giran desde el centro.",
        "acentos": ["opaque-red", "opaque-bright-yellow"],
    },
    "picture": {
        "nombre": "Picture disc",
        "slug": "picture-disc",
        "descripcion": "La portada impresa en el disco.",
        "acentos": [],
    },
}

EFECTOS_POR_SLUG = {e["slug"]: e for e in EFECTOS.values()}


def _ajustar(rgb, factor: float):
    """Aclara (factor > 0) u oscurece (factor < 0) un color."""
    if factor >= 0:
        return tuple(int(c + (255 - c) * factor) for c in rgb)
    return tuple(int(c * (1 + factor)) for c in rgb)


def _brillo(rgb):
    luminancia = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
    if luminancia > 190:
        return _ajustar(rgb, -0.38)
    if luminancia < 70:
        return _ajustar(rgb, 0.72)
    return _ajustar(rgb, 0.46)


def _nombre(color: dict, efecto: str) -> str:
    if efecto == "picture":
        return "Picture disc"
    if efecto == "estandar":
        return color["nombre"]
    return f"{color['nombre']} · {EFECTOS[efecto]['nombre']}"


def _slug(color: dict, efecto: str) -> str:
    if efecto == "picture":
        return "picture-disc"
    if efecto == "estandar":
        return color["slug"]
    return f"{color['slug']}-{EFECTOS[efecto]['slug']}"


def _acentos_validos(acentos: Iterable[str] | None, efecto: str) -> list[str]:
    if efecto in ("estandar", "picture"):
        return []
    vistos = []
    for slug in acentos or []:
        if slug in COLORES_POR_SLUG and slug not in vistos:
            vistos.append(slug)
    if not vistos:
        vistos = list(EFECTOS[efecto]["acentos"])
    return vistos


def construir_variante(color_slug: str = "opaque-black", efecto: str = "estandar",
                       acentos: Iterable[str] | None = None) -> dict:
    """Devuelve una configuración que entiende `mockups.generar_disco`.

    El catálogo es abierto: cualquier color base se puede combinar con cualquier
    acabado. Si el color o el efecto no existen, se usa un valor seguro.
    """
    color = COLORES_POR_SLUG.get(color_slug, COLORES_POR_SLUG["opaque-black"])
    if efecto not in EFECTOS:
        efecto = "estandar"
    acentos_slugs = _acentos_validos(acentos, efecto)
    colores = [COLORES_POR_SLUG[s]["rgb"] for s in acentos_slugs]
    luminancia = 0.299 * color["rgb"][0] + 0.587 * color["rgb"][1] + 0.114 * color["rgb"][2]
    if luminancia > 185:
        label, texto_label, borde_label = (28, 24, 30, 255), (246, 242, 238), (255, 255, 255, 70)
    else:
        label, texto_label, borde_label = (246, 242, 238, 255), (30, 24, 36), (0, 0, 0, 55)
    return {
        "slug": _slug(color, efecto),
        "nombre": _nombre(color, efecto),
        "color_slug": color["slug"],
        "color_nombre": color["nombre"],
        "color_en": color["nombre_en"],
        "tipo": color["tipo"],
        "pms": color["pms"],
        "efecto_clave": efecto,
        "efecto": None if efecto == "estandar" else efecto,
        "acentos_slugs": acentos_slugs,
        "disco": (*color["rgb"], color["alpha"]),
        "brillo": (*_brillo(color["rgb"]), 255),
        "label": label,
        "texto_label": texto_label,
        "borde_label": borde_label,
        "colores": colores,
    }


def variante_por_slug(slug: str) -> dict | None:
    """Reconstruye una variante desde el nombre de archivo que usa el panel."""
    if slug == "picture-disc":
        return construir_variante("opaque-black", "picture")
    if slug in COLORES_POR_SLUG:
        return construir_variante(slug, "estandar")
    for clave, efecto in EFECTOS.items():
        if clave in ("estandar", "picture"):
            continue
        sufijo = "-" + efecto["slug"]
        if slug.endswith(sufijo):
            color_slug = slug[:-len(sufijo)]
            if color_slug in COLORES_POR_SLUG:
                return construir_variante(color_slug, clave)
    return None


__all__ = [
    "TIPOS", "COLORES", "COLORES_POR_SLUG", "EFECTOS", "EFECTOS_POR_SLUG",
    "construir_variante", "variante_por_slug",
]
