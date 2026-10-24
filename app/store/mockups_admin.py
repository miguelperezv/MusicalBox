"""Sección del panel para generar mockups y piezas de preventa por lanzamiento.

La generación vive en `app/store/mockups.py` (Pillow). Esta capa solo resuelve
el lanzamiento, valida las opciones, guarda los PNG en instance/mockups/admin y
los sirve al panel.
"""
from __future__ import annotations

import re
from pathlib import Path

from flask import abort, current_app, flash, redirect, request, send_from_directory, url_for

from .auditoria import registrar_evento
from .mockups import PRESETS, datos_preventa, etiqueta_archivo, guardar_poc
from .models import Lanzamiento, Producto, get_artist_by_release
from .variantes import COLORES, COLORES_POR_SLUG, EFECTOS, construir_variante
from .views import dashboard, render_seccion


def _carpeta(release_id: int) -> Path:
    return Path(current_app.instance_path) / "mockups" / "admin" / str(release_id)


def _archivos(release_id: int) -> list[dict]:
    carpeta = _carpeta(release_id)
    if not carpeta.exists():
        return []
    salida = []
    for archivo in sorted(carpeta.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True):
        stem = archivo.stem
        preventa = "_preventa" in stem
        if "_story" in stem:
            tipo = "Story 1080×1920"
        elif preventa:
            tipo = "Ficha 1080×1350"
        else:
            tipo = "Mockup 1400×1400"
        salida.append({
            "nombre": archivo.name,
            "etiqueta": etiqueta_archivo(archivo.name),
            "url": url_for("dashboard.mockup_archivo", release_id=release_id,
                           filename=archivo.name, v=int(archivo.stat().st_mtime)),
            "preventa": preventa,
            "tipo": tipo,
            "fecha": archivo.stat().st_mtime,
        })
    return salida


def _producto_vinilo(productos):
    simples = [p for p in productos if getattr(p, "tipo", "SIMPLE") == "SIMPLE"]
    for p in simples:
        if (p.k_categoria or "").upper() == "VINILO":
            return p
    for p in simples:
        if "vinilo" in (p.n_producto or "").lower():
            return p
    return None


def _vinylmockup_local():
    """VinylMockup para elegir una variante dentro del panel local.

    No se busca en el catálogo al cargar la página: el buscador pide las
    sugerencias por AJAX y solo se resuelve el detalle de la variante elegida.
    Así el panel no depende de la red ni muestra errores antes de buscar.
    """
    if not current_app.debug or not current_app.config.get("VINYLMOCKUP_SPIKE"):
        return {"activo": False}

    from .vinylmockup_api import VinylMockupError, obtener_variante

    q = (request.args.get("vm_q") or "").strip()
    variant_id = (request.args.get("vm_id") or "").strip()
    variante, error = None, None
    if variant_id:
        try:
            variante = obtener_variante(variant_id)
        except VinylMockupError as e:
            error = str(e)

    return {
        "activo": True,
        "q": q,
        "variante": variante,
        "error": error,
    }


