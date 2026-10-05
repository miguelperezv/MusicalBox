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
Flujo guiado por botones (estado en memoria, un proceso):
  detalle -> [💻 web] [💲 precio] [🔎 disco] [🛒 producto] [📝 nota] + [✖ retirar ítem]
  disco -> top 5 (opt:<k>:<ext>) · producto -> top 5 del catálogo (opro:<k>:<id>)
  -> precio por ítem -> precio de envío (número; 0 gratis; "ok" = estimado) -> cotiza.
  El mensaje del cliente va con foto (portada chica), envío y botón "Copiar" (copy_text).

Solo responde al chat TG_ADMIN_CHAT_ID; si se configura TG_WEBHOOK_SECRET, exige ese
secret_token en el webhook (segundo candado).

Nunca lanza excepciones: si un aviso falla, se registra y la operación que lo pidió sigue adelante.
"""
import logging
import os
import time
from datetime import datetime

import requests
from flask import Blueprint, current_app, jsonify, request

telegram_bp = Blueprint('telegram_bot', __name__)


#los logs van por logging (en produccion solo se ve el error log, no el stdout de print)
log = logging.getLogger("mb.tgbot")

#estado guiado del bot en memoria (dev y PA corren un solo proceso):
# chat_id (str) -> {"espera": "disco"|"precio", "k": id de solicitud, "ext": id de spotify (opcional)}
_guiado = {}
_ctx = {}  #contexto guiado por chat: {"k", "ext" (spotify), "prod" (producto), "nota"}
#albumes de la busqueda mas reciente: external_id -> item (para los botones opt:<k>:<ext>)
_albumes = {}


def _ck(chat_id):
    #llave de estado: Telegram manda int y la config trae str; se normaliza a str
    return str(chat_id)


def _markup(botones):
    #cada botón en su propia fila; url -> enlace, callback -> respuesta del bot
    filas = []
    for b in botones or []:
        if b.get("url"):
            filas.append([{"text": b["texto"], "url": b["url"]}])
        else:
            filas.append([{"text": b["texto"], "callback_data": b["callback"]}])
    return {"inline_keyboard": filas} if filas else None


def enviar_admin(mensaje, botones=None):
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
            cuerpo = {"chat_id": chat, "text": mensaje, "parse_mode": "HTML",
                     "disable_web_page_preview": True}
            markup = _markup(botones)
            if markup:
                cuerpo["reply_markup"] = markup
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json=cuerpo,
                timeout=10,
            )
            if r.status_code != 200:
                log.warning(f"aviso falló: HTTP {r.status_code} {r.text[:200]}")
                return False
            log.info(f"aviso enviado (real) · {len(mensaje)} chars · {len(botones or [])} botones")
            return True
        carpeta = os.path.join(current_app.instance_path, "telegram")
        os.makedirs(carpeta, exist_ok=True)
        nombre = datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".txt"
        with open(os.path.join(carpeta, nombre), "w", encoding="utf-8") as f:
            f.write(mensaje + "\n")
        print(f"\n===== TELEGRAM (consola) al admin: {mensaje}\n===== guardado en instance/telegram/{nombre}\n")
        return True
    except Exception as e:
        log.warning(f"aviso falló: {e}")
        return False


def remitir(chat_id, texto, copiar=None, botones=None, foto=None):
    #envío directo del bot (sin HTML); `copiar` añade botón de copiar y `foto` (url) va con el texto
    token = (current_app.config.get("TG_BOT_TOKEN") or "").strip()
    if not token:
        log.warning(f"remitir sin TG_BOT_TOKEN: {texto[:60]!r}")
        return False
    es_foto = bool(foto and str(foto).startswith("http"))
    if es_foto:  #con foto va por sendPhoto (caption + botones); sin foto, texto plano
        payload = {"chat_id": chat_id, "photo": str(foto), "caption": texto}
    else:
        payload = {"chat_id": chat_id, "text": texto, "disable_web_page_preview": True}
    filas = []
    if copiar:
        filas.append([{"type": "copy_text", "text": "📋 Copiar", "copy_text": {"text": copiar}}])
    markup = _markup(botones)
    if markup:
        filas.extend(markup["inline_keyboard"])
    if filas:
        payload["reply_markup"] = {"inline_keyboard": filas}
    log.info(f"bot responde a {chat_id} · {texto[:50]!r} · copiar={bool(copiar)} · botones={len(botones or [])} · foto={bool(foto)}")
    url = f"https://api.telegram.org/bot{token}/{'sendPhoto' if es_foto else 'sendMessage'}"
    for intento in (1, 2):  #el proxy saliente de PA fallan con 503 de vez en cuando; reintentar suele pasar
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                return True
            log.warning(f"bot falló (intento {intento}): HTTP {r.status_code} {r.text[:150]}")
        except Exception as e:
            log.warning(f"bot falló (intento {intento}): {e}")
        if intento == 1:
            time.sleep(1.5)
    return False


def _cop_bot(total):
    return "${:,}".format(int(total or 0)).replace(",", ".")


def _uso():
    return ("Todo se hace con los botones de cada solicitud:\n"
            "💲 Poner precio (uno por ítem si hay varios)\n"
            "🔎 Buscar el disco (Spotify) · 🛒 Buscar producto del catálogo\n"
            "📝 Nota para el cliente · ✖ Retirar un ítem\n"
            "Al final: precio de envío (fíjalo o deja que lo calcule el sistema)\n\n"
            "Y por texto, si lo prefieres:\n"
            "• lista - solicitudes pendientes\n"
            "• <id> - detalle · <id> <precio> - cotizar rápido\n"
            "• buscar <id> <texto> [opcion precio] - buscar disco y cotizar")

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
    from .store.models import Solicitud, SolicitudItem, items_efectivos
    s = Solicitud.query.get(k)
    if not s:
        return remitir(chat_id, f"No existe la solicitud #{k}. (usa 'lista')")
    items = items_efectivos(s)
    lineas = _lineas_items(s)
    correo = f" · {s.email_contacto}" if s.email_contacto else ""
    from flask import url_for
    botones = [
        {"texto": "💻 Cotizar en web", "url": url_for('home.admin', sol=s.id, _external=True)},
        {"texto": "💲 Poner precio", "callback": f"prc:{s.id}"},
        {"texto": "🔎 Buscar el disco", "callback": f"busk:{s.id}"},
        {"texto": "🛒 Buscar producto", "callback": f"prod:{s.id}"},
        {"texto": "📝 Nota para el cliente", "callback": f"nota:{s.id}"},
    ]
    for i, it in enumerate(items):
        if isinstance(it, SolicitudItem):
            botones.append({"texto": f"✖ {i+1}. {(it.nombre or 'ítem')[:30]}", "callback": f"rit:{s.id}:{i}"})
    remitir(chat_id, (f"Solicitud #{s.id} · {s.estado}\n"
                      f"Cliente: {s.cel_contacto or 'sin contacto'}{correo}\n"
                      + "\n".join(lineas) + "\n\n"
                      f"Para cotizar: {s.id} <precio>. (o los botones de arriba)"), botones=botones)

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


def _portada_http(valor):
    return valor if isinstance(valor, str) and valor.startswith("http") else None


def _buscar_disco(chat_id, k, texto):
    from .store.musicapi import buscar_albumes_spotify
    res = buscar_albumes_spotify(texto)
    if res.get("error"):
        return remitir(chat_id, f"Búsqueda: {res['error']}")
    items = res.get("items", [])[:5]
    if not items:
        return remitir(chat_id, f"No encontré discos para “{texto}”. Prueba con otro nombre.")
    for a in items:
        _albumes[a["id"]] = a
    lineas = [f"{i+1}. {a['nombre']} — {a['artista']}" for i, a in enumerate(items)]
    botones = [{"texto": f"{i+1}. {a['nombre'][:34]}", "callback": f"opt:{k}:{a['id']}"}
              for i, a in enumerate(items)]
    return remitir(chat_id, f"Discos para “{texto}”:\n" + "\n".join(lineas) +
                       "\n\nToca la opción que sea (y luego el precio).",
                   botones=botones, foto=_portada_http(items[0].get("portada_chica") or items[0].get("portada")))


def _cotizar_con(chat_id, k, precios, ext=None, prod=None, nota=None, envio=None):
    from .db import db
    from .store.models import (Solicitud, Producto, cotizar_solicitud, buscar_o_crear_lanzamiento_spotify,
                               items_efectivos)
    from .store.envio import costo_envio, lineas_desde_cats
    _guiado.pop(_ck(chat_id), None)
    _ctx.pop(_ck(chat_id), None)
    s = Solicitud.query.get(k)
    if not s:
        return remitir(chat_id, f"No existe la solicitud #{k}.")
    items = items_efectivos(s)
    if isinstance(precios, int):
        precios = [precios] * len(items)
    try:
        precios = [int(p) for p in (precios or [])]
    except (TypeError, ValueError):
        precios = []
    if len(precios) != len(items) or any(p <= 0 for p in precios):
        return remitir(chat_id, f"La solicitud #{k} tiene {len(items)} ítem(s): necesito {len(items)} precio(s).")
    lanza_id, portada, disco = None, None, ""
    if ext:
        a = _albumes.get(ext)
        if not a:
            return remitir(chat_id, "Esos resultados expiraron: usa otra vez '🔎 Buscar el disco'.")
        l, _ = buscar_o_crear_lanzamiento_spotify({
            "external_id": a["id"], "n_lanzamiento": a.get("nombre"), "artista": a.get("artista"),
            "i_lanzamiento": a.get("portada"), "f_lanzamiento": a.get("fecha"), "external_url": a.get("url")})
        if not l:
            return remitir(chat_id, "No se pudo asociar el disco.")
        lanza_id, disco = l.id, a.get("nombre", "")
        portada = a.get("portada_chica") or a.get("portada")
    producto = db.session.get(Producto, int(prod)) if prod else None
    if prod and not producto:
        return remitir(chat_id, "Ese producto no existe: usa otra vez '🛒 Buscar producto'.")
    lineas = [{"k_producto": producto.id if producto else it.k_producto,
               "k_lanzamiento": lanza_id or it.k_lanzamiento,
               "cantidad": it.cantidad, "precio": p} for it, p in zip(items, precios)]
    token, err = cotizar_solicitud(k, lineas, nota, p_envio=envio)
    if err:
        return remitir(chat_id, f"No se pudo cotizar la #{k}: {err}")
    if not portada:
        for it in items:
            lz = it.lanzamiento or (it.producto.lanzamiento if it.producto else None)
            if lz and _portada_http(lz.i_lanzamiento):
                portada = lz.i_lanzamiento
                disco = disco or lz.n_lanzamiento
                break
    from flask import url_for
    total = sum(p * int(it.cantidad or 1) for it, p in zip(items, precios))
    bloques = [f"👋 ¡Ya tienes precio, solicitud #{k}!", ""]
    if disco:
        bloques.append(f"Disco: {disco}")
    bloques += ["\n".join(f"{int(it.cantidad or 1)} × {it.nombre or 'pedido'} · {_cop_bot(p * int(it.cantidad or 1))}"
                          for it, p in zip(items, precios)),
                f"Total: {_cop_bot(total)}"]
    if s.p_envio_cotizado is not None:
        bloques.append("¡Y el envío es gratis!" if s.p_envio_cotizado == 0
                       else f"Envío: {_cop_bot(s.p_envio_cotizado)} · total {_cop_bot(total + s.p_envio_cotizado)}")
    elif s.lugar_solicitud:
        cats = "|".join(f"{(it.producto.k_categoria if it.producto else it.categoria) or 'OTRO'}:{int(it.cantidad or 1)}"
                        for it in items)
        env = costo_envio(lineas_desde_cats(cats), total, s.lugar_solicitud)
        if env:
            if env["p_envio"] == 0:
                bloques.append(f"¡Y el envío a {s.lugar_solicitud} es gratis!")
            else:
                bloques.append(f"Envío estimado a {s.lugar_solicitud}: {_cop_bot(env['p_envio'])} · total {_cop_bot(total + env['p_envio'])}")
    if s.d_cotizacion:
        bloques.append(s.d_cotizacion)
    bloques += ["", f"Paga y enviarlo: {url_for('solicitud.confirmar', token=token, _external=True)}"]
    resumen = (f"✅ Solicitud #{k} cotizada ({_cop_bot(total)})"
               + (f" · disco: {disco}" if disco else "")
               + (f" · producto: {(producto.n_producto or '')[:30]}" if producto else "")
               + (f" · nota: {s.d_cotizacion[:50]}" if s.d_cotizacion else "")
               + f"\nPanel: {url_for('solicitud.lista', _external=True)}")
    remitir(chat_id, resumen)
    remitir(chat_id, "Mensaje listo para el cliente 📩", copiar="\n".join(bloques), foto=portada)

def _prompt_precio(chat_id, k):
    from .store.models import Solicitud, items_efectivos
    s = Solicitud.query.get(k)
    if not s:
        _guiado.pop(_ck(chat_id), None)
        return remitir(chat_id, f"No existe la solicitud #{k}.")
    items = items_efectivos(s)
    if len(items) == 1:
        return remitir(chat_id, f"Ítem: {items[0].nombre or 'pedido'}\n¿Cuánto vale?\nEscribe el precio en pesos o 'cancelar'.")
    return remitir(chat_id, (f"La solicitud #{k} tiene {len(items)} ítems: pido el precio de cada uno.\n\n"
                             f"1/{len(items)}: {items[0].nombre or 'ítem'}\n¿Precio en pesos? (o 'cancelar')"))


def _esperando_precio(chat_id, t, estado):
    k = int(estado.get("k") or 0)
    if t.isdigit() and int(t) > 0:
        from .store.models import Solicitud, items_efectivos
        s = Solicitud.query.get(k)
        if not s:
            _guiado.pop(_ck(chat_id), None)
            return remitir(chat_id, f"No existe la solicitud #{k}.")
        items = items_efectivos(s)
        precios = list(estado.get("precios") or [])
        if len(precios) >= len(items):
            _guiado.pop(_ck(chat_id), None)
            return remitir(chat_id, "Ya estaban todos los precios: 'cancelar' y vuelve a intentarlo.")
        precios.append(int(t))
        estado["precios"] = precios
        if len(precios) == len(items):
            _guiado[_ck(chat_id)] = estado
            return _prompt_envio(chat_id, k, estado)
        _guiado[_ck(chat_id)] = estado
        nombre = items[len(precios)].nombre or 'ítem'
        return remitir(chat_id, f"{len(precios)+1}/{len(items)}: {nombre}\n¿Precio en pesos? (o 'cancelar')")
    return remitir(chat_id, "El precio va solo en números (pesos), ej. 180000 - o escribe 'cancelar'.")


def _prompt_envio(chat_id, k, estado):
    from .store.models import Solicitud, items_efectivos
    from .store.envio import costo_envio, lineas_desde_cats
    s = Solicitud.query.get(k)
    if not s:
        _guiado.pop(_ck(chat_id), None)
        return remitir(chat_id, f"No existe la solicitud #{k}.")
    items = items_efectivos(s)
    total = sum(int(p) * int(it.cantidad or 1) for it, p in zip(items, estado.get("precios") or []))
    est = None
    if s.lugar_solicitud:
        cats = "|".join(f"{(it.producto.k_categoria if it.producto else it.categoria) or 'OTRO'}:{int(it.cantidad or 1)}"
                        for it in items)
        res = costo_envio(lineas_desde_cats(cats), total, s.lugar_solicitud)
        est = int(res["p_envio"]) if res and res.get("p_envio") is not None else None
    estado["espera"] = "envio"
    estado["envio_est"] = est
    _guiado[_ck(chat_id)] = estado
    if est is None:
        return remitir(chat_id, (f"Precios listos. ¿Precio de envío para la solicitud #{k}?\n"
                                 f"Número en pesos (0 = gratis), 'ok' = lo calcula el sistema al pagar, 'cancelar' = volver."))
    return remitir(chat_id, (f"Envío estimado a {s.lugar_solicitud}: {_cop_bot(est)}.\n"
                             f"¿Qué precio de envío meto? Número (0 = gratis), 'ok' = usar el estimado, 'cancelar' = volver."))


def _esperando_envio(chat_id, t, estado):
    k = int(estado.get("k") or 0)
    base = _ctx.get(_ck(chat_id)) or {}
    if t.lower() in ("cancelar", "no", "salir", "x"):
        _guiado.pop(_ck(chat_id), None)
        _ctx.pop(_ck(chat_id), None)
        return remitir(chat_id, "Listo, se canceló. (usa 'lista' u otro comando)")
    kwargs = dict(ext=base.get("ext"), prod=base.get("prod"), nota=base.get("nota"))
    if t.isdigit():
        _guiado.pop(_ck(chat_id), None)
        _ctx.pop(_ck(chat_id), None)
        return _cotizar_con(chat_id, k, estado.get("precios") or [], envio=int(t), **kwargs)
    if t.lower() in ("ok", "s", "si", "envio", "est"):
        #ok: usa el estimado si lo hubo; si no, que lo calcule el checkout con la dirección final
        _guiado.pop(_ck(chat_id), None)
        _ctx.pop(_ck(chat_id), None)
        return _cotizar_con(chat_id, k, estado.get("precios") or [], envio=estado.get("envio_est"), **kwargs)
    return remitir(chat_id, "Un número en pesos (0 = gratis), 'ok' para el estimado, o 'cancelar'.")


def _ctx_de(chat_id, k):
    #contexto guiado de este chat (solo cuenta si es de la misma solicitud)
    base = _ctx.get(_ck(chat_id))
    return base if (base and int(base.get("k") or 0) == k) else {"k": k}


def _guardar_nota(chat_id, t, estado):
    k = int(estado.get("k") or 0)
    base = _ctx.get(_ck(chat_id)) or {"k": k}
    _ctx[_ck(chat_id)] = dict(base, k=k, nota=t[:300])
    _guiado.pop(_ck(chat_id), None)
    remitir(chat_id, f"📝 Nota guardada para la solicitud #{k}: va en el mensaje de la cotización.")
    return _cmd_detalle(chat_id, k)


def _buscar_producto(chat_id, k, texto):
    from .store.models import get_catalogo_solicitud
    q = (texto or '').strip().lower()
    if len(q) < 2:
        return remitir(chat_id, "Escribe al menos 2 letras del nombre del producto (o 'cancelar').")
    matches = [p for p in get_catalogo_solicitud() if q in p["nombre"].lower()][:5]
    if not matches:
        return remitir(chat_id, f"No encontré “{texto}” en el catálogo.\nPrueba con otra palabra, o 'cancelar'.")
    lineas = [f"{i+1}. {p['nombre']}" for i, p in enumerate(matches)]
    botones = [{"texto": f"{i+1}. {p['nombre'][:40]}", "callback": f"opro:{k}:{p['id']}"} for i, p in enumerate(matches)]
    return remitir(chat_id, "Productos del catálogo:\n" + "\n".join(lineas) + "\n\nToca el que sea.", botones=botones)


def _retirar_item(chat_id, k, i):
    from .db import db
    from .store.models import Solicitud, SolicitudItem, items_efectivos
    s = Solicitud.query.get(k)
    if not s:
        return remitir(chat_id, f"No existe la solicitud #{k}.")
    items = items_efectivos(s)
    if i >= len(items):
        return remitir(chat_id, "Ese ítem ya no está en la lista.")
    if not isinstance(items[i], SolicitudItem):
        return remitir(chat_id, "Ese ítem no se puede retirar (solicitud antigua): cotízala tal cual, o cancela la solicitud.")
    if len(items) <= 1:
        return remitir(chat_id, "Queda al menos un ítem: si el pedido ya no le interesa, márcala como cancelada.")
    db.session.delete(items[i])
    db.session.commit()
    _guiado.pop(_ck(chat_id), None)
    _ctx.pop(_ck(chat_id), None)
    remitir(chat_id, f"✖ Se retiró el ítem {i+1} de la solicitud #{k}.")
    return _cmd_detalle(chat_id, k)

def procesar_mensaje_tg(chat_id, texto):
    t = (texto or "").strip()
    if not t:
        return
    estado = _guiado.get(_ck(chat_id))
    if estado:
        if t.lower() in ("cancelar", "no", "salir", "x"):
            _guiado.pop(_ck(chat_id), None)
            _ctx.pop(_ck(chat_id), None)
            return remitir(chat_id, "Listo, se canceló. (usa 'lista' u otro comando)")
        espera = (estado or {}).get("espera")
        if espera == "precio":
            return _esperando_precio(chat_id, t, estado)
        if espera == "envio":
            return _esperando_envio(chat_id, t, estado)
        if espera == "nota":
            return _guardar_nota(chat_id, t, estado)
        if espera == "producto":
            return _buscar_producto(chat_id, int(estado.get("k") or 0), t)
        _guiado.pop(_ck(chat_id), None)
        return _buscar_disco(chat_id, int(estado.get("k") or 0), t)
    if t.lower() in ("lista", "listar", "menu", "ayuda", "help", "?"):
        return _cmd_lista(chat_id)
    palabras = t.split()
    if palabras[0].lower() in ("buscar", "spotify"):  #spotify queda como alias
        return _cmd_buscar(chat_id, palabras[1:])
    if palabras[0].isdigit():
        return _cmd_cotizar(chat_id, int(palabras[0]), palabras[1:])
    remitir(chat_id, "No entendí.\n\n" + _uso())

def _es_admin(remitente):
    return str(remitente) == str(current_app.config.get("TG_ADMIN_CHAT_ID") or "")


def _responder_callback(cb):
    #apretón de botón inline; answerCallbackQuery quita la carita de "procesando"
    #el webhook ya validó que es el admin y el chat es privado: el chat de destino es el propio admin
    chat_id = current_app.config.get("TG_ADMIN_CHAT_ID")
    data = cb.get("data") or ""
    try:
        token = (current_app.config.get("TG_BOT_TOKEN") or "").strip()
        if token:
            requests.post(f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                          json={"callback_query_id": cb.get("id")}, timeout=5)
    except Exception:
        pass
    if not data:
        return
    prefijo, _, resto = data.partition(":")
    if prefijo in ("opt", "opro", "rit"):
        #opt:<k>:<ext_spotify> · opro:<k>:<producto> · rit:<k>:<ítem>
        partes = resto.split(":", 1)
        if len(partes) != 2 or not partes[0].isdigit():
            return
        k, extra = int(partes[0]), partes[1]
        if prefijo == "rit":
            if not extra.isdigit():
                return
            return _retirar_item(chat_id, k, int(extra))
        base = _ctx_de(chat_id, k)
        if prefijo == "opt":
            album = _albumes.get(extra)
            if not album:
                return remitir(chat_id, "Esos resultados expiraron: usa otra vez '🔎 Buscar el disco'.")
            _ctx[_ck(chat_id)] = dict(base, k=k, ext=extra)
            _guiado[_ck(chat_id)] = {"espera": "precio", "k": k}
            return _prompt_precio(chat_id, k)
        if not extra.isdigit():
            return
        from .store.models import Producto
        from .db import db
        if not db.session.get(Producto, int(extra)):
            return remitir(chat_id, "Ese producto no existe: usa otra vez '🛒 Buscar producto'.")
        _ctx[_ck(chat_id)] = dict(base, k=k, prod=int(extra))
        _guiado[_ck(chat_id)] = {"espera": "precio", "k": k}
        return _prompt_precio(chat_id, k)
    if not resto.isdigit():
        return
    k = int(resto)
    if prefijo == "mtx":
        return _cmd_detalle(chat_id, k)
    base = _ctx_de(chat_id, k)
    if prefijo == "prc":
        _ctx[_ck(chat_id)] = dict(base, k=k)
        _guiado[_ck(chat_id)] = {"espera": "precio", "k": k}
        return _prompt_precio(chat_id, k)
    if prefijo == "busk":
        _ctx[_ck(chat_id)] = dict(base, k=k)
        _guiado[_ck(chat_id)] = {"espera": "disco", "k": k}
        return remitir(chat_id, f"¿Cuál disco, para la solicitud #{k}?\nEscribe el nombre y te muestro los resultados.")
    if prefijo == "prod":
        _ctx[_ck(chat_id)] = dict(base, k=k)
        _guiado[_ck(chat_id)] = {"espera": "producto", "k": k}
        return remitir(chat_id, f"¿Qué producto del catálogo, para la solicitud #{k}?\nEscribe el nombre y te muestro los más parecidos.")
    if prefijo == "nota":
        _ctx[_ck(chat_id)] = dict(base, k=k)
        _guiado[_ck(chat_id)] = {"espera": "nota", "k": k}
        return remitir(chat_id, f"Escribe la nota para el cliente de la solicitud #{k} (tiempos, edición...).\nMáx. 300; va en el mensaje de la cotización.")

@telegram_bp.route("/webhook", methods=["POST"])
def webhook():
    datos = request.get_json(silent=True) or {}
    #Solo el chat del admin; el secret_token (si se configura) actúa como segundo candado
    esperado = (current_app.config.get("TG_WEBHOOK_SECRET") or "").strip()
    if esperado and request.args.get("secret_token") != esperado:
        log.warning(f"403: secreto inválido (UA: {request.headers.get('User-Agent')})")
        return jsonify({"ok": False}), 403
    cb = datos.get("callback_query")
    if cb:
        remitente = (cb.get("from") or {}).get("id")
        if not _es_admin(remitente):
            log.warning(f"origen no autorizado (botón): {remitente}")
            return jsonify({"ok": True}), 200
        log.info(f"webhook botón de {remitente}: {(cb.get('data') or '')!r}")
        _responder_callback(cb)
        return jsonify({"ok": True}), 200
    mensaje = datos.get("message") or {}
    chat_id = mensaje.get("chat_id") or (mensaje.get("chat") or {}).get("id")  #Telegram trae chat.id
    remitente = (mensaje.get("from") or {}).get("id")
    texto = mensaje.get("text")
    if chat_id is None or not texto:
        return jsonify({"ok": True}), 200
    if not _es_admin(remitente):
        log.warning(f"origen no autorizado: {remitente}")
        return jsonify({"ok": True}), 200
    log.info(f"webhook mensaje de {remitente}: {texto[:60]!r}")
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
    datos = {"url": url, "allowed_updates": ["message", "callback_query"]}
    secreto = (current_app.config.get("TG_WEBHOOK_SECRET") or "").strip()
    if secreto:
        datos["secret_token"] = secreto
    r = requests.post(f"https://api.telegram.org/bot{token}/setWebhook", json=datos, timeout=10)
    return jsonify({"url": url, "respuesta": r.json()})
