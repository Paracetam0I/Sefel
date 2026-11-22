"""codigos en mayusculas

Desde ahora los códigos de APU y de presupuestos se guardan siempre en
MAYÚSCULAS (app/core/validaciones.py: validarCodigo). Esta migración convierte
los que ya existían.

Se hace en Python y no con UPPER() de SQLite porque este solo convierte letras
ASCII (dejaría "ñ" o "á" en minúscula).

downgrade: no hace nada. No se puede saber cómo estaba escrito cada código
originalmente, y tenerlo en mayúsculas es válido también para la versión
anterior (las búsquedas de duplicados ya ignoraban mayúsculas/minúsculas).

Revision ID: 7a3c1e9d2b40
Revises: 59241f60df74
Create Date: 2026-11-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a3c1e9d2b40'
down_revision: Union[str, Sequence[str], None] = '59241f60df74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLAS = (("apu", "id"), ("presupuesto", "id_presupuesto"))


def upgrade() -> None:
    """Upgrade schema."""
    conexion = op.get_bind()
    for tabla, clave in TABLAS:
        filas = conexion.execute(sa.text(f"SELECT {clave}, code FROM {tabla}")).fetchall()
        for id_fila, codigo in filas:
            if codigo is not None and codigo != codigo.upper():
                conexion.execute(
                    sa.text(f"UPDATE {tabla} SET code = :codigo WHERE {clave} = :id"),
                    {"codigo": codigo.upper(), "id": id_fila},
                )


def downgrade() -> None:
    """Downgrade schema."""
    # Irreversible a propósito: ver la explicación arriba.
    pass
