"""
Seed de datos iniciales.

Uso:
    python -m scripts.seed
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, SQLModel, select

from app.core.db import engine
from app.models.user import User, UserRole
from app.core.security import hashPassword


# -----------------------------
# Datos a sembrar
# -----------------------------
@dataclass(frozen=True)
class UserSeed:
    username: str
    email: str
    password: str
    full_name: str
    role: UserRole

# Constante para los usuarios en la base de datos, pueden cambiarse desde aquí para realizar pruebas
SEED_USERS: list[UserSeed] = [
    UserSeed(
        username="admin",
        email="admin@example.com",
        password="admin123",
        full_name="Administrador",
        role=UserRole.ADMIN,
    ),
    UserSeed(
        username="materiales",
        email="materiales@example.com",
        password="materiales123",
        full_name="Encargado de Materiales",
        role=UserRole.MATERIALS,
    ),
    UserSeed(
        username="presupuestos",
        email="presupuestos@example.com",
        password="presupuestos123",
        full_name="Encargado de Presupuestos",
        role=UserRole.BUDGETS,
    ),
    UserSeed(
        username="viewer",
        email="viewer@example.com",
        password="viewer123",
        full_name="Solo Lectura",
        role=UserRole.VIEWER,
    ),
]


# -----------------------------
# Helpers
# -----------------------------
def _get_by_username(session: Session, username: str) -> User | None:
    return session.exec(select(User).where(User.username == username)).first()


def upsert_user(session: Session, data: UserSeed, *, update_password: bool = False) -> User:
    """
    Crea el usuario si no existe. Si existe:
      - no hace nada por defecto,
      - si update_password=True, actualiza el hash.
    """
    existing = _get_by_username(session, data.username)

    if existing is None:
        user = User(
            username=data.username,
            email=data.email,
            hashed_password=hashPassword(data.password),
            full_name=data.full_name,
            role=data.role,
            is_active=True,
        )
        session.add(user)
        session.flush()  # asigna id sin cerrar la transacción
        print(f"  + creado  {user.username:<14} rol={user.role.value}")
        return user

    if update_password:
        existing.hashed_password = hashPassword(data.password)
        session.add(existing)
        print(f"  ~ password actualizada para {existing.username}")
    else:
        print(f"  = ya existía {existing.username} (sin cambios)")

    return existing


# -----------------------------
# Entrypoint
# -----------------------------
# Función principal de seed
def run(*, create_tables: bool = False, update_passwords: bool = False) -> None:
    if create_tables:
        print("Creando tablas...")
        SQLModel.metadata.create_all(engine)

    print("Sembrando usuarios...")
    with Session(engine) as session:
        for data in SEED_USERS:
            upsert_user(session, data, update_password=update_passwords)
        session.commit()

    print("✔ Seed completado.")


# Ayuda visual en consola durante la ejecución
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed de la base de datos")
    parser.add_argument(
        "--create-tables",
        action="store_true",
        help="Ejecuta SQLModel.metadata.create_all antes de sembrar",
    )
    parser.add_argument(
        "--update-passwords",
        action="store_true",
        help="Si el usuario existe, actualiza su contraseña al valor del seed",
    )
    args = parser.parse_args()

    run(
        create_tables=args.create_tables,
        update_passwords=args.update_passwords,
    )