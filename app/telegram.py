"""Avisos al admin por Telegram (bot API).

TG_BACKEND:
  real    -> llama a api.telegram.org (requiere TG_BOT_TOKEN y TG_ADMIN_CHAT_ID)
  consola -> imprime y guarda en instance/telegram/ (desarrollo; también si no hay credenciales)
  memoria -> los guarda en app.extensions["telegram_enviados"] (pruebas)
  off     -> no hace nada

Los avisos llevan parse_mode HTML (negritas, links <a>): los textos se arman en
app/store/notif_admin.py escapando los valores dinámicos.

Nunca lanza excepciones: si un aviso falla, se registra y la operación que lo pidió sigue adelante.
"""
import os
import sys
from datetime import datetime

import requests

from flask import current_app

#la consola de Windows no soporta emoji en stdout; se fuerza UTF-8 para no perder el aviso
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def enviar_admin(mensaje):
    cfg = current_app.config
    token = (cfg.get("TG_BOT_TOKEN") or "").strip()
    chat = (cfg.get("TG_ADMIN_CHAT_ID") or "").strip()
    backend = (cfg.get("TG_BACKEND") or "real").lower()
    if not token or not chat:
        backend = "consola"
    try:
        if backend == "off":
            return True
        if backend == "memoria":
            current_app.extensions.setdefault("telegram_enviados", []).append(mensaje)
            return True
        if backend == "real":
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": mensaje, "parse_mode": "HTML",
                      "disable_web_page_preview": True},
                timeout=10,
            )
            if r.status_code != 200:
                print(f"ERROR Telegram {r.status_code}: {r.text[:200]}")
                return False
            return True
        carpeta = os.path.join(current_app.instance_path, "telegram")
        os.makedirs(carpeta, exist_ok=True)
        nombre = datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".txt"
        with open(os.path.join(carpeta, nombre), "w", encoding="utf-8") as f:
            f.write(mensaje + "\n")
        print(f"\n===== TELEGRAM (consola) al admin: {mensaje}\n===== guardado en instance/telegram/{nombre}\n")
        return True
    except Exception as e:
        print(f"ERROR enviando aviso de Telegram: {e}")
        return False
