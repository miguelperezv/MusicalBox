"""POC de mockups por lanzamiento (no por producto).

La idea: para cada lanzamiento se generan dos piezas a partir de la misma portada:

1. una foto limpia del vinilo (funda + disco), para la ficha o la galería;
2. una pieza de preventa con artista, álbum, precio, abono y fecha.

Los "presets" son combinaciones de disco + efecto. En este POC se dibujan con
Pillow para validar el flujo sin depender de una API externa. Si la calidad
convence, el mismo contrato se puede cambiar por Dynamic Mockups/SudoMock.

Además de los presets curados, `variantes.py` define un catálogo propio de 34
colores base y varios acabados que se combinan sin copiar assets externos.
"""
from __future__ import annotations

import io
import math
import random
import re
from datetime import date
from pathlib import Path
from typing import Iterable

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from .models import Lanzamiento, Producto, get_artist_by_release
from .texto import titulo
from .variantes import variante_por_slug


RAIZ_APP = Path(__file__).resolve().parent.parent
FUENTE_TITULO = RAIZ_APP / "static" / "fonts" / "Berlin Sans FB Demi Bold.ttf"
FUENTE_TEXTO = RAIZ_APP / "static" / "fonts" / "Smooth-Circulars.otf"
# Acentos y formato de la plantilla "pre-orden!": serif con acentos completos.
FUENTE_ITALICA = RAIZ_APP / "static" / "fonts" / "PlayfairDisplay-Italic-VF.ttf"
FUENTE_SERIF = RAIZ_APP / "static" / "fonts" / "PlayfairDisplay-VF.ttf"

# Plantilla oficial 9:16 (3126×5556) y sticker recortado de la misma referencia.
# El sticker conserva tallo y vetas para que se lea como calabaza.
# La story de pre-orden se monta sobre esta base para no reinventar la geometría.
BASE_STORY_PREORDEN = RAIZ_APP / "static" / "img" / "preventa_story_preorden.png"
STICKER_STORY = RAIZ_APP / "static" / "img" / "preventa_sticker.png"

NARANJA = (255, 106, 0)
VERDE = (183, 227, 109)
BLANCO = (248, 247, 252)

# Colores muestreados de la plantilla llena.
VERDE_PLANTILLA = (164, 210, 106)
NARANJA_PLANTILLA = (246, 88, 12)
CREMA_PLANTILLA = (226, 226, 202)
TINTA_PLANTILLA = (47, 20, 12)
SOMBRA_VERDE = (38, 62, 22)
SOMBRA_NARANJA = (82, 28, 6)


# preset -> cómo se ve el disco. El catálogo abierto vive en `variantes.py`.
PRESETS = {
    "negro": {
        "nombre": "Vinilo negro estándar",
        "disco": (17, 17, 20, 255),
        "brillo": (95, 95, 105, 255),
        "label": (242, 240, 245, 255),
        "efecto": None,
    },
    "color": {
        "nombre": "Vinilo color",
        "disco": (214, 54, 67, 255),
        "brillo": (255, 135, 120, 255),
        "label": (246, 242, 238, 255),
        "efecto": None,
    },
    "splatter": {
        "nombre": "Vinilo splatter",
        "disco": (20, 20, 24, 255),
        "brillo": (110, 110, 120, 255),
        "label": (246, 242, 238, 255),
        "efecto": "splatter",
        "colores": [(236, 70, 50), (245, 180, 60), (78, 170, 230), (240, 240, 240)],
    },
    "marble": {
        "nombre": "Vinilo marble",
        "disco": (32, 22, 62, 255),
        "brillo": (140, 110, 210, 255),
        "label": (246, 242, 238, 255),
        "efecto": "marble",
        "colores": [(119, 70, 200), (231, 121, 181), (250, 221, 160)],
    },
    "cherry": {
        "nombre": "Cherry Glaze",
        "disco": (122, 24, 47, 200),
        "brillo": (255, 205, 216, 210),
        "label": (15, 12, 14, 255),
        "texto_label": (247, 241, 235),
        "borde_label": (255, 255, 255, 28),
        "efecto": "cherry",
        "colores": [(203, 73, 104), (82, 8, 28), (246, 201, 210), (157, 33, 62)],
    },
    "clear": {
        "nombre": "Vinilo clear",
        "disco": (208, 224, 235, 175),
        "brillo": (255, 255, 255, 230),
        "label": (246, 242, 238, 255),
        "efecto": None,
    },
    "picture": {
        "nombre": "Picture disc",
        "disco": None,
        "brillo": (255, 255, 255, 255),
        "label": None,
        "efecto": "picture",
    },
}


def _fuente(ruta: Path, tamano: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(ruta), tamano)
    except OSError:
        return ImageFont.load_default()


def _mezclar(c1, c2, t: float):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1[:3], c2[:3]))


def _degradado(tamano, arriba, abajo) -> Image.Image:
    ancho, alto = tamano
    franja = Image.new("RGB", (1, alto))
    for y in range(alto):
        franja.putpixel((0, y), _mezclar(arriba, abajo, y / max(1, alto - 1)))
    return franja.resize((ancho, alto), Image.Resampling.BILINEAR).convert("RGBA")


