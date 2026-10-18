"""guia de envio en el pedido

Revision ID: 3f9c1a7d5e20
Revises: 56b5d750487b
Create Date: 2026-10-18 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3f9c1a7d5e20'
down_revision = '56b5d750487b'
branch_labels = None
depends_on = None


def upgrade():
    #la guía la escribe el admin al despachar: viaja al correo del comprador y a /pedido/<token>
    with op.batch_alter_table('invoice', schema=None) as batch_op:
        batch_op.add_column(sa.Column('guia', sa.String(length=60), nullable=True))


def downgrade():
    with op.batch_alter_table('invoice', schema=None) as batch_op:
        batch_op.drop_column('guia')
