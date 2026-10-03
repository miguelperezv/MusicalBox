"""Suscriptores de drops/preventas: email capturado en el footer para avisar de lanzamientos,
restocks y ofertas. El correo se manda manualmente desde el panel (sección "Suscriptores")."""
from datetime import datetime

from flask import flash, redirect, render_template, request, url_for, abort

from ..db import db
from .forms import SuscriptorForm
from .views import home, dashboard


class Suscriptor(db.Model):
    #email del aviso de drops: se guarda en minúsculas y no duplica (único)
    __tablename__ = 'suscriptor'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), nullable=False, unique=True, index=True)
    #pausado: sigue en la lista pero no se le manda aviso manual
    activo = db.Column(db.Boolean, nullable=False, default=True, server_default='1')
    f_creacion = db.Column(db.DateTime, default=datetime.now)
    f_actualizacion = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


def suscribir(email):
    """Guarda el email (minúsculas). Devuelve (suscriptor, estado): estado = 'nuevo' | 'repetido' | None (error)."""
    email = (email or '').strip().lower()
    if not email:
        return None, None
    existente = Suscriptor.query.filter(db.func.lower(Suscriptor.email) == email).first()
    if existente:
        existente.activo = True
        db.session.commit()
        return existente, 'repetido'
    s = Suscriptor(email=email)
    try:
        db.session.add(s)
        db.session.commit()
        return s, 'nuevo'
    except Exception:
        db.session.rollback()
        return None, None


def listar(busca=''):
    #busca: filtro de texto sobre el correo
    busca = (busca or '').strip().lower()
    q = Suscriptor.query
    if busca:
        q = q.filter(db.func.lower(Suscriptor.email).like(f"%{busca}%"))
    return q.order_by(db.desc(Suscriptor.f_creacion), db.desc(Suscriptor.id)).all()


@home.route("/suscribir", methods=["POST"])
def suscribir_correo():
    #el form del footer va en el contexto (ver app/__init__.py); el resultado se avisa con flash
    form = SuscriptorForm()
    if form.validate_on_submit():
        _, estado = suscribir(form.email.data)
        if estado == 'nuevo':
            flash("¡Listo! Te avisaremos cuando llegue el próximo drop o prevanta.", "success")
        elif estado == 'repetido':
            flash("Ya estabas en la lista: te seguiremos avisando.", "info")
        else:
            flash("No se pudo guardar tu correo, inténtalo de nuevo.", "error")
    else:
        flash("Revisa el formulario: escribe un correo válido y acepta los avisos.", "warning")
    return redirect(request.referrer or url_for('home.index'))


#panel: listado para mandarles correo manualmente (issue #4)
@dashboard.route("/suscriptores")
def suscriptores_admin():
    filas = listar(request.args.get("busca"))
    total = Suscriptor.query.count()
    activos = Suscriptor.query.filter_by(activo=True).count()
    return render_template("suscriptores_admin.html", filas=filas, total=total, activos=activos,
                           busca=(request.args.get("busca") or '').strip())


@dashboard.route("/suscriptor/<int:k>/activo", methods=["POST"])
def suscriptor_activo(k):
    s = db.session.get(Suscriptor, k) or abort(404)
    s.activo = not s.activo
    db.session.commit()
    flash("Suscriptor " + ("pausado" if not s.activo else "reactivado"), "success")
    return redirect(url_for('dashboard.suscriptores_admin'))


@dashboard.route("/suscriptor/<int:k>/eliminar", methods=["POST"])
def suscriptor_eliminar(k):
    s = db.session.get(Suscriptor, k) or abort(404)
    db.session.delete(s)
    db.session.commit()
    flash("Suscriptor eliminado", "success")
    return redirect(url_for('dashboard.suscriptores_admin'))
