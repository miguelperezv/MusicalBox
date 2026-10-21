"""Operaciones de pago y recordatorios."""
from datetime import datetime

from ..models import db, confirmar_pago, rechazar_pago, token_pedido


def marcar_recordatorio(abono):
    #el panel cuenta cuántos recordatorios de saldo se han mandado por pedido
    abono.f_recordatorio = datetime.now()
    abono.n_recordatorios = int(abono.n_recordatorios or 0) + 1
    db.session.commit()


__all__ = ["confirmar_pago", "marcar_recordatorio", "rechazar_pago", "token_pedido"]
