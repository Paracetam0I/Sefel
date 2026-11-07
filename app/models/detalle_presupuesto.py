# app/models/detalle_presupuesto.py
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, Index
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.apu import APU
    from app.models.user import Presupuesto


class DetallePresupuesto(SQLModel, table=True):
    __tablename__ = "detalle_presupuesto"

    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_detalle_cantidad_positiva"),
        CheckConstraint("precio_unitario >= 0", name="ck_detalle_precio_no_negativo"),
        CheckConstraint("subtotal >= 0", name="ck_detalle_subtotal_no_negativo"),
        Index("ix_detalle_id_presupuesto", "id_presupuesto"),
        Index("ix_detalle_id_apu", "id_apu"),
        # Si quieres que un APU no se repita en el mismo presupuesto,
        # descomenta la siguiente línea:
        # UniqueConstraint("id_presupuesto", "id_apu", name="uq_detalle_presupuesto_apu"),
    )

    id: int | None = Field(default=None, primary_key=True)

    # --- FKs ---
    id_presupuesto: int = Field(
        foreign_key="presupuesto.id_presupuesto",
        nullable=False,
    )
    id_apu: int = Field(
        foreign_key="apu.id",
        nullable=False,
    )

    # --- Datos de la línea ---
    cantidad: int = Field(default=1, nullable=False, ge=1)
    precio_unitario: int = Field(nullable=False, ge=0)  # snapshot de APU.unit_cost
    subtotal: int = Field(nullable=False, ge=0)         # cantidad * precio_unitario

    descripcion: str | None = Field(default=None, max_length=500)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # --- Relaciones ---
    presupuesto: Optional["Presupuesto"] = Relationship(back_populates="detalles")
    apu: Optional["APU"] = Relationship(back_populates="detalles_presupuesto")