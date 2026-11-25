# app/models/detalle_apu.py
"""Recursos de un APU (la "receta"): qué recurso usa y cuánto consume.

- Si se borra el APU, se borran sus líneas (ON DELETE CASCADE).
- Un recurso en uso no se puede borrar (ON DELETE RESTRICT): se desactiva.
- Un mismo recurso aparece una sola vez por APU; para usar más, se edita la cantidad.

Costo parcial de la línea = cantidad × precio unitario del recurso
(ver app/core/calculos.py).
"""
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.apu import APU
    from app.models.material import Material


class DetalleApu(SQLModel, table=True):
    __tablename__ = "detalles_apu"

    __table_args__ = (
        UniqueConstraint("id_apu", "id_material", name="uq_detalles_apu_apu_material"),
        CheckConstraint("cantidad > 0", name="ck_detalles_apu_cantidad_positiva"),
        Index("ix_detalles_apu_id_material", "id_material"),
    )

    id: int | None = Field(default=None, primary_key=True)

    id_apu: int = Field(foreign_key="apu.id", ondelete="CASCADE", nullable=False)
    id_material: int = Field(foreign_key="materiales.id", ondelete="RESTRICT", nullable=False)

    unit: str = Field(max_length=30, nullable=False)
    # Consumo del recurso por unidad de APU (admite decimales: 0,35 m3, 1,2 HH...)
    cantidad: float = Field(gt=0, nullable=False)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: datetime | None = Field(default=None, nullable=True)

    apu: Optional["APU"] = Relationship(back_populates="recursos")
    material: Optional["Material"] = Relationship(back_populates="detalles_apu")
