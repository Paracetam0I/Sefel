# app/models/detalle_presupuesto.py
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, Index
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.apu import APU
    from app.models.material import Material
    from app.models.user import Presupuesto


class DetallePresupuesto(SQLModel, table=True):
    __tablename__ = "detalle_presupuesto"

    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_detalle_cantidad_positiva"),
        CheckConstraint(
            "estimated_unit_cost >= 0", name="ck_detalle_costo_estimado_no_negativo"
        ),
        CheckConstraint("subtotal >= 0", name="ck_detalle_subtotal_no_negativo"),
        CheckConstraint(
            "costo_directo >= 0", name="ck_detalle_costo_directo_no_negativo"
        ),
        CheckConstraint(
            "costo_indirecto >= 0", name="ck_detalle_costo_indirecto_no_negativo"
        ),
        Index("ix_detalle_id_presupuesto", "id_presupuesto"),
        Index("ix_detalle_id_apu", "id_apu"),
        Index("ix_detalle_id_material", "id_material"),
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
    id_material: int = Field(
        foreign_key="material.id",
        nullable=False,
    )
    # --- Datos de la línea ---
    unit: str = Field(max_length=30, nullable=False)
    cantidad: int = Field(default=1, nullable=False, ge=1)
    estimated_unit_cost: int = Field(nullable=False, ge=0)  # snapshot de APU.unit_cost
    cantidad: int = Field(default=1, nullable=False, ge=1)
    subtotal: int = Field(nullable=False, ge=0)         # cantidad * estimated_unit_cost

    costo_directo: int = Field(default=0, nullable=False, ge=0)
    costo_indirecto: int = Field(default=0, nullable=False, ge=0)

    descripcion: str | None = Field(default=None, max_length=500)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # --- Relaciones ---
    presupuesto: Optional["Presupuesto"] = Relationship(back_populates="detalles")
    apu: Optional["APU"] = Relationship(back_populates="detalles_presupuesto")
    material: Optional["Material"] = Relationship()