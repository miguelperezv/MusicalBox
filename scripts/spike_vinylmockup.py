#!/usr/bin/env python
"""Spike local de la API interna de VinylMockup (solo lectura).

No está conectado a la web pública ni al panel. Las imágenes se guardan en
la carpeta temporal del sistema y no se commitean. No usar en producción sin
licencia.

Uso:
    venv/bin/python scripts/spike_vinylmockup.py buscar clear
    venv/bin/python scripts/spike_vinylmockup.py buscar splatter --limit 5
    venv/bin/python scripts/spike_vinylmockup.py variante 1rMSmdRmr1jOiLnZPpH1zc
    venv/bin/python scripts/spike_vinylmockup.py prensa 1o0Xf6NpetuZObPKw15vtQ
    venv/bin/python scripts/spike_vinylmockup.py descargar 1rMSmdRmr1jOiLnZPpH1zc
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from app.store.vinylmockup_api import (  # noqa: E402
    VinylMockupError, buscar_variantes, descargar_variante,
    obtener_prensa, obtener_variante,
)


def _corte(texto: str, ancho: int) -> str:
    texto = str(texto or "")
    return texto if len(texto) <= ancho else texto[: ancho - 1] + "…"


def _kb(bytes_: int | None) -> str:
    if not bytes_:
        return "?"
    return f"{bytes_ / 1024:.0f} KB"


def _carpeta_permitida(carpeta: Path) -> bool:
    """Evita guardar imágenes en rutas que git podría trackear.

    Fuera del repo se permite cualquier carpeta; dentro, solo `instance/`,
    que ya está en `.gitignore`.
    """
    try:
        relativa = carpeta.resolve().relative_to(RAIZ.resolve())
    except ValueError:
        return True
    return bool(relativa.parts) and relativa.parts[0] == "instance"


def _imprimir_busqueda(data: dict, limite: int) -> None:
    items = data["items"][:limite]
    if not items:
        print("Sin resultados.")
        return
    print(f"Resultados: {data['total']} · página {data['page']} · "
          f"{'hay más' if data['has_next'] else 'última página'}")
    print(f"{'NOMBRE':<34} {'PRENSA':<27} {'ID':<22}")
    print("-" * 85)
    for v in items:
        print(f"{_corte(v['name'], 34):<34} "
              f"{_corte(v['press_name'], 27):<27} "
              f"{v['id']:<22}")
    if len(data["items"]) > limite:
        print(f"\n(mostrando {limite} de {len(data['items'])} de esta página)")


def _imprimir_variante(v: dict) -> None:
    print(f"{v['name']} · {v['press_name']}")
    print(f"  id:        {v['id']}")
    print(f"  slug:      {v['slug']}")
    print(f"  prensa:    {v['press_name']} ({v['press_id']})")
    print(f"  tipo:      {v['type'] or '-'}")
    print(f"  estilo:    {v['style'] or '-'}")
    print(f"  colores:   {', '.join(v['colors']) or '-'}")
    if v["image_url"]:
        print(f"  imagen:    {v['image_width']}×{v['image_height']} · "
              f"{_kb(v['image_bytes'])} · {v['image_content_type']}")
        print(f"  url:       {v['image_url']}")
    print(f"  página:    {v['page_url']}")


def _imprimir_prensa(p: dict) -> None:
    print(f"{p['name']}")
    print(f"  id:      {p['id']}")
    print(f"  slug:    {p['slug']}")
    print(f"  web:     {p['website'] or '-'}")
    print(f"  logo:    {p['logo_url'] or '-'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Spike local de la API interna de VinylMockup. Solo lectura; "
                    "no usar en producción sin licencia.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_buscar = sub.add_parser("buscar", help="Busca variantes por texto")
    p_buscar.add_argument("q", nargs="?", default=None, help="Texto a buscar, ej. clear")
    p_buscar.add_argument("--press", help="ID de Contentful de la prensa (no el slug)")
    p_buscar.add_argument("--page", type=int, default=1)
    p_buscar.add_argument("--limit", type=int, default=10,
                          help="Cuántas filas mostrar de la página (máx. 20)")
    p_buscar.add_argument("--json", action="store_true", help="Salida JSON")

    p_variante = sub.add_parser("variante", help="Muestra el detalle de una variante")
    p_variante.add_argument("id")
    p_variante.add_argument("--json", action="store_true", help="Salida JSON")

    p_prensa = sub.add_parser("prensa", help="Muestra el detalle de una prensa")
    p_prensa.add_argument("id")
    p_prensa.add_argument("--json", action="store_true", help="Salida JSON")

    p_descargar = sub.add_parser("descargar", help="Baja una imagen puntual a /tmp")
    p_descargar.add_argument("id")
    p_descargar.add_argument("--out", default=None,
                             help="Carpeta de salida: fuera del repo o dentro de instance/ "
                                  "(por defecto, la carpeta temporal del sistema)")
    p_descargar.add_argument("--json", action="store_true", help="Salida JSON")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "buscar":
            limite = max(1, min(args.limit, 20))
            data = buscar_variantes(q=args.q, press=args.press, page=args.page)
            if args.json:
                data["items"] = data["items"][:limite]
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                _imprimir_busqueda(data, limite)
            return 0

        if args.cmd == "variante":
            v = obtener_variante(args.id)
            if not v:
                print("No se encontró la variante.", file=sys.stderr)
                return 1
            if args.json:
                print(json.dumps(v, ensure_ascii=False, indent=2))
            else:
                _imprimir_variante(v)
            return 0

        if args.cmd == "prensa":
            p = obtener_prensa(args.id)
            if not p:
                print("No se encontró la prensa.", file=sys.stderr)
                return 1
            if args.json:
                print(json.dumps(p, ensure_ascii=False, indent=2))
            else:
                _imprimir_prensa(p)
            return 0

        if args.cmd == "descargar":
            carpeta = (Path(args.out).expanduser() if args.out
                       else Path(tempfile.gettempdir()) / "vinylmockup_spike")
            if not _carpeta_permitida(carpeta):
                print("Error: para no meter assets en git, usá una carpeta fuera "
                      "del repo o dentro de instance/.", file=sys.stderr)
                return 2
            v = descargar_variante(args.id, carpeta)
            if args.json:
                print(json.dumps({
                    "id": v["id"], "name": v["name"], "path": v["path"],
                    "bytes": v["bytes"], "image_url": v["image_url"],
                }, ensure_ascii=False, indent=2))
            else:
                print(f"Guardado: {v['path']}")
                print(f"Imagen:   {v['image_width']}×{v['image_height']} · {_kb(v['bytes'])}")
                print("Aviso:   prueba local; no publicar sin licencia.")
            return 0
    except VinylMockupError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
