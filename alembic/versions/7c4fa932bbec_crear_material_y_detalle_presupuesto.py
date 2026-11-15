"""crear_material_y_detalle_presupuesto

Revision ID: 7c4fa932bbec
Revises: 5691bba44b53
Create Date: 2026-11-14 13:11:32.753470

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '7c4fa932bbec'
down_revision: Union[str, Sequence[str], None] = '5691bba44b53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'material',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=150), nullable=False),
        sa.Column('category', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
        sa.Column('unit', sqlmodel.sql.sqltypes.AutoString(length=30), nullable=False),
        sa.Column('unit_cost', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column('updated_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
        sa.CheckConstraint('unit_cost >= 0', name='ck_material_unit_cost_non_negative'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'uq_material_code_lower',
        'material',
        [sa.text('lower(code)')],
        unique=True
    )

    op.create_table(
        'detalle_presupuesto',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('id_presupuesto', sa.Integer(), nullable=False),
        sa.Column('id_apu', sa.Integer(), nullable=False),
        sa.Column('id_material', sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(['id_material'], ['material.id']),
        sa.ForeignKeyConstraint(['id_presupuesto'], ['presupuesto.id_presupuesto']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_detalle_id_apu', 'detalle_presupuesto', ['id_apu'], unique=False)
    op.create_index('ix_detalle_id_material', 'detalle_presupuesto', ['id_material'], unique=False)
    op.create_index('ix_detalle_id_presupuesto', 'detalle_presupuesto', ['id_presupuesto'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_detalle_id_presupuesto', table_name='detalle_presupuesto')
    op.drop_index('ix_detalle_id_material', table_name='detalle_presupuesto')
    op.drop_index('ix_detalle_id_apu', table_name='detalle_presupuesto')
    op.drop_table('detalle_presupuesto')
    op.drop_index('uq_material_code_lower', table_name='material')
    op.drop_table('material')