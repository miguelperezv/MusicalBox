#panel admin: sección "Envíos" (configuración general y reglas de envío gratis) y
#corrección del costo de envío por orden (hasta que quede ENVIADO)
from flask import flash, redirect, render_template, request, url_for, jsonify, abort
from .views import dashboard
from .models import ReglaEnvio, Invoice, get_categorias
from .redes import get_config, set_config
from ..db import db

TIPOS_REGLA = {
    'SOLO_CATEGORIA': "Todo el pedido es de una sola categoría (ej. solo vinilos)",
    'CANTIDAD_CATEGORIA': "N o más unidades de una categoría (ej. 4+ CDs)",
    'TOTAL_MIN': "El total del pedido llega a $X o más",
    'SIEMPRE': "Siempre envío gratis",
}
#demo: las paqueterías que contesta EnvíoClick; se elige la preferida por nombre
PAQUETERIAS = ['COORDINADORA', 'ENVIA', 'TCC']


def _volver_envios(err=None, ok=None):
    flash(err or ok, "warning" if err else "success")
    return redirect(url_for('dashboard.envios_admin'))


@dashboard.route("/envios")
def envios_admin():
    reglas = ReglaEnvio.query.order_by(ReglaEnvio.orden, ReglaEnvio.id).all()
    criterios = [('MENOR_COSTO', 'La más barata'), ('MENOR_TIEMPO', 'La más rápida')] + \
                [(p, f"Paquetería {p.lower()} (si responde la ruta)") for p in PAQUETERIAS]
    return render_template("envios_admin.html", reglas=reglas, tipos=TIPOS_REGLA, criterios=criterios,
                           categorias=get_categorias() or [],
                           habilitado=get_config('envio.habilitado') == '1',
                           criterio=get_config('envio.criterio') or 'MENOR_COSTO',
                           zona_bogota=get_config('envio.zona_bogota') or '0',
                           zona_nacional=get_config('envio.zona_nacional') or '0',
                           caja=get_config('envio.caja') or '31x30x5')


@dashboard.route("/envios/config", methods=["POST"])
def envios_config():
    f = request.form
    criterio = (f.get("criterio") or "MENOR_COSTO").strip().upper()
    try:
        z_bogota = int(f.get("zona_bogota") or 0)
        z_nacional = int(f.get("zona_nacional") or 0)
    except ValueError:
        return _volver_envios("Las tarifas de respaldo deben ser números en pesos")
    if z_bogota < 0 or z_nacional < 0:
        return _volver_envios("Las tarifas de respaldo no pueden ser negativas")
    set_config({
        'envio.habilitado': '1' if f.get("habilitado") == "1" else '0',
        'envio.criterio': criterio,
        'envio.zona_bogota': str(z_bogota),
        'envio.zona_nacional': str(z_nacional),
        'envio.caja': (f.get("caja") or "31x30x5").strip(),
    })
    return _volver_envios(ok="Configuración de envíos guardada")


@dashboard.route("/envios/regla", methods=["POST"])
def regla_nueva():
    f = request.form
    tipo = f.get("tipo")
    if tipo not in TIPOS_REGLA:
        return _volver_envios("Elige un tipo de regla")
    categoria = (f.get("categoria") or "").strip().upper() or None
    if tipo in ('SOLO_CATEGORIA', 'CANTIDAD_CATEGORIA') and not categoria:
        return _volver_envios("Indica la categoría de la regla")
    try:
        orden = int(f.get("orden") or 0)
    except ValueError:
        orden = 0
    regla = ReglaEnvio(tipo=tipo,
                       k_categoria=categoria if tipo in ('SOLO_CATEGORIA', 'CANTIDAD_CATEGORIA') else None,
                       cantidad=(f.get("cantidad", type=int) or None) if tipo == 'CANTIDAD_CATEGORIA' else None,
                       total_min=(f.get("total_min", type=int) or None) if tipo == 'TOTAL_MIN' else None,
                       orden=orden, activo=f.get("activo") == "1")
    db.session.add(regla)
    db.session.commit()
    return _volver_envios(ok="Regla creada: los pedidos que la cumplan no pagan envío")


@dashboard.route("/envios/regla/<int:k>/activo", methods=["POST"])
def regla_activo(k):
    regla = db.session.get(ReglaEnvio, k) or abort(404)
    regla.activo = not regla.activo
    db.session.commit()
    return _volver_envios(ok="Regla " + ("activada" if regla.activo else "desactivada"))


@dashboard.route("/envios/regla/<int:k>/eliminar", methods=["POST"])
def regla_eliminar(k):
    regla = db.session.get(ReglaEnvio, k) or abort(404)
    db.session.delete(regla)
    db.session.commit()
    return _volver_envios(ok="Regla eliminada")


#corrección del costo de envío de una orden (queda cerrada cuando el pedido se marca ENVIADO)
@dashboard.route("/pedido/<int:k_invoice>/costo_envio", methods=["POST"])
def pedido_costo_envio(k_invoice):
    p = db.session.get(Invoice, k_invoice) or abort(404)
    if p.estado not in ('PENDIENTE', 'PAGADO') or p.estado_envio in ('ENVIADO', 'ENTREGADO'):
        return jsonify({"error": "El costo de envío solo se corrige hasta que el pedido quede ENVIADO"}), 400
    try:
        p_envio = int(request.form.get("p_envio"))
    except ValueError:
        return jsonify({"error": "Escribe el costo en pesos, sin puntos"}), 400
    if p_envio < 0:
        return jsonify({"error": "El costo no puede ser negativo"}), 400
    p.p_envio = p_envio
    p.envio_manual = True
    p.d_envio = (request.form.get("detalle") or "Ajuste manual del admin")[:100]
    db.session.commit()
    return jsonify({"p_envio": int(p.p_envio), "total_pago": int((p.total or 0) + p.p_envio), "d_envio": p.d_envio})
