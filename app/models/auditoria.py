# app/models/auditoria.py
"""
auditoria.py — Historial de bloqueos y reactivaciones de cuentas.

EN SIMPLE
    Es un "libro de actas": cada vez que una cuenta se bloquea, se desbloquea
    o se desactiva, se anota quién lo hizo, a quién, cuándo y por qué.
    Solo se agregan filas; nunca se editan.

TÉCNICO
    Tabla "auditoria_cuentas" con dos FK a user: id_usuario (afectado) e
    id_actor (quien actuó; NULL = el sistema). Las filas las crea
    registrarAuditoria() en app/core/bloqueo.py.
"""
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, Enum as SQLAlchemyEnum
from sqlmodel import Field, SQLModel


class AccionAuditoria(str, Enum):
    BLOQUEO = "BLOQUEO"                    # cuenta desactivada por intentos fallidos
    BLOQUEO_TEMPORAL = "BLOQUEO_TEMPORAL"  # único ADMIN activo: bloqueo corto
    REACTIVACION = "REACTIVACION"          # un ADMIN reactivó la cuenta
    DESACTIVACION = "DESACTIVACION"        # un ADMIN desactivó la cuenta


class AuditoriaCuenta(SQLModel, table=True):
    """Registro de bloqueos y reactivaciones de cuentas (quién, cuándo, motivo)."""

    __tablename__ = "auditoria_cuentas"

    id: int | None = Field(default=None, primary_key=True)

    # Cuenta afectada
    id_usuario: int = Field(foreign_key="user.id", nullable=False, index=True)
    # Quién hizo la acción (None = el sistema, p. ej. un bloqueo automático)
    id_actor: int | None = Field(default=None, foreign_key="user.id", nullable=True)

    accion: AccionAuditoria = Field(
        sa_column=Column(
            SQLAlchemyEnum(
                AccionAuditoria,
                name="accion_auditoria",
                native_enum=False,
                create_constraint=True,
                values_callable=lambda enum_class: [m.value for m in enum_class],
            ),
            nullable=False,
        ),
    )
    motivo: str = Field(max_length=255, nullable=False)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
