"""bitácora de cambios del panel

Revision ID: 8f4c2a7d9b31
Revises: d5c7a91f2b64
Create Date: 2026-10-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8f4c2a7d9b31'
down_revision = 'd5c7a91f2b64'
branch_labels = None
depends_on = None


def upgrade():
    #quién cambió qué en el panel; el correo queda copiado para que el registro sobreviva
    #a la eliminación del usuario (por eso usuario_id es opcional)
    op.create_table('admin_event',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=True),
    sa.Column('usuario_email', sa.String(length=50), nullable=False),
    sa.Column('accion', sa.String(length=40), nullable=False),
    sa.Column('entidad', sa.String(length=20), nullable=True),
    sa.Column('entidad_id', sa.Integer(), nullable=True),
    sa.Column('detalle', sa.String(length=300), nullable=True),
    sa.Column('datos', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], name=op.f('fk_admin_event_usuario_id_usuario')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_admin_event'))
    )
    with op.batch_alter_table('admin_event', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_admin_event_accion'), ['accion'], unique=False)
        batch_op.create_index(batch_op.f('ix_admin_event_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_admin_event_usuario_email'), ['usuario_email'], unique=False)


def downgrade():
    with op.batch_alter_table('admin_event', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_admin_event_usuario_email'))
        batch_op.drop_index(batch_op.f('ix_admin_event_created_at'))
        batch_op.drop_index(batch_op.f('ix_admin_event_accion'))

    op.drop_table('admin_event')
