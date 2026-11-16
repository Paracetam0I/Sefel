"""seguridad de cuentas, auditoria y total del presupuesto

- user: failed_attempts, lock_reason, locked_at, locked_until (bloqueo por
  intentos fallidos de inicio de sesión).
- auditoria_cuentas: registro de bloqueos y reactivaciones.
- presupuesto: monto_total y recálculo de montos con el formato de cotización:
  GG y utilidad sobre el costo directo, neto = CD + GG + utilidad,
  IVA sobre el neto y total = neto + IVA.

Revision ID: 59241f60df74
Revises: cc5d56d0ebf4
Create Date: 2026-11-16 20:20:01.576498

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '59241f60df74'
down_revision: Union[str, Sequence[str], None] = 'cc5d56d0ebf4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ACCIONES = ('BLOQUEO', 'BLOQUEO_TEMPORAL', 'REACTIVACION', 'DESACTIVACION')

BASE = "(CASE WHEN costo_directo > 0 THEN costo_directo ELSE total_real END)"
NETO = "(CASE WHEN costo_neto > 0 THEN costo_neto ELSE monto_costo_neto END)"


def _redondear(expresion: str) -> str:
    return f"CAST(ROUND({expresion}) AS INTEGER)"


def upgrade() -> None:
    """Upgrade schema."""
    # --- Auditoría ---
    op.create_table(
        'auditoria_cuentas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('id_usuario', sa.Integer(), nullable=False),
        sa.Column('id_actor', sa.Integer(), nullable=True),
        sa.Column('accion', sa.String(length=16), nullable=False),
        sa.Column('motivo', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "accion IN ('" + "', '".join(ACCIONES) + "')", name='accion_auditoria',
        ),
        sa.ForeignKeyConstraint(['id_actor'], ['user.id']),
        sa.ForeignKeyConstraint(['id_usuario'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_auditoria_cuentas_created_at', 'auditoria_cuentas', ['created_at'])
    op.create_index('ix_auditoria_cuentas_id_usuario', 'auditoria_cuentas', ['id_usuario'])

    # --- Bloqueo de cuentas (ADD COLUMN simple: no recrea la tabla user) ---
    op.add_column('user', sa.Column('failed_attempts', sa.Integer(), server_default='0', nullable=False))
    op.add_column('user', sa.Column('lock_reason', sa.String(length=255), nullable=True))
    op.add_column('user', sa.Column('locked_at', sa.DateTime(), nullable=True))
    op.add_column('user', sa.Column('locked_until', sa.DateTime(), nullable=True))

    # --- Total del presupuesto y recálculo con el formato de cotización ---
    op.add_column('presupuesto', sa.Column('monto_total', sa.Integer(), server_default='0', nullable=False))
    op.execute(
        "UPDATE presupuesto SET "
        f"monto_gastos_generales = {_redondear(BASE + ' * pct_gastos_generales / 100.0')}, "
        f"monto_utilidad = {_redondear(BASE + ' * pct_utilidad / 100.0')}"
    )
    op.execute(
        f"UPDATE presupuesto SET monto_costo_neto = "
        f"{BASE} + monto_gastos_generales + monto_utilidad"
    )
    op.execute(
        f"UPDATE presupuesto SET monto_iva = {_redondear(NETO + ' * pct_iva / 100.0')}"
    )
    op.execute(f"UPDATE presupuesto SET monto_total = {NETO} + monto_iva")


def downgrade() -> None:
    """Downgrade schema."""
    # Vuelve a la fórmula anterior (IVA y utilidad sobre base + GG; neto con IVA)
    con_gg = f"({BASE} + monto_gastos_generales)"
    op.execute(
        "UPDATE presupuesto SET "
        f"monto_iva = {_redondear(con_gg + ' * pct_iva / 100.0')}, "
        f"monto_utilidad = {_redondear(con_gg + ' * pct_utilidad / 100.0')}"
    )
    op.execute(
        f"UPDATE presupuesto SET monto_costo_neto = "
        f"{BASE} + monto_gastos_generales + monto_iva + monto_utilidad"
    )
    with op.batch_alter_table('presupuesto', schema=None) as batch_op:
        batch_op.drop_column('monto_total')

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('locked_until')
        batch_op.drop_column('locked_at')
        batch_op.drop_column('lock_reason')
        batch_op.drop_column('failed_attempts')

    op.drop_index('ix_auditoria_cuentas_id_usuario', table_name='auditoria_cuentas')
    op.drop_index('ix_auditoria_cuentas_created_at', table_name='auditoria_cuentas')
    op.drop_table('auditoria_cuentas')
