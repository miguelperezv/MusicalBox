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

NARANJA = (255, 106, 0)
VERDE = (183, 227, 109)
BLANCO = (248, 247, 252)


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
                    fondo: str = "estudio") -> Image.Image:
    """Funda + disco. `fondo="transparente"` devuelve solo la composición con sombras."""
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
    disco = generar_disco(preset, disco_t, portada)
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
    lienzo.alpha_composite(disco, (disco_x, disco_y))

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
    ds.text((sx, sy), "1LP", font=_fuente(FUENTE_TITULO, max(12, int(sticker_r * 0.8))),
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
                   precio=None, abono=None, formato=None, eta=None) -> dict:
    """Datos que alimentan la pieza. Los overrides existen para el POC."""
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

    return {
        "artista": titulo(artista.n_artista) if artista else "Artista por confirmar",
        "album": titulo(lanzamiento.n_lanzamiento),
        "formato": formato,
        "precio": precio,
        "abono": abono,
        "eta": eta,
        "preorden": bool(lanzamiento.preorden or (producto_vinilo and producto_vinilo.preorden)),
    }


def generar_pieza_preventa(portada: Image.Image, datos: dict, preset="negro",
                           tamano=(1080, 1350)) -> Image.Image:
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
    mock = componer_mockup(portada, preset=preset, tamano=1000, fondo="transparente")
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
    if base.endswith("_preventa"):
        return "Pieza de preventa"
    if base.endswith("_claro"):
        base = base[:-len("_claro")]
    clave = _PREFIJO_ARCHIVO.sub("", base)
    if clave in PRESETS:
        return PRESETS[clave]["nombre"]
    variante = variante_por_slug(clave)
    if variante:
        return variante["nombre"]
    return clave.replace("_", " ").replace("-", " ").title()


def guardar_poc(lanzamiento: Lanzamiento, salida: Path, presets=("negro", "color", "splatter", "picture"),
                datos: dict | None = None, fondo: str = "estudio") -> list[Path]:
    """Genera las piezas del POC y devuelve las rutas."""
    salida.mkdir(parents=True, exist_ok=True)
    productos = Producto.query.filter_by(k_lanzamiento=lanzamiento.id).all()
    portada = cargar_portada(lanzamiento, productos)
    datos = datos or datos_preventa(lanzamiento, productos)
    sufijo = "_claro" if fondo == "claro" else ""
    rutas = []
    for preset in presets:
        slug = _slug_preset(preset)
        img = componer_mockup(portada, preset=preset, tamano=1400, fondo=fondo)
        ruta = salida / f"lanzamiento_{lanzamiento.id}_{slug}{sufijo}.png"
        img.convert("RGB").save(ruta, "PNG", optimize=True)
        rutas.append(ruta)
    card = generar_pieza_preventa(portada, datos, preset=presets[0])
    ruta_card = salida / f"lanzamiento_{lanzamiento.id}_preventa.png"
    card.save(ruta_card, "PNG", optimize=True)
    rutas.append(ruta_card)
    return rutas
