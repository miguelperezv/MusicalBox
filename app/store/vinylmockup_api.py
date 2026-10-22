"""Cliente de solo lectura para la API interna de VinylMockup.

Esto es un spike local, no una integración de producción. La API no es
pública, no tiene documentación ni licencia visible y las imágenes siguen
siendo de VinylMockup y/o de las plantas de prensado. Por eso este módulo no
se importa desde la app: solo lo usa `scripts/spike_vinylmockup.py`.

Si algún día hay licencia, este contrato se puede convertir en un proveedor
más del renderer propio.
"""
from __future__ import annotations

import os
import re
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import requests


BASE_URL = os.getenv("VINYLMOCKUP_API_BASE", "https://vinylmockup.com").rstrip("/")
TIMEOUT = float(os.getenv("VINYLMOCKUP_TIMEOUT", "20"))
USER_AGENT = os.getenv("VINYLMOCKUP_USER_AGENT", "MusicalBox-spike/0.1")
MAX_IMAGE_BYTES = 12 * 1024 * 1024
HOSTS_IMAGEN = {"images.ctfassets.net"}


class VinylMockupError(RuntimeError):
    """Error de red, de formato o de una respuesta inesperada de la API."""


def carpeta_por_defecto() -> Path:
    """Carpeta temporal del spike: nunca dentro del repositorio."""
    return Path(tempfile.gettempdir()) / "vinylmockup_spike"


def _url_abs(url: str | None) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return BASE_URL + url
    return url


def miniatura_url(url: str, ancho: int = 400, alto: int | None = None) -> str:
    """Pide una miniatura a Contentful sin bajar el JPEG de 2160×2160."""
    if not url:
        return ""
    alto = alto or ancho
    separador = "&" if "?" in url else "?"
    return f"{url}{separador}w={int(ancho)}&h={int(alto)}&fit=fill&f=center"


def _params(params: dict[str, Any] | None) -> tuple[tuple[str, str], ...]:
    if not params:
        return ()
    return tuple((str(k), str(v)) for k, v in params.items() if v not in (None, ""))


