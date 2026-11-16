"""add real costs and budget percentages

- APU: costo real unitario (real_unit_cost).
- DetallePresupuesto: costo real unitario y subtotal real.
- Presupuesto: costo neto fijo, porcentajes (gastos generales, IVA, utilidad)
  y totales/montos calculados.
- Elimina la tabla temporal test_model.

Los datos existentes se rellenan con costo real = costo cotizado, para que
los totales reales partan iguales a los cotizados.

Revision ID: cc5d56d0ebf4
Revises: cbb87f34d7fe
Create Date: 2026-11-16 19:15:29.149434

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc5d56d0ebf4'
down_revision: Union[str, Sequence[str], None] = 'cbb87f34d7fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# El indice por expresion no se puede reflejar en SQLite, asi que el modo
# batch (que recrea la tabla) lo pierde: se vuelve a crear a mano.
INDICE_APU_CODE = "CREATE UNIQUE INDEX IF NOT EXISTS uq_apu_code_lower ON apu (lower(code))"

COLUMNAS_PRESUPUESTO_INT = (
    "costo_neto",
    "total_cotizado",
    "total_real",
    "monto_gastos_generales",
    "monto_iva",
    "monto_utilidad",
    "monto_costo_neto",
)
COLUMNAS_PRESUPUESTO_PCT = ("pct_gastos_generales", "pct_iva", "pct_utilidad")


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DROP TABLE IF EXISTS test_model")

    # --- APU ---
    with op.batch_alter_table('apu', schema=None) as batch_op:
        batch_op.add_column(sa.Column('real_unit_cost', sa.Integer(), server_default='0', nullable=False))
        batch_op.create_check_constraint('ck_apu_real_unit_cost_non_negative', 'real_unit_cost >= 0')
    op.execute(INDICE_APU_CODE)
    op.execute("UPDATE apu SET real_unit_cost = unit_cost")

    # --- DetallePresupuesto ---
    with op.batch_alter_table('detalle_presupuesto', schema=None) as batch_op:
        batch_op.add_column(sa.Column('real_unit_cost', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('real_subtotal', sa.Integer(), server_default='0', nullable=False))
        batch_op.create_check_constraint('ck_detalle_costo_real_no_negativo', 'real_unit_cost >= 0')
        batch_op.create_check_constraint('ck_detalle_subtotal_real_no_negativo', 'real_subtotal >= 0')
    op.execute(
        "UPDATE detalle_presupuesto "
        "SET real_unit_cost = estimated_unit_cost, real_subtotal = subtotal"
    )

    # --- Presupuesto ---
    with op.batch_alter_table('presupuesto', schema=None) as batch_op:
        for columna in COLUMNAS_PRESUPUESTO_INT:
            batch_op.add_column(sa.Column(columna, sa.Integer(), server_default='0', nullable=False))
        for columna in COLUMNAS_PRESUPUESTO_PCT:
            batch_op.add_column(sa.Column(columna, sa.Float(), server_default='0', nullable=False))
            batch_op.create_check_constraint(
                f'ck_presupuesto_{columna}_rango', f'{columna} >= 0 AND {columna} <= 100'
            )
        batch_op.create_check_constraint('ck_presupuesto_costo_neto_no_negativo', 'costo_neto >= 0')
        batch_op.create_check_constraint('ck_presupuesto_total_cotizado_no_negativo', 'total_cotizado >= 0')
        batch_op.create_check_constraint('ck_presupuesto_total_real_no_negativo', 'total_real >= 0')

    # Totales de los presupuestos existentes (porcentajes en 0 => neto = base)
    op.execute(
        "UPDATE presupuesto SET "
        "total_cotizado = COALESCE((SELECT SUM(d.subtotal) FROM detalle_presupuesto d "
        "  WHERE d.id_presupuesto = presupuesto.id_presupuesto), 0), "
        "total_real = COALESCE((SELECT SUM(d.real_subtotal) FROM detalle_presupuesto d "
        "  WHERE d.id_presupuesto = presupuesto.id_presupuesto), 0)"
    )
    op.execute(
        "UPDATE presupuesto SET monto_costo_neto = "
        "CASE WHEN costo_directo > 0 THEN costo_directo ELSE total_real END"
    )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('presupuesto', schema=None) as batch_op:
        batch_op.drop_constraint('ck_presupuesto_total_real_no_negativo', type_='check')
        batch_op.drop_constraint('ck_presupuesto_total_cotizado_no_negativo', type_='check')
        batch_op.drop_constraint('ck_presupuesto_costo_neto_no_negativo', type_='check')
        for columna in COLUMNAS_PRESUPUESTO_PCT:
            batch_op.drop_constraint(f'ck_presupuesto_{columna}_rango', type_='check')
            batch_op.drop_column(columna)
        for columna in COLUMNAS_PRESUPUESTO_INT:
            batch_op.drop_column(columna)

    with op.batch_alter_table('detalle_presupuesto', schema=None) as batch_op:
        batch_op.drop_constraint('ck_detalle_subtotal_real_no_negativo', type_='check')
        batch_op.drop_constraint('ck_detalle_costo_real_no_negativo', type_='check')
        batch_op.drop_column('real_subtotal')
        batch_op.drop_column('real_unit_cost')

    with op.batch_alter_table('apu', schema=None) as batch_op:
        batch_op.drop_constraint('ck_apu_real_unit_cost_non_negative', type_='check')
        batch_op.drop_column('real_unit_cost')
    op.execute(INDICE_APU_CODE)

    op.create_table(
        'test_model',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
