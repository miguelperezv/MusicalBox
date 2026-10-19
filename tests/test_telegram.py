"""Webhook y avisos de Telegram: candado del secreto, updates repetidos y reintentos."""
import pytest

from app import telegram


@pytest.fixture
def tg(app):
    """Bot configurado con un admin y secret, y con el backend real interceptado."""
    app.config.update(TG_BOT_TOKEN="token-de-prueba", TG_ADMIN_CHAT_ID="12345",
                      TG_WEBHOOK_SECRET="secreto", TG_BACKEND="real", PUBLIC_BASE_URL="")
    return app


class Envios:
    """Reemplaza requests.post y registra lo que se intenta enviar a Telegram."""

    def __init__(self, fallos=0, status=200):
        self.llamadas = []
        self.fallos = fallos  #cuántas primeras llamadas fallan (para probar los reintentos)
        self.status = status

    def __call__(self, url, json=None, timeout=None, **kw):
        self.llamadas.append({"url": url, "payload": json})
        n = len(self.llamadas)
        clase = type("R", (), {"status_code": 503 if n <= self.fallos else self.status,
                               "text": "boom", "json": staticmethod(lambda: {})})
        return clase()


def update(texto="lista", update_id=1, chat=12345, remitente=12345):
    return {"update_id": update_id, "message": {"chat": {"id": chat}, "from": {"id": remitente}, "text": texto}}


def test_el_webhook_exige_el_secreto_en_la_cabecera_de_telegram(tg, monkeypatch):
    monkeypatch.setattr(telegram.requests, "post", Envios())
    #sin cabecera ni parámetro: 403 y no se contesta nada
    assert tg.test_client().post("/telegram-bot/webhook", json=update()).status_code == 403
    #la cabecera real de Telegram sí entra
    r = tg.test_client().post("/telegram-bot/webhook", json=update(),
                              headers={"X-Telegram-Bot-Api-Secret-Token": "secreto"})
    assert r.status_code == 200
    #y un secreto equivocado no
    r = tg.test_client().post("/telegram-bot/webhook", json=update(),
                              headers={"X-Telegram-Bot-Api-Secret-Token": "otro"})
    assert r.status_code == 403


def test_el_mismo_update_no_se_atiende_dos_veces(tg, monkeypatch):
    #Telegram reenvía el update si tarda la respuesta: el bot no debe cotizar dos veces lo mismo
    envios = Envios()
    monkeypatch.setattr(telegram.requests, "post", envios)
    c = tg.test_client()
    cab = {"X-Telegram-Bot-Api-Secret-Token": "secreto"}
    for _ in range(3):
        assert c.post("/telegram-bot/webhook", json=update(update_id=99), headers=cab).status_code == 200
    assert len(envios.llamadas) == 1  #una sola respuesta al admin
    #otro update sí se atiende
    c.post("/telegram-bot/webhook", json=update(update_id=100), headers=cab)
    assert len(envios.llamadas) == 2


def test_mensajes_de_otro_chat_no_se_contestan(tg, monkeypatch):
    envios = Envios()
    monkeypatch.setattr(telegram.requests, "post", envios)
    r = tg.test_client().post("/telegram-bot/webhook", json=update(remitente=999),
                              headers={"X-Telegram-Bot-Api-Secret-Token": "secreto"})
    assert r.status_code == 200 and envios.llamadas == []


def test_los_avisos_reintentan_si_el_proxy_falla(tg, monkeypatch):
    #el proxy de PythonAnywhere devuelve 503 de vez en cuando: el aviso de venta no se puede perder
    envios = Envios(fallos=1)
    monkeypatch.setattr(telegram.requests, "post", envios)
    monkeypatch.setattr(telegram.time, "sleep", lambda s: None)
    with tg.app_context():
        assert telegram.enviar_admin("<b>NUEVO PEDIDO #1</b>") is True
    assert len(envios.llamadas) == 2
    #si fallan todos, avisa que no se pudo (y no rompe nada)
    envios = Envios(fallos=9)
    monkeypatch.setattr(telegram.requests, "post", envios)
    with tg.app_context():
        assert telegram.enviar_admin("<b>NUEVO PEDIDO #2</b>") is False


def test_un_aviso_largo_se_parte_en_varios_mensajes(tg, monkeypatch):
    #Telegram rechaza los mensajes de más de 4096 caracteres: se parten y los botones van al final
    envios = Envios()
    monkeypatch.setattr(telegram.requests, "post", envios)
    largo = "\n".join(f"ítem {i} del pedido" for i in range(400))  #~7000 caracteres
    with tg.app_context():
        assert telegram.enviar_admin(largo, botones=[{"texto": "Ir", "url": "https://x.test/1"}]) is True
    assert len(envios.llamadas) == 2
    assert all(len(ll["payload"]["text"]) <= 4096 for ll in envios.llamadas)
    assert "reply_markup" not in envios.llamadas[0]["payload"]  #los botones van con el último
    assert "reply_markup" in envios.llamadas[-1]["payload"]
    #y el texto completo se conserva (no se pierde el final)
    unido = "\n".join(ll["payload"]["text"] for ll in envios.llamadas)
    assert "ítem 399 del pedido" in unido


def test_sin_credenciales_el_aviso_cae_a_consola(app, monkeypatch, tmp_path):
    app.config.update(TG_BOT_TOKEN="", TG_ADMIN_CHAT_ID="", TG_BACKEND="real")
    monkeypatch.setattr(app, "instance_path", str(tmp_path))
    monkeypatch.setattr(telegram.requests, "post", lambda *a, **k: pytest.fail("no debe llamar a Telegram"))
    with app.app_context():
        assert telegram.enviar_admin("<b>aviso</b>") is True
