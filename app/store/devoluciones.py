"""Política pública de cambios y devoluciones, editable desde el panel.

El contenido se guarda en la tabla Configuracion (clave-valor), igual que los textos de
envío. Se escribe en texto plano para que el admin no tenga que tocar HTML: las líneas
que empiezan con "## " crean un título, las que empiezan con "- " crean una lista y los
bloques separados por una línea en blanco crean párrafos.
"""
import re
from datetime import datetime

from markupsafe import Markup, escape

from .models import MESES
from .redes import Configuracion, get_config, set_config
from ..db import db


TITULO_DEFAULT = "Cambios y devoluciones"
INTRO_DEFAULT = ("Queremos que tu compra llegue bien y que sepas qué hacer si algo no sale como "
                 "esperabas. Aquí están los plazos, las condiciones y los pasos para solicitar un cambio.")
TEXTO_DEFAULT = """## Cambios dentro de los 30 días
Puedes solicitar un cambio dentro de los 30 días posteriores a la entrega si el producto está en su estado original, completo, sin uso y con su empaque. Para iniciar el proceso escríbenos con tu número de pedido y cuéntanos el motivo.

- Escríbenos por WhatsApp o al correo de la tienda.
- Conserva el producto y su empaque hasta que te confirmemos el procedimiento.
- Te responderemos con los pasos y la dirección de envío si aplica.

## Si el producto llegó dañado o incompleto
Mándanos fotos del empaque y del producto dentro de los 30 días posteriores a la entrega. Revisaremos el caso y lo repondremos o te devolveremos el valor correspondiente.

## Reembolsos
Si el caso termina en reembolso, lo hacemos por el mismo medio de pago utilizado en la compra. El tiempo en que se refleja depende del banco o de la plataforma de pago; te confirmamos el valor y la fecha de la solicitud por escrito.

## Productos a la medida y preórdenes
Si el proveedor finalmente no consigue un disco pedido a la medida, te devolvemos el valor pagado. En preórdenes, si el pedido aún no ha salido, escríbenos para revisar la opción disponible según el estado de la tirada.

## Tus derechos
Cada caso se revisa conforme a la ley colombiana. Conservamos todos los derechos que la ley reconoce a los consumidores. Si no estás de acuerdo con la respuesta, puedes acudir a la autoridad de protección al consumidor.
"""


def _fecha_larga(fecha):
    return f"{fecha.day} de {MESES[fecha.month]} de {fecha.year}"


def texto_a_html(texto):
    """Convierte el texto plano del panel en HTML seguro (sin interpretar HTML del admin)."""
    if not texto:
        return Markup("")
    def cuerpo(lineas):
        if not lineas:
            return ""
        if all(linea.startswith(("- ", "* ")) for linea in lineas):
            return "<ul>" + "".join(
                f"<li>{escape(linea[2:].strip())}</li>" for linea in lineas
            ) + "</ul>"
        return "<p>" + "<br>".join(escape(linea) for linea in lineas) + "</p>"

    bloques = re.split(r"\n\s*\n", str(texto).replace("\r\n", "\n").strip())
    html = []
    for bloque in bloques:
        lineas = [linea.strip() for linea in bloque.splitlines() if linea.strip()]
        if not lineas:
            continue
        if lineas[0].startswith("## "):
            html.append(f"<h2 class=\"h5 mt-4 mb-2\">{escape(lineas[0][3:].strip())}</h2>")
            html.append(cuerpo(lineas[1:]))
        elif lineas[0].startswith("### "):
            html.append(f"<h3 class=\"h6 mt-4 mb-2\">{escape(lineas[0][4:].strip())}</h3>")
            html.append(cuerpo(lineas[1:]))
        else:
            html.append(cuerpo(lineas))
    return Markup("".join(html))


def obtener_devoluciones():
    """Título, introducción, texto y fecha de la última edición."""
    fila = db.session.get(Configuracion, "devoluciones.texto")
    actualizado = fila.f_actualizacion if fila and fila.f_actualizacion else datetime.now()
    titulo = get_config("devoluciones.titulo") or TITULO_DEFAULT
    intro = get_config("devoluciones.intro") or INTRO_DEFAULT
    texto = get_config("devoluciones.texto") or TEXTO_DEFAULT
    return {
        "titulo": titulo,
        "intro": intro,
        "texto": texto,
        "contenido_html": texto_a_html(texto),
        "actualizado": _fecha_larga(actualizado),
    }


def guardar_devoluciones(titulo, intro, texto):
    set_config({
        "devoluciones.titulo": (titulo or "").strip()[:120],
        "devoluciones.intro": (intro or "").strip()[:1000],
        "devoluciones.texto": (texto or "").strip()[:30000],
    })
