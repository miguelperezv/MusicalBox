"""Sección del panel para generar mockups y piezas de preventa por lanzamiento.

La generación vive en `app/store/mockups.py` (Pillow). Esta capa solo resuelve
el lanzamiento, valida las opciones, guarda los PNG en instance/mockups/admin y
los sirve al panel.
"""
from __future__ import annotations

from pathlib import Path

from flask import abort, current_app, flash, redirect, request, send_from_directory, url_for

from .auditoria import registrar_evento
from .mockups import PRESETS, datos_preventa, guardar_poc
from .models import Lanzamiento, Producto, get_artist_by_release
from .views import dashboard, render_seccion


def _carpeta(release_id: int) -> Path:
    return Path(current_app.instance_path) / "mockups" / "admin" / str(release_id)


def _archivos(release_id: int) -> list[dict]:
    carpeta = _carpeta(release_id)
    if not carpeta.exists():
        return []
    salida = []
    for archivo in sorted(carpeta.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True):
        salida.append({
            "nombre": archivo.name,
            "url": url_for("dashboard.mockup_archivo", release_id=release_id,
                           filename=archivo.name, v=int(archivo.stat().st_mtime)),
            "preventa": archivo.name.endswith("_preventa.png"),
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

    if request.method == "POST":
        if not selected:
            flash("Elegí un lanzamiento para generar sus piezas.", "warning")
            return redirect(url_for("dashboard.mockups_admin"))
        presets = [p for p in request.form.getlist("presets") if p in PRESETS]
        if not presets:
            flash("Elegí al menos un estilo de vinilo.", "warning")
            return redirect(url_for("dashboard.mockups_admin", release=selected.id))
        fondo = request.form.get("fondo", "claro")
        if fondo not in ("estudio", "claro"):
            fondo = "claro"

        productos = Producto.query.filter_by(k_lanzamiento=selected.id).all()
        precio = request.form.get("precio", type=int)
        abono = request.form.get("abono", type=int)
        formato = (request.form.get("formato") or "").strip() or None
        eta = (request.form.get("eta") or "").strip() or None
        datos = datos_preventa(selected, productos, precio=precio,
                               abono=abono, formato=formato, eta=eta)
        try:
            rutas = guardar_poc(selected, _carpeta(selected.id), presets=tuple(presets),
                                datos=datos, fondo=fondo)
        except Exception as e:
            current_app.logger.exception("No se pudieron generar los mockups")
            flash(f"No se pudieron generar las piezas: {e}", "danger")
            return redirect(url_for("dashboard.mockups_admin", release=selected.id))

        registrar_evento("lanzamiento.mockup", "lanzamiento", selected.id,
                         f"{len(rutas)} pieza(s) · {', '.join(presets)} · fondo {fondo}")
        flash(f"Listo: {len(rutas)} pieza(s) generadas para {selected.n_lanzamiento}.", "success")
        return redirect(url_for("dashboard.mockups_admin", release=selected.id,
                                fondo=fondo, presets=",".join(presets)))

    productos = Producto.query.filter_by(k_lanzamiento=selected.id).all() if selected else []
    datos = datos_preventa(selected, productos) if selected else {}
    artista = get_artist_by_release(selected.id) if selected else None
    vinilo = _producto_vinilo(productos)
    archivos = _archivos(selected.id) if selected else []
    presets_query = (request.args.get("presets") or "").split(",")
    presets_marcados = [p for p in presets_query if p in PRESETS] or ["negro", "cherry"]

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
        fondo_actual=request.args.get("fondo", "claro"),
    )


@dashboard.route("/mockups/archivo/<int:release_id>/<filename>")
def mockup_archivo(release_id, filename):
    # Solo se sirven PNG generados por esta sección, nunca rutas arbitrarias.
    if filename != Path(filename).name or not filename.lower().endswith(".png"):
        abort(404)
    carpeta = _carpeta(release_id)
    return send_from_directory(carpeta, filename, max_age=3600)
