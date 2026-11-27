"""
apu.py — APU: Análisis de Precio Unitario (catálogo de partidas).

EN SIMPLE
    Un APU es una "ficha de precio" reutilizable: por ejemplo
    "Hormigón H25, unidad m3, cuesta $95.000". Es el catálogo desde donde se
    eligen los ítems al armar un presupuesto.
    Tiene dos precios: el COTIZADO (lo que se estima) y el REAL (lo que de
    verdad se paga).

TÉCNICO
    Dos clases:
      - APUValidacion: solo valida lo que llega del formulario (no es tabla).
      - APU (table=True): la tabla "apu".
    Restricciones en la BD: código único sin distinguir mayúsculas (índice
    sobre lower(code)) y costos >= 0. No se borra: se desactiva (is_active),
    porque presupuestos antiguos pueden referenciarlo.
"""
from typing import TYPE_CHECKING, List
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Index, column, func
from sqlmodel import Field, SQLModel, Relationship
from pydantic import field_validator

from app.core.validaciones import validarCodigo, validarTexto

if TYPE_CHECKING:
    from app.models.detalle_presupuesto import DetallePresupuesto

class APUValidacion(SQLModel):
    """Valida y limpia los datos del formulario de APU antes de guardarlos.

    Cada @field_validator se ejecuta para su campo: quita espacios, rechaza
    vacíos obligatorios y aplica las reglas de app/core/validaciones.py.
    Si algo falla, pydantic lanza ValidationError y el router muestra el error.
    """
    code: str = Field(max_length=50)
    name: str = Field(max_length=150)
    unit: str = Field(max_length=30)
    category: str | None = Field(default=None, max_length=100)
    description: str | None = None
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

    @field_validator("category")
    @classmethod
    def validar_categoria(cls, valor: str | None) -> str | None:
        if valor is None or not valor.strip():
            return None
        return validarTexto(valor, "La categoría")

    @field_validator("description")
    @classmethod
    def limpiar_opcionales(cls, valor: str | None) -> str | None:
        # Texto vacío o solo espacios -> None (se guarda NULL, no "")
        return valor.strip() or None if valor is not None else None


class APU(SQLModel, table=True):
    """Fila del catálogo de APU (tabla "apu")."""
    __tablename__ = "apu"

    # Restricciones a nivel de BD (la última defensa, aunque falle la validación de Python)
    __table_args__ = (
        # "PRE-01" y "pre-01" cuentan como el mismo código
        Index(
            "uq_apu_code_lower",
            func.lower(column("code")),
            unique=True,
        ),
        CheckConstraint(
            "unit_cost >= 0",
            name="ck_apu_unit_cost_non_negative",
        ),
        CheckConstraint(
            "real_unit_cost >= 0",
            name="ck_apu_real_unit_cost_non_negative",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)

    code: str = Field(max_length=50, nullable=False)
    name: str = Field(max_length=150, nullable=False)
    description: str | None = Field(default=None)
    unit: str = Field(max_length=30, nullable=False)
    category: str | None = Field(default=None, max_length=100)

    # Costo cotizado (estimado) con el que se crea el APU
    unit_cost: int = Field(ge=0, nullable=False)
    # Costo real: lo que finalmente se paga al ejecutar el presupuesto
    real_unit_cost: int = Field(
        default=0,
        ge=0,
        nullable=False,
        sa_column_kwargs={"server_default": "0"},
    )

    # Borrado lógico: False = oculto del catálogo, pero sigue en la BD
    is_active: bool = Field(default=True, nullable=False)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: datetime | None = Field(default=None, nullable=True)

    # Relación 1..N: en qué líneas de presupuestos se usa este APU
    detalles_presupuesto: List["DetallePresupuesto"] = Relationship(
        back_populates="apu",
    )