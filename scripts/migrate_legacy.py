"""Crea instance/musicalbox.sqlite3 juntando los datos de las dos apps anteriores.

- Tienda:  app/musicalboxPRUEBA.sqlite3 (la BD que usaba la config de MusicalBox)
- Manager: ../musical_box_manager/instance/MBOX_MANAGER.sqlite3

Las BD originales solo se leen. Uso:
    python scripts/migrate_legacy.py [--store RUTA] [--manager RUTA] [--force]
"""
import argparse
import os
import secrets
import sqlite3
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import create_app
from app.db import db
from app.store.models import Usuario, Solicitud

STORE_TABLES = ["rol", "categoria", "genero", "artista", "lanzamiento", "lanzamiento__artista",
                "lanzamiento__genero", "usuario", "producto", "imagen", "invoice", "item"]


def parse_dt(value):
    return datetime.fromisoformat(value) if value else None


def copy_store(conn, store_db):
    conn.execute("ATTACH DATABASE ? AS legacy", (store_db,))
    for table in STORE_TABLES:
        new_cols = {r[1] for r in conn.execute(f'PRAGMA main.table_info("{table}")')}
        old_cols = [r[1] for r in conn.execute(f'PRAGMA legacy.table_info("{table}")')]
        cols = ", ".join(f'"{c}"' for c in old_cols if c in new_cols)
        if not cols:
            continue
        n = conn.execute(f'INSERT OR IGNORE INTO main."{table}" ({cols}) SELECT {cols} FROM legacy."{table}"').rowcount
        print(f"  tienda.{table}: {n}")
    conn.commit()
    conn.execute("DETACH DATABASE legacy")


def copy_manager(manager_db):
    src = sqlite3.connect(manager_db)
    src.row_factory = sqlite3.Row

    #usuarios: se unen por email (en la tienda el email es único)
    user_map = {}
    for u in src.execute("SELECT * FROM usuario ORDER BY id"):
        email = (u["email"] or f"cliente{u['id']}@sin-email.local").strip()
        user = Usuario.query.filter(db.func.lower(Usuario.email_usuario) == email.lower()).first()
        if not user:
            es_admin = u["tipo_usuario"] == "ADMIN"
            user = Usuario(k_rol="ADMIN" if es_admin else "CLIENTE", n_usuario=u["nombre"], ape_usuario=u["apellido"] or "",
                           email_usuario=email, pwd_usuario=u["pwd"] if es_admin else secrets.token_hex(16),
                           f_registro=parse_dt(u["created_on"]))
            db.session.add(user)
        user.tipo_id = user.tipo_id or u["tipo_id"]
        user.num_id = user.num_id or u["num_id"]
        user.dir_usuario = user.dir_usuario or u["direccion"]
        user.lugar_usuario = user.lugar_usuario or u["ciudad"]
        user.barrio_usuario = user.barrio_usuario or u["barrio"]
        user.cel_usuario = user.cel_usuario or u["celular"]
        db.session.flush()
        user_map[u["id"]] = user.id
    print(f"  manager.usuario: {len(user_map)} -> {len(set(user_map.values()))} usuarios")

    #los productos del manager eran solo nombre + descripción: pasan como texto de la solicitud
    productos = {p["id"]: p for p in src.execute("SELECT * FROM producto")}
    n = 0
    for s in src.execute("SELECT * FROM solicitud ORDER BY id"):
        if s["k_usuario"] not in user_map:
            continue
        p = productos.get(s["k_producto"]) if s["k_producto"] not in (None, "") else None
        db.session.add(Solicitud(k_usuario=user_map[s["k_usuario"]], estado=s["estado"] or "ACTIVO",
                                 n_producto_solicitado=(p["nombre"] if p else None) or "(sin producto)",
                                 d_producto_solicitado=(p["descripcion"] or None) if p else None,
                                 f_solicitud=parse_dt(s["created_on"]), f_actualizacion=parse_dt(s["updated_on"])))
        n += 1
    db.session.commit()
    print(f"  manager.solicitud: {n}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", default=os.path.join(ROOT, "app", "musicalboxPRUEBA.sqlite3"))
    parser.add_argument("--manager", default=os.path.join(ROOT, "..", "musical_box_manager", "instance", "MBOX_MANAGER.sqlite3"))
    parser.add_argument("--force", action="store_true", help="reemplaza instance/musicalbox.sqlite3 si ya existe")
    args = parser.parse_args()

    target = os.path.join(ROOT, "instance", "musicalbox.sqlite3")
    if os.path.exists(target):
        if not args.force:
            sys.exit(f"{target} ya existe, usa --force para reemplazarla")
        os.remove(target)

    app = create_app()
    with app.app_context():
        conn = db.engine.raw_connection()
        try:
            if os.path.exists(args.store):
                print("Copiando tienda desde", args.store)
                copy_store(conn, args.store)
            else:
                print("No se encontró la BD de la tienda:", args.store)
        finally:
            conn.close()

        if os.path.exists(args.manager):
            print("Copiando manager desde", args.manager)
            copy_manager(args.manager)
        else:
            print("No se encontró la BD del manager:", args.manager)
    print("Listo:", target)


if __name__ == "__main__":
    main()
