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
#cada plataforma se configura aparte: Instagram en cuadrícula (últimas 9 = 3x3) y TikTok 1 al azar
DEFAULTS = {'redes.activa': '0',
            'redes.instagram.modo': 'ultimas_n', 'redes.instagram.n': '9', 'redes.instagram.m': '9',
            'redes.tiktok.modo': 'random_n_de_m', 'redes.tiktok.n': '1', 'redes.tiktok.m': '10',
            #textos de envío visibles en tienda (clave-valor; si no hay fila en Configuracion vale el default)
            'envio.proceso': '1–2 días hábiles',
            'envio.bogota': '24–72 h',
            'envio.ciudades': '2–5 días',
            'envio.resto': '3–7 días'}
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


def envio():
    """Textos de envío para la tienda (zonas y procesado); editables por Configuracion, con default."""
    return {"proceso": get_config('envio.proceso'), "bogota": get_config('envio.bogota'),
            "ciudades": get_config('envio.ciudades'), "resto": get_config('envio.resto')}


def config_redes():
    cfg = {"activa": get_config('redes.activa') == '1'}
    for plat in PLATAFORMAS:
        cfg[plat] = {"modo": get_config(f'redes.{plat}.modo'), "n": int(get_config(f'redes.{plat}.n')),
                     "m": int(get_config(f'redes.{plat}.m'))}
    return cfg


def guardar_config_redes(activa, por_plataforma):
    #por_plataforma = {"instagram": (modo, n, m), "tiktok": (modo, n, m)}
    valores = {'redes.activa': '1' if activa else '0'}
    for plat, (modo, n, m) in por_plataforma.items():
        nombre = PLATAFORMAS[plat]
        if modo not in MODOS:
            return f"{nombre}: modo no válido"
        if n is None or n < 0 or not m or m < 1:
            return f"{nombre}: N debe ser 0 o más (0 = no mostrar) y M mayor que 0"
        if modo == 'random_n_de_m' and n > m:
            return f"{nombre}: en modo al azar, N no puede ser mayor que M"
        valores.update({f'redes.{plat}.modo': modo, f'redes.{plat}.n': n, f'redes.{plat}.m': m})
    set_config(valores)
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
    #solo se oculta si TikTok dice que no existe; límites (429), caídas o red: queda visible y el navegador lo omite si no carga
    try:
        r = requests.get("https://www.tiktok.com/oembed", params={"url": pub.url}, timeout=10)
        if r.status_code in (400, 404):
            pub.error_embed = "TikTok dice que el post no existe o es privado"
        elif r.status_code == 200:
            pub.error_embed = None if "html" in (r.json() or {}) else "TikTok no devolvió el embed del post"
    except Exception as e:
        print(f"No se pudo verificar el post {pub.url}: {e}")
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


def publicaciones_visibles(plataforma=None):
    q = PublicacionSocial.query.filter_by(activo=True).filter(PublicacionSocial.error_embed.is_(None))
    if plataforma:
        q = q.filter_by(plataforma=plataforma)
    return q.order_by(PublicacionSocial.orden, PublicacionSocial.id.desc()).all()


def _seleccion(plataforma, cfg):
    visibles = publicaciones_visibles(plataforma)
    if cfg["modo"] == 'ultimas_n':
        return visibles[:cfg["n"]]
    conjunto = visibles[:cfg["m"]]
    #firma: si cambia la configuración o el conjunto, se sortea de nuevo; si no, se repite lo de esta sesión
    firma = hashlib.sha256(repr((cfg, [(p.id, p.f_actualizacion) for p in conjunto])).encode()).hexdigest()[:16]
    sorteos = dict(session.get("redes_sorteo") or {})
    guardado = sorteos.get(plataforma) or {}
    por_id = {p.id: p for p in conjunto}
    if guardado.get("firma") != firma or not all(i in por_id for i in guardado.get("ids", [])):
        guardado = {"firma": firma, "ids": [p.id for p in random.sample(conjunto, min(cfg["n"], len(conjunto)))]}
        sorteos[plataforma] = guardado
        session["redes_sorteo"] = sorteos
    return [por_id[i] for i in guardado["ids"]]


def seleccion_para_inicio():
    """{"instagram": [...], "tiktok": [...]} para el inicio, o None si la sección está apagada o no hay nada."""
    cfg = config_redes()
    if not cfg["activa"]:
        return None
    sel = {plat: _seleccion(plat, cfg[plat]) for plat in PLATAFORMAS}
    return sel if any(sel.values()) else None
