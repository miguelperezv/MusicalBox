"""Avisos y bot al admin por Telegram (bot API).

TG_BACKEND:
  real    -> llama a api.telegram.org (requiere TG_BOT_TOKEN y TG_ADMIN_CHAT_ID)
  consola -> imprime y guarda en instance/telegram/ (desarrollo; también si no hay credenciales)
  memoria -> los guarda en app.extensions["telegram_enviados"] (pruebas)
  off     -> no hace nada

Los avisos llevan parse_mode HTML (negritas, links <a>): los textos se arman en
app/store/notif_admin.py escapando los valores dinámicos.

Bot de cotización (webhook /telegram-bot/webhook): el admin escribe al bot y el bot
responde por el propio canal (sin parse_mode):
  lista                      -> solicitudes pendientes
  <id>                       -> detalle de la solicitud
  <id> <precio>...           -> cotizar (1 precio: para todos; N precios: por ítem, en orden)
  buscar <id> <texto>        -> top 5 lanzamientos encontrados
  buscar <id> <texto> <opcion> <precio> -> cotizar asociando el lanzamiento elegido
La respuesta de cotización incluye botón "Copiar" (copy_text) con el mensaje listo para el cliente.
Solo responde al chat TG_ADMIN_CHAT_ID; si se configura TG_WEBHOOK_SECRET, exige ese
secret_token en el webhook (segundo candado).

Nunca lanza excepciones: si un aviso falla, se registra y la operación que lo pidió sigue adelante.
"""
import os
from datetime import datetime

import requests
from flask import Blueprint, current_app, jsonify, request

telegram_bp = Blueprint('telegram_bot', __name__)


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


def remitir(chat_id, texto, copiar=None):
    #envío directo del bot (sin HTML); si hay `copiar`, va con botón inline de copiar
    token = (current_app.config.get("TG_BOT_TOKEN") or "").strip()
    if not token:
        return False
    payload = {"chat_id": chat_id, "text": texto, "disable_web_page_preview": True}
    if copiar:
        payload["reply_markup"] = {"inline_keyboard": [[{"type": "copy_text", "text": "📋 Copiar",
                                                        "copy_text": {"text": copiar}}]]}
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"ERROR bot Telegram: {e}")
        return False


def _cop_bot(total):
    return "${:,}".format(int(total or 0)).replace(",", ".")


def _uso():
    return ("Comandos:\n"
            "· lista — solicitudes pendientes\n"
            "· <id> — detalle de la solicitud\n"
            "· <id> <precio>… — cotizar (1 precio: para todos; N: por ítem, en orden)\n"
            "· buscar <id> <texto> — buscar el disco (top 5)\n"
            "· buscar <id> <texto> <opcion> <precio> — cotizar con el disco elegido")


def _lineas_items(s):
    from .store.models import items_efectivos
    lineas = []
    for it in items_efectivos(s):
        n = int(it.cantidad or 1)
        extra = f" ({it.categoria})" if it.categoria else ""
        desc = f" · “{it.descripcion}”" if it.descripcion else ""
        precio = f" · {_cop_bot(it.precio_unit)}" if it.precio_unit else ""
        lineas.append(f"{n} × {it.nombre or 'pedido'}{extra}{desc}{precio}")
    return lineas


def _cmd_lista(chat_id):
    from .store.models import get_all_solicitudes
    pendientes = [s for s in get_all_solicitudes()[:12]
                  if s.estado in ("ACTIVO", "EN PROCESO", "COTIZADA", "REVISADA")]
    lineas = []
    for s in pendientes:
        lineas_s = _lineas_items(s)
        primero = (lineas_s[0][:60]) if lineas_s else "sin ítems"
        lineas.append(f"#{s.id} · {s.estado} · {s.cel_contacto or 'sin contacto'} · {primero}")
    remitir(chat_id, ("Solicitudes pendientes:\n" + "\n".join(lineas) if lineas else "Sin pendientes ahora.") +
            "\n\n" + _uso())


