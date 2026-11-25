# app/models/material.py
"""Base de datos de recursos (tabla `materiales`).

Cada recurso (material, mano de obra, equipo o herramienta) tiene un precio
unitario. Los APU son "recetas" que combinan estos recursos (ver
app/models/detalle_apu.py); el costo del APU se calcula a partir de ellos.

Un recurso nunca se elimina: se desactiva (RN-07), para no romper los APU que
ya lo usan.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, List

from pydantic import field_validator
from sqlalchemy import CheckConstraint, Column, Enum as SQLAlchemyEnum, Index, column, func
from sqlmodel import Field, Relationship, SQLModel

from app.core.validaciones import validarCodigo, validarTexto

if TYPE_CHECKING:
    from app.models.detalle_apu import DetalleApu


class CategoriaRecurso(str, Enum):
    """Categorías FIJAS de recursos (definidas por el sistema, no por el usuario)."""

    MATERIALES = "Materiales"
    MANO_DE_OBRA = "Mano de obra"
    EQUIPOS = "Equipos"
    HERRAMIENTAS = "Herramientas"


# Orden en que se muestran (filtros, formularios y detalle del APU)
CATEGORIAS_RECURSO: list[str] = [categoria.value for categoria in CategoriaRecurso]

LARGO_CODIGO = 50
LARGO_NOMBRE = 150
LARGO_UNIDAD = 30
LARGO_DESCRIPCION = 500


class MaterialValidacion(SQLModel):
    code: str = Field(max_length=LARGO_CODIGO)
    name: str = Field(max_length=LARGO_NOMBRE)
    unit: str = Field(max_length=LARGO_UNIDAD)
    category: CategoriaRecurso
    description: str | None = Field(default=None, max_length=LARGO_DESCRIPCION)
    unit_cost: int = Field(ge=0)
    # Costo real pagado. Si el formulario lo deja vacío se usa el costo cotizado.
    real_unit_cost: int = Field(ge=0)

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

    @field_validator("description")
    @classmethod
    def limpiar_descripcion(cls, valor: str | None) -> str | None:
        return valor.strip() or None if valor is not None else None


class Material(SQLModel, table=True):
    __tablename__ = "materiales"

    __table_args__ = (
        Index("uq_materiales_code_lower", func.lower(column("code")), unique=True),
        CheckConstraint("unit_cost >= 0", name="ck_materiales_unit_cost_no_negativo"),
        CheckConstraint("real_unit_cost >= 0", name="ck_materiales_real_unit_cost_no_negativo"),
    )

    id: int | None = Field(default=None, primary_key=True)

    code: str = Field(max_length=LARGO_CODIGO, nullable=False)
    name: str = Field(max_length=LARGO_NOMBRE, nullable=False)
    description: str | None = Field(default=None, max_length=LARGO_DESCRIPCION)
    unit: str = Field(max_length=LARGO_UNIDAD, nullable=False)

    category: CategoriaRecurso = Field(
        sa_column=Column(
            SQLAlchemyEnum(
                CategoriaRecurso,
                name="categoria_recurso",
                native_enum=False,
                create_constraint=True,
                length=50,
                values_callable=lambda enum_class: [m.value for m in enum_class],
            ),
            nullable=False,
        ),
    )

    # Precio unitario cotizado del recurso
    unit_cost: int = Field(ge=0, nullable=False)
    # Precio unitario real (lo que finalmente se paga)
    real_unit_cost: int = Field(
        default=0, ge=0, nullable=False, sa_column_kwargs={"server_default": "0"},
    )

    is_active: bool = Field(default=True, nullable=False)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: datetime | None = Field(default=None, nullable=True)

    detalles_apu: List["DetalleApu"] = Relationship(back_populates="material")
