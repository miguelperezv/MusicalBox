#validación de municipios contra la lista DIVIPOLA que usa el autocompletado del checkout.
#el envío se cotiza por municipio: aceptar texto libre permitía pagar la tarifa de una zona
#y escribir otra dirección (o una ciudad inventada) para pagar menos.
import json
import re
import unicodedata

from flask import current_app

_CACHE = None


def _norm(texto):
    t = unicodedata.normalize("NFD", (texto or "").strip().lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t)).strip()


def _lista():
    #normalizado -> texto de la lista; Bogotá se maneja como un solo municipio
    global _CACHE
    if _CACHE is None:
        with current_app.open_resource("static/data/municipios_colombia.json") as f:
            municipios = set(json.load(f))
        municipios.discard("Bogotá, D.C., Bogotá, D.C.")
        municipios.add("Bogotá D.C.")
        por_nombre = {}
        for m in municipios:
            clave = _norm(m)
            if clave:
                por_nombre[clave] = m
        _CACHE = por_nombre
    return _CACHE


def canonico(texto):
    """Devuelve el municipio tal como está en la lista (ej. "Medellín, Antioquia") o None.

    Acepta el texto completo del autocompletado y, si el nombre no es ambiguo, solo el
    municipio ("Medellín"). Bogotá acepta también localidades ("Suba, Bogotá D.C.").
    """
    t = _norm(texto)
    if not t:
        return None
    lista = _lista()
    if t in lista:
        return lista[t]
    #cualquier texto que declare Bogotá se cotiza como Bogotá (las localidades no cambian la tarifa)
    if "bogota" in t:
        return "Bogotá D.C."
    #solo el nombre del municipio: se acepta si no hay homónimos en otros departamentos.
    #se compara contra las palabras del nombre oficial para aceptar "Cali" (Santiago de Cali)
    #y "Cúcuta" (San José de Cúcuta), que son los nombres que escribe la gente.
    partes = [p.strip() for p in (texto or "").split(",") if p.strip()]
    if not partes:
        return None
    objetivo = _norm(partes[0])

    def nombres(m):
        return _norm(m.split(",", 1)[0]).split()

    candidatos = [m for m in lista.values()
                  if objetivo == " ".join(nombres(m)) or objetivo in nombres(m)]
    if len(partes) > 1:
        dep = _norm(partes[1])
        candidatos = [m for m in candidatos
                      if dep and dep in _norm(m.split(",", 1)[1] if "," in m else "")]
    return candidatos[0] if len(candidatos) == 1 else None


def mismo_municipio(a, b):
    """True si los dos textos apuntan al mismo municipio (aunque uno venga sin departamento)."""
    ca, cb = canonico(a), canonico(b)
    if ca and cb:
        return _norm(ca) == _norm(cb)
    #si alguno no está en la lista (dato viejo), se comparan los nombres tal como vienen
    return _norm((a or "").split(",")[0]) == _norm((b or "").split(",")[0]) and bool(_norm(a))
