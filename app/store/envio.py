#costo de envío del pedido: reglas de gratis -> cotización real de EnvíoClick -> tarifa por zona (respaldo)
#el origen es Bogotá D.C. (DANE 11001000). El código DANE del destino se resuelve al vuelo con
#api-colombia.com (gratis, sin token): /City/search para el municipio y /UrbanCenter/city para el código.
import re
import unicodedata
from datetime import datetime, timedelta

import requests
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

from flask import current_app
from ..db import db
from .models import Ubicacion, ReglaEnvio, CotizacionCache
from .redes import get_config

#origen fijo de los envíos (la tienda)
ORIGEN_DANE = "11001000"  #Bogotá D.C.
ORIGEN_DIRECCION = "Carrera 15 # 85-40"
API_COLOMBIA = "https://api-colombia.com/api/v1"
API_ENVIOCLICK = "https://api.envioclickpro.com.co/api/v2/quotation"
#cloudflare de EnvíoClick bloquea user-agents que no son de navegador
_NAV = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
_DEPARTAMENTOS = {}  #cache por proceso: nombre normalizado -> departmentId de api-colombia


def _norm(texto):
    #minúsculas, espacios simples y sin tildes: "Medellín" == "medellin"
    t = unicodedata.normalize("NFD", (texto or "").strip().lower())
    return re.sub(r"[^\w\s]", "", "".join(c for c in t if unicodedata.category(c) != "Mn")).strip()


def _http(url, timeout=20, **kw):
    r = requests.get(url, headers=_NAV, timeout=timeout, **kw)
    r.raise_for_status()
    return r.json()


_CIUDADES = {}  #cache por proceso: nombre normalizado -> (nombre, departmentId, id) de api-colombia


def _cargar_ciudades():
    #todas las ciudades del país en una sola llamada (/City/search es fuzzy y no estable)
    if not _CIUDADES:
        for c in _http(f"{API_COLOMBIA}/City"):
            _CIUDADES.setdefault(_norm(c.get("name")), (c.get("name"), c.get("departmentId"), c.get("id")))


def _buscar_ciudad(ciudad, dep_id):
    """(nombre, departmentId, id) de la ciudad de la API que corresponde al texto digitado.
    La API usa nombres formales ('San Andres de Tumaco', 'Guadalajara de Buga'), por lo que se
    acepta: igual, empieza por, empieza por al revés ('Cartagena de Indias' -> 'Cartagena') y
    contiene solo si el municipio fue dicho con departamento. Devuelve None si es ambiguo."""
    if ciudad in _CIUDADES:
        return _CIUDADES[ciudad]
    if dep_id is None:
        pref = [n for n in _CIUDADES if n.startswith(ciudad)]
        return _CIUDADES[pref[0]] if len(pref) == 1 else None
    pref = [n for n in _CIUDADES if n.startswith(ciudad) and _CIUDADES[n][1] == dep_id]
    if len(pref) == 1:
        return _CIUDADES[pref[0]]
    if pref:  #varias con el mismo prefijo: si una coincide en nombre exacto sin departamento, no hay forma de elegir
        return None
    rev = [n for n in _CIUDADES if len(n) >= 4 and ciudad.startswith(n) and _CIUDADES[n][1] == dep_id]
    if len(rev) == 1:
        return _CIUDADES[rev[0]]
    if len(ciudad) >= 5:
        cont = [n for n in _CIUDADES if ciudad in n and _CIUDADES[n][1] == dep_id]
        if len(cont) == 1:
            return _CIUDADES[cont[0]]
    return None


def resolver_dane(nombre_municipio):
    """Devuelve el código DANE de 8 dígitos de "Medellín, Antioquia" (o "Kennedy, Bogotá D.C.").
    Bogotá siempre es 11001000; el resto se resuelve con api-colombia y queda guardado en ubicacion."""
    #se parte por la coma ANTES de normalizar (el _norm quitaria la coma)
    partes = (nombre_municipio or "").strip().rsplit(",", 1)
    ciudad = _norm(partes[0])
    dep = _norm(partes[1]) if len(partes) == 2 else ""
    if not ciudad:
        return None
    if "bogot" in ciudad:
        return ORIGEN_DANE
    clave = f"{ciudad}|{dep}"
    guardado = db.session.query(Ubicacion).filter_by(n_ubicacion=clave).first()
    if guardado:
        return guardado.c_dane
    code = None
    try:
        _cargar_ciudades()
        dep_id = _DEPARTAMENTOS.get(dep) if dep else None
        if not dep_id and dep:
            for d in _http(f"{API_COLOMBIA}/Department"):
                _DEPARTAMENTOS.setdefault(_norm(d.get("name")), d.get("id"))
            dep_id = _DEPARTAMENTOS.get(dep)
        match = _buscar_ciudad(ciudad, dep_id)
        if match:
            _, _dep, city_id = match
            centros = _http(f"{API_COLOMBIA}/UrbanCenter/city/{city_id}")
            #la cabecera municipal (tipo CM) es la que importa para el envío; si no hay, el primero
            code = next((u.get("code") for u in centros if u.get("type") == "CM"), None) or \
                   (centros[0].get("code") if centros else None)
    except Exception:
        code = None
    if code:
        db.session.add(Ubicacion(n_ubicacion=clave, c_dane=str(code)))
        db.session.commit()
        return str(code)
    return None