@dashboard.route("/mockups", methods=["GET", "POST"])
def mockups_admin():
    releases = Lanzamiento.query.order_by(Lanzamiento.f_lanzamiento.desc(), Lanzamiento.id.desc()).all()
    release_id = request.values.get("release", type=int)
    if release_id is None and releases:
        release_id = releases[0].id
    selected = next((l for l in releases if l.id == release_id), None)
    if selected is None and request.method == "GET" and releases:
        selected = releases[0]
        release_id = selected.id

    modo = (request.form.get("modo") if request.method == "POST"
            else request.args.get("modo")) or "presets"
    if modo not in ("presets", "personalizada"):
        modo = "presets"

    if request.method == "POST":
        if not selected:
            flash("Elegí un lanzamiento para generar sus piezas.", "warning")
            return redirect(url_for("dashboard.mockups_admin", modo=modo))
        fondo = request.form.get("fondo", "estudio")
        if fondo not in ("estudio", "claro"):
            fondo = "estudio"

        productos = Producto.query.filter_by(k_lanzamiento=selected.id).all()
        precio = request.form.get("precio", type=int)
        abono = request.form.get("abono", type=int)
        formato = (request.form.get("formato") or "").strip() or None
        eta = (request.form.get("eta") or "").strip() or None
        lps = request.form.get("lps", type=int)
        if lps not in (1, 2):
            lps = None
        envio = request.form.get("envio", type=int)
        if envio is not None and envio <= 0:
            envio = None
        envio_incluido = request.form.get("envio_incluido") == "1"
        preorden_sel = request.form.get("preorden")
        preorden = None
        if preorden_sel in ("si", "no"):
            preorden = preorden_sel == "si"
        variante = None
        if modo == "personalizada":
            acentos = [request.form.get(f"acento_{i}", "") for i in (1, 2, 3)]
            variante = construir_variante(
                request.form.get("color_base", "opaque-black"),
                request.form.get("efecto", "estandar"),
                acentos,
            )
            presets = [variante]
            formato = formato or variante["nombre"]
            descripcion = variante["nombre"]
        else:
            presets = [p for p in request.form.getlist("presets") if p in PRESETS]
            if not presets:
                flash("Elegí al menos un estilo de vinilo.", "warning")
                return redirect(url_for("dashboard.mockups_admin", release=selected.id,
                                        modo=modo))
            descripcion = ", ".join(PRESETS[p]["nombre"] for p in presets)

        # Por ahora el panel genera únicamente la story oficial de Halloween.
        # La ficha 1080×1350 sigue disponible desde el CLI para pruebas puntuales.
        plantilla = "story"
        # La story solo tiene plantilla oficial de pre-orden. Si el título queda
        # en automático, usamos esa variante para no caer en el render viejo.
        if preorden is None:
            preorden = True
            preorden_sel = "si"
        datos = datos_preventa(selected, productos, precio=precio,
                               abono=abono, formato=formato, eta=eta,
                               lps=lps, envio=envio, envio_incluido=envio_incluido,
                               preorden=preorden)
        try:
            rutas = guardar_poc(selected, _carpeta(selected.id), presets=tuple(presets),
                                datos=datos, fondo=fondo, plantilla=plantilla)
        except Exception as e:
            current_app.logger.exception("No se pudieron generar los mockups")
            flash(f"No se pudieron generar las piezas: {e}", "danger")
            return redirect(url_for("dashboard.mockups_admin", release=selected.id,
                                    modo=modo))

        registrar_evento("lanzamiento.mockup", "lanzamiento", selected.id,
                         f"{len(rutas)} pieza(s) · {descripcion} · story")
        flash(f"Listo: {len(rutas)} pieza(s) generadas para {selected.n_lanzamiento}.", "success")
        params = {"release": selected.id, "fondo": fondo, "modo": modo,
                  "plantilla": plantilla}
        if preorden_sel in ("si", "no"):
            params["preorden"] = preorden_sel
        for clave, valor in (("precio", precio), ("abono", abono),
                             ("formato", formato), ("eta", eta),
                             ("lps", lps), ("envio", envio)):
            if valor is not None:
                params[clave] = valor
        params["envio_incluido"] = "1" if envio_incluido else "0"
        if modo == "personalizada":
            params.update(color=variante["color_slug"],
                          efecto=variante["efecto_clave"],
                          acentos=",".join(variante["acentos_slugs"]))
        else:
            params["presets"] = ",".join(presets)
        return redirect(url_for("dashboard.mockups_admin", **params) + "#piezas-generadas")

    productos = Producto.query.filter_by(k_lanzamiento=selected.id).all() if selected else []
    precio_q = request.args.get("precio", type=int)
    abono_q = request.args.get("abono", type=int)
    formato_q = (request.args.get("formato") or "").strip() or None
    eta_q = (request.args.get("eta") or "").strip() or None
    lps_q = request.args.get("lps", type=int)
    if lps_q not in (1, 2):
        lps_q = None
    envio_q = request.args.get("envio", type=int)
    if envio_q is not None and envio_q <= 0:
        envio_q = None
    envio_incluido_q = None
    if "envio_incluido" in request.args:
        envio_incluido_q = request.args.get("envio_incluido") != "0"
    preorden_q = None
    preorden_arg = request.args.get("preorden")
    if preorden_arg in ("si", "no"):
        preorden_q = preorden_arg == "si"
    datos = (datos_preventa(selected, productos, precio=precio_q, abono=abono_q,
                            formato=formato_q, eta=eta_q, lps=lps_q,
                            envio=envio_q, envio_incluido=envio_incluido_q,
                            preorden=preorden_q)
             if selected else {})
    artista = get_artist_by_release(selected.id) if selected else None
    vinilo = _producto_vinilo(productos)
    archivos = _archivos(selected.id) if selected else []
    presets_query = (request.args.get("presets") or "").split(",")
    presets_marcados = [p for p in presets_query if p in PRESETS] or ["negro", "cherry"]
    preorden_actual = request.args.get("preorden")
    if preorden_actual not in ("si", "no"):
        preorden_actual = "auto"

    color_actual = request.args.get("color") or "opaque-black"
    if color_actual not in COLORES_POR_SLUG:
        color_actual = "opaque-black"
    efecto_actual = request.args.get("efecto") or "splatter"
    if efecto_actual not in EFECTOS:
        efecto_actual = "splatter"
    acentos_actuales = [s for s in (request.args.get("acentos") or "").split(",")
                        if s in COLORES_POR_SLUG]
    if not acentos_actuales:
        acentos_actuales = list(EFECTOS[efecto_actual]["acentos"])
    variante_actual = construir_variante(color_actual, efecto_actual, acentos_actuales)

    opciones = [{"l": l, "artista": get_artist_by_release(l.id)} for l in releases]
    return render_seccion(
        "mockups_admin.html",
        releases=releases,
        opciones=opciones,
        selected=selected,
        artista=artista,
        vinilo=vinilo,
        datos=datos,
        archivos=archivos,
        presets=PRESETS,
        presets_marcados=presets_marcados,
        colores=COLORES,
        efectos=EFECTOS,
        modo_actual=modo,
        color_actual=color_actual,
        efecto_actual=efecto_actual,
        acentos_actuales=acentos_actuales,
        variante_actual=variante_actual,
        preorden_actual=preorden_actual,
        vm=_vinylmockup_local(),
    )


