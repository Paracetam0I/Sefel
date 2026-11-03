from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Index, column, func
from sqlmodel import Field, SQLModel


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