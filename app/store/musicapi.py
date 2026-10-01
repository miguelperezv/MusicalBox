#cliente de la API de Spotify (client credentials) para buscar lanzamientos y refrescar metadatos
#las llaves van en SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET (config.py, variables de entorno)
import time

import requests
from flask import current_app

BASE = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"
_token = {"access": None, "expira": 0}

def _llaves():
    return current_app.config.get("SPOTIFY_CLIENT_ID"), current_app.config.get("SPOTIFY_CLIENT_SECRET")

def _token_spotify():
    #token de aplicacion; se refresca con margen de 30 s
    client_id, client_secret = _llaves()
    if not client_id or not client_secret:
        return None
    if _token["access"] and time.time() < _token["expira"] - 30:
        return _token["access"]
    r = requests.post(TOKEN_URL, auth=(client_id, client_secret),
                      data={"grant_type": "client_credentials"}, timeout=10)
    if r.status_code != 200:
        return None
    d = r.json()
    _token["access"] = d.get("access_token")
    _token["expira"] = time.time() + int(d.get("expires_in", 3600))
    return _token["access"]

def _headers():
    t = _token_spotify()
    return {"Authorization": "Bearer " + t} if t else None

def _error_config():
    return {"error": "Falta configurar SPOTIFY_CLIENT_ID y SPOTIFY_CLIENT_SECRET"}

def buscar_albumes_spotify(consulta):
    #busca albums por texto; devuelve {"items":[...]} o {"error": "..."}
    h = _headers()
    if not h:
        return _error_config()
    try:
        r = requests.get(BASE + "/search", params={"q": (consulta or '').strip(), "type": "album", "limit": 8},
                         headers=h, timeout=10)
        if r.status_code == 429:
            return {"error": "Límite de llamadas a Spotify: espera un momento e intenta de nuevo"}
        r.raise_for_status()
        items = []
        for a in r.json().get("albums", {}).get("items", []):
            imagenes = a.get("images") or []
            items.append({
                "id": a.get("id"),
                "nombre": a.get("name", ""),
                "artista": ((a.get("artists") or [{}])[0].get("name") or ""),
                "fecha": a.get("release_date") or "",
                "portada": (imagenes[0].get("url") or "") if imagenes else "",
                "url": (a.get("external_urls") or {}).get("spotify", ""),
            })
        return {"items": items}
    except requests.RequestException:
        return {"error": "No se pudo conectar con Spotify"}

def detalles_album_spotify(external_id):
    #metadatos de un album ya guardado (para el botón "Actualizar desde Spotify")
    h = _headers()
    if not h:
        return _error_config()
    try:
        r = requests.get(BASE + "/albums/" + external_id, headers=h, timeout=10)
        r.raise_for_status()
        a = r.json()
        imagenes = a.get("images") or []
        return {
            "n_lanzamiento": a.get("name"),
            "f_lanzamiento": a.get("release_date"),
            "i_lanzamiento": (imagenes[0].get("url") or "") if imagenes else "",
            "external_url": (a.get("external_urls") or {}).get("spotify", ""),
        }
    except requests.RequestException:
        return {"error": "No se pudo conectar con Spotify"}
