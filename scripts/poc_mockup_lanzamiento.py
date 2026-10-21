#!/usr/bin/env python
"""POC: genera mockup y pieza de preventa para un lanzamiento.

Uso:
    venv/bin/python scripts/poc_mockup_lanzamiento.py 2 --demo
    venv/bin/python scripts/poc_mockup_lanzamiento.py 2 --presets negro,color,splatter,picture
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from app import create_app  # noqa: E402
from app.db import db  # noqa: E402
from app.store.mockups import PRESETS, datos_preventa, guardar_poc  # noqa: E402
from app.store.models import Lanzamiento, Producto  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="POC de mockups por lanzamiento")
    parser.add_argument("release", type=int, help="ID del lanzamiento")
    parser.add_argument("--presets", default="negro,color,splatter,picture",
                        help="Presets separados por coma: " + ", ".join(PRESETS))
    parser.add_argument("--salida", default="instance/mockups", help="Carpeta de salida")
    parser.add_argument("--fondo", choices=("estudio", "claro"), default="estudio",
                        help="Fondo del mockup: estudio oscuro o claro")
    parser.add_argument("--demo", action="store_true",
                        help="Usa precio/abono/fecha de ejemplo si el lanzamiento no tiene vinilo")
    parser.add_argument("--precio", type=float, help="Precio de venta para la pieza")
    parser.add_argument("--abono", type=float, help="Valor de la reserva")
    parser.add_argument("--formato", help="Texto del formato, ej. Vinilo negro estándar")
    parser.add_argument("--eta", help="Texto de llegada, ej. Diciembre 2026")
    args = parser.parse_args()

    presets = tuple(p.strip() for p in args.presets.split(",") if p.strip())
    desconocidos = [p for p in presets if p not in PRESETS]
    if desconocidos:
        parser.error("Presets desconocidos: " + ", ".join(desconocidos))
    if not presets:
        parser.error("Elegí al menos un preset")

    app = create_app()
    with app.app_context():
        lanzamiento = db.session.get(Lanzamiento, args.release)
        if not lanzamiento:
            print(f"No existe el lanzamiento {args.release}", file=sys.stderr)
            return 1

        productos = Producto.query.filter_by(k_lanzamiento=lanzamiento.id).all()
        precio = args.precio
        abono = args.abono
        formato = args.formato
        eta = args.eta
        if args.demo:
            precio = precio if precio is not None else 150000
            abono = abono if abono is not None else 95000
            formato = formato or PRESETS["negro"]["nombre"]
            eta = eta or "Diciembre 2026"

        datos = datos_preventa(lanzamiento, productos, precio=precio, abono=abono,
                               formato=formato, eta=eta)
        salida = (RAIZ / args.salida).resolve()
        rutas = guardar_poc(lanzamiento, salida, presets=presets, datos=datos, fondo=args.fondo)

        print(f"Lanzamiento: {datos['album']} · {datos['artista']}")
        for ruta in rutas:
            print(ruta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
