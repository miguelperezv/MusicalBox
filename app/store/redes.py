"""Sección "Redes" del inicio: publicaciones de TikTok/Instagram guardadas por el admin y configuración del sitio.

Solo se guarda la referencia del post (URL + id); el contenido lo renderiza el embed oficial de cada plataforma.
Modo random_n_de_m: el sorteo se fija por sesión y se repite solo si cambia la configuración o el conjunto.
"""
import hashlib
import random
import re
from datetime import datetime

import requests
from flask import session

from ..db import db


class Configuracion(db.Model):
    #ajustes del sitio editables desde el admin (clave-valor), p. ej. redes.modo
    clave = db.Column(db.String(60), primary_key=True)
    valor = db.Column(db.Text)
    f_actualizacion = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class PublicacionSocial(db.Model):
    __tablename__ = 'publicacion_social'
    id = db.Column(db.Integer, primary_key=True)
    plataforma = db.Column(db.String(10), nullable=False)
    url = db.Column(db.String(300), nullable=False)
    id_externo = db.Column(db.String(60), nullable=False)
    #menor = aparece primero; las nuevas entran arriba
    orden = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    activo = db.Column(db.Boolean, nullable=False, default=True, server_default='1')
    #último error al verificar el embed (solo lo ve el admin; con error no se muestra en el inicio)
    error_embed = db.Column(db.String(200))
    f_creacion = db.Column(db.DateTime, default=datetime.now)
    f_actualizacion = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    __table_args__ = (db.UniqueConstraint('plataforma', 'id_externo', name='uq_publicacion_social_plataforma_id'),)


PLATAFORMAS = {'tiktok': 'TikTok', 'instagram': 'Instagram'}
MODOS = {'ultimas_n': 'Últimas N', 'random_n_de_m': 'N al azar de las últimas M'}
DEFAULTS = {'redes.activa': '0', 'redes.modo': 'ultimas_n', 'redes.n': '3', 'redes.m': '10'}
_PATRONES = {
    'tiktok': re.compile(r"^https?://(www\.|m\.)?tiktok\.com/@[\w.\-]+/(video|photo)/(\d{8,25})"),
    'instagram': re.compile(r"^https?://(www\.)?instagram\.com/(p|reel|tv)/([\w\-]{5,40})"),
}


#configuración
def get_config(clave):
    c = db.session.get(Configuracion, clave)
    return c.valor if c else DEFAULTS.get(clave)


def set_config(valores):
    for clave, valor in valores.items():
        c = db.session.get(Configuracion, clave) or Configuracion(clave=clave)
        c.valor = str(valor)
        db.session.add(c)
    db.session.commit()


def config_redes():
    return {"activa": get_config('redes.activa') == '1', "modo": get_config('redes.modo'),
            "n": int(get_config('redes.n')), "m": int(get_config('redes.m'))}


def guardar_config_redes(activa, modo, n, m):
    if modo not in MODOS:
        return "Modo no válido"
    if not n or n < 1 or not m or m < 1:
        return "N y M deben ser mayores que 0"
    if modo == 'random_n_de_m' and n > m:
        return "En modo al azar, N no puede ser mayor que M"
    set_config({'redes.activa': '1' if activa else '0', 'redes.modo': modo, 'redes.n': n, 'redes.m': m})
    return None


#publicaciones
def leer_url(plataforma, url):
    """Valida la URL según la plataforma. Devuelve (url_limpia, id_externo, error)."""
    url = (url or "").strip().split("?")[0]
    patron = _PATRONES.get(plataforma)
    if not patron:
        return None, None, "Plataforma no válida"
    m = patron.match(url)
    if not m:
        ejemplo = "https://www.tiktok.com/@usuario/video/123..." if plataforma == 'tiktok' else "https://www.instagram.com/p/ABC123/ o /reel/..."
        return None, None, f"La URL no es de un post de {PLATAFORMAS[plataforma]} (ej. {ejemplo}). Los enlaces cortos no sirven."
    return url, m.group(3), None


def verificar_embed(pub):
    #TikTok tiene oEmbed público; Instagram exige token de Facebook, así que solo se valida el formato
    if pub.plataforma != 'tiktok':
        pub.error_embed = None
        return None
    try:
        r = requests.get("https://www.tiktok.com/oembed", params={"url": pub.url}, timeout=10)
        pub.error_embed = None if r.status_code == 200 and "html" in (r.json() or {}) else f"TikTok respondió {r.status_code}: el post no existe o es privado"
    except Exception as e:
        pub.error_embed = f"No se pudo verificar: {str(e)[:120]}"
    return pub.error_embed


def crear_publicacion(plataforma, url):
    url, id_externo, err = leer_url(plataforma, url)
    if err:
        return None, err
    if PublicacionSocial.query.filter_by(plataforma=plataforma, id_externo=id_externo).first():
        return None, "Esa publicación ya está guardada"
    primero = db.session.query(db.func.min(PublicacionSocial.orden)).scalar()
    pub = PublicacionSocial(plataforma=plataforma, url=url, id_externo=id_externo, orden=(primero or 0) - 1)
    verificar_embed(pub)
    db.session.add(pub)
    db.session.commit()
    return pub, None


def mover_publicacion(pub, direccion):
    #intercambia el orden con la vecina de arriba o de abajo
    lista = PublicacionSocial.query.order_by(PublicacionSocial.orden, PublicacionSocial.id.desc()).all()
    for pos, p in enumerate(lista):
        p.orden = pos
    i = lista.index(pub)
    j = i - 1 if direccion == 'arriba' else i + 1
    if 0 <= j < len(lista):
        lista[i].orden, lista[j].orden = lista[j].orden, lista[i].orden
    db.session.commit()


def publicaciones_visibles():
    return (PublicacionSocial.query.filter_by(activo=True).filter(PublicacionSocial.error_embed.is_(None))
            .order_by(PublicacionSocial.orden, PublicacionSocial.id.desc()).all())


def seleccion_para_inicio():
    """Publicaciones a mostrar en el inicio, o None si la sección está apagada o no hay nada."""
    cfg = config_redes()
    if not cfg["activa"]:
        return None
    visibles = publicaciones_visibles()
    if cfg["modo"] == 'ultimas_n':
        return visibles[:cfg["n"]] or None
    conjunto = visibles[:cfg["m"]]
    #firma: si cambia la configuración o el conjunto, se sortea de nuevo; si no, se repite lo de esta sesión
    firma = hashlib.sha256(repr((cfg, [(p.id, p.f_actualizacion) for p in conjunto])).encode()).hexdigest()[:16]
    guardado = session.get("redes_sorteo") or {}
    por_id = {p.id: p for p in conjunto}
    if guardado.get("firma") != firma or not all(i in por_id for i in guardado.get("ids", [])):
        guardado = {"firma": firma, "ids": [p.id for p in random.sample(conjunto, min(cfg["n"], len(conjunto)))]}
        session["redes_sorteo"] = guardado
    return [por_id[i] for i in guardado["ids"]] or None