@dashboard.route("/mockups/vinylmockup/sugerencias.json")
def mockups_vm_sugerencias():
    """Autocompletado del buscador principal de variantes. Solo local."""
    if not (current_app.debug and current_app.config.get("VINYLMOCKUP_SPIKE")):
        abort(404)
    from .vinylmockup_api import VinylMockupError, buscar_variantes, miniatura_url

    q = (request.args.get("q") or "").strip() or None
    try:
        data = buscar_variantes(q=q)
    except VinylMockupError as e:
        return {"error": str(e), "items": []}
    items = [{"id": i["id"], "name": i["name"], "press_name": i["press_name"],
              "thumb_url": miniatura_url(i["thumb_url"], 160)}
             for i in data["items"][:8]]
    return {"items": items}


@dashboard.route("/mockups/vinylmockup/<variant_id>", methods=["GET"])
def mockups_vm_usar(variant_id):
    """Genera la pieza del lanzamiento usando la imagen de una variante VM.

    Modo evaluación local: requiere debug + VINYLMOCKUP_SPIKE. Las imágenes son
    hoja de VinylMockup/plantas; no se publican sin licencia.
    """
    if not (current_app.debug and current_app.config.get("VINYLMOCKUP_SPIKE")):
        abort(404)
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,}", variant_id):
        abort(404)
    release_id = request.args.get("release", type=int)
    selected = Lanzamiento.query.filter_by(id=release_id).first()
    if selected is None:
        abort(404)

    plantilla = request.args.get("plantilla") or "story"
    if plantilla not in ("ficha", "story"):
        plantilla = "story"
    fondo = request.args.get("fondo") or "estudio"
    if fondo not in ("estudio", "claro"):
        fondo = "estudio"
    lps = request.args.get("lps", type=int)
    if lps not in (1, 2):
        lps = None
    envio = request.args.get("envio", type=int)
    if envio is not None and envio <= 0:
        envio = None
    envio_incluido = request.args.get("envio_incluido") != "0"
    preorden_sel = request.args.get("preorden")
    preorden = None
    if preorden_sel in ("si", "no"):
        preorden = preorden_sel == "si"
    # La story oficial es la de pre-orden: si no se indicó título, usamos esa.
    if plantilla == "story" and preorden is None:
        preorden = True
        preorden_sel = "si"
    precio = request.args.get("precio", type=int)
    abono = request.args.get("abono", type=int)
    eta = (request.args.get("eta") or "").strip() or None

    from PIL import Image
    from .vinylmockup_api import VinylMockupError, descargar_variante

    cache = Path(current_app.instance_path) / "mockups" / "vm_cache"
    try:
        ficha = descargar_variante(variant_id, cache)
        disco = Image.open(ficha["path"]).convert("RGB")
    except (VinylMockupError, OSError) as e:
        current_app.logger.exception("No se pudo usar la variante de VinylMockup")
        flash(f"No se pudo usar la variante de VinylMockup: {e}", "danger")
        return redirect(url_for("dashboard.mockups_admin", release=selected.id,
                                vm_id=variant_id) + "#vinylmockup-local")

    productos = Producto.query.filter_by(k_lanzamiento=selected.id).all()
    datos = datos_preventa(selected, productos,
                           formato=f"Vinilo · {ficha['name']}",
                           precio=precio, abono=abono, eta=eta,
                           lps=lps, envio=envio, envio_incluido=envio_incluido,
                           preorden=preorden)
    try:
        rutas = guardar_poc(selected, _carpeta(selected.id), presets=("negro",),
                            datos=datos, fondo=fondo, plantilla=plantilla, disco=disco)
    except Exception as e:
        current_app.logger.exception("No se pudieron generar las piezas con VinylMockup")
        flash(f"No se pudieron generar las piezas con VinylMockup: {e}", "danger")
        return redirect(url_for("dashboard.mockups_admin", release=selected.id,
                                vm_id=variant_id) + "#vinylmockup-local")

    registrar_evento("lanzamiento.mockup", "lanzamiento", selected.id,
                     f"{len(rutas)} pieza(s) con variante VM "
                     f"«{ficha['name']}» · {plantilla} · fondo {fondo}")
    flash(f"Listo: pieza{'s' if len(rutas) != 1 else ''} generada con la variante "
          f"VM «{ficha['name']}». Están abajo, en «Piezas generadas». Solo uso local: "
          "no publicar sin licencia.", "success")
    params = {"release": selected.id, "fondo": fondo, "plantilla": plantilla,
              "modo": "presets", "vm_id": variant_id,
              "formato": f"Vinilo · {ficha['name']}",
              "envio_incluido": "1" if envio_incluido else "0"}
    for clave, valor in (("precio", precio), ("abono", abono), ("eta", eta),
                         ("lps", lps), ("envio", envio)):
        if valor is not None:
            params[clave] = valor
    if preorden_sel in ("si", "no"):
        params["preorden"] = preorden_sel
    return redirect(url_for("dashboard.mockups_admin", **params) + "#piezas-generadas")


@dashboard.route("/mockups/archivo/<int:release_id>/<filename>/borrar", methods=["POST"])
def mockup_archivo_borrar(release_id, filename):
    """Borra una pieza generada (PNG de esta sección, nunca rutas arbitrarias)."""
    if filename != Path(filename).name or not filename.lower().endswith(".png"):
        abort(404)
    ruta = _carpeta(release_id) / filename
    if not ruta.is_file():
        abort(404)
    ruta.unlink()
    registrar_evento("lanzamiento.mockup", "lanzamiento", release_id,
                     f"Pieza borrada: {filename}")
    flash(f"Se borró la pieza {filename}.", "success")
    return redirect(url_for("dashboard.mockups_admin", release=release_id)
                    + "#piezas-generadas")


@dashboard.route("/mockups/archivo/<int:release_id>/<filename>")
def mockup_archivo(release_id, filename):
    # Solo se sirven PNG generados por esta sección, nunca rutas arbitrarias.
    if filename != Path(filename).name or not filename.lower().endswith(".png"):
        abort(404)
    carpeta = _carpeta(release_id)
    return send_from_directory(carpeta, filename, max_age=3600)
