"""Envío de correos.

MAIL_BACKEND:
  consola -> imprime el correo y lo guarda como .eml en instance/correos/ (desarrollo, por defecto)
  smtp    -> MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD, MAIL_USE_TLS, MAIL_FROM
  memoria -> los guarda en app.extensions["correos_enviados"] (pruebas)

Nunca lanza excepciones: si el correo falla, se registra y la operación que lo pidió sigue adelante.
"""
import os
import re
import smtplib
from datetime import datetime
from email.message import EmailMessage

from flask import current_app


def _mensaje(destino, asunto, texto, html):
    msg = EmailMessage()
    msg["From"] = current_app.config["MAIL_FROM"]
    msg["To"] = destino
    msg["Subject"] = asunto
    msg.set_content(texto)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


def enviar(destino, asunto, texto, html=None):
    backend = current_app.config.get("MAIL_BACKEND", "consola")
    try:
        msg = _mensaje(destino, asunto, texto, html)
        if backend == "memoria":
            current_app.extensions.setdefault("correos_enviados", []).append(msg)
        elif backend == "smtp":
            cfg = current_app.config
            with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=15) as smtp:
                if cfg.get("MAIL_USE_TLS"):
                    smtp.starttls()
                if cfg.get("MAIL_USERNAME"):
                    smtp.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
                smtp.send_message(msg)
        else:
            carpeta = os.path.join(current_app.instance_path, "correos")
            os.makedirs(carpeta, exist_ok=True)
            nombre = datetime.now().strftime("%Y%m%d-%H%M%S-") + re.sub(r"[^a-z0-9]+", "-", asunto.lower())[:40] + ".eml"
            with open(os.path.join(carpeta, nombre), "wb") as f:
                f.write(bytes(msg))
            print(f"\n===== CORREO (consola) para {destino}: {asunto}\n{texto}\n===== guardado en instance/correos/{nombre}\n")
        return True
    except Exception as e:
        print(f"ERROR enviando correo a {destino} ({asunto}): {e}")
        return False
