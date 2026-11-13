from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Index, column, func
from sqlmodel import Field, SQLModel


class Material(SQLModel, table=True):
    __tablename__ = "material"

    __table_args__ = (
        Index(
            "uq_material_code_lower",
            func.lower(column("code")),
            unique=True,
        ),
        CheckConstraint(
            "unit_cost >= 0",
            name="ck_material_unit_cost_non_negative",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)

    code: str = Field(max_length=50, nullable=False)
    name: str = Field(max_length=150, nullable=False)
    category: str | None = Field(default=None, max_length=100)
    unit: str = Field(max_length=30, nullable=False)

    unit_cost: int = Field(ge=0, nullable=False)  # precio actual del catálogo

    is_active: bool = Field(default=True, nullable=False)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: datetime | None = Field(default=None, nullable=True)