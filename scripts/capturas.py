"""Toma capturas de las páginas principales en escritorio y celular (necesita la app corriendo).

    python scripts/capturas.py [carpeta_salida] [--base http://127.0.0.1:5000]

Entra como admin (el primero de la BD) para capturar también el panel.
"""
import argparse
import os
import sqlite3

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PUBLICAS = ["/", "/releases/", "/releases/1", "/products/", "/purchase/", "/solicitud/", "/login", "/signup"]
PRIVADAS = ["/account", "/dashboard"]
VIEWPORTS = {"desktop": {"width": 1366, "height": 900}, "mobile": {"width": 390, "height": 844}}


def nombre(path):
    return path.strip("/").replace("/", "_") or "home"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("salida", nargs="?", default=os.path.join(ROOT, ".capturas", "actual"))
    parser.add_argument("--base", default="http://127.0.0.1:5000")
    args = parser.parse_args()
    os.makedirs(args.salida, exist_ok=True)

    db = sqlite3.connect(os.path.join(ROOT, "instance", "musicalbox.sqlite3"))
    email, pwd = db.execute("SELECT email_usuario, pwd_usuario FROM usuario WHERE k_rol='ADMIN' ORDER BY id").fetchone()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for vp_name, vp in VIEWPORTS.items():
            ctx = browser.new_context(viewport=vp, is_mobile=vp_name == "mobile", has_touch=vp_name == "mobile")
            page = ctx.new_page()
            errores = []
            page.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errores.append(str(e)))
            for path in PUBLICAS + ["LOGIN"] + PRIVADAS:
                if path == "LOGIN":
                    page.goto(args.base + "/login")
                    page.fill("input[name=email_usuario]", email)
                    page.fill("input[name=pwd_usuario]", pwd)
                    page.click("form [type=submit]")
                    page.wait_for_load_state("networkidle")
                    continue
                errores.clear()
                page.goto(args.base + path, wait_until="networkidle")
                page.wait_for_timeout(500)
                #ancho real vs viewport: detecta scroll horizontal (no responsive)
                overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                archivo = os.path.join(args.salida, f"{vp_name}_{nombre(path)}.png")
                page.screenshot(path=archivo, full_page=True)
                print(f"{vp_name:8} {path:16} overflow={overflow:>4}px errores_js={len(errores)} {errores[:2]}")
            ctx.close()
        browser.close()


if __name__ == "__main__":
    main()
