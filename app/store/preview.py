"""Reproductor de Spotify (embed) para la página "Pronto".

La API de Spotify ya no entrega `preview_url` (viene nulo), pero sí se puede incrustar el
reproductor oficial: sin sesión se oyen 30 s y con Spotify, el tema completo. No requiere
llaves. Se elige el lanzamiento más popular (más vendido; si no hay ventas, el más reciente)
que tenga álbum de Spotify asociado (`lanzamiento.external_id`, ver app/store/musicapi.py).
"""
import re

from ..db import db
from .models import Lanzamiento, get_releases_cards

#id de álbum de Spotify: 22 caracteres base62 (descarta valores de prueba como "test123")
_SPOTIFY_ID = re.compile(r"^[A-Za-z0-9]{22}$")


def spotify_destacado():
    """{spotify_id, titulo, artista} del lanzamiento más popular con álbum de Spotify, o None."""
    for card in get_releases_cards(orden='vendidos'):
        lanz = db.session.get(Lanzamiento, card['id'])
        ext = (lanz.external_id or '').strip() if lanz else ''
        if _SPOTIFY_ID.match(ext):
            return {"spotify_id": ext,
                    "titulo": card.get("nombre") or "",
                    "artista": card["artista"].n_artista if card.get("artista") else ""}
    return None
