# app/models/detalle_presupuesto.py
"""
detalle_presupuesto.py — Ítems (líneas) de un presupuesto.

EN SIMPLE
    Si el presupuesto es una boleta, cada DetallePresupuesto es una línea:
    "Hormigón H25 — 10 m3 — $95.000 c/u — subtotal $950.000".
    Une un Presupuesto con un APU del catálogo.

    Importante: al agregar el ítem se COPIAN los precios del APU (snapshot).
    Si mañana el APU sube de precio, los presupuestos ya armados no cambian.

TÉCNICO
    Tabla intermedia con datos propios entre presupuesto (N) y apu (N).
    FK: id_presupuesto -> presupuesto, id_apu -> apu, ambas indexadas.
    Los subtotales los calcula calcularSubtotales() en app/core/calculos.py.
"""
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, Index
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.apu import APU
    from app.models.presupuesto import Presupuesto


class DetallePresupuesto(SQLModel, table=True):
    """Una línea del presupuesto: qué APU, cuántas unidades y a qué precio."""
    __tablename__ = "detalle_presupuesto"

    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_detalle_cantidad_positiva"),
        CheckConstraint(
            "estimated_unit_cost >= 0", name="ck_detalle_costo_estimado_no_negativo"
        ),
        CheckConstraint("subtotal >= 0", name="ck_detalle_subtotal_no_negativo"),
        CheckConstraint(
            "real_unit_cost >= 0", name="ck_detalle_costo_real_no_negativo"
        ),
        CheckConstraint(
            "real_subtotal >= 0", name="ck_detalle_subtotal_real_no_negativo"
        ),
        CheckConstraint(
            "costo_directo >= 0", name="ck_detalle_costo_directo_no_negativo"
        ),
        CheckConstraint(
            "costo_indirecto >= 0", name="ck_detalle_costo_indirecto_no_negativo"
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
    cantidad: int = Field(default=1, nullable=False, ge=1)

    # Valores cotizados (estimados)
    estimated_unit_cost: int = Field(nullable=False, ge=0)  # snapshot de APU.unit_cost
    subtotal: int = Field(nullable=False, ge=0)             # cantidad * estimated_unit_cost

    # Valores reales (lo que finalmente se paga)
    real_unit_cost: int = Field(                             # snapshot de APU.real_unit_cost
        default=0,
        nullable=False,
        ge=0,
        sa_column_kwargs={"server_default": "0"},
    )
    real_subtotal: int = Field(                              # cantidad * real_unit_cost
        default=0,
        nullable=False,
        ge=0,
        sa_column_kwargs={"server_default": "0"},
    )

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
