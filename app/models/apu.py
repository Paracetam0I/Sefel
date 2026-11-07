from typing import TYPE_CHECKING, List
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Index, column, func
from sqlmodel import Field, SQLModel, Relationship
from pydantic import field_validator

if TYPE_CHECKING:
    from app.models.detalle_presupuesto import DetallePresupuesto

class APUValidacion(SQLModel):
    code: str = Field(max_length=50)
    name: str = Field(max_length=150)
    unit: str = Field(max_length=30)
    category: str | None = Field(default=None, max_length=100)
    description: str | None = None
    unit_cost: int = Field(ge=0)

    @field_validator("code")
    @classmethod
    def validar_codigo(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("El código es obligatorio.")
        return valor

    @field_validator("name")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("El nombre es obligatorio.")
        return valor

    @field_validator("unit")
    @classmethod
    def validar_unidad(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("La unidad es obligatoria.")
        return valor

    @field_validator("category", "description")
    @classmethod
    def limpiar_opcionales(cls, valor: str | None) -> str | None:
        return valor.strip() or None if valor is not None else None


class APU(SQLModel, table=True):
    __tablename__ = "apu"

    __table_args__ = (
        Index(
            "uq_apu_code_lower",
            func.lower(column("code")),
            unique=True,
        ),
        CheckConstraint(
            "unit_cost >= 0",
            name="ck_apu_unit_cost_non_negative",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)

    code: str = Field(max_length=50, nullable=False)
    name: str = Field(max_length=150, nullable=False)
    description: str | None = Field(default=None)
    unit: str = Field(max_length=30, nullable=False)
    category: str | None = Field(default=None, max_length=100)

    unit_cost: int = Field(ge=0, nullable=False)

    is_active: bool = Field(default=True, nullable=False)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: datetime | None = Field(default=None, nullable=True)

    detalles_presupuesto: List["DetallePresupuesto"] = Relationship(
        back_populates="apu",
    )