"""crear_detalle_presupuesto

Revision ID: cbb87f34d7fe
Revises: 5691bba44b53
Create Date: 2026-11-15 10:02:23.856222

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'cbb87f34d7fe'
down_revision: Union[str, Sequence[str], None] = '5691bba44b53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'detalle_presupuesto',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('id_presupuesto', sa.Integer(), nullable=False),
        sa.Column('id_apu', sa.Integer(), nullable=False),
        sa.Column('unit', sqlmodel.sql.sqltypes.AutoString(length=30), nullable=False),
        sa.Column('cantidad', sa.Integer(), nullable=False),
        sa.Column('estimated_unit_cost', sa.Integer(), nullable=False),
        sa.Column('subtotal', sa.Integer(), nullable=False),
        sa.Column('costo_directo', sa.Integer(), nullable=False),
        sa.Column('costo_indirecto', sa.Integer(), nullable=False),
        sa.Column('descripcion', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.CheckConstraint('cantidad > 0', name='ck_detalle_cantidad_positiva'),
        sa.CheckConstraint('costo_directo >= 0', name='ck_detalle_costo_directo_no_negativo'),
        sa.CheckConstraint('costo_indirecto >= 0', name='ck_detalle_costo_indirecto_no_negativo'),
        sa.CheckConstraint('estimated_unit_cost >= 0', name='ck_detalle_costo_estimado_no_negativo'),
        sa.CheckConstraint('subtotal >= 0', name='ck_detalle_subtotal_no_negativo'),
        sa.ForeignKeyConstraint(['id_apu'], ['apu.id']),
        sa.ForeignKeyConstraint(['id_presupuesto'], ['presupuesto.id_presupuesto']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_detalle_id_apu', 'detalle_presupuesto', ['id_apu'], unique=False)
    op.create_index('ix_detalle_id_presupuesto', 'detalle_presupuesto', ['id_presupuesto'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_detalle_id_presupuesto', table_name='detalle_presupuesto')
    op.drop_index('ix_detalle_id_apu', table_name='detalle_presupuesto')
    op.drop_table('detalle_presupuesto')