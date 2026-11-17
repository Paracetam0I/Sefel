"""presupuesto_fechas_y_ruta_opcionales

Revision ID: 5103b7fc71aa
Revises: 92515388ea77
Create Date: 2026-11-17 09:04:04.042094

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5103b7fc71aa'
down_revision: Union[str, Sequence[str], None] = '92515388ea77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Fechas y ruta de reporte pasan a ser opcionales (el formulario ya las trata así)."""
    with op.batch_alter_table('presupuesto') as batch_op:
        batch_op.alter_column('start_date', existing_type=sa.DateTime(), nullable=True)
        batch_op.alter_column('end_date', existing_type=sa.DateTime(), nullable=True)
        batch_op.alter_column('ruta_reporte', existing_type=sa.String(length=75), nullable=True)


def downgrade() -> None:
    """Vuelve a exigirlas; rellena los vacíos antes para no romper la restricción."""
    op.execute("UPDATE presupuesto SET start_date = created_at WHERE start_date IS NULL")
    op.execute("UPDATE presupuesto SET end_date = created_at WHERE end_date IS NULL")
    op.execute("UPDATE presupuesto SET ruta_reporte = '' WHERE ruta_reporte IS NULL")
    with op.batch_alter_table('presupuesto') as batch_op:
        batch_op.alter_column('start_date', existing_type=sa.DateTime(), nullable=False)
        batch_op.alter_column('end_date', existing_type=sa.DateTime(), nullable=False)
        batch_op.alter_column('ruta_reporte', existing_type=sa.String(length=75), nullable=False)