def _cmd_detalle(chat_id, k):
    from .store.models import Solicitud, items_efectivos
    s = Solicitud.query.get(k)
    if not s:
        return remitir(chat_id, f"No existe la solicitud #{k}. (usa 'lista')")
    lineas = _lineas_items(s)
    correo = f" · {s.email_contacto}" if s.email_contacto else ""
    remitir(chat_id, (f"Solicitud #{s.id} · {s.estado}\n"
                      f"Cliente: {s.cel_contacto or 'sin contacto'}{correo}\n"
                      + "\n".join(lineas) + "\n\n"
                      f"Para cotizar: {s.id} <precio>… (o mira 'lista')"))


def _cmd_cotizar(chat_id, k, rest):
    from .store.models import Solicitud, cotizar_solicitud
    s = Solicitud.query.get(k)
    if not s:
        return remitir(chat_id, f"No existe la solicitud #{k}. (usa 'lista')")
    if not rest:
        return _cmd_detalle(chat_id, k)
    if not all(x.isdigit() for x in rest):
        return remitir(chat_id, "Precios en pesos, solo números.\n\n" + _uso())
    precios = [int(x) for x in rest]
    items = list(s.items)
    if len(precios) == 1 and len(items) > 1:
        precios = precios * len(items)  #un solo precio: se aplica a todos los ítems
    if len(precios) != len(items):
        return remitir(chat_id, f"La solicitud {k} tiene {len(items)} ítem(s): dame {len(items)} precio(s) o uno solo para todos.")
    lineas = [{"k_producto": it.k_producto, "k_lanzamiento": it.k_lanzamiento,
               "cantidad": it.cantidad, "precio": p} for it, p in zip(items, precios)]
    token, err = cotizar_solicitud(k, lineas, None)
    if err:
        return remitir(chat_id, f"No se pudo cotizar la #{k}: {err}")
    from flask import url_for
    total = sum(p * int(it.cantidad or 1) for it, p in zip(items, precios))
    link = url_for('solicitud.confirmar', token=token, _external=True)
    bloques = [f"🎵 ¡Ya tienes precio, solicitud #{k}!", "",
               "\n".join(f"{int(it.cantidad or 1)} × {it.nombre or 'pedido'} · {_cop_bot(p * int(it.cantidad or 1))}"
                          for it, p in zip(items, precios)),
               f"Total: {_cop_bot(total)}", "", f"Paga y enviarlo: {link}"]
    remitir(chat_id, f"✅ Solicitud #{k} cotizada ({_cop_bot(total)}).\nPanel: {url_for('solicitud.lista', _external=True)}")
    remitir(chat_id, "Mensaje listo para el cliente 👇", copiar="\n".join(bloques))


def _cmd_buscar(chat_id, rest):
    from .store.musicapi import buscar_albumes_spotify
    if not rest or not rest[0].isdigit():
        return remitir(chat_id, "Uso: buscar <id> <texto> [opcion precio]\n\n" + _uso())
    k = int(rest[0])
    if len(rest) >= 4 and rest[-1].isdigit() and rest[-2].isdigit():
        opcion, precio, texto = int(rest[-2]), int(rest[-1]), " ".join(rest[1:-2])
    else:
        opcion, precio, texto = None, None, " ".join(rest[1:])
    if not texto:
        return remitir(chat_id, "Falta el nombre del disco.\n\n" + _uso())
    res = buscar_albumes_spotify(texto)
    if res.get("error"):
        return remitir(chat_id, f"Búsqueda: {res['error']}")
    items = res.get("items", [])[:5]
    if not items:
        return remitir(chat_id, f"No encontré álbumes para “{texto}”.")
    lineas = [f"{i+1}. {a['nombre']} — {a['artista']} ({a['fecha'][:4] or 's/f'})" for i, a in enumerate(items)]
    if opcion is None:
        return remitir(chat_id, f"Resultados para “{texto}”:\n" + "\n".join(lineas) +
                        f"\n\nPara cotizar: buscar {k} {texto} <opcion> <precio>")
    if not 1 <= opcion <= len(items):
        return remitir(chat_id, f"Opción fuera de rango (1 a {len(items)}).")
    from .store.models import Solicitud, cotizar_solicitud, buscar_o_crear_lanzamiento_spotify
    s = Solicitud.query.get(k)
    if not s:
        return remitir(chat_id, f"No existe la solicitud #{k}.")
    album = items[opcion - 1]
    lanza, _ = buscar_o_crear_lanzamiento_spotify({
        "external_id": album["id"], "n_lanzamiento": album["nombre"], "artista": album["artista"],
        "i_lanzamiento": album["portada"], "f_lanzamiento": album["fecha"], "external_url": album["url"]})
    if not lanza:
        return remitir(chat_id, "No se pudo asociar el lanzamiento.")
    items_s = list(s.items)
    precios = [precio] * len(items_s)
    lineas_c = [{"k_producto": it.k_producto, "k_lanzamiento": lanza.id,
                 "cantidad": it.cantidad, "precio": p} for it, p in zip(items_s, precios)]
    token, err = cotizar_solicitud(k, lineas_c, None)
    if err:
        return remitir(chat_id, f"No se pudo cotizar la #{k}: {err}")
    from flask import url_for
    total = sum(p * int(it.cantidad or 1) for it, p in zip(items_s, precios))
    link = url_for('solicitud.confirmar', token=token, _external=True)
    bloques = [f"🎵 ¡Ya tienes precio, solicitud #{k}!", "",
               f"Disco: {album['nombre']} — {album['artista']}",
               "\n".join(f"{int(it.cantidad or 1)} × {it.nombre or 'pedido'} · {_cop_bot(p * int(it.cantidad or 1))}"
                          for it, p in zip(items_s, precios)),
               f"Total: {_cop_bot(total)}", "", f"Paga y enviarlo: {link}"]
    remitir(chat_id, f"✅ Solicitud #{k} cotizada con “{album['nombre']}” ({_cop_bot(total)}).")
    remitir(chat_id, "Mensaje listo para el cliente 👇", copiar="\n".join(bloques))


