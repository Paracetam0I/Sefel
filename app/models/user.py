
from typing import List,Optional
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, Enum as SQLAlchemyEnum
from sqlmodel import Field, SQLModel, Relationship


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
    presupuestos: List["Presupuesto"] = Relationship(back_populates="usuario")

# Crearé modelos para la subida del informe 2. Luego podemos mover los modelos de acá abajo para otro archivo models
class Presupuesto(SQLModel, table=True):
    __tablename__ = "presupuesto"
    
    # PK
    id_presupuesto: Optional[int] = Field(default=None, primary_key=True)
    
    # FK (Clave Foránea): Apunta a la tabla 'usuario' y a su columna 'id'
    id_usuario: int = Field(foreign_key="user.id", nullable=False)
    
    code: str = Field(max_length=50, nullable=False)
    client_name: str = Field(max_length=50, nullable=False)
    status: str = Field(max_length=50, nullable=False)
    estimate_income: int = Field(nullable=False)
    start_date: datetime | None = Field(default=None, nullable=True)
    end_date: datetime | None = Field(default=None, nullable=True)
    description: str = Field(max_length=500, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default=None, nullable=True)
    costo_directo: int | None = Field(default=None, nullable=True)
    costo_indirecto: int | None = Field(default=None, nullable=True)
    ruta_reporte: str | None = Field(default=None, max_length=75)

    # Relación
    usuario: Optional[User] = Relationship(back_populates="presupuestos")
