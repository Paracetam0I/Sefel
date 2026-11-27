"""
user.py — Modelo de usuario (tabla "user").

EN SIMPLE
    Cada fila es una persona que puede entrar a la app: su nombre de usuario,
    correo, contraseña (triturada), rol (qué puede hacer) y si está activa o
    bloqueada.

TÉCNICO
    SQLModel = pydantic + SQLAlchemy: la misma clase sirve para validar datos
    y como tabla (table=True). El rol se guarda como texto ("ADMIN"...) con un
    CHECK en la BD (native_enum=False + create_constraint=True), porque SQLite
    no tiene tipo ENUM. Un usuario tiene muchos presupuestos (1 a N).
"""
from typing import TYPE_CHECKING, List

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, Enum as SQLAlchemyEnum
from sqlmodel import Field, SQLModel, Relationship

# TYPE_CHECKING es False al ejecutar: este import solo lo ven los editores y
# los chequeadores de tipos. Evita un import circular user <-> presupuesto.
if TYPE_CHECKING:
    from app.models.presupuesto import Presupuesto

class UserRole(str, Enum):
    """Roles posibles. Qué puede hacer cada uno está en app/core/permisos.py."""
    ADMIN = "ADMIN"          # todo, incluida la gestión de usuarios
    MATERIALS = "MATERIALS"  # catálogo de APU
    BUDGETS = "BUDGETS"      # presupuestos
    BOTH = "BOTH"            # APU + presupuestos
    VIEWER = "VIEWER"        # solo ver y exportar presupuestos


class User(SQLModel, table=True):
    """Una cuenta de usuario. La contraseña se guarda solo como hash (security.py)."""
    __tablename__ = "user"

    id: int | None = Field(default=None, primary_key=True)

    username: str = Field(
        unique=True,
        index=True,
    )

    email: str = Field(
        unique=True,
        index=True,
    )

    hashed_password: str

    full_name: str

    role: UserRole = Field(
        default=UserRole.VIEWER,
        sa_column=Column(
            SQLAlchemyEnum(
                UserRole,
                name="user_role",
                native_enum=False,
                create_constraint=True,
                values_callable=lambda enum_class: [
                    member.value for member in enum_class
                ],
            ),
            nullable=False,
        ),
    )

    is_active: bool = Field(default=True)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    last_login: datetime | None = Field(
        default=None,
        nullable=True,
    )

    # --- Bloqueo por intentos fallidos (ver app/core/bloqueo.py) ---
    failed_attempts: int = Field(
        default=0, nullable=False, sa_column_kwargs={"server_default": "0"},
    )
    # Motivo por el que el sistema desactivó la cuenta (None = no bloqueada)
    lock_reason: str | None = Field(default=None, max_length=255, nullable=True)
    locked_at: datetime | None = Field(default=None, nullable=True)
    # Bloqueo temporal: solo se usa con el único ADMIN activo, que no se desactiva
    locked_until: datetime | None = Field(default=None, nullable=True)
    # Relación 1..N: usuario.presupuestos -> lista de sus presupuestos
    presupuestos: List["Presupuesto"] = Relationship(back_populates="usuario")


# Presupuesto vive ahora en app/models/presupuesto.py. Se reexporta aquí para
# no romper los imports existentes (`from app.models.user import Presupuesto`)
# y para que la relación User.presupuestos siempre quede registrada.
from app.models.presupuesto import (  # noqa: E402
    PorcentajesValidacion,
    Presupuesto,
    PresupuestoValidacion,
    StatusPresupuestos,
)
