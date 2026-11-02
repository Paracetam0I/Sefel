"""rename presupuesto columns to snake_case

Revision ID: ab7c4e2173a2
Revises: de66a7578e43
Create Date: 2026-11-02 11:05:41.507558

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ab7c4e2173a2'
down_revision: Union[str, Sequence[str], None] = 'de66a7578e43'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("presupuesto") as batch_op:
        batch_op.alter_column("idPresupuesto", new_column_name="id_presupuesto")
        batch_op.alter_column("idUsuario",     new_column_name="id_usuario")
        batch_op.alter_column("clientName",    new_column_name="client_name")
        batch_op.alter_column("estimateincome", new_column_name="estimate_income")
        batch_op.alter_column("startdate",     new_column_name="start_date")
        batch_op.alter_column("enddate",       new_column_name="end_date")
        batch_op.alter_column("createdAt",     new_column_name="created_at")
        batch_op.alter_column("updatedAt",     new_column_name="updated_at")
        batch_op.alter_column("costoDirecto",  new_column_name="costo_directo")
        batch_op.alter_column("costoIndirecto", new_column_name="costo_indirecto")
        batch_op.alter_column("ruteReporte",   new_column_name="ruta_reporte")


def downgrade() -> None:
    with op.batch_alter_table("presupuesto") as batch_op:
        batch_op.alter_column("id_presupuesto", new_column_name="idPresupuesto")
        batch_op.alter_column("id_usuario",     new_column_name="idUsuario")
        batch_op.alter_column("client_name",    new_column_name="clientName")
        batch_op.alter_column("estimate_income",    new_column_name="estimateincome")
        batch_op.alter_column("start_date",    new_column_name="startdate")
        batch_op.alter_column("end_date",    new_column_name="enddate")
        batch_op.alter_column("created_at",    new_column_name="createdAt")
        batch_op.alter_column("updated_at",    new_column_name="updatedAt")
        batch_op.alter_column("costo_directo",    new_column_name="costoDirecto")
        batch_op.alter_column("costo_indirecto",    new_column_name="costoIndirecto")
        batch_op.alter_column("ruta_reporte",    new_column_name="ruteReporte")
