"""Adelanto de 30 s de "la canción más popular" de nuestros lanzamientos, para la página "Pronto".

Qué se puede y qué no (comprobado en 2026):
- La API de Spotify ya NO entrega `preview_url` ni `popularity` (vienen nulos), así que con
  Spotify se elige el tema (su buscador ordena por popularidad) y se guarda el link para abrirlo;
  el audio se toma del preview de Deezer (30 s, sin llaves).
- El navegador no deja sonar solo en la primera visita: el JS intenta y, si lo bloquea,
  arranca al primer scroll/tap (ver proximamente.html).

La elección queda cacheada una semana en Configuracion (deezer_id + metadatos). Las URLs de
preview de Deezer expiran a los 15 min, por eso la URL se pide fresca en cada visita.
"""
import re
import time

import requests

from ..db import db
from .redes import get_config, set_config
from .musicapi import _headers
from .models import Lanzamiento, get_releases_cards

_SPOTIFY_ID = re.compile(r"^[A-Za-z0-9]{22}$")
_VIGENCIA = 7 * 24 * 3600  #una semana para la elección (no para la URL, que dura 15 min)
_MAX = 5                   #lanzamientos que se prueban


def _spotify_tema(album, artista):
    """Primer resultado de Spotify para el álbum (su buscador ordena por popularidad)."""
    h = _headers()
    if not h:
        return None
    partes = [f'artist:"{artista}"' if artista else '', f'album:"{album}"' if album else '']
    consulta = " ".join(p for p in partes if p) or artista
    try:
        r = requests.get("https://api.spotify.com/v1/search", headers=h,
                         params={"q": consulta, "type": "track", "limit": 10, "market": "CO"}, timeout=8)
        r.raise_for_status()
        items = r.json().get("tracks", {}).get("items") or []
        if items:
            return {"nombre": items[0].get("name") or "",
                    "spotify": (items[0].get("external_urls") or {}).get("spotify", "")}
    except (requests.RequestException, ValueError):
        return None
    return None


def _deezer_buscar(tema, artista):
    """Track de Deezer con preview (30 s) y su `rank` (popularidad). None si no hay."""
    try:
        r = requests.get("https://api.deezer.com/search",
                         params={"q": f"{tema} {artista}".strip(), "limit": 5}, timeout=8)
        r.raise_for_status()
        for t in (r.json().get("data") or []):
            if t.get("preview"):
                return {"deezer_id": t.get("id"), "rank": int(t.get("rank") or 0),
                        "titulo": t.get("title") or tema,
                        "artista": (t.get("artist") or {}).get("name") or artista}
    except (requests.RequestException, ValueError):
        return None
    return None


def _deezer_url_fresca(deezer_id):
    """URL de preview vigente (Deezer las firma por 15 min). None si falla."""
    try:
        r = requests.get(f"https://api.deezer.com/track/{deezer_id}", timeout=8)
        r.raise_for_status()
        t = r.json()
        return {"url": t.get("preview") or "",
                "titulo": t.get("title") or "",
                "artista": (t.get("artist") or {}).get("name") or ""}
    except (requests.RequestException, ValueError):
        return None


def _resolver():
    """Elige, entre nuestros lanzamientos con álbum de Spotify, el tema con mayor rank de Deezer."""
    mejor = None
    for card in get_releases_cards(orden='vendidos')[:_MAX]:
        lanz = db.session.get(Lanzamiento, card['id'])
        ext = (lanz.external_id or '').strip() if lanz else ''
        if not _SPOTIFY_ID.match(ext):
            continue
        artista = card['artista'].n_artista if card.get('artista') else ''
        sp = _spotify_tema(card.get('nombre') or '', artista)
        if not sp:
            continue
        dz = _deezer_buscar(sp['nombre'], artista)
        if not dz:
            continue
        dz["spotify"] = sp.get("spotify", "")
        if mejor is None or dz["rank"] > mejor["rank"]:
            mejor = dz
    return mejor


def cancion_destacada(saltar_cache=False):
    """{url, titulo, artista, spotify} del adelanto, o None. `saltar_cache=True` la re-elige."""
    if not saltar_cache:
        deezer_id = get_config('preview.deezer_id')
        if deezer_id and time.time() < int(get_config('preview.expira') or 0):
            fresco = _deezer_url_fresca(deezer_id)  #la URL caduca: se pide nueva
            if fresco and fresco.get("url"):
                fresco["spotify"] = get_config('preview.spotify') or ""
                return fresco
    elegido = _resolver()
    if not elegido:
        return None
    set_config({'preview.deezer_id': elegido["deezer_id"], 'preview.titulo': elegido["titulo"],
                'preview.artista': elegido["artista"], 'preview.spotify': elegido.get("spotify", ""),
                'preview.expira': int(time.time()) + _VIGENCIA})
    fresco = _deezer_url_fresca(elegido["deezer_id"])
    if not fresco or not fresco.get("url"):
        return None
    fresco["spotify"] = elegido.get("spotify", "")
    return fresco