#peso aproximado por categoría, en gramos: un estimado "más o menos" según lo que se compra
#(la API de EnvíoClick pide un mínimo de 1 kg, que cubre los pedidos chicos)
PESOS_APROXIMADOS = {"VINILO": 200, "CD": 25, "CASSETTE": 60, "POSTER": 120, "CAMISETA": 250, "MUG": 300}
PESO_DEFECTO = 250  #merch u otras categorías sin peso definido


def peso_linea(producto, cantidad):
    """Gramos de una línea según su categoría; los packs suman el de sus componentes."""
    n = int(cantidad or 1)
    if producto is None:
        return PESO_DEFECTO * n
    if getattr(producto, 'tipo', 'SIMPLE') == 'BUNDLE':
        return sum(peso_linea(c.componente, c.cantidad * n) for c in producto.componentes)
    return PESOS_APROXIMADOS.get((getattr(producto, 'k_categoria', '') or '').upper(), PESO_DEFECTO) * n


def regla_envio_aplicada(lineas, total):
    """Primera regla activa (por orden) que aplique -> mensaje de gratis; si no, None.
    lineas: tuplas (producto, variante, cantidad, ...) de crear_pedido."""
    categorias = [(p.k_categoria if p is not None else None) for p, _v, _c, *_r in lineas]
    for regla in ReglaEnvio.query.filter_by(activo=True).order_by(ReglaEnvio.orden, ReglaEnvio.id).all():
        if regla.tipo == 'SIEMPRE':
            return "Envío gratis · consulta nuestra política de envíos"
        if regla.tipo == 'TOTAL_MIN' and total >= (regla.total_min or 0):
            return "Envío gratis · consulta nuestra política de envíos"
        if regla.tipo in ('SOLO_CATEGORIA', 'CANTIDAD_CATEGORIA') and regla.k_categoria:
            if regla.tipo == 'SOLO_CATEGORIA' and categorias and all(c == regla.k_categoria for c in categorias):
                return "Envío gratis · consulta nuestra política de envíos"
            unidades = sum(int(c or 1) for p, _v, c, *_r in lineas if p is not None and p.k_categoria == regla.k_categoria)
            if regla.tipo == 'CANTIDAD_CATEGORIA' and unidades >= (regla.cantidad or 0):
                return "Envío gratis · consulta nuestra política de envíos"
    return None


def umbral_envio_gratis():
    """Menor total mínimo (reglas TOTAL_MIN activas) que da envío gratis: 0 si siempre es gratis,
    None si no hay umbral configurado. Las preórdenes cuentan en el total, como cualquier ítem."""
    umbral = None
    for regla in ReglaEnvio.query.filter_by(activo=True).all():
        if regla.tipo == 'SIEMPRE':
            return 0
        if regla.tipo == 'TOTAL_MIN':
            t = int(regla.total_min or 0)
            umbral = t if umbral is None else min(umbral, t)
    return umbral


def aviso_envio_gratis(lineas, total):
    """Banner de envío gratis para carrito/checkout: si este pedido ya lo tiene y, si no,
    cuánto falta para el umbral activo. Devuelve None si el envío está apagado o no hay
    reglas que apliquen al carrito (el aviso "faltan $X" solo existe con umbral TOTAL_MIN)."""
    if get_config('envio.habilitado') != '1':
        return None
    umbral = umbral_envio_gratis()
    if regla_envio_aplicada(lineas, total):
        return {"gratis": True, "umbral": umbral, "falta": 0}
    if umbral is None:
        return None
    return {"gratis": False, "umbral": umbral, "falta": umbral - int(total or 0)}


def _caja():
    #dimensiones de la caja por defecto "largoxanchoxalto" en cm (config editable en el panel)
    try:
        l, a, h = (int(x) for x in (get_config('envio.caja') or '31x30x5').lower().split('x'))
        return max(1, l), max(1, a), max(1, h)
    except ValueError:
        return 31, 30, 5