def _glow(tamano, centro, radio, color, alpha=150) -> Image.Image:
    ancho, alto = tamano
    capa = Image.new("RGBA", tamano, (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    cx, cy = centro
    pasos = 18
    for i in range(pasos, 0, -1):
        r = radio * i / pasos
        a = int(alpha * (1 - i / (pasos + 1)) ** 1.7)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(*color[:3], a))
    return capa.filter(ImageFilter.GaussianBlur(max(2, radio // 10)))


def _recorte_circular(imagen: Image.Image, tamano: int) -> Image.Image:
    imagen = ImageOps.fit(imagen.convert("RGB"), (tamano, tamano), method=Image.Resampling.LANCZOS)
    mascara = Image.new("L", (tamano, tamano), 0)
    ImageDraw.Draw(mascara).ellipse((0, 0, tamano - 1, tamano - 1), fill=255)
    salida = Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))
    salida.paste(imagen, (0, 0), mascara)
    return salida


def _capa_recortada(capa: Image.Image, mascara: Image.Image) -> Image.Image:
    salida = Image.new("RGBA", capa.size, (0, 0, 0, 0))
    salida.paste(capa, (0, 0), mascara)
    return salida


def _splatter(tamano: int, radio: int, colores, semilla: int) -> Image.Image:
    capa = Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    rng = random.Random(semilla)
    centro = tamano / 2
    for _ in range(180):
        angulo = rng.uniform(0, math.tau)
        distancia = rng.uniform(0, radio * 0.96)
        x = centro + math.cos(angulo) * distancia
        y = centro + math.sin(angulo) * distancia
        r = rng.uniform(tamano * 0.002, tamano * 0.022)
        color = rng.choice(colores)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(*color, rng.randint(130, 235)))
    return capa.filter(ImageFilter.GaussianBlur(max(1, tamano // 900)))


def _marble(tamano: int, radio: int, colores, lineas: int = 28,
            ancho: int | None = None, blur: int | None = None,
            alpha_min: int = 55, alpha_max: int = 130,
            semilla: int = 7) -> Image.Image:
    capa = Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    rng = random.Random(semilla)
    centro = tamano / 2
    for i in range(lineas):
        color = rng.choice(colores)
        base_y = rng.uniform(-radio, radio)
        amplitud = rng.uniform(tamano * 0.02, tamano * 0.09)
        frecuencia = rng.uniform(2.0, 5.0)
        fase = rng.uniform(0, math.tau)
        puntos = []
        for x in range(-radio, radio + 1, max(2, tamano // 300)):
            y = base_y + math.sin((x / radio) * frecuencia + fase) * amplitud
            puntos.append((centro + x, centro + y))
        d.line(puntos, fill=(*color, rng.randint(alpha_min, alpha_max)),
               width=ancho or max(2, tamano // 150), joint="curve")
    return capa.filter(ImageFilter.GaussianBlur(blur or max(2, tamano // 250)))


def _swirl(tamano: int, radio: int, colores, semilla: int = 11) -> Image.Image:
    """Espirales anchas desde el centro hacia el borde."""
    capa = Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    rng = random.Random(semilla)
    centro = tamano / 2
    for i in range(22):
        color = rng.choice(colores)
        fase = rng.uniform(0, math.tau)
        vueltas = rng.uniform(1.4, 3.2)
        r0 = radio * rng.uniform(0.06, 0.20)
        r1 = radio * rng.uniform(0.82, 1.0)
        puntos = []
        for paso in range(130):
            t = paso / 129
            angulo = fase + t * vueltas * math.tau
            r = r0 + (r1 - r0) * t
            puntos.append((centro + math.cos(angulo) * r,
                           centro + math.sin(angulo) * r))
        d.line(puntos, fill=(*color, rng.randint(60, 150)),
               width=max(3, tamano // 90), joint="curve")
    return capa.filter(ImageFilter.GaussianBlur(max(2, tamano // 250)))


def _smoke(tamano: int, radio: int, colores, semilla: int = 73) -> Image.Image:
    return _marble(tamano, radio, colores, lineas=34,
                   ancho=max(6, tamano // 28), blur=max(8, tamano // 42),
                   alpha_min=24, alpha_max=82, semilla=semilla)


def _color_in_color(tamano: int, radio: int, colores, semilla: int = 19) -> Image.Image:
    return _marble(tamano, radio, colores, lineas=18,
                   ancho=max(10, tamano // 18), blur=max(5, tamano // 100),
                   alpha_min=110, alpha_max=220, semilla=semilla)


def _half_and_half(tamano: int, radio: int, colores) -> Image.Image:
    capa = Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    centro = tamano / 2
    color = colores[0] if colores else (245, 245, 245)
    d.pieslice((centro - radio, centro - radio, centro + radio, centro + radio),
               90, 270, fill=(*color, 245))
    return capa


def _pinwheel(tamano: int, radio: int, colores) -> Image.Image:
    capa = Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    centro = tamano / 2
    caja = (centro - radio, centro - radio, centro + radio, centro + radio)
    for i in range(4):
        color = colores[i % len(colores)] if colores else (245, 245, 245)
        inicio = i * 90
        d.pieslice(caja, inicio, inicio + 46, fill=(*color, 242))
    return capa


def _config_preset(preset) -> dict:
    if isinstance(preset, dict):
        return preset
    return PRESETS.get(preset, PRESETS["negro"])


def _disco_desde_imagen(imagen: Image.Image) -> Image.Image:
    """Convierte una foto cuadrada del vinilo (fondo negro, JPEG sin alfa) en un
    disco RGBA circular.

    Detecta el borde del vinilo para recortar el aire negro que sobra; si la
    detección falla, cae a un círculo centrado estándar.
    """
    img = imagen.convert("RGB")
    S = min(img.size)
    if img.size != (S, S):
        img = img.resize((S, S), Image.Resampling.LANCZOS)
    gris = img.convert("L")
    caja = gris.point(lambda v: 255 if v >= 14 else 0).getbbox()
    if caja and (caja[2] - caja[0]) > S * 0.3 and (caja[3] - caja[1]) > S * 0.3:
        cx, cy = (caja[0] + caja[2]) // 2, (caja[1] + caja[3]) // 2
        radio = min(caja[2] - caja[0], caja[3] - caja[1]) // 2
    else:
        cx = cy = S // 2
        radio = int(S * 0.485)
    mascara = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mascara).ellipse((cx - radio, cy - radio, cx + radio, cy + radio),
                                    fill=255)
    disco = img.convert("RGBA")
    disco.putalpha(mascara)
    return disco


def generar_disco(preset, tamano: int = 900, portada: Image.Image | None = None,
                  semilla: int = 11) -> Image.Image:
    """Dibuja un disco cuadrado con grooves, label y el efecto del preset."""
    cfg = _config_preset(preset)
    S = max(600, tamano * 2)
    centro = S // 2
    radio = int(S * 0.47)
    mascara = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mascara).ellipse((centro - radio, centro - radio,
                                     centro + radio, centro + radio), fill=255)

    if cfg["efecto"] == "picture" and portada is not None:
        base = _recorte_circular(portada, S)
        velo = Image.new("RGBA", (S, S), (0, 0, 0, 46))
        base = Image.alpha_composite(base, velo)
    else:
        base = Image.new("RGBA", (S, S), cfg["disco"] or (20, 20, 20, 255))

    disco = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    disco.paste(base, (0, 0), mascara)

    colores = cfg.get("colores", [])
    if cfg["efecto"] == "splatter":
        capa = _splatter(S, radio, colores, semilla)
        disco.alpha_composite(_capa_recortada(capa, mascara))
    elif cfg["efecto"] == "swirl":
        capa = _swirl(S, radio, colores, semilla)
        disco.alpha_composite(_capa_recortada(capa, mascara))
    elif cfg["efecto"] == "marble":
        capa = _marble(S, radio, colores)
        disco.alpha_composite(_capa_recortada(capa, mascara))
    elif cfg["efecto"] == "smoke":
        capa = _smoke(S, radio, colores, semilla)
        disco.alpha_composite(_capa_recortada(capa, mascara))
    elif cfg["efecto"] == "color_in_color":
        capa = _color_in_color(S, radio, colores, semilla)
        disco.alpha_composite(_capa_recortada(capa, mascara))
    elif cfg["efecto"] == "half_and_half":
        capa = _half_and_half(S, radio, colores)
        disco.alpha_composite(_capa_recortada(capa, mascara))
    elif cfg["efecto"] == "pinwheel":
        capa = _pinwheel(S, radio, colores)
        disco.alpha_composite(_capa_recortada(capa, mascara))
    elif cfg["efecto"] == "cherry":
        # dos capas: vetas anchas de glaze y vetas finas encima
        capa = _marble(S, radio, colores, lineas=42,
                       ancho=max(4, S // 24), blur=max(3, S // 80),
                       alpha_min=32, alpha_max=92, semilla=23)
        disco.alpha_composite(_capa_recortada(capa, mascara))
        capa = _marble(S, radio, colores, lineas=26,
                       ancho=max(2, S // 70), blur=max(2, S // 220),
                       alpha_min=45, alpha_max=110, semilla=41)
        disco.alpha_composite(_capa_recortada(capa, mascara))

    # grooves en una capa aparte: así no perforan la transparencia del clear.
    grooves = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dg = ImageDraw.Draw(grooves)
    for i in range(74):
        r = radio * (0.955 - i * 0.0072)
        if r < radio * 0.34:
            break
        claro = cfg["brillo"]
        alpha = 18 if i % 3 else 30
        ancho = max(1, S // 900)
        dg.ellipse((centro - r, centro - r, centro + r, centro + r),
                   outline=(*claro[:3], alpha), width=ancho)
    disco.alpha_composite(_capa_recortada(grooves, mascara))

    # brillo lateral: un arco suave que simula la luz del estudio
    brillo = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    db = ImageDraw.Draw(brillo)
    db.arc((centro - radio * 0.94, centro - radio * 0.94,
            centro + radio * 0.94, centro + radio * 0.94),
           start=196, end=330, fill=(255, 255, 255, 58), width=max(4, S // 55))
    db.arc((centro - radio * 0.78, centro - radio * 0.78,
            centro + radio * 0.78, centro + radio * 0.78),
           start=205, end=300, fill=(255, 255, 255, 34), width=max(2, S // 110))
    brillo = brillo.filter(ImageFilter.GaussianBlur(max(2, S // 220)))
    disco.alpha_composite(_capa_recortada(brillo, mascara))

    # label central. En picture disc dejamos ver la portada y usamos un label
    # pequeño de papel, como en un picture disc real.
    es_picture = cfg["efecto"] == "picture" and portada is not None
    label_r = int(radio * (0.24 if es_picture else 0.29))
    label = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dl = ImageDraw.Draw(label)
    dl.ellipse((centro - label_r, centro - label_r,
                centro + label_r, centro + label_r),
               fill=cfg["label"] or (245, 242, 238, 255))
    dl.ellipse((centro - label_r, centro - label_r,
                centro + label_r, centro + label_r),
               outline=cfg.get("borde_label", (0, 0, 0, 55)), width=max(2, S // 260))

    f_marca = _fuente(FUENTE_TEXTO, max(10, int(label_r * 0.19)))
    f_disco = _fuente(FUENTE_TITULO, max(12, int(label_r * 0.26)))
    texto_color = cfg.get("texto_label", (30, 24, 36))
    dl.text((centro, centro - label_r * 0.30), "MUSICAL BOX", font=f_marca,
            fill=(*texto_color[:3], 210), anchor="mm")
    dl.text((centro, centro + label_r * 0.02), "VINILO", font=f_disco,
            fill=(*texto_color[:3], 235), anchor="mm")
    dl.text((centro, centro + label_r * 0.34), "1LP", font=f_marca,
            fill=(*texto_color[:3], 180), anchor="mm")

    disco.alpha_composite(_capa_recortada(label, mascara))

    # agujero central y borde exterior
    d = ImageDraw.Draw(disco)
    agujero = max(3, S // 180)
    d.ellipse((centro - agujero, centro - agujero,
               centro + agujero, centro + agujero), fill=(8, 7, 10, 255))
    d.ellipse((centro - radio, centro - radio, centro + radio, centro + radio),
              outline=(255, 255, 255, 28), width=max(1, S // 600))

    return disco.resize((tamano, tamano), Image.Resampling.LANCZOS)


def _sombra(tamano, caja, radio=28, alpha=150) -> Image.Image:
    capa = Image.new("RGBA", tamano, (0, 0, 0, 0))
    ImageDraw.Draw(capa).rounded_rectangle(caja, radius=radio, fill=(0, 0, 0, alpha))
    return capa.filter(ImageFilter.GaussianBlur(max(6, radio)))


def _portada_cuadrada(portada: Image.Image, tamano: int) -> Image.Image:
    return ImageOps.fit(portada.convert("RGB"), (tamano, tamano), method=Image.Resampling.LANCZOS)


def componer_mockup(portada: Image.Image, preset="negro", tamano: int = 1400,
                    fondo: str = "estudio",
                    disco: Image.Image | None = None,
                    lps: int = 1) -> Image.Image:
    """Funda + disco. `fondo="transparente"` devuelve solo la composición con sombras.

    Con `disco` (RGBA) se usa en vez del vinilo procedural: para la imagen de
    VinylMockup, la prepara `_disco_desde_imagen` con un recorte circular.
    `lps` cambia el sticker (1LP/2LP).
    """
    S = tamano
    if fondo == "transparente":
        lienzo = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    elif fondo == "claro":
        lienzo = _degradado((S, S), (250, 247, 241), (235, 230, 222))
        lienzo.alpha_composite(_glow((S, S), (int(S * 0.55), int(S * 0.38)),
                                     int(S * 0.58), (255, 253, 247), 110))
    else:
        lienzo = _degradado((S, S), (10, 8, 17), (27, 14, 42))
        lienzo.alpha_composite(_glow((S, S), (int(S * 0.62), int(S * 0.48)),
                                     int(S * 0.52), (105, 55, 170), 130))
        lienzo.alpha_composite(_glow((S, S), (int(S * 0.15), int(S * 0.15)),
                                     int(S * 0.45), (30, 80, 130), 55))

    # sombra de piso, solo en el estudio oscuro; en claro ya hay sombras suaves
    if fondo != "claro":
        piso = _sombra((S, S), (int(S * 0.12), int(S * 0.77),
                                int(S * 0.92), int(S * 0.88)), radio=int(S * 0.04),
                       alpha=110)
        lienzo.alpha_composite(piso)

    # disco detrás, a la derecha
    disco_t = int(S * 0.62)
    if disco is None:
        disco_img = generar_disco(preset, disco_t, portada)
    else:
        disco_img = _disco_desde_imagen(disco).resize((disco_t, disco_t),
                                                      Image.Resampling.LANCZOS)
    disco_x = int(S * 0.64) - disco_t // 2
    disco_y = int(S * 0.50) - disco_t // 2
    # sombra del disco
    claro = fondo == "claro"
    sombra_dx = int(S * (0.012 if claro else 0.02))
    sombra_dy = int(S * (0.02 if claro else 0.035))
    alpha_disco = 32 if claro else 170
    sombra_d = _sombra((S, S), (disco_x + sombra_dx, disco_y + sombra_dy,
                                disco_x + disco_t + sombra_dx, disco_y + disco_t + sombra_dy),
                       radio=int(S * (0.02 if claro else 0.03)), alpha=alpha_disco)
    lienzo.alpha_composite(sombra_d)
    lienzo.alpha_composite(disco_img, (disco_x, disco_y))

    # funda encima, a la izquierda
    funda_t = int(S * 0.43)
    funda_x = int(S * 0.10)
    funda_y = int(S * 0.25)
    alpha_funda = 40 if claro else 185
    sombra_fx = int(S * (0.01 if claro else 0.018))
    sombra_fy = int(S * (0.015 if claro else 0.025))
    sombra_f = _sombra((S, S), (funda_x + sombra_fx, funda_y + sombra_fy,
                                funda_x + funda_t + sombra_fx, funda_y + funda_t + sombra_fy),
                       radio=int(S * (0.008 if claro else 0.012)), alpha=alpha_funda)
    lienzo.alpha_composite(sombra_f)
    portada_img = _portada_cuadrada(portada, funda_t)
    lienzo.paste(portada_img, (funda_x, funda_y))
    d = ImageDraw.Draw(lienzo)
    borde_funda = (0, 0, 0, 28) if fondo == "claro" else (255, 255, 255, 30)
    d.rectangle((funda_x, funda_y, funda_x + funda_t - 1, funda_y + funda_t - 1),
                outline=borde_funda, width=max(1, S // 700))
    # brillo sutil en el borde superior de la funda
    brillo = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(brillo).polygon(
        [(funda_x, funda_y), (funda_x + funda_t, funda_y),
         (funda_x + funda_t, funda_y + int(funda_t * 0.18)),
         (funda_x, funda_y + int(funda_t * 0.32))],
        fill=(255, 255, 255, 18))
    brillo = brillo.filter(ImageFilter.GaussianBlur(max(4, S // 180)))
    lienzo.alpha_composite(brillo)

    # sticker 1LP
    sticker_r = max(24, int(S * 0.045))
    sx = funda_x + funda_t - int(sticker_r * 0.65)
    sy = funda_y + funda_t - int(sticker_r * 0.65)
    ds = ImageDraw.Draw(lienzo)
    ds.ellipse((sx - sticker_r, sy - sticker_r, sx + sticker_r, sy + sticker_r),
               fill=(*NARANJA, 255), outline=(255, 255, 255, 60), width=max(1, S // 500))
    ds.text((sx, sy), f"{max(1, int(lps))}LP",
            font=_fuente(FUENTE_TITULO, max(12, int(sticker_r * 0.8))),
            fill=(20, 12, 18, 255), anchor="mm")

    return lienzo


def _wrap(draw: ImageDraw.ImageDraw, texto: str, fuente, ancho_max: int) -> list[str]:
    palabras = (texto or "").split()
    lineas, actual = [], ""
    for palabra in palabras:
        prueba = (actual + " " + palabra).strip()
        if draw.textbbox((0, 0), prueba, font=fuente)[2] <= ancho_max:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas or [""]


def _texto_centrado(draw, y, texto, fuente, fill, ancho=980, interlinea=1.08):
    lineas = _wrap(draw, texto, fuente, ancho)
    alto_linea = draw.textbbox((0, 0), "Ag", font=fuente)[3] * interlinea
    for i, linea in enumerate(lineas):
        draw.text((draw._image.width // 2, y + i * alto_linea), linea,
                  font=fuente, fill=fill, anchor="mt")
    return y + len(lineas) * alto_linea


def _fuente_ajustada(draw, texto, ruta, tamano_max, ancho, max_lineas=1):
    """Baja el tamaño hasta que el texto entre en el ancho y las líneas pedidas."""
    tamano = tamano_max
    while tamano > 12:
        fuente = _fuente(ruta, tamano)
        if len(_wrap(draw, texto, fuente, ancho)) <= max_lineas:
            return fuente
        tamano -= 2
    return _fuente(ruta, 12)


def _fecha_larga(fecha: date | None) -> str:
    if not fecha:
        return "Por confirmar"
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
             "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    return f"{meses[fecha.month - 1].capitalize()} {fecha.year}"


def _pesos(valor) -> str:
    if valor is None:
        return ""
    return "$" + f"{int(valor):,}".replace(",", ".")


def datos_preventa(lanzamiento: Lanzamiento, productos: Iterable[Producto] | None = None,
                   precio=None, abono=None, formato=None, eta=None,
                   lps=None, envio=None, envio_incluido=None,
                   preorden=None) -> dict:
    """Datos que alimentan la pieza. Los overrides existen para el POC.

    `lps` define el sticker (1LP/2LP), `envio` el costo de envío,
    `envio_incluido` si ese costo se suma al precio que se muestra y
    `preorden` fuerza el título (si es None se detecta del lanzamiento).
    """
    productos = list(productos or [])
    artista = get_artist_by_release(lanzamiento.id)
    # El POC es por lanzamiento: solo tomamos precio/abono de un vinilo.
    # Si el lanzamiento únicamente tiene merch, no inventamos un precio.
    producto_vinilo = next((p for p in productos
                            if (p.k_categoria or "").upper() == "VINILO"
                            and getattr(p, "tipo", "SIMPLE") == "SIMPLE"), None)
    if producto_vinilo is None:
        producto_vinilo = next((p for p in productos
                                if "vinilo" in (p.n_producto or "").lower()
                                and getattr(p, "tipo", "SIMPLE") == "SIMPLE"), None)

    if precio is None and producto_vinilo is not None:
        precio = producto_vinilo.p_producto
    if abono is None and producto_vinilo is not None and producto_vinilo.porcentaje_abono:
        abono = float(precio or 0) * float(producto_vinilo.porcentaje_abono) / 100
    if formato is None:
        formato = (producto_vinilo.n_producto if producto_vinilo else None) or PRESETS["negro"]["nombre"]
    if eta is None:
        eta = _fecha_larga(lanzamiento.f_lanzamiento)
    if lps is None:
        nombre_vinilo = (producto_vinilo.n_producto if producto_vinilo else "") or ""
        lps = 2 if re.search(r"\b2\s*(lp|vinilos?)\b|\bdoble\b", nombre_vinilo, re.I) else 1
    if envio_incluido is None:
        envio_incluido = True
    if preorden is None:
        preorden = bool(lanzamiento.preorden
                        or (producto_vinilo and producto_vinilo.preorden))
    precio_base = float(precio) if precio is not None else None
    precio_final = precio_base
    if precio_base is not None and envio and envio_incluido:
        precio_final = precio_base + float(envio)

    return {
        "artista": titulo(artista.n_artista) if artista else "Artista por confirmar",
        "album": titulo(lanzamiento.n_lanzamiento),
        "formato": formato,
        "precio": precio_final,
        "precio_base": precio_base,
        "envio": float(envio) if envio else None,
        "envio_incluido": bool(envio_incluido),
        "lps": int(lps or 1),
        "abono": abono,
        "eta": eta,
        "preorden": bool(preorden),
    }


def generar_pieza_preventa(portada: Image.Image, datos: dict, preset="negro",
                           tamano=(1080, 1350), disco: Image.Image | None = None,
                           lps: int = 1) -> Image.Image:
    W, H = tamano
    lienzo = _degradado((W, H), (44, 7, 70), (10, 4, 18))
    lienzo.alpha_composite(_glow((W, H), (int(W * 0.78), int(H * 0.30)),
                                 int(W * 0.62), (112, 36, 180), 155))
    lienzo.alpha_composite(_glow((W, H), (int(W * 0.10), int(H * 0.78)),
                                 int(W * 0.48), (28, 74, 140), 75))

    # rayos diagonales sutiles
    rayos = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(rayos)
    for x, alpha, ancho in [(-90, 60, 3), (70, 32, 2), (W - 180, 48, 2), (W - 40, 24, 1)]:
        dr.line([(x, 0), (x + 220, H)], fill=(147, 198, 255, alpha), width=ancho)
    rayos = rayos.filter(ImageFilter.GaussianBlur(1.2))
    lienzo.alpha_composite(rayos)

    d = ImageDraw.Draw(lienzo)
    f_marca = _fuente(FUENTE_TEXTO, 23)
    f_pre = _fuente(FUENTE_TITULO, 82)
    f_artista = _fuente_ajustada(d, datos["artista"], FUENTE_TITULO, 41, 930, 1)
    f_album = _fuente_ajustada(d, datos["album"], FUENTE_TITULO, 56, 940, 2)
    f_formato = _fuente_ajustada(d, datos["formato"], FUENTE_TITULO, 27, 900, 1)
    f_precio = _fuente(FUENTE_TITULO, 68)
    f_abono = _fuente(FUENTE_TITULO, 36)
    f_chico = _fuente(FUENTE_TITULO, 22)
    f_cta = _fuente(FUENTE_TITULO, 31)
    f_footer = _fuente(FUENTE_TITULO, 19)

    d.text((52, 38), "MUSICAL BOX", font=f_marca, fill=(*BLANCO, 190), anchor="lt")
    titulo_pieza = "PRE-ORDER" if datos.get("preorden") else "A LA VENTA"
    d.text((48, 74), titulo_pieza, font=f_pre, fill=(*NARANJA, 255), anchor="lt")

    # mockup transparente: recortamos el aire sobrante para que la pieza
    # aproveche el ancho de la tarjeta.
    mock = componer_mockup(portada, preset=preset, tamano=1000, fondo="transparente",
                           disco=disco, lps=lps)
    # ignoramos la sombra muy difusa al recortar: el contenido real es funda + disco
    alfa = mock.getchannel("A").point(lambda a: 255 if a >= 36 else 0)
    bbox = alfa.getbbox()
    if bbox:
        margen = 14
        bbox = (max(0, bbox[0] - margen), max(0, bbox[1] - margen),
                min(mock.width, bbox[2] + margen), min(mock.height, bbox[3] + margen))
        mock = mock.crop(bbox)
    max_w, max_h = 980, 720
    escala = min(max_w / mock.width, max_h / mock.height)
    if abs(escala - 1) > 0.01:
        mock = mock.resize((max(1, int(mock.width * escala)), max(1, int(mock.height * escala))),
                           Image.Resampling.LANCZOS)
    lienzo.alpha_composite(mock, ((W - mock.width) // 2, 165))

    y = _texto_centrado(d, 900, datos["artista"], f_artista, (*VERDE, 255), ancho=930) + 8
    y = _texto_centrado(d, y, datos["album"], f_album, (*NARANJA, 255), ancho=940) + 8
    y = _texto_centrado(d, y, datos["formato"], f_formato, (*BLANCO, 210), ancho=900) + 18
    d.line((170, y, W - 170, y), fill=(*BLANCO, 45), width=1)
    y += 18

    if datos["precio"] is not None:
        d.text((58, y), "LLÉVALO POR:", font=f_chico, fill=(*BLANCO, 190), anchor="lt")
        d.text((58, y + 26), _pesos(datos["precio"]), font=f_precio, fill=(*BLANCO, 255), anchor="lt")
        if datos["abono"]:
            d.text((W - 58, y + 4), "Reserva con:", font=f_chico, fill=(*BLANCO, 190), anchor="rt")
            d.text((W - 58, y + 32), _pesos(datos["abono"]), font=f_abono,
                   fill=(*VERDE, 255), anchor="rt")
            d.text((W - 58, y + 82), "Llegada est. " + datos["eta"], font=f_chico,
                   fill=(*BLANCO, 175), anchor="rt")
        else:
            d.text((W - 58, y + 26), "Llegada est. " + datos["eta"], font=f_chico,
                   fill=(*BLANCO, 175), anchor="rt")
        y += 126
    else:
        y = _texto_centrado(d, y + 8, "Precio y reserva por confirmar", f_chico,
                            (*BLANCO, 190), ancho=900) + 12

    _texto_centrado(d, y, "¡ORDENA EL TUYO AHORA!", f_cta, (*VERDE, 255), ancho=900)
    pie = "musicalbox.co · preventa oficial" if datos.get("preorden") else "musicalbox.co"
    d.text((W // 2, H - 30), pie, font=f_footer, fill=(*BLANCO, 120), anchor="mt")
    return lienzo.convert("RGB")


def _rayos_preorden(W: int, H: int) -> Image.Image:
    """Rayos blancos con halo azul, como en la plantilla de pre-orden."""
    trazo_a = [(0.88, -0.03), (0.83, 0.09), (0.87, 0.085), (0.78, 0.22),
               (0.84, 0.22), (0.74, 0.34), (0.79, 0.35), (0.70, 0.44)]
    trazo_b = [(0.02, 0.55), (0.09, 0.60), (0.07, 0.63), (0.15, 0.68),
               (0.13, 0.72), (0.21, 0.77), (0.19, 0.80), (0.27, 0.86)]
    rama_b = [(0.15, 0.68), (0.195, 0.615), (0.26, 0.645)]
    rama_a = [(0.78, 0.22), (0.835, 0.16), (0.885, 0.195)]

    def a_puntos(trazo):
        return [(int(x * W), int(y * H)) for x, y in trazo]

    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dh = ImageDraw.Draw(halo)
    for trazo in (trazo_a, trazo_b, rama_a, rama_b):
        dh.line(a_puntos(trazo), fill=(70, 130, 250, 190),
                width=max(12, W // 58), joint="curve")
    halo = halo.filter(ImageFilter.GaussianBlur(18))
    halo2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dh2 = ImageDraw.Draw(halo2)
    for trazo in (trazo_a, trazo_b):
        dh2.line(a_puntos(trazo), fill=(120, 175, 255, 190),
                 width=max(6, W // 150), joint="curve")
    halo2 = halo2.filter(ImageFilter.GaussianBlur(5))
    halo = Image.alpha_composite(halo, halo2)

    núcleo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dn = ImageDraw.Draw(núcleo)
    for trazo in (rama_a, rama_b):
        dn.line(a_puntos(trazo), fill=(190, 220, 255, 230),
                width=max(3, W // 320), joint="curve")
    for trazo in (trazo_a, trazo_b):
        dn.line(a_puntos(trazo), fill=(248, 251, 255, 255),
                width=max(4, W // 200), joint="curve")
    núcleo = núcleo.filter(ImageFilter.GaussianBlur(1.2))
    return Image.alpha_composite(halo, núcleo)


def _estrella_5(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float,
                color, width: int = 2) -> None:
    """Estrella de cinco puntas hueca (ornamento de la plantilla)."""
    puntos = []
    for i in range(10):
        rad = r if i % 2 == 0 else r * 0.42
        ang = -math.pi / 2 + i * math.pi / 5
        puntos.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    d.line(puntos + [puntos[0]], fill=color, width=max(1, width), joint="curve")


def _fantasma(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float,
              color, width: int = 3) -> None:
    """Silueta hueca de fantasma para la pastilla de precio."""
    d.arc((cx - r, cy - r, cx + r, cy + r), 180, 360, fill=color, width=width)
    d.line((cx - r, cy, cx - r, cy + r * 0.72), fill=color, width=width)
    d.line((cx + r, cy, cx + r, cy + r * 0.72), fill=color, width=width)
    onda = [(cx - r, cy + r * 0.72), (cx - r * 0.5, cy + r * 0.30),
            (cx, cy + r * 0.72), (cx + r * 0.5, cy + r * 0.30),
            (cx + r, cy + r * 0.72)]
    d.line(onda, fill=color, width=width, joint="curve")
    d.ellipse((cx - r * 0.48, cy - r * 0.42, cx - r * 0.18, cy - r * 0.06), fill=color)
    d.ellipse((cx + r * 0.18, cy - r * 0.42, cx + r * 0.48, cy - r * 0.06), fill=color)


def _nota(d: ImageDraw.ImageDraw, x: float, y: float, s: float, color) -> None:
    """Nota musical simple para la 'o' vinilo del título."""
    d.ellipse((x, y + s * 0.5, x + s * 0.75, y + s), fill=color)
    d.line((x + s * 0.66, y + s * 0.6, x + s * 0.66, y), fill=color,
           width=max(2, int(s * 0.14)))
    d.line((x + s * 0.66, y, x + s * 1.15, y + s * 0.18), fill=color,
           width=max(2, int(s * 0.14)))


def _texto_inclinado(lienzo: Image.Image, centro: tuple[int, int], texto: str,
                     fuente, fill, angulo: float = 8.0) -> None:
    """Texto con inclinación ligera (estilo tipografía de la plantilla)."""
    caja = ImageDraw.Draw(Image.new("RGB", (8, 8))).textbbox((0, 0), texto, font=fuente)
    pad = 40
    capa = Image.new("RGBA", (caja[2] - caja[0] + pad * 2, caja[3] - caja[1] + pad * 2),
                     (0, 0, 0, 0))
    ImageDraw.Draw(capa).text((pad - caja[0], pad - caja[1]), texto, font=fuente, fill=fill)
    capa = capa.rotate(-angulo, resample=Image.Resampling.BICUBIC, expand=True)
    lienzo.alpha_composite(capa, (int(centro[0] - capa.width / 2),
                                  int(centro[1] - capa.height / 2)))


def _texto_escalado(lienzo: Image.Image, x: int, base: int, texto: str, fuente,
                    fill, factor_x: float) -> int:
    """Dibuja texto comprimido en horizontal sin mover la línea base.

    La plantilla usa un título más alto y angosto que la Berlin Sans: se
    renderiza al tamaño alto y se comprime para conservar el ancho. Devuelve
    el ancho final dibujado.
    """
    d = ImageDraw.Draw(lienzo)
    caja = d.textbbox((0, 0), texto, font=fuente, anchor="ls")
    ancho, alto = caja[2] - caja[0], caja[3] - caja[1]
    if ancho <= 0 or alto <= 0:
        return 0
    capa = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    ImageDraw.Draw(capa).text((-caja[0], -caja[1]), texto, font=fuente,
                              fill=fill, anchor="ls")
    nuevo_ancho = max(1, int(round(ancho * factor_x)))
    if nuevo_ancho != ancho:
        capa = capa.resize((nuevo_ancho, alto), Image.Resampling.LANCZOS)
    lienzo.alpha_composite(capa, (int(x), int(base + caja[1])))
    return nuevo_ancho


def _texto_arriba(d, x, arriba, texto, fuente, fill, anchor="ma",
                  sombra=None, stroke=0, stroke_fill=None):
    """Dibuja el texto con su parte visible superior exactamente en `arriba`."""
    caja = d.textbbox((0, 0), texto, font=fuente, anchor=anchor)
    y = arriba - caja[1]
    if sombra:
        dx, dy, color = sombra
        d.text((x + dx, y + dy), texto, font=fuente, fill=color, anchor=anchor)
    d.text((x, y), texto, font=fuente, fill=fill, anchor=anchor,
           stroke_width=stroke, stroke_fill=stroke_fill or fill)
    return y


def _story_dibujada(portada: Image.Image, datos: dict, preset="negro",
                    tamano=(1080, 1920),
                    disco: Image.Image | None = None) -> Image.Image:
    """Fallback dibujado a mano (se usa para "a la venta!" o sin plantilla).

    Mantiene la estética de la tienda: título con vinilo en la "o", rayos,
    portada con contorno naranja y el disco metido detrás, separador con
    diamante, estrellas con el formato, pastilla de precio con fantasma y
    banda naranja de reserva. `preset` queda por compatibilidad.
    """
    W, H = tamano
    sc = W / 1080.0

    def s(v):
        return int(round(v * sc))

    ARCO = (229, 74, 10)
    OCRE = (150, 55, 8)
    PARTILLA = (66, 24, 104)
    NEGRO_BAN = (52, 20, 40)

    # ---- fondo violeta con luz arriba a la izquierda y viñeta abajo
    lienzo = _degradado((W, H), (111, 50, 201), (39, 14, 78))
    lienzo.alpha_composite(_glow((W, H), (s(150), s(60)), s(780), (150, 100, 240), 80))
    lienzo.alpha_composite(_glow((W, H), (s(1000), s(1900)), s(520), (24, 8, 48), 80))
    lienzo.alpha_composite(_rayos_preorden(W, H))
    d = ImageDraw.Draw(lienzo)

    # ---- título plano, alto y angosto como la plantilla (sin sombra)
    nombre_titulo = "pre-orden!" if datos.get("preorden") else "a la venta!"
    tam_t = s(255)
    f_t = _fuente(FUENTE_TITULO, tam_t)
    disponible = W - s(56)
    base = s(312)
    if datos.get("preorden"):
        izq, der = "pre-", "rden!"
        hueco_natural = int(tam_t * 0.76)
        natural = (d.textlength(izq, font=f_t) + hueco_natural
                   + d.textlength(der, font=f_t))
        factor = min(1.0, disponible / natural) if natural else 1.0
        hueco = int(hueco_natural * factor)
        w_izq = int(round(d.textlength(izq, font=f_t) * factor))
        w_der = int(round(d.textlength(der, font=f_t) * factor))
        x0 = int((W - (w_izq + hueco + w_der)) / 2)
        _texto_escalado(lienzo, x0, base, izq, f_t, (*NARANJA, 255), factor)
        _texto_escalado(lienzo, x0 + w_izq + hueco, base, der, f_t,
                        (*NARANJA, 255), factor)
        cxo = x0 + w_izq + hueco // 2
        cyt = base - int(tam_t * 0.26)
        r_o = int(tam_t * 0.31)
        d.ellipse((cxo - r_o, cyt - r_o, cxo + r_o, cyt + r_o),
                  fill=(*NARANJA, 255))
        for fr in (0.74, 0.52, 0.30):
            rr = int(r_o * fr)
            d.ellipse((cxo - rr, cyt - rr, cxo + rr, cyt + rr),
                      outline=OCRE, width=max(1, s(2)))
        ch = int(r_o * 0.14)
        d.ellipse((cxo - ch, cyt - ch, cxo + ch, cyt + ch), fill=OCRE)
        s_nota = int(r_o * 0.68)
        _nota(d, cxo - int(s_nota * 0.55), cyt - int(s_nota * 0.52), s_nota, VERDE)
    else:
        natural = d.textlength(nombre_titulo, font=f_t)
        factor = min(1.0, disponible / natural) if natural else 1.0
        ancho_final = int(round(natural * factor))
        _texto_escalado(lienzo, int((W - ancho_final) / 2), base, nombre_titulo,
                        f_t, (*NARANJA, 255), factor)

    # ---- portada y disco: el vinilo es 1.3× la funda y va corrido abajo,
    # asomando solo a la derecha del borde de la funda (como la plantilla).
    cover_x, cover_y, C = s(114), s(348), s(654)
    cover_r, cover_b = cover_x + C, cover_y + C
    disco_t = int(C * 1.30)
    disco_cx = cover_r + s(300) - disco_t // 2
    disco_cy = cover_y + C // 2 + int(C * 0.175)
    disco_x, disco_y = disco_cx - disco_t // 2, disco_cy - disco_t // 2
    if disco is not None:
        imagen_disco = _disco_desde_imagen(disco).resize(
            (disco_t, disco_t), Image.Resampling.LANCZOS)
    else:
        imagen_disco = generar_disco(preset, disco_t, portada)
    recorte = max(0, cover_r - disco_x)
    visible = imagen_disco.crop((recorte, 0, disco_t, disco_t))
    lienzo.alpha_composite(visible, (max(disco_x, cover_r), disco_y))
    lienzo.paste(_portada_cuadrada(portada, C), (cover_x, cover_y))

    # ---- contorno: tres líneas de la funda + elipse vertical a la derecha
    # (la elipse nace en la esquina superior derecha y muere un poco más
    # abajo que la base, dejando el escalón de la plantilla).
    stroke = max(3, s(5))
    notch = s(26)
    d.line((cover_x, cover_y, cover_r, cover_y), fill=ARCO, width=stroke)
    d.line((cover_x, cover_y, cover_x, cover_b), fill=ARCO, width=stroke)
    d.line((cover_x, cover_b, cover_r, cover_b), fill=ARCO, width=stroke)
    rx = s(212)
    ry = C // 2 + notch // 2
    ecy = cover_y + C // 2 + notch // 2
    d.arc((cover_r - rx, ecy - ry, cover_r + rx, ecy + ry),
          -90, 90, fill=ARCO, width=stroke)
    d.line((cover_r, cover_b, cover_r, cover_b + notch), fill=ARCO, width=stroke)

    # ---- sticker de discos (1lp / 2lp), tipo calabaza
    lps = max(1, int(datos.get("lps", 1)))
    st_r = int(C * 0.128)
    st_cx, st_cy = cover_r - int(C * 0.034), cover_y + int(C * 0.60)
    d.ellipse((st_cx - st_r, st_cy - st_r, st_cx + st_r, st_cy + st_r),
              fill=(*NARANJA, 255), outline=(60, 22, 10), width=max(2, s(3)))
    for dx in (-0.82, -0.52, 0.52, 0.82):
        puntos = []
        for i in range(17):
            ty = -0.94 + 1.88 * i / 16
            y = st_cy + int(st_r * ty)
            bulge = (1 - abs(ty)) * st_r * 0.05
            x = st_cx + int(st_r * dx) + int((1 if dx > 0 else -1) * bulge)
            puntos.append((x, y))
        d.line(puntos, fill=OCRE, width=max(2, s(2)), joint="curve")
    d.text((st_cx, st_cy), f"{lps}lp", font=_fuente(FUENTE_TITULO, int(st_r * 0.66)),
           fill=(60, 22, 10, 255), anchor="mm")

    # ---- artista / álbum, anclados desde arriba del separador
    separator_y = s(1214)
    f_album = _fuente_ajustada(d, datos["album"], FUENTE_TITULO, s(64), s(940), 2)
    lineas_album = _wrap(d, datos["album"], f_album, s(940))
    h_album = len(lineas_album) * (f_album.size + s(10))
    f_artista = _fuente_ajustada(d, datos["artista"], FUENTE_TITULO, s(54), s(940), 1)
    y_artista = separator_y - s(38) - h_album - s(18) - f_artista.size
    d.text((W // 2, y_artista), datos["artista"], font=f_artista,
           fill=(*VERDE, 255), anchor="ma")
    y = separator_y - s(38) - h_album
    for linea in lineas_album:
        d.text((W // 2, y), linea, font=f_album, fill=(*NARANJA, 255), anchor="ma")
        y += f_album.size + s(10)

    # ---- separador con diamante central
    d.line((s(110), separator_y, s(970), separator_y), fill=ARCO, width=max(2, s(3)))
    half = s(16)
    d.polygon([(W // 2, separator_y - half), (W // 2 + half, separator_y),
               (W // 2, separator_y + half), (W // 2 - half, separator_y)],
              fill=ARCO)

    # ---- estrellas + formato (horizontal, como la plantilla)
    y_fmt = separator_y + s(66)
    for i in range(3):
        _estrella_5(d, s(92) + i * s(48), y_fmt, s(16), ARCO, width=max(2, s(2)))
        _estrella_5(d, s(988) - i * s(48), y_fmt, s(16), ARCO, width=max(2, s(2)))
    d.text((W // 2, y_fmt), datos["formato"],
           font=_fuente_ajustada(d, datos["formato"], FUENTE_SERIF, s(44), s(660), 1),
           fill=(*VERDE, 255), anchor="mm")

    # ---- "LLÉVALO POR:" fino e inclinado
    _texto_inclinado(lienzo, (s(250), s(1482)), "LLÉVALO POR:",
                     _fuente(FUENTE_ITALICA, s(46)), (*VERDE, 255), angulo=-6)
    d = ImageDraw.Draw(lienzo)

    # ---- pastilla de precio con fantasma
    pill_x0, pill_x1 = s(165), s(925)
    pill_y0, pill_y1 = s(1540), s(1740)
    d.rounded_rectangle((pill_x0, pill_y0, pill_x1, pill_y1),
                        radius=s(52), fill=(*PARTILLA, 175),
                        outline=ARCO, width=max(3, s(5)))
    _fantasma(d, s(214), (pill_y0 + pill_y1) // 2, s(38), ARCO, width=max(2, s(3)))
    f_precio = _fuente(FUENTE_TITULO, s(100))
    centro_y = (pill_y0 + pill_y1) // 2
    if datos["precio"] is not None:
        d.text((s(500), centro_y), _pesos(datos["precio"]),
               font=f_precio, fill=(*VERDE, 255), anchor="mm")
    else:
        f_desc = _fuente(FUENTE_TITULO, s(40))
        d.text((s(500), centro_y - s(22)), "Precio y reserva",
               font=f_desc, fill=(*VERDE, 255), anchor="mm")
        d.text((s(500), centro_y + s(26)), "por confirmar",
               font=f_desc, fill=(*VERDE, 255), anchor="mm")

    # envío: fino inclinado, con tilde si está incluido en el precio
    f_envio = _fuente(FUENTE_ITALICA, s(36))
    incluye = bool(datos.get("envio_incluido", True))
    ancho_envio = d.textlength("envío", font=f_envio)
    borde_envio = s(858)
    _texto_inclinado(lienzo, (borde_envio - int(ancho_envio / 2), pill_y0 + s(62)),
                     "envío", f_envio, (*VERDE, 255), angulo=-6)
    d = ImageDraw.Draw(lienzo)
    if incluye:
        x_tilde, y_tilde = borde_envio + s(10), pill_y0 + s(58)
        d.line((x_tilde, y_tilde, x_tilde + s(7), y_tilde + s(7),
                x_tilde + s(20), y_tilde - s(12)),
               fill=(*VERDE, 255), width=max(2, s(3)), joint="curve")
    texto_envio = "incluido" if incluye else "aparte"
    ancho_envio2 = d.textlength(texto_envio, font=f_envio)
    _texto_inclinado(lienzo, (s(884) - int(ancho_envio2 / 2), pill_y0 + s(106)),
                     texto_envio, f_envio, (*VERDE, 255), angulo=-6)
    d = ImageDraw.Draw(lienzo)

    # ---- banda naranja de reserva
    band_y0, band_y1 = pill_y1, s(1802)
    d.rounded_rectangle((pill_x0, band_y0, pill_x1, band_y1), radius=s(30), fill=ARCO)
    d.rectangle((pill_x0, band_y0, pill_x1, band_y0 + s(24)), fill=ARCO)
    reserva = f"Reserva con: {_pesos(datos['abono'])}" if datos["abono"] else "Reserva:"
    llegada = f"Llegada est: {datos['eta'] or 'por confirmar'}"
    x_izq, x_der = s(190), s(890)
    tam_ban = s(26)
    f_ban = _fuente(FUENTE_TITULO, tam_ban)
    while (d.textlength(reserva, font=f_ban) + d.textlength(llegada, font=f_ban)
           > (x_der - x_izq - s(56)) and tam_ban > s(15)):
        tam_ban -= max(1, s(1))
        f_ban = _fuente(FUENTE_TITULO, tam_ban)
    ancho_izq = d.textlength(reserva, font=f_ban)
    ancho_der = d.textlength(llegada, font=f_ban)
    y_ban = (band_y0 + band_y1) // 2
    d.text((x_izq, y_ban), reserva, font=f_ban, fill=(*NEGRO_BAN, 255), anchor="lm")
    star_x = int((x_izq + ancho_izq + (x_der - ancho_der)) / 2)
    _estrella_5(d, star_x, y_ban, s(11), (*NEGRO_BAN, 255), width=max(1, s(2)))
    d.text((x_der, y_ban), llegada, font=f_ban, fill=(*NEGRO_BAN, 255), anchor="rm")

    # ---- CTA fino inclinado, alineado a la derecha como la plantilla
    f_cta = _fuente(FUENTE_ITALICA, s(52))
    texto_cta = "¡ORDENA EL TUYO AHORA!"
    ancho_cta = d.textlength(texto_cta, font=f_cta)
    _texto_inclinado(lienzo, (int(s(975) - ancho_cta / 2), s(1844)), texto_cta,
                     f_cta, (*VERDE, 255), angulo=-6)
    return lienzo.convert("RGB")


def _story_plantilla(portada: Image.Image, datos: dict, preset="negro",
                     tamano=(1080, 1920),
                     disco: Image.Image | None = None) -> Image.Image:
    """Monta la story sobre la plantilla oficial de pre-orden.

    La base ya trae título, rayos, contorno, separador, estrellas, pastilla,
    banda y CTA. Acá solo se agregan portada, vinilo, sticker y datos.
    """
    W, H = tamano
    sc = W / 1080.0

    def s(v):
        return int(round(v * sc))

    with Image.open(BASE_STORY_PREORDEN) as base_img:
        base = base_img.convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    lienzo = base.convert("RGBA")

    # ---- portada dentro del contorno naranja
    cover_x, cover_y, C = s(124), s(366), s(651)

    # ---- vinilo detrás, con el centro y el radio de la plantilla
    disco_cx, disco_cy, disco_r = s(662), s(691), s(317)
    diam = disco_r * 2
    if disco is not None:
        imagen_disco = _disco_desde_imagen(disco).resize(
            (diam, diam), Image.Resampling.LANCZOS)
    else:
        imagen_disco = generar_disco(preset, diam, portada)
    mascara = Image.new("L", (diam, diam), 0)
    ImageDraw.Draw(mascara).ellipse((0, 0, diam - 1, diam - 1), fill=255)
    lienzo.paste(imagen_disco, (disco_cx - disco_r, disco_cy - disco_r), mascara)

    # la funda tapa la mitad izquierda del disco
    lienzo.paste(_portada_cuadrada(portada, C), (cover_x, cover_y))

    # ---- sticker 1lp / 2lp
    lps = max(1, int(datos.get("lps", 1)))
    if STICKER_STORY.exists():
        # El PNG incluye 20 px de tallo arriba de la calabaza. Se pega más
        # arriba para que el cuerpo quede en la misma posición de siempre y el
        # tallo sobresalga sobre el disco.
        tallo = 20
        with Image.open(STICKER_STORY) as sticker_img:
            sticker = sticker_img.convert("RGBA").resize(
                (s(162), s(157 + tallo)), Image.Resampling.LANCZOS)
        lienzo.alpha_composite(sticker, (s(684), s(601 - tallo)))
        d = ImageDraw.Draw(lienzo)
        d.text((s(765), s(680)), f"{lps}lp",
               font=_fuente(FUENTE_TITULO, s(38)),
               fill=(*TINTA_PLANTILLA, 255), anchor="mm")
    else:
        d = ImageDraw.Draw(lienzo)
        st_r = s(66)
        d.ellipse((s(765) - st_r, s(680) - st_r,
                   s(765) + st_r, s(680) + st_r),
                  fill=(*NARANJA_PLANTILLA, 255),
                  outline=(*TINTA_PLANTILLA, 255), width=max(2, s(3)))
        d.text((s(765), s(680)), f"{lps}lp",
               font=_fuente(FUENTE_TITULO, s(38)),
               fill=(*TINTA_PLANTILLA, 255), anchor="mm")

    d = ImageDraw.Draw(lienzo)

    # ---- artista / álbum: una línea grande o dos líneas compactas
    separator_y = s(1223)
    ancho_texto = s(900)
    f_album = _fuente_ajustada(d, datos["album"], FUENTE_TITULO,
                               s(62), ancho_texto, 2)
    lineas_album = _wrap(d, datos["album"], f_album, ancho_texto)
    if len(lineas_album) == 1:
        alto_linea = f_album.size + s(8)
        album_arriba = s(1126)
        f_artista = _fuente_ajustada(d, datos["artista"], FUENTE_TITULO,
                                     s(56), ancho_texto, 1)
    else:
        f_album = _fuente_ajustada(d, datos["album"], FUENTE_TITULO,
                                   s(40), ancho_texto, 2)
        lineas_album = _wrap(d, datos["album"], f_album, ancho_texto)
        alto_linea = f_album.size + s(8)
        album_arriba = separator_y - s(33) - len(lineas_album) * alto_linea
        f_artista = _fuente_ajustada(d, datos["artista"], FUENTE_TITULO,
                                     s(40), ancho_texto, 1)

    caja_artista = d.textbbox((0, 0), datos["artista"], font=f_artista)
    alto_artista = caja_artista[3] - caja_artista[1]
    artista_arriba = album_arriba - s(25) - alto_artista

    _texto_arriba(d, W // 2, artista_arriba, datos["artista"], f_artista,
                  (*VERDE_PLANTILLA, 255),
                  sombra=(s(3), s(4), (*SOMBRA_VERDE, 255)))
    for i, linea in enumerate(lineas_album):
        _texto_arriba(d, W // 2, album_arriba + i * alto_linea, linea, f_album,
                      (*NARANJA_PLANTILLA, 255),
                      sombra=(s(3), s(4), (*SOMBRA_NARANJA, 255)))

    # ---- formato serif entre las estrellas
    f_formato = _fuente_ajustada(d, datos["formato"], FUENTE_SERIF,
                                 s(38), s(640), 1)
    _texto_arriba(d, W // 2, s(1297), datos["formato"], f_formato,
                  (*CREMA_PLANTILLA, 255))

    # ---- precio dentro de la pastilla
    centro_precio = (s(540), s(1616))
    if datos["precio"] is not None:
        texto_precio = _pesos(datos["precio"])
        f_precio = _fuente_ajustada(d, texto_precio, FUENTE_TITULO,
                                    s(96), s(420), 1)
        d.text((centro_precio[0] + s(4), centro_precio[1] + s(5)), texto_precio,
               font=f_precio, fill=(*SOMBRA_VERDE, 255), anchor="mm")
        d.text(centro_precio, texto_precio, font=f_precio,
               fill=(*VERDE_PLANTILLA, 255), anchor="mm",
               stroke_width=max(1, s(2)), stroke_fill=(*SOMBRA_VERDE, 255))
    else:
        f_desc = _fuente(FUENTE_TITULO, s(40))
        d.text((centro_precio[0], centro_precio[1] - s(22)), "Precio y reserva",
               font=f_desc, fill=(*VERDE_PLANTILLA, 255), anchor="mm")
        d.text((centro_precio[0], centro_precio[1] + s(26)), "por confirmar",
               font=f_desc, fill=(*VERDE_PLANTILLA, 255), anchor="mm")

    # ---- valores de reserva y llegada (las etiquetas ya están en la base)
    # La etiqueta "Reserva con:" termina en x≈333 y "Llegada est:" en x≈651.
    y_banda = s(1704)
    abono = _pesos(datos["abono"]) if datos["abono"] is not None else "por confirmar"
    f_abono = _fuente_ajustada(d, abono, FUENTE_TITULO, s(30), s(140), 1)
    d.text((s(345), y_banda), abono, font=f_abono,
           fill=(*TINTA_PLANTILLA, 255), anchor="lm")

    eta = datos["eta"] or "por confirmar"
    f_eta = _fuente_ajustada(d, eta, FUENTE_ITALICA, s(28), s(205), 1)
    d.text((s(663), y_banda), eta, font=f_eta,
           fill=(*TINTA_PLANTILLA, 255), anchor="lm",
           stroke_width=max(1, s(1)), stroke_fill=(*TINTA_PLANTILLA, 255))

    # ---- "envío incluido" ya está en la base; si es aparte, se parchea
    if not datos.get("envio_incluido", True):
        # Franja limpia justo arriba del texto fijo, lejos del precio.
        limpio = lienzo.crop((s(770), s(1582), s(912), s(1588)))
        parche = limpio.resize((s(146), s(67)), Image.Resampling.LANCZOS)
        mascara = Image.new("L", (s(146), s(67)), 0)
        ImageDraw.Draw(mascara).rounded_rectangle(
            (0, 0, s(146) - 1, s(67) - 1), radius=s(8), fill=255)
        mascara = mascara.filter(ImageFilter.GaussianBlur(s(5)))
        lienzo.paste(parche, (s(766), s(1583)), mascara)
        d = ImageDraw.Draw(lienzo)
        f_envio = _fuente(FUENTE_ITALICA, s(30))
        _texto_arriba(d, s(776), s(1591), "envío", f_envio,
                      (*VERDE_PLANTILLA, 255), anchor="la")
        _texto_arriba(d, s(776), s(1615), "aparte", f_envio,
                      (*VERDE_PLANTILLA, 255), anchor="la")
        cx, cy = s(875), s(1600)
        d.line((cx - s(7), cy - s(7), cx + s(7), cy + s(7)),
               fill=(*VERDE_PLANTILLA, 255), width=max(2, s(3)))
        d.line((cx - s(7), cy + s(7), cx + s(7), cy - s(7)),
               fill=(*VERDE_PLANTILLA, 255), width=max(2, s(3)))

    return lienzo.convert("RGB")


def generar_pieza_preventa_story(portada: Image.Image, datos: dict, preset="negro",
                                 tamano=(1080, 1920),
                                 disco: Image.Image | None = None) -> Image.Image:
    """Story 1080×1920: plantilla oficial para pre-orden y fallback dibujado.

    Si la pieza es de pre-orden y existe la base oficial, se monta sobre esa
    plantilla para conservar la geometría exacta. Para "a la venta!" se usa el
    renderer dibujado hasta contar con la plantilla de venta.
    """
    if datos.get("preorden") and BASE_STORY_PREORDEN.exists():
        return _story_plantilla(portada, datos, preset=preset, tamano=tamano, disco=disco)
    return _story_dibujada(portada, datos, preset=preset, tamano=tamano, disco=disco)


def cargar_portada(lanzamiento: Lanzamiento, productos: Iterable[Producto] | None = None,
                   timeout=20) -> Image.Image:
    """Portada del lanzamiento: URL de Spotify/portada o primera foto de producto."""
    productos = list(productos or [])
    if lanzamiento.i_lanzamiento:
        try:
            r = requests.get(lanzamiento.i_lanzamiento, timeout=timeout)
            if r.ok:
                return Image.open(io.BytesIO(r.content)).convert("RGB")
        except Exception:
            pass
    for producto in productos:
        imagenes = getattr(producto, "imagenes", None) or []
        for img in imagenes:
            if img.img:
                datos = img.img if isinstance(img.img, bytes) else img.img.encode("latin-1")
                try:
                    return Image.open(io.BytesIO(datos)).convert("RGB")
                except Exception:
                    pass
    # último recurso: portada abstracta con las iniciales
    S = 900
    base = _degradado((S, S), (40, 20, 70), (12, 8, 20))
    d = ImageDraw.Draw(base)
    d.ellipse((S * 0.15, S * 0.15, S * 0.85, S * 0.85), outline=(*NARANJA, 100), width=4)
    letras = "".join(p[0] for p in (lanzamiento.n_lanzamiento or "MB").split()[:2]).upper()
    d.text((S // 2, S // 2), letras, font=_fuente(FUENTE_TITULO, 220),
           fill=(*BLANCO, 230), anchor="mm")
    return base.convert("RGB")


def _slug_preset(preset) -> str:
    if isinstance(preset, dict):
        return preset.get("slug") or "variante"
    return str(preset)


_PREFIJO_ARCHIVO = re.compile(r"^lanzamiento_\d+_")


def etiqueta_archivo(nombre: str) -> str:
    """Nombre legible para la galería del panel a partir del PNG generado."""
    base = Path(nombre).stem
    vm = base.endswith("_vm")
    if vm:
        base = base[:-len("_vm")]
    if base.endswith("_preventa"):
        return "Pieza de preventa · VinylMockup" if vm else "Pieza de preventa"
    if base.endswith("_preventa_story"):
        return "Preventa story · VinylMockup" if vm else "Preventa (story)"
    if base.endswith("_claro"):
        base = base[:-len("_claro")]
    clave = _PREFIJO_ARCHIVO.sub("", base)
    if clave in PRESETS:
        return PRESETS[clave]["nombre"]
    if clave == "vinylmockup":
        return "Mockup · VinylMockup"
    variante = variante_por_slug(clave)
    if variante:
        return variante["nombre"]
    return clave.replace("_", " ").replace("-", " ").title()


def guardar_poc(lanzamiento: Lanzamiento, salida: Path,
                presets=("negro", "color", "splatter", "picture"),
                datos: dict | None = None, fondo: str = "estudio",
                plantilla: str = "ficha",
                disco: Image.Image | None = None) -> list[Path]:
    """Genera las piezas del POC y devuelve las rutas.

    `plantilla="story"` genera únicamente la story vertical 1080×1920: no crea
    la ficha ni el mockup cuadrado con fondo claro. La ficha 1080×1350 queda
    disponible con `plantilla="ficha"` para el CLI. Con `disco` (p. ej. la
    imagen de VinylMockup, solo modo local) se usa esa foto en lugar del vinilo
    procedural, con el sufijo `_vm`.
    """
    salida.mkdir(parents=True, exist_ok=True)
    productos = Producto.query.filter_by(k_lanzamiento=lanzamiento.id).all()
    portada = cargar_portada(lanzamiento, productos)
    datos = datos or datos_preventa(lanzamiento, productos)
    lps = max(1, int(datos.get("lps", 1)))
    sufijo_vm = "_vm" if disco is not None else ""

    if plantilla == "story":
        card = generar_pieza_preventa_story(portada, datos, preset=presets[0], disco=disco)
        ruta = salida / f"lanzamiento_{lanzamiento.id}_preventa_story{sufijo_vm}.png"
        card.save(ruta, "PNG", optimize=True)
        return [ruta]

    sufijo = "_claro" if fondo == "claro" else ""
    rutas = []
    if disco is None:
        rutas.extend(_guardar_mockups_presets(lanzamiento, salida, presets, fondo,
                                              portada, sufijo, lps=lps))
    else:
        img = componer_mockup(portada, preset=presets[0], tamano=1400, fondo=fondo,
                              disco=disco, lps=lps)
        ruta = salida / f"lanzamiento_{lanzamiento.id}_vinylmockup{sufijo}.png"
        img.convert("RGB").save(ruta, "PNG", optimize=True)
        rutas.append(ruta)

    card = generar_pieza_preventa(portada, datos, preset=presets[0], disco=disco,
                                  lps=lps)
    ruta_card = salida / f"lanzamiento_{lanzamiento.id}_preventa{sufijo_vm}.png"
    card.save(ruta_card, "PNG", optimize=True)
    rutas.append(ruta_card)
    return rutas


def _guardar_mockups_presets(lanzamiento: Lanzamiento, salida: Path, presets: tuple,
                             fondo: str, portada: Image.Image,
                             sufijo: str, lps: int = 1) -> list[Path]:
    """Mockups 1400×1400 por preset procedural (cuando no hay disco externo)."""
    rutas = []
    for preset in presets:
        slug = _slug_preset(preset)
        img = componer_mockup(portada, preset=preset, tamano=1400, fondo=fondo,
                              lps=lps)
        ruta = salida / f"lanzamiento_{lanzamiento.id}_{slug}{sufijo}.png"
        img.convert("RGB").save(ruta, "PNG", optimize=True)
        rutas.append(ruta)
    return rutas