@lru_cache(maxsize=128)
def _get_json(path: str, params: tuple[tuple[str, str], ...] = ()) -> Any:
    """GET cacheado por proceso. No se cachean errores."""
    url = BASE_URL + path
    try:
        r = requests.get(url, params=dict(params), timeout=TIMEOUT,
                         headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    except requests.RequestException as e:
        raise VinylMockupError(f"No se pudo conectar con VinylMockup: {e}") from e

    if r.status_code == 204:
        return None
    if r.status_code == 404:
        raise VinylMockupError(f"No existe el recurso: {path}")
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        raise VinylMockupError(f"VinylMockup respondió {r.status_code}: {path}") from e
    try:
        return r.json()
    except ValueError as e:
        raise VinylMockupError(f"VinylMockup no devolvió JSON: {path}") from e


def _resumen(item: dict[str, Any]) -> dict[str, Any]:
    """Normaliza un resultado de /api/variants/search."""
    value = item.get("value") or item
    slug = value.get("slug") or ""
    variant_id = value.get("id") or ""
    return {
        "id": variant_id,
        "name": value.get("name") or item.get("label") or "",
        "slug": slug,
        "press_name": value.get("pressName") or "",
        "press_slug": value.get("pressSlug") or "",
        "press_website": value.get("pressWebsite") or "",
        "thumb_url": _url_abs(value.get("vinylIcon")),
        "page_url": f"{BASE_URL}/v/{variant_id}-{slug}" if variant_id else "",
    }


def _ficha(entry: dict[str, Any] | None) -> dict[str, Any] | None:
    """Normaliza el detalle de una variante (entrada de Contentful)."""
    if not entry:
        return None
    fields = entry.get("fields") or {}
    press = fields.get("press") or {}
    press_fields = press.get("fields") or {}
    type_fields = (fields.get("type") or {}).get("fields") or {}
    style_fields = (fields.get("style") or {}).get("fields") or {}
    image = fields.get("image") or {}
    image_fields = image.get("fields") or {}
    image_file = image_fields.get("file") or {}
    image_details = image_file.get("details") or {}
    image_size = image_details.get("image") or {}

    colores = []
    for color in fields.get("color") or []:
        color_fields = color.get("fields") or {}
        if color_fields.get("name"):
            colores.append(color_fields["name"])

    slug = fields.get("slug") or ""
    variant_id = (entry.get("sys") or {}).get("id") or ""
    return {
        "id": variant_id,
        "name": fields.get("name") or "",
        "slug": slug,
        "press_name": press_fields.get("name") or "",
        "press_slug": press_fields.get("slug") or "",
        "press_website": press_fields.get("website") or "",
        "press_id": (press.get("sys") or {}).get("id") or "",
        "type": type_fields.get("name") or "",
        "style": style_fields.get("name") or "",
        "colors": colores,
        "image_url": _url_abs(image_file.get("url")),
        "image_filename": image_file.get("fileName") or "",
        "image_content_type": image_file.get("contentType") or "",
        "image_width": image_size.get("width"),
        "image_height": image_size.get("height"),
        "image_bytes": image_details.get("size"),
        "page_url": f"{BASE_URL}/v/{variant_id}-{slug}" if variant_id else "",
    }


def buscar_variantes(q: str | None = None, press: str | None = None,
                     page: int = 1) -> dict[str, Any]:
    """Busca variantes.

    `press` debe ser el ID de Contentful de la prensa, no el slug. La API
    devuelve 20 resultados por página.
    """
    if page < 1:
        raise ValueError("page debe ser mayor o igual a 1")
    data = _get_json("/api/variants/search",
                     _params({"q": q, "press": press, "page": page}))
    if not data:
        return {"items": [], "page": page, "has_next": False, "total": 0}
    items = [_resumen(item) for item in data.get("items") or []]
    return {
        "items": items,
        "page": data.get("page") or page,
        "has_next": bool(data.get("hasNextPage")),
        "total": data.get("total") or len(items),
    }


def obtener_variante(variant_id: str) -> dict[str, Any] | None:
    """Detalle de una variante, incluida la imagen grande (2160×2160)."""
    if not variant_id:
        raise ValueError("Falta el id de la variante")
    return _ficha(_get_json(f"/api/variants/{quote(str(variant_id), safe='')}"))


def obtener_prensa(press_id: str) -> dict[str, Any] | None:
    """Detalle de una prensa. `press_id` es el ID de Contentful."""
    if not press_id:
        raise ValueError("Falta el id de la prensa")
    data = _get_json(f"/api/presses/{quote(str(press_id), safe='')}")
    if not data:
        return None
    fields = data.get("fields") or {}
    logo = fields.get("logo") or {}
    logo_file = (logo.get("fields") or {}).get("file") or {}
    return {
        "id": (data.get("sys") or {}).get("id") or press_id,
        "name": fields.get("name") or "",
        "slug": fields.get("slug") or "",
        "website": fields.get("website") or "",
        "logo_url": _url_abs(logo_file.get("url")),
    }


def variante_de_prensa(press_id: str) -> dict[str, Any] | None:
    """Variante destacada que devuelve /api/presses/{id}/variant."""
    if not press_id:
        raise ValueError("Falta el id de la prensa")
    return _ficha(_get_json(f"/api/presses/{quote(str(press_id), safe='')}/variant"))


def _validar_url_imagen(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in HOSTS_IMAGEN:
        raise VinylMockupError(f"URL de imagen no permitida en el spike: {url}")


def descargar_imagen(url: str, destino: Path,
                     max_bytes: int = MAX_IMAGE_BYTES) -> dict[str, Any]:
    """Descarga una imagen puntual, con límite de tamaño.

    Solo acepta hosts de imagen conocidos. No hay descarga masiva.
    """
    _validar_url_imagen(url)
    destino = Path(destino).expanduser()
    destino.parent.mkdir(parents=True, exist_ok=True)

    try:
        with requests.get(url, stream=True, timeout=TIMEOUT,
                          headers={"User-Agent": USER_AGENT}) as r:
            r.raise_for_status()
            content_type = r.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                raise VinylMockupError(f"La respuesta no es una imagen: {content_type}")
            total = 0
            with destino.open("wb") as fh:
                for bloque in r.iter_content(chunk_size=64 * 1024):
                    if not bloque:
                        continue
                    total += len(bloque)
                    if total > max_bytes:
                        fh.close()
                        destino.unlink(missing_ok=True)
                        raise VinylMockupError(
                            f"La imagen supera el límite de {max_bytes // (1024 * 1024)} MB")
                    fh.write(bloque)
    except requests.RequestException as e:
        destino.unlink(missing_ok=True)
        raise VinylMockupError(f"No se pudo descargar la imagen: {e}") from e

    return {"path": str(destino), "bytes": total, "content_type": content_type}


def descargar_variante(variant_id: str, carpeta: Path | None = None) -> dict[str, Any]:
    """Baja la imagen grande de una variante a una carpeta temporal.

    Devuelve la ficha de la variante más `path` y `bytes`.
    """
    variante = obtener_variante(variant_id)
    if not variante:
        raise VinylMockupError(f"No se encontró la variante {variant_id}")
    if not variante["image_url"]:
        raise VinylMockupError(f"La variante {variant_id} no tiene imagen")

    carpeta = Path(carpeta).expanduser() if carpeta else carpeta_por_defecto()
    sufijo = Path(variante["image_filename"]).suffix.lower() or ".jpg"
    if sufijo not in (".jpg", ".jpeg", ".png", ".webp"):
        sufijo = ".jpg"
    nombre = f"{variante['id']}-{variante['slug']}{sufijo}"
    nombre = re.sub(r"[^a-zA-Z0-9._-]+", "-", nombre).strip("-") or f"{variant_id}{sufijo}"
    archivo = carpeta / nombre
    if archivo.exists():
        # caché simple del spike: si la variante ya está en la carpeta destino,
        # no se vuelve a bajar (mismo archivo, misma imagen).
        return {**variante, "path": str(archivo), "bytes": archivo.stat().st_size,
                "content_type": variante["image_content_type"] or "image/jpeg"}
    descarga = descargar_imagen(variante["image_url"], archivo)
    return {**variante, **descarga}


__all__ = [
    "VinylMockupError", "BASE_URL", "carpeta_por_defecto", "miniatura_url",
    "buscar_variantes", "obtener_variante", "obtener_prensa",
    "variante_de_prensa", "descargar_imagen", "descargar_variante",
]