def cotizar_envioclick(c_dane_destino, peso_g, valor_cop):
    """Cotización real de EnvíoClick; devuelve la tarifa elegida según el criterio configurado
    ({'p_envio', 'carrier', 'product', 'id_rate', 'dias'}). Lanza si no hay llave o no hay tarifas."""
    clave = current_app.config.get("ENVIOCLICK_TOKEN")
    if not clave:
        raise RuntimeError("Falta ENVIOCLICK_TOKEN en el entorno")
    l, a, h = _caja()
    body = {
        "description": "Musical Box",  #máximo 25 caracteres en EnvíoClick
        "contentValue": int(valor_cop or 0),
        "packages": [{"weight": max(1.0, int(peso_g or 0) / 1000.0), "height": h, "width": a, "length": l,
                      "codValue": 0, "includeGuideCost": False, "codPaymentMethod": "cash"}],
        "origin": {"daneCode": ORIGEN_DANE, "address": ORIGEN_DIRECCION},
        "destination": {"daneCode": str(c_dane_destino), "address": "Avenida Principal 1 # 1-1"},
    }
    r = requests.post(API_ENVIOCLICK, json=body,
                      headers={"Authorization": clave, "Content-Type": "application/json", **_NAV}, timeout=30)
    j = r.json()
    rates = (j.get("data") or {}).get("rates") or []
    if not rates:
        #status_messages: [{"error": ["Unprocessed Entity.", {"description": ["..."]}], ...}]
        detalle = " ".join(" ".join((err[1].get("description") or [])) if isinstance(err, list) and len(err) > 1
                           and isinstance(err[1], dict) else str(m)
                           for m in (j.get("status_messages") or [])
                           for err in ([m.get("error")] if m.get("error") else []))
        raise RuntimeError(f"EnvíoClick no devolvió tarifas {detalle}".strip())
    criterio = (get_config('envio.criterio') or 'menor_costo').strip().upper()
    if criterio == 'MENOR_TIEMPO':
        mejor = min(rates, key=lambda x: (x.get('deliveryDays') or 99, x.get('flete') or 0))
    elif criterio == 'MENOR_COSTO' or criterio not in {x.get('carrier', '').upper() for x in rates}:
        #demo: si el criterio es el nombre de una paquetería y no contesta la ruta, se toma la más barata
        mejor = min(rates, key=lambda x: x.get('flete') or 0)
    else:
        #paquetería preferida por nombre (demo: COORDINADORA)
        mejor = next(x for x in rates if str(x.get('carrier') or '').upper() == criterio)
    return {"p_envio": int(mejor.get("flete") or 0), "carrier": mejor.get("carrier"),
            "product": mejor.get("product"), "id_rate": str(mejor.get("idRate") or ""),
            "dias": mejor.get("deliveryDays")}


def cotizar_con_cache(c_dane_destino, peso_g, valor_cop):
    """Cotización con caché de 24 h por (destino, peso) para no repetir la llamada a cada pedido."""
    clave_peso = int(peso_g or 0)
    actual = CotizacionCache.query.filter_by(c_dane=str(c_dane_destino), peso_g=clave_peso).first()
    if actual and actual.f_creacion > datetime.now() - timedelta(hours=24):
        return {"p_envio": int(actual.p_envio), "carrier": actual.carrier, "product": actual.product,
                "id_rate": actual.id_rate, "dias": actual.dias}
    res = cotizar_envioclick(c_dane_destino, clave_peso, valor_cop)
    db.session.add(CotizacionCache(c_dane=str(c_dane_destino), peso_g=clave_peso, p_envio=res["p_envio"],
                                   carrier=res["carrier"], product=res["product"], id_rate=res["id_rate"], dias=res["dias"]))
    db.session.commit()
    return res


def tarifa_zona(nombre_municipio):
    #respaldo si no se pudo cotizar (municipio sin código o API caído): tarifa fija por zona
    if "bogot" in _norm(nombre_municipio):
        return int(get_config('envio.zona_bogota') or 0), "Envío estimado (Bogotá)"
    return int(get_config('envio.zona_nacional') or 0), "Envío estimado (resto del país)"


def lineas_desde_cats(cats, total=None):
    """'VINILO:2|CD:1' -> líneas falsas para evaluar las reglas sin el carrito de verdad (estimado en vivo)."""
    lineas = []
    for par in (cats or "").split("|"):
        par = par.strip()
        if not par:
            continue
        cat, _, n = par.partition(":")
        cat = cat.strip().upper()
        try:
            n = int(n or 1)
        except ValueError:
            n = 1
        if cat and n > 0:
            lineas.append((type("L", (), {"k_categoria": cat})(), None, n))
    return lineas


def costo_envio(lineas, total, ciudad):
    """El costo de envío del pedido. Devuelve None si la función está apagada (no se cobra),
    o {'p_envio', 'detalle', 'carrier', 'id_rate'} para guardar en la orden y mostrar."""
    if get_config('envio.habilitado') != '1':
        return None
    regla = regla_envio_aplicada(lineas, total)
    if regla:
        return {"p_envio": 0, "detalle": regla, "carrier": None, "id_rate": None}
    peso_g = max(sum(peso_linea(p, c) for p, _v, c, *_r in (lineas or [])), 1000)
    c_dane = resolver_dane(ciudad)
    if not c_dane:
        p, detalle = tarifa_zona(ciudad)
        return {"p_envio": p, "detalle": detalle, "carrier": None, "id_rate": None}
    try:
        q = cotizar_con_cache(c_dane, peso_g, total)
        dias = f" · {q['dias']} días" if q.get('dias') else ""
        return {"p_envio": q["p_envio"], "detalle": f"Envío estimado ({q.get('carrier') or 'paquetería'}){dias}",
                "carrier": q.get("carrier"), "id_rate": q.get("id_rate")}
    except Exception:
        p, detalle = tarifa_zona(ciudad)
        return {"p_envio": p, "detalle": detalle + " (sin cotización en línea)", "carrier": None, "id_rate": None}
