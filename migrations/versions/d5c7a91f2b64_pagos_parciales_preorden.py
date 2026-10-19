"""pagos parciales de preorden (abono y saldo)

Revision ID: d5c7a91f2b64
Revises: 3f9c1a7d5e20
Create Date: 2026-10-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5c7a91f2b64'
down_revision = '3f9c1a7d5e20'
branch_labels = None
depends_on = None


def upgrade():
    #el admin puede fijar qué % del precio se cobra como abono en una preorden
    with op.batch_alter_table('producto', schema=None) as batch_op:
        batch_op.add_column(sa.Column('porcentaje_abono', sa.Numeric(precision=5, scale=2), nullable=True))

    with op.batch_alter_table('invoice', schema=None) as batch_op:
        batch_op.add_column(sa.Column('es_preorden_abonada', sa.Boolean(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('monto_abono', sa.Numeric(precision=13, scale=2), nullable=True))
        batch_op.add_column(sa.Column('monto_saldo', sa.Numeric(precision=13, scale=2), nullable=True))

    #historial de los dos pagos de una preorden y de los recordatorios del saldo
    op.create_table(
        'abono_pago',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('k_invoice', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=10), server_default='ABONO', nullable=False),
        sa.Column('porcentaje_abono', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('p_abono', sa.Numeric(precision=13, scale=2), nullable=False),
        sa.Column('p_saldo', sa.Numeric(precision=13, scale=2), nullable=False),
        sa.Column('p_abono_pagado', sa.Numeric(precision=13, scale=2), nullable=True),
        sa.Column('p_saldo_pagado', sa.Numeric(precision=13, scale=2), nullable=True),
        sa.Column('estado_abono', sa.String(length=20), server_default='PENDIENTE', nullable=False),
        sa.Column('estado_saldo', sa.String(length=20), server_default='PENDIENTE', nullable=False),
        sa.Column('mp_pref_id_abono', sa.String(length=100), nullable=True),
        sa.Column('mp_pref_id_saldo', sa.String(length=100), nullable=True),
        sa.Column('mp_payment_id_abono', sa.String(length=100), nullable=True),
        sa.Column('mp_payment_id_saldo', sa.String(length=100), nullable=True),
        sa.Column('f_pago_abono', sa.DateTime(), nullable=True),
        sa.Column('f_pago_saldo', sa.DateTime(), nullable=True),
        sa.Column('f_recordatorio', sa.DateTime(), nullable=True),
        sa.Column('n_recordatorios', sa.Integer(), server_default='0', nullable=False),
        sa.Column('f_creacion', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['k_invoice'], ['invoice.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('k_invoice'),
    )
    with op.batch_alter_table('abono_pago', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_abono_pago_k_invoice'), ['k_invoice'], unique=False)


def downgrade():
    with op.batch_alter_table('abono_pago', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_abono_pago_k_invoice'))
    op.drop_table('abono_pago')

    with op.batch_alter_table('invoice', schema=None) as batch_op:
        batch_op.drop_column('monto_saldo')
        batch_op.drop_column('monto_abono')
        batch_op.drop_column('es_preorden_abonada')

    with op.batch_alter_table('producto', schema=None) as batch_op:
        batch_op.drop_column('porcentaje_abono')
