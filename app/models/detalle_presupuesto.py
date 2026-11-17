# app/models/detalle_presupuesto.py
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, Index
from sqlmodel import Field, Relationship, SQLModel

from decimal import Decimal

from sqlalchemy import Column

from app.core.money import DecimalText

if TYPE_CHECKING:
    from app.models.apu import APU
    from app.models.user import Presupuesto


class DetallePresupuesto(SQLModel, table=True):
    __tablename__ = "detalle_presupuesto"

    __table_args__ = (
        CheckConstraint("CAST(cantidad AS NUMERIC) > 0", name="ck_detalle_cantidad_positiva"),
        CheckConstraint(
            "CAST(estimated_unit_cost AS NUMERIC) >= 0", name="ck_detalle_costo_estimado_no_negativo"
        ),
        CheckConstraint("CAST(subtotal AS NUMERIC) >= 0", name="ck_detalle_subtotal_no_negativo"),
        CheckConstraint(
            "CAST(costo_directo AS NUMERIC) >= 0", name="ck_detalle_costo_directo_no_negativo"
        ),
        CheckConstraint(
            "CAST(costo_indirecto AS NUMERIC) >= 0", name="ck_detalle_costo_indirecto_no_negativo"
        ),
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
    unit: str = Field(max_length=30, nullable=False)
    cantidad: Decimal = Field(
        default=Decimal("1"),
        sa_column=Column(DecimalText(), nullable=False),
    )
    estimated_unit_cost: Decimal = Field(
        sa_column=Column(DecimalText(), nullable=False),
    )
    subtotal: Decimal = Field(
        sa_column=Column(DecimalText(), nullable=False),  # cantidad * estimated_unit_cost, redondeado
    )
    costo_directo: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(DecimalText(), nullable=False),
    )
    costo_indirecto: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(DecimalText(), nullable=False),
    )

    descripcion: str | None = Field(default=None, max_length=500)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # --- Relaciones ---
    presupuesto: Optional["Presupuesto"] = Relationship(back_populates="detalles")
    apu: Optional["APU"] = Relationship(back_populates="detalles_presupuesto")