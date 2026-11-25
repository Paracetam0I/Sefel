from typing import TYPE_CHECKING, List
from datetime import datetime, timezone

from sqlalchemy import Index, column, func
from sqlmodel import Field, SQLModel, Relationship
from pydantic import field_validator

from app.core.validaciones import validarCodigo, validarTexto

if TYPE_CHECKING:
    from app.models.detalle_apu import DetalleApu
    from app.models.detalle_presupuesto import DetallePresupuesto

class APUValidacion(SQLModel):
    code: str = Field(max_length=50)
    name: str = Field(max_length=150)
    unit: str = Field(max_length=30)
    category: str | None = Field(default=None, max_length=100)
    description: str | None = None
    # Sin costos: el costo unitario del APU se calcula con sus recursos
    # (app.core.calculos.costosApu).

    @field_validator("code")
    @classmethod
    def validar_codigo(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("El código es obligatorio.")
        return validarCodigo(valor)   # siempre en mayúsculas

    @field_validator("name")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("El nombre es obligatorio.")
        return validarTexto(valor, "El nombre")

    @field_validator("unit")
    @classmethod
    def validar_unidad(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("La unidad es obligatoria.")
        return valor

    @field_validator("category")
    @classmethod
    def validar_categoria(cls, valor: str | None) -> str | None:
        if valor is None or not valor.strip():
            return None
        return validarTexto(valor, "La categoría")

    @field_validator("description")
    @classmethod
    def limpiar_opcionales(cls, valor: str | None) -> str | None:
        return valor.strip() or None if valor is not None else None


class APU(SQLModel, table=True):
    """APU = "receta": combina recursos de la base de datos (tabla materiales).

    No guarda costo propio. Su costo directo unitario (CDU) es la suma de
    cantidad × precio de cada recurso (ver app/core/calculos.py).
    """

    __tablename__ = "apu"

    __table_args__ = (
        Index(
            "uq_apu_code_lower",
            func.lower(column("code")),
            unique=True,
        ),
    )

    id: int | None = Field(default=None, primary_key=True)

    code: str = Field(max_length=50, nullable=False)
    name: str = Field(max_length=150, nullable=False)
    description: str | None = Field(default=None)
    unit: str = Field(max_length=30, nullable=False)
    category: str | None = Field(default=None, max_length=100)

    is_active: bool = Field(default=True, nullable=False)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: datetime | None = Field(default=None, nullable=True)

    # Recursos de la receta; se borran junto con el APU
    recursos: List["DetalleApu"] = Relationship(
        back_populates="apu",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "DetalleApu.id",
        },
    )

    detalles_presupuesto: List["DetallePresupuesto"] = Relationship(
        back_populates="apu",
    )