"""Adelanto de 30 s de una canción al azar entre las más populares de nuestros lanzamientos.

Qué se puede y qué no (comprobado en 2026):
- La API de Spotify ya NO entrega `preview_url` ni `popularity` (vienen nulos). Con Spotify se
  toma el link del tema; la popularidad real y el audio salen de Deezer (`rank` y preview de 30 s).
- El navegador no deja sonar solo en la primera visita: el JS intenta y, si lo bloquea,
  arranca al primer scroll/tap (ver proximamente.html).

Se arma un repertorio (top 10 por rank entre los temas de nuestros álbumes de Spotify) que queda
cacheado una semana en Configuracion. En cada visita se elige uno al azar; las URLs de preview de
Deezer caducan a los 15 min, así que la del tema elegido se pide fresca.
"""
import json
import random
import re
import time

import requests

from ..db import db
from .redes import get_config, set_config
from .musicapi import _headers
from .models import Lanzamiento, get_releases_cards

_SPOTIFY_ID = re.compile(r"^[A-Za-z0-9]{22}$")
_VIGENCIA = 7 * 24 * 3600  #el repertorio (no la URL, que dura 15 min)
_MAX_ALBUMES = 8           #álbumes que se recorren para armar el repertorio
_TOP = 10                  #temas que entran al sorteo


def _norm(texto):
    return re.sub(r"\W+", " ", (texto or "").lower()).strip()


def _spotify_urls(album, artista):
    """{nombre_normalizado: url_de_spotify} de los temas del álbum (para el enlace 'abrir en Spotify')."""
    h = _headers()
    if not h:
        return {}
    partes = [f'artist:"{artista}"' if artista else '', f'album:"{album}"' if album else '']
    consulta = " ".join(p for p in partes if p) or artista
    try:
        r = requests.get("https://api.spotify.com/v1/search", headers=h,
                         params={"q": consulta, "type": "track", "limit": 10, "market": "CO"}, timeout=8)
        r.raise_for_status()
        return {_norm(t.get("name")): (t.get("external_urls") or {}).get("spotify", "")
                for t in (r.json().get("tracks", {}).get("items") or [])}
    except (requests.RequestException, ValueError):
        return {}


def _deezer_temas(album, artista):
    """Temas del álbum en Deezer con rank y preview: busca el álbum y lee sus pistas."""
    try:
        s = requests.get("https://api.deezer.com/search/album",
                         params={"q": f"{artista} {album}".strip(), "limit": 1}, timeout=8)
        s.raise_for_status()
        data = s.json().get("data") or []
        if not data:
            return []
        nombre_artista = (data[0].get("artist") or {}).get("name") or artista
        d = requests.get(f"https://api.deezer.com/album/{data[0]['id']}", timeout=8)
        d.raise_for_status()
        temas = []
        for t in (d.json().get("tracks", {}).get("data") or []):
            if t.get("preview"):
                temas.append({"deezer_id": t.get("id"), "rank": int(t.get("rank") or 0),
                              "titulo": t.get("title") or "", "artista": nombre_artista})
        return temas
    except (requests.RequestException, ValueError):
        return []


def _deezer_url_fresca(deezer_id):
    """URL de preview vigente (Deezer las firma por 15 min). None si falla."""
    try:
        r = requests.get(f"https://api.deezer.com/track/{deezer_id}", timeout=8)
        r.raise_for_status()
        t = r.json()
        return {"url": t.get("preview") or "", "titulo": t.get("title") or "",
                "artista": (t.get("artist") or {}).get("name") or ""}
    except (requests.RequestException, ValueError):
        return None


def _armar_repertorio():
    #un mismo álbum de Deezer puede salir por varios lanzamientos: se deja una vez por tema
    vistos = {}
    for card in get_releases_cards(orden='vendidos')[:_MAX_ALBUMES]:
        lanz = db.session.get(Lanzamiento, card['id'])
        ext = (lanz.external_id or '').strip() if lanz else ''
        if not _SPOTIFY_ID.match(ext):
            continue
        nombre, artista = card.get('nombre') or '', (card['artista'].n_artista if card.get('artista') else '')
        sp = _spotify_urls(nombre, artista)
        for t in _deezer_temas(nombre, artista):
            t["spotify"] = sp.get(_norm(t["titulo"]), "")
            previo = vistos.get(t["deezer_id"])
            if not previo or (t["spotify"] and not previo["spotify"]):
                vistos[t["deezer_id"]] = t
    temas = sorted(vistos.values(), key=lambda t: t["rank"], reverse=True)
    return temas[:_TOP]


def repertorio(saltar_cache=False):
    if not saltar_cache:
        crudo = get_config('preview.pool')
        if crudo and time.time() < int(get_config('preview.expira') or 0):
            try:
                temas = json.loads(crudo)
                if temas:
                    return temas
            except ValueError:
                pass
    temas = _armar_repertorio()
    if temas:
        set_config({'preview.pool': json.dumps(temas), 'preview.expira': int(time.time()) + _VIGENCIA})
    return temas


def cancion_destacada(saltar_cache=False):
    """Tema al azar del repertorio: {url, titulo, artista, spotify} o None."""
    temas = repertorio(saltar_cache)
    if not temas:
        return None
    elegido = random.choice(temas)
    fresco = _deezer_url_fresca(elegido["deezer_id"])
    if not fresco or not fresco.get("url"):
        return None
    fresco["spotify"] = elegido.get("spotify", "")
    return fresco
