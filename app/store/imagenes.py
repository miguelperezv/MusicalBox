"""Imágenes de producto redimensionadas (WebP) con caché en disco y en el navegador.

Las fotos se guardan en la BD tal como se suben (pueden pesar varios MB); aquí se sirven al tamaño que
necesita cada vista. La versión redimensionada se guarda en instance/cache_img/ y se regenera si la
imagen cambia (la clave incluye id, tamaño en bytes y nombre del archivo).
"""
import hashlib
import io
import os

from flask import Response, current_app, request
from PIL import Image as PILImage, ImageOps

from ..db import db
from .models import Imagen

ANCHOS = (300, 600, 1200)
UN_DIA = 86400


def imagen_producto(k_producto, ancho=600):
    img = Imagen.query.filter_by(k_producto=k_producto).first()
    if not img or not img.img:
        return None
    ancho = min(ANCHOS, key=lambda a: abs(a - (ancho or 600)))
    datos = img.img if isinstance(img.img, bytes) else img.img.encode("latin-1")
    etag = hashlib.md5(f"{img.id}-{len(datos)}-{img.name}-{ancho}".encode()).hexdigest()
    if request.if_none_match and etag in request.if_none_match:
        return Response(status=304, headers={"ETag": etag, "Cache-Control": f"public, max-age={UN_DIA}"})

    carpeta = os.path.join(current_app.instance_path, "cache_img")
    ruta = os.path.join(carpeta, f"{etag}.webp")
    if not os.path.exists(ruta):
        try:
            with PILImage.open(io.BytesIO(datos)) as original:
                foto = ImageOps.exif_transpose(original)  #respeta la orientación de fotos de celular
                foto.thumbnail((ancho, ancho))
                if foto.mode not in ("RGB", "RGBA"):
                    foto = foto.convert("RGBA" if "transparency" in foto.info else "RGB")
                os.makedirs(carpeta, exist_ok=True)
                foto.save(ruta, "WEBP", quality=80, method=4)
        except Exception as e:
            #si no se puede procesar, se entrega la original
            print(f"No se pudo redimensionar la imagen del producto {k_producto}: {e}")
            return Response(datos, mimetype=img.mimetype, headers={"Cache-Control": f"public, max-age={UN_DIA}"})
    with open(ruta, "rb") as f:
        return Response(f.read(), mimetype="image/webp",
                        headers={"ETag": etag, "Cache-Control": f"public, max-age={UN_DIA}"})