def procesar_mensaje_tg(chat_id, texto):
    t = (texto or "").strip()
    if not t:
        return
    if t.lower() in ("lista", "listar", "menu", "ayuda", "help", "?"):
        return _cmd_lista(chat_id)
    palabras = t.split()
    if palabras[0].lower() in ("buscar", "spotify"):  #spotify queda como alias
        return _cmd_buscar(chat_id, palabras[1:])
    if palabras[0].isdigit():
        return _cmd_cotizar(chat_id, int(palabras[0]), palabras[1:])
    remitir(chat_id, "No entendí.\n\n" + _uso())


@telegram_bp.route("/webhook", methods=["POST"])
def webhook():
    #Solo el chat del admin; el secret_token (si se configura) actúa como segundo candado
    esperado = (current_app.config.get("TG_WEBHOOK_SECRET") or "").strip()
    if esperado and request.args.get("secret_token") != esperado:
        current_app.logger.warning(f"[TG-BOT] 403: secreto inválido (UA: {request.headers.get('User-Agent')})")
        return jsonify({"ok": False}), 403
    datos = request.get_json(silent=True) or {}
    mensaje = datos.get("message") or {}
    chat_id = mensaje.get("chat_id")
    remitente = (mensaje.get("from") or {}).get("id")
    texto = mensaje.get("text")
    if chat_id is None or not texto:
        return jsonify({"ok": True}), 200
    if str(remitente) != str(current_app.config.get("TG_ADMIN_CHAT_ID") or ""):
        current_app.logger.warning(f"[TG-BOT] Origen no autorizado: {remitente}")
        return jsonify({"ok": True}), 200
    procesar_mensaje_tg(chat_id, texto)
    return jsonify({"ok": True}), 200


@telegram_bp.route("/configure", methods=["GET"])
def configure():
    #desarrollo: registra el webhook en Telegram; ?url= para forzar la URL pública (si no, usa la del request)
    if not current_app.debug:
        return jsonify({"error": "solo disponible en desarrollo"}), 403
    token = (current_app.config.get("TG_BOT_TOKEN") or "").strip()
    if not token:
        return jsonify({"error": "falta TG_BOT_TOKEN"}), 400
    url = request.args.get("url") or (request.url_root.rstrip("/") + "/telegram-bot/webhook")
    datos = {"url": url, "allowed_updates": ["message"]}
    secreto = (current_app.config.get("TG_WEBHOOK_SECRET") or "").strip()
    if secreto:
        datos["secret_token"] = secreto
    r = requests.post(f"https://api.telegram.org/bot{token}/setWebhook", json=datos, timeout=10)
    return jsonify({"url": url, "respuesta": r.json()})
