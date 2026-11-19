# app/models/presupuesto.py
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from pydantic import BaseModel, Field as CampoValidacion, NaiveDatetime, ValidationInfo, field_validator
from sqlalchemy import CheckConstraint, Column, Enum as SQLAlchemyEnum
from sqlmodel import Field, Relationship, SQLModel

from app.core.validaciones import validarFechaInicio, validarFechaTermino, validarTexto

if TYPE_CHECKING:
    from app.models.detalle_presupuesto import DetallePresupuesto
    from app.models.user import User


class StatusPresupuestos(str, Enum):
    ACTIVE = "ACTIVE"
    CLOSE = "CLOSE"
    DRAFT = "DRAFT"


PCT_MINIMO = 0
PCT_MAXIMO = 100


class Presupuesto(SQLModel, table=True):
    __tablename__ = "presupuesto"

    __table_args__ = (
        CheckConstraint(
            "pct_gastos_generales >= 0 AND pct_gastos_generales <= 100",
            name="ck_presupuesto_pct_gastos_generales_rango",
        ),
        CheckConstraint(
            "pct_iva >= 0 AND pct_iva <= 100",
            name="ck_presupuesto_pct_iva_rango",
        ),
        CheckConstraint(
            "pct_utilidad >= 0 AND pct_utilidad <= 100",
            name="ck_presupuesto_pct_utilidad_rango",
        ),
        CheckConstraint("costo_neto >= 0", name="ck_presupuesto_costo_neto_no_negativo"),
        CheckConstraint("total_cotizado >= 0", name="ck_presupuesto_total_cotizado_no_negativo"),
        CheckConstraint("total_real >= 0", name="ck_presupuesto_total_real_no_negativo"),
    )

    # PK
    id_presupuesto: Optional[int] = Field(default=None, primary_key=True)

    # FK (Clave Foránea): Apunta a la tabla 'user' y a su columna 'id'
    id_usuario: int = Field(foreign_key="user.id", nullable=False, index=True)

    code: str = Field(max_length=50, nullable=False)
    client_name: str = Field(max_length=50, nullable=False)

    status: StatusPresupuestos = Field(
        default=StatusPresupuestos.DRAFT,
        sa_column=Column(
            SQLAlchemyEnum(
                StatusPresupuestos,
                name="status_presupuestos",
                native_enum=False,
                create_constraint=True,
                values_callable=lambda enum_class: [
                    estado.value for estado in enum_class
                ],
            ),
            nullable=False,
            server_default=StatusPresupuestos.DRAFT.value,
        ))

    estimate_income: int = Field(nullable=False)

    start_date: NaiveDatetime = Field(default=None)
    end_date: NaiveDatetime = Field(default=None)

    description: str = Field(max_length=500, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default=None, nullable=True)

    # --- Montos fijos opcionales (0 / None = se calculan) ---
    # Si se ingresa un costo directo fijo (> 0) se usa como base de los
    # porcentajes en lugar de la suma de subtotales reales.
    costo_directo: int | None = Field(default=None, nullable=True)
    costo_indirecto: int | None = Field(default=None, nullable=True)
    # Precio neto fijo acordado (si aplica). Si es > 0 reemplaza al neto
    # calculado; el IVA se aplica sobre este valor.
    costo_neto: int = Field(default=0, nullable=False, ge=0, sa_column_kwargs={"server_default": "0"})

    # --- Porcentajes de gastos (0–100) ---
    pct_gastos_generales: float = Field(
        default=0, nullable=False, ge=PCT_MINIMO, le=PCT_MAXIMO,
        sa_column_kwargs={"server_default": "0"},
    )
    pct_iva: float = Field(
        default=0, nullable=False, ge=PCT_MINIMO, le=PCT_MAXIMO,
        sa_column_kwargs={"server_default": "0"},
    )
    pct_utilidad: float = Field(
        default=0, nullable=False, ge=PCT_MINIMO, le=PCT_MAXIMO,
        sa_column_kwargs={"server_default": "0"},
    )

    # --- Totales calculados (se recalculan con app.core.calculos) ---
    total_cotizado: int = Field(default=0, nullable=False, ge=0, sa_column_kwargs={"server_default": "0"})
    total_real: int = Field(default=0, nullable=False, ge=0, sa_column_kwargs={"server_default": "0"})
    monto_gastos_generales: int = Field(default=0, nullable=False, sa_column_kwargs={"server_default": "0"})
    monto_iva: int = Field(default=0, nullable=False, sa_column_kwargs={"server_default": "0"})
    monto_utilidad: int = Field(default=0, nullable=False, sa_column_kwargs={"server_default": "0"})
    monto_costo_neto: int = Field(default=0, nullable=False, sa_column_kwargs={"server_default": "0"})
    # Total de la cotización = neto + IVA
    monto_total: int = Field(default=0, nullable=False, sa_column_kwargs={"server_default": "0"})

    ruta_reporte: str | None = Field(default=None, max_length=75)

    detalles: List["DetallePresupuesto"] = Relationship(
        back_populates="presupuesto",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    # Relación
    usuario: Optional["User"] = Relationship(back_populates="presupuestos")

    @property
    def base_calculo(self) -> int:
        """Base sobre la que se aplican los porcentajes."""
        return self.costo_directo if self.costo_directo else self.total_real

    @property
    def neto(self) -> int:
        """Neto sobre el que se calcula el IVA: el fijo si se ingresó."""
        return self.costo_neto if self.costo_neto else self.monto_costo_neto

    @property
    def monto_final(self) -> int:
        """Monto final del presupuesto (total con IVA)."""
        return self.monto_total


class PresupuestoValidacion(BaseModel):
    """Validación de creación y edición. En pantalla, `description` se llama "Nombre"."""

    code: str = Field(min_length=1, max_length=50)
    client_name: str = Field(min_length=1, max_length=50)
    estimate_income: int = Field(ge=0)
    # Obligatorias: validate_default hace que falten también cuando no se envían
    start_date: datetime | None = CampoValidacion(default=None, validate_default=True)
    end_date: datetime | None = CampoValidacion(default=None, validate_default=True)
    description: str = Field(min_length=1, max_length=500)
    status: StatusPresupuestos = StatusPresupuestos.DRAFT

    @field_validator("code", "client_name", "description")
    @classmethod
    def _no_vacio(cls, v: str, info: ValidationInfo) -> str:
        if not v.strip():
            raise ValueError("campo vacío")
        if info.field_name == "code":
            return validarTexto(v, "El código")
        etiqueta = "El cliente" if info.field_name == "client_name" else "El nombre"
        return validarTexto(v, etiqueta, puntuacion=True)

    @field_validator("start_date")
    @classmethod
    def _inicio(cls, v: datetime | None) -> datetime:
        return validarFechaInicio(v)

    @field_validator("end_date")
    @classmethod
    def _termino(cls, v: datetime | None, info: ValidationInfo) -> datetime:
        return validarFechaTermino(v, info.data.get("start_date"))


class PorcentajesValidacion(BaseModel):
    """Valida el formulario de porcentajes y montos fijos del presupuesto."""

    pct_gastos_generales: float = Field(ge=PCT_MINIMO, le=PCT_MAXIMO)
    pct_iva: float = Field(ge=PCT_MINIMO, le=PCT_MAXIMO)
    pct_utilidad: float = Field(ge=PCT_MINIMO, le=PCT_MAXIMO)
    costo_directo: int = Field(ge=0)
    costo_neto: int = Field(ge=0)

    @field_validator("pct_gastos_generales", "pct_iva", "pct_utilidad", mode="before")
    @classmethod
    def _porcentajeVacioEsCero(cls, v):
        # Acepta coma decimal ("19,5") y trata los campos vacíos como 0
        if isinstance(v, str):
            v = v.strip().replace(",", ".")
            return v or 0
        return 0 if v is None else v

    @field_validator("costo_directo", "costo_neto", mode="before")
    @classmethod
    def _montoVacioEsCero(cls, v):
        if isinstance(v, str):
            return v.strip() or 0
        return 0 if v is None else v
