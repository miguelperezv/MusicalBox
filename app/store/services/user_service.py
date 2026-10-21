"""Consultas y actualizaciones de la cuenta del cliente."""
from ..models import Invoice, Solicitud, Usuario, db, get_items_by_id_factura


def get_usuario_por_email(email):
    return Usuario.query.filter(
        db.func.lower(Usuario.email_usuario) == (email or "").strip().lower()
    ).first()


def edit_user_by_email(email, nombre, apellido, ciudad, direccion, barrio=None, celular=None):
    try:
        user = Usuario.query.filter_by(email_usuario=email).first()
        user.n_usuario = nombre
        user.ape_usuario = apellido
        user.lugar_usuario = ciudad
        user.dir_usuario = direccion
        user.barrio_usuario = barrio
        user.cel_usuario = celular
        db.session.commit()
        db.session.flush()
        return user
    except Exception:
        db.session.rollback()
        return None


def get_purchases_by_user(email):
    #los pedidos de su cuenta y los que hizo como invitado con ese mismo correo
    user = get_usuario_por_email(email)
    filtro = db.func.lower(Invoice.email_envio) == (email or "").lower()
    if user:
        filtro = db.or_(Invoice.k_usuario == user.id, filtro)
    invoices = Invoice.query.filter(filtro).order_by(db.desc(Invoice.f_compra)).all()
    facturas = []
    for i in invoices:
        facturas.append([i, get_items_by_id_factura(i.id)])
    return facturas


def get_solicitudes_by_user(email):
    #las del usuario y las que dejó solo con su correo de contacto
    user = get_usuario_por_email(email)
    filtro = db.func.lower(Solicitud.email_contacto) == (email or "").lower()
    if user:
        filtro = db.or_(Solicitud.k_usuario == user.id, filtro)
    return Solicitud.query.filter(filtro).order_by(db.desc(Solicitud.f_solicitud)).all()


__all__ = [
    "edit_user_by_email",
    "get_purchases_by_user",
    "get_solicitudes_by_user",
    "get_usuario_por_email",
]
