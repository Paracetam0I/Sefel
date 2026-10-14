
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, Enum as SQLAlchemyEnum
from sqlmodel import Field, SQLModel


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    MATERIALS = "MATERIALS"
    BUDGETS = "BUDGETS"
    BOTH = "BOTH"
    VIEWER = "VIEWER"


class User(SQLModel, table=True):
    __tablename__ = "user"

    id: int | None = Field(default=None, primary_key=True)

    username: str = Field(
        unique=True,
        index=True,
    )

    email: str = Field(
        unique=True,
        index=True,
    )

    hashed_password: str

    full_name: str

    role: UserRole = Field(
        default=UserRole.VIEWER,
        sa_column=Column(
            SQLAlchemyEnum(
                UserRole,
                name="user_role",
                native_enum=False,
                create_constraint=True,
                values_callable=lambda enum_class: [
                    member.value for member in enum_class
                ],
            ),
            nullable=False,
        ),
    )

    is_active: bool = Field(default=True)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    last_login: datetime | None = Field(
        default=None,
        nullable=True,
    )
