"""detalle_presupuesto_dinero_decimal

Revision ID: 92515388ea77
Revises: cbb87f34d7fe
Create Date: 2026-11-16 22:34:14.918312

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = '92515388ea77'
down_revision: Union[str, Sequence[str], None] = 'cbb87f34d7fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _crear_detalle(como_texto: bool) -> None:
    """Crea detalle_presupuesto con dinero como texto (Decimal) o como entero (antes)."""
    tipo = sa.String(length=40) if como_texto else sa.Integer()

    def valor(columna: str) -> str:
        return f"CAST({columna} AS NUMERIC)" if como_texto else columna

    op.create_table(
        'detalle_presupuesto',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('id_presupuesto', sa.Integer(), nullable=False),
        sa.Column('id_apu', sa.Integer(), nullable=False),
        sa.Column('unit', sqlmodel.sql.sqltypes.AutoString(length=30), nullable=False),
        sa.Column('cantidad', tipo, nullable=False),
        sa.Column('estimated_unit_cost', tipo, nullable=False),
        sa.Column('subtotal', tipo, nullable=False),
        sa.Column('costo_directo', tipo, nullable=False),
        sa.Column('costo_indirecto', tipo, nullable=False),
        sa.Column('descripcion', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.CheckConstraint(f"{valor('cantidad')} > 0", name='ck_detalle_cantidad_positiva'),
        sa.CheckConstraint(f"{valor('costo_directo')} >= 0", name='ck_detalle_costo_directo_no_negativo'),
        sa.CheckConstraint(f"{valor('costo_indirecto')} >= 0", name='ck_detalle_costo_indirecto_no_negativo'),
        sa.CheckConstraint(f"{valor('estimated_unit_cost')} >= 0", name='ck_detalle_costo_estimado_no_negativo'),
        sa.CheckConstraint(f"{valor('subtotal')} >= 0", name='ck_detalle_subtotal_no_negativo'),
        sa.ForeignKeyConstraint(['id_apu'], ['apu.id']),
        sa.ForeignKeyConstraint(['id_presupuesto'], ['presupuesto.id_presupuesto']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_detalle_id_apu', 'detalle_presupuesto', ['id_apu'], unique=False)
    op.create_index('ix_detalle_id_presupuesto', 'detalle_presupuesto', ['id_presupuesto'], unique=False)


def _borrar_detalle() -> None:
    op.drop_index('ix_detalle_id_presupuesto', table_name='detalle_presupuesto')
    op.drop_index('ix_detalle_id_apu', table_name='detalle_presupuesto')
    op.drop_table('detalle_presupuesto')


def upgrade() -> None:
    """Dinero y cantidades pasan de entero a Decimal guardado como texto."""
    _borrar_detalle()
    _crear_detalle(como_texto=True)


def downgrade() -> None:
    """Vuelve a la versión con enteros."""
    _borrar_detalle()
    _crear_detalle(como_texto=False)