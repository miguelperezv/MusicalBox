#Avisos al admin por WhatsApp (Meta Cloud API): segundo canal adyacente al de Telegram.
#
#WA_BACKEND:
#  real    -> llama a graph.facebook.com (requiere WA_ACCESS_TOKEN, WA_PHONE_NUMBER_ID y WA_ADMIN_PHONE_NUMBER)
#  consola -> imprime y guarda en instance/whatsapp/ (desarrollo; también si no hay credenciales)
#  memoria -> los guarda en app.extensions["whatsapp_enviados"] (pruebas)
#  off     -> no hace nada
#
#Los mensajes son texto plano (los botones requieren una plantilla de utilidad aprobada en Meta;
#la firma de enviar_admin_wa ya acepta `botones` para cuando se apruebe).
#
#Nunca lanza excepciones: si un envío falla, se registra y la operación que lo pidió sigue adelante.
#Acciones por webhook (/whatsapp/webhook): solo los números de WA_ADMIN_PHONE_NUMBER pueden
#dispararlas; se validan contra esa lista antes de tocar negocio.
import os
from datetime import datetime

import requests
from flask import Blueprint, current_app, jsonify, request

whatsapp_bp = Blueprint('whatsapp', __name__)


def _numeros_admin():
    #lista de números autorizados (uno o varios, separados por coma); solo dígitos
    raw = (current_app.config.get("WA_ADMIN_PHONE_NUMBER") or "")
    return [n for n in (x.strip().lstrip("+").replace(" ", "") for x in raw.split(",")) if n]


def enviar_admin_wa(mensaje, botones=None):
    cfg = current_app.config
    token = (cfg.get("WA_ACCESS_TOKEN") or "").strip()
    numero_id = (cfg.get("WA_PHONE_NUMBER_ID") or "").strip()
    version = (cfg.get("WA_API_VERSION") or "v21.0").strip()
    backend = (cfg.get("WA_BACKEND") or "real").lower()
    destinos = _numeros_admin()
    if not token or not numero_id or not destinos:
        backend = "consola"
    try:
        if backend == "off":
            return True
        if backend == "memoria":
            enviados = current_app.extensions.setdefault("whatsapp_enviados", [])
            enviados.append({"to": destinos, "texto": mensaje, "botones": botones or []})
            return True
        if backend == "real":
            #los botones necesitan plantilla de utilidad aprobada en Meta; hasta entonces, texto solo
            if botones:
                current_app.logger.warning("[WA] Se omiten botones: falta plantilla de utilidad aprobada en Meta")
            for destino in destinos:
                r = requests.post(
                    f"https://graph.facebook.com/{version}/{numero_id}/messages",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json={"messaging_product": "whatsapp", "to": destino,
                          "type": "text", "text": {"preview_url": False, "body": mensaje}},
                    timeout=10,
                )
                if r.status_code != 200:
                    current_app.logger.error(f"[WA] Error {r.status_code} al escribir a {destino}: {r.text[:200]}")
                    return False
            return True
        carpeta = os.path.join(current_app.instance_path, "whatsapp")
        os.makedirs(carpeta, exist_ok=True)
        nombre = datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".txt"
        with open(os.path.join(carpeta, nombre), "w", encoding="utf-8") as f:
            f.write(mensaje + "\n")
        print(f"\n===== WHATSAPP (consola) al admin {'/'.join(destinos) or 'sin numero'}:\n{mensaje}\n===== guardado en instance/whatsapp/{nombre}\n")
        return True
    except Exception as e:
        current_app.logger.error(f"[WA] Error enviando aviso: {e}")
        return False


def _accion(texto):
    #payload de botón ("enviado:42") o comando de texto ("enviado 42") -> (accion, id)
    limpio = (texto or "").strip().lower()
    for separador in (":", " "):
        if separador in limpio:
            parte, resto = limpio.split(separador, 1)
            if parte in ("enviado", "revisada") and resto.isdigit():
                return parte, int(resto)
    return None, None


@whatsapp_bp.route("/webhook", methods=["GET"])
def webhook_verificacion():
    #Meta valida la URL del webhook con este handshake
    modo = request.args.get("hub.mode")
    reto = request.args.get("hub.challenge")
    token = request.args.get("hub.verify_token")
    esperado = (current_app.config.get("WA_WEBHOOK_VERIFY_TOKEN") or "")
    if modo == "subscribe" and token and token == esperado:
        return reto, 200
    return "token inválido", 403


@whatsapp_bp.route("/webhook", methods=["POST"])
def webhook():
    #callbacks de Meta: pulsaciones de botón (interactions.button.payload) y comandos de texto
    payload = request.get_json(silent=True) or {}
    intentos = []
    for entrada in payload.get("entry", []):
        for cambio in entrada.get("changes", []):
            valor = cambio.get("value") or {}
            intento = {"from": (valor.get("from") or "").lstrip("+"),
                       "payload": (valor.get("interactions") or {}).get("button", {}).get("payload"),
                       "texto": (valor.get("text") or {}).get("body")}
            if intento["from"]:
                intentos.append(intento)
    for intento in intentos:
        resultado = procesar_mensaje_admin(intento["from"], intento.get("payload") or intento.get("texto"))
        if resultado is not None:
            enviar_admin_wa(resultado)
    return jsonify({"status": "ok"}), 200


def procesar_mensaje_admin(numero, contenido):
    #devuelve None si el remitente no está autorizado (se ignora en silencio); si no, el mensaje de respuesta
    if numero not in _numeros_admin():
        current_app.logger.warning(f"[WA-WEBHOOK] Remitente no autorizado: {numero}")
        return None
    accion, identificador = _accion(contenido)
    from .store.models import actualizar_envio, update_estado_solicitud
    if accion == "enviado":
        p = actualizar_envio(identificador, "ENVIADO")
        if p:
            return f"✅ Pedido #{p.id} marcado como ENVIADO."
        return f"⚠️ No se pudo marcar el pedido #{identificador} como enviado (debe estar PAGADO)."
    if accion == "revisada":
        s = update_estado_solicitud(identificador, "REVISADA")
        if s:
            return f"✅ Cotización #{s.id} marcada como REVISADA."
        return f"⚠️ No se pudo marcar la cotización #{identificador} como revisada."
    return f"Comandos: «enviado <nº pedido>» o «revisada <nº cotización>»."


@whatsapp_bp.route("/webhook-test", methods=["POST"])
def webhook_test():
    #desarrollo: simula un callback de Meta sin Meta; {"numero": "57...", "texto": "enviado 4"} o "payload"
    datos = request.get_json(silent=True) or request.form
    if not datos.get("numero"):
        return jsonify({"error": "falta el campo numero"}), 400
    respuesta = procesar_mensaje_admin(str(datos["numero"]).lstrip("+"), datos.get("texto") or datos.get("payload"))
    if respuesta is None:
        return jsonify({"error": "número no autorizado"}), 403
    return jsonify({"respuesta": respuesta}), 200
