"""variantes, bundles e item con id propio

Aditivo:
  - tabla `variante` (talla, color, sku, stock por variante)
  - tabla `producto_componente` (qué productos/variantes lleva un bundle y cuántos)
  - `producto.tipo` ('SIMPLE' por defecto; todos los productos existentes quedan SIMPLE)

Reconstrucción (aprobada): `item` pasa de clave compuesta (k_producto, k_factura) a `id` propio y
gana `k_variante` (NULL en todas las líneas existentes). La tabla se recrea copiando las filas; la
migración verifica que el número de líneas y la suma de cant_item * p_item no cambien.

Solo se implementa para SQLite (desarrollo). Para MySQL/otro motor se escribirá cuando toque el hosting.

Revision ID: 3c91f0d79d11
Revises: a36be8d1f63e
Create Date: 2026-09-27 04:31:08.818339

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3c91f0d79d11'
down_revision = 'a36be8d1f63e'
branch_labels = None
depends_on = None


def _solo_sqlite():
    if op.get_bind().dialect.name != "sqlite":
        raise NotImplementedError("La reconstrucción de `item` solo está escrita para SQLite; "
                                  "hay que escribir la versión para este motor antes de migrar.")


def _resumen_items():
    return op.get_bind().execute(sa.text("SELECT COUNT(*), COALESCE(SUM(cant_item * p_item), 0) FROM item")).one()


def upgrade():
    _solo_sqlite()
    op.create_table('variante',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('k_producto', sa.Integer(), nullable=False),
    sa.Column('talla', sa.String(length=20), nullable=True),
    sa.Column('color', sa.String(length=30), nullable=True),
    sa.Column('sku', sa.String(length=40), nullable=True),
    sa.Column('stock', sa.Integer(), server_default='0', nullable=False),
    sa.CheckConstraint('stock >= 0', name=op.f('ck_variante_stock_no_negativo')),
    sa.ForeignKeyConstraint(['k_producto'], ['producto.id'], name=op.f('fk_variante_k_producto_producto')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_variante')),
    sa.UniqueConstraint('k_producto', 'talla', 'color', name='uq_variante_producto_talla_color'),
    sa.UniqueConstraint('sku', name=op.f('uq_variante_sku'))
    )
    with op.batch_alter_table('variante', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_variante_k_producto'), ['k_producto'], unique=False)

    op.create_table('producto_componente',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('k_bundle', sa.Integer(), nullable=False),
    sa.Column('k_componente', sa.Integer(), nullable=False),
    sa.Column('k_variante', sa.Integer(), nullable=True),
    sa.Column('cantidad', sa.Integer(), server_default='1', nullable=False),
    sa.CheckConstraint('cantidad > 0', name=op.f('ck_producto_componente_cantidad_positiva')),
    sa.CheckConstraint('k_bundle <> k_componente', name=op.f('ck_producto_componente_no_se_contiene')),
    sa.ForeignKeyConstraint(['k_bundle'], ['producto.id'], name=op.f('fk_producto_componente_k_bundle_producto')),
    sa.ForeignKeyConstraint(['k_componente'], ['producto.id'], name=op.f('fk_producto_componente_k_componente_producto')),
    sa.ForeignKeyConstraint(['k_variante'], ['variante.id'], name=op.f('fk_producto_componente_k_variante_variante')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_producto_componente'))
    )
    with op.batch_alter_table('producto_componente', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_producto_componente_k_bundle'), ['k_bundle'], unique=False)

    with op.batch_alter_table('producto', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tipo', sa.String(length=10), server_default='SIMPLE', nullable=False))

    #--- reconstrucción de item: clave compuesta -> id propio + k_variante ---
    antes = _resumen_items()
    op.create_table('item_nuevo',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('k_producto', sa.Integer(), nullable=False),
    sa.Column('k_factura', sa.Integer(), nullable=False),
    sa.Column('k_variante', sa.Integer(), nullable=True),
    sa.Column('cant_item', sa.Numeric(precision=3, scale=0), nullable=False),
    sa.Column('p_item', sa.Numeric(precision=11, scale=2), nullable=False),
    sa.ForeignKeyConstraint(['k_factura'], ['invoice.id'], name='fk_item_k_factura_invoice'),
    sa.ForeignKeyConstraint(['k_producto'], ['producto.id'], name='fk_item_k_producto_producto'),
    sa.ForeignKeyConstraint(['k_variante'], ['variante.id'], name='fk_item_k_variante_variante'),
    sa.PrimaryKeyConstraint('id', name='pk_item')
    )
    #orden estable: los ids nuevos siguen el orden de pedido y producto
    op.execute("INSERT INTO item_nuevo (k_producto, k_factura, k_variante, cant_item, p_item) "
               "SELECT k_producto, k_factura, NULL, cant_item, p_item FROM item ORDER BY k_factura, k_producto")
    op.drop_table('item')
    op.rename_table('item_nuevo', 'item')
    with op.batch_alter_table('item', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_item_k_factura'), ['k_factura'], unique=False)
    despues = _resumen_items()
    if tuple(antes) != tuple(despues):
        raise RuntimeError(f"La copia de `item` no coincide: antes {tuple(antes)}, después {tuple(despues)}")


def downgrade():
    _solo_sqlite()
    #volver a la clave compuesta solo es posible si no hay dos líneas del mismo producto en un pedido
    duplicados = op.get_bind().execute(sa.text(
        "SELECT COUNT(*) FROM (SELECT 1 FROM item GROUP BY k_producto, k_factura HAVING COUNT(*) > 1)")).scalar()
    if duplicados:
        raise RuntimeError(f"No se puede revertir: {duplicados} pedidos tienen el mismo producto en varias variantes.")
    en_uso = op.get_bind().execute(sa.text(
        "SELECT (SELECT COUNT(*) FROM item WHERE k_variante IS NOT NULL) + (SELECT COUNT(*) FROM producto WHERE tipo <> 'SIMPLE')")).scalar()
    if en_uso:
        raise RuntimeError("No se puede revertir: ya hay líneas con variante o productos BUNDLE guardados.")

    antes = _resumen_items()
    op.create_table('item_viejo',
    sa.Column('k_producto', sa.Integer(), nullable=False),
    sa.Column('k_factura', sa.Integer(), nullable=False),
    sa.Column('cant_item', sa.Numeric(precision=3, scale=0), nullable=False),
    sa.Column('p_item', sa.Numeric(precision=11, scale=2), nullable=False),
    sa.ForeignKeyConstraint(['k_factura'], ['invoice.id'], name='fk_item_k_factura_invoice'),
    sa.ForeignKeyConstraint(['k_producto'], ['producto.id'], name='fk_item_k_producto_producto'),
    sa.PrimaryKeyConstraint('k_producto', 'k_factura', name='pk_item')
    )
    op.execute("INSERT INTO item_viejo (k_producto, k_factura, cant_item, p_item) "
               "SELECT k_producto, k_factura, cant_item, p_item FROM item")
    op.drop_table('item')
    op.rename_table('item_viejo', 'item')
    despues = _resumen_items()
    if tuple(antes) != tuple(despues):
        raise RuntimeError(f"La copia de `item` no coincide: antes {tuple(antes)}, después {tuple(despues)}")

    with op.batch_alter_table('producto', schema=None) as batch_op:
        batch_op.drop_column('tipo')
    with op.batch_alter_table('producto_componente', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_producto_componente_k_bundle'))
    op.drop_table('producto_componente')
    with op.batch_alter_table('variante', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_variante_k_producto'))
    op.drop_table('variante')
