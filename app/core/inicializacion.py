"""Preparación de la base de datos y del administrador al arrancar.

La usan scripts/iniciar.py (desarrollo) y client.py (también el ejecutable,
que no incluye la carpeta scripts/):

- prepararBaseDatos(): si la BD no existe o está vacía crea todas las tablas
  y la marca con la última migración; si existe, aplica las migraciones
  pendientes (así una versión nueva del .exe actualiza la BD del usuario).
- asegurarAdmin(): si no hay ningún ADMIN activo, crea los usuarios iniciales.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import inspect
from sqlmodel import Session, SQLModel, select

import app.models  # noqa: F401  registra todas las tablas en SQLModel.metadata
from app.core.config import DATABASE_PATH
from app.core.db import engine
from app.core.security import hashPassword
from app.models.user import User, UserRole


def _raiz() -> Path:
    """Carpeta que contiene alembic/ y alembic.ini (repo o bundle de PyInstaller)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2]


RAIZ = _raiz()
ALEMBIC_INI = RAIZ / "alembic.ini"
ALEMBIC_DIR = RAIZ / "alembic"


@dataclass(frozen=True)
class UsuarioInicial:
    username: str
    email: str
    password: str
    full_name: str
    role: UserRole


# Administrador que se crea si no hay ninguno (también es el primero de
# scripts/seed_admin.py). Cambia su contraseña apenas entres.
ADMIN_INICIAL = UsuarioInicial(
    username="admin",
    email="admin@example.com",
    password="admin123",
    full_name="Administrador",
    role=UserRole.ADMIN,
)


# Base de datos
# ==========================================

def hayMigraciones() -> bool:
    return ALEMBIC_INI.exists() and ALEMBIC_DIR.is_dir()


def _configAlembic():
    from alembic.config import Config

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    return config


def _revisiones(config) -> tuple[str | None, str]:
    """(revisión aplicada en la BD, última revisión disponible)."""
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    with engine.connect() as conn:
        actual = MigrationContext.configure(conn).get_current_revision()
    return actual, ScriptDirectory.from_config(config).get_current_head()


def prepararBaseDatos() -> str:
    """Crea o actualiza el esquema. Devuelve un resumen de lo que hizo."""
    existia = DATABASE_PATH.exists()
    tablas = set(inspect(engine).get_table_names())
    migraciones = hayMigraciones()

    if not tablas:
        # BD nueva: el esquema sale directo de los modelos y se marca como al día
        SQLModel.metadata.create_all(engine)
        estado = "vacía" if existia else "no existía"
        if not migraciones:
            return f"{estado}: tablas creadas (sin Alembic disponible)"
        from alembic import command

        config = _configAlembic()
        command.stamp(config, "head")
        _, head = _revisiones(config)
        return f"{estado}: tablas creadas (revisión {head})"

    if "alembic_version" not in tablas or not migraciones:
        # Tablas creadas sin Alembic (o sin migraciones a mano): solo agrega las que falten
        faltantes = set(SQLModel.metadata.tables) - tablas
        SQLModel.metadata.create_all(engine)
        detalle = (
            f"se crearon las tablas faltantes {sorted(faltantes)}" if faltantes
            else "no faltan tablas"
        )
        if not migraciones:
            return f"existe; {detalle} (sin Alembic disponible)"
        return (
            f"existe sin control de Alembic; {detalle}. "
            "Revisa 'python -m alembic stamp' (ver README)."
        )

    from alembic import command

    config = _configAlembic()
    actual, head = _revisiones(config)
    if actual == head:
        return f"al día (revisión {head})"

    command.upgrade(config, "head")
    return f"migrada de {actual} a {head}"


def verificarTablas() -> list[str]:
    """Tablas de los modelos que siguen faltando (debería ser una lista vacía)."""
    return sorted(set(SQLModel.metadata.tables) - set(inspect(engine).get_table_names()))


# Usuarios
# ==========================================

def _adminActivo(session: Session) -> User | None:
    return session.exec(
        select(User).where(User.role == UserRole.ADMIN, User.is_active.is_(True))
    ).first()


def asegurarAdmin(usuarios: list[UsuarioInicial] | None = None) -> str:
    """Si no hay ningún ADMIN activo, crea `usuarios` (por defecto, solo ADMIN_INICIAL).

    No modifica usuarios que ya existan con el mismo nombre.
    """
    usuarios = usuarios or [ADMIN_INICIAL]

    with Session(engine) as session:
        admin = _adminActivo(session)
        if admin is not None:
            return f"OK, existe el administrador '{admin.username}'"

        existentes = set(session.exec(select(User.username)).all())
        creados = []
        for data in usuarios:
            if data.username in existentes:
                continue
            session.add(User(
                username=data.username,
                email=data.email,
                hashed_password=hashPassword(data.password),
                full_name=data.full_name,
                role=data.role,
                is_active=True,
            ))
            creados.append(data.username)
        session.commit()
        admin = _adminActivo(session)

    if admin is None:
        # Ej.: el usuario 'admin' existe pero está desactivado
        return (
            "ATENCIÓN: sigue sin haber un ADMIN activo (¿el usuario 'admin' está "
            "desactivado?). Reactívalo o crea uno nuevo."
        )
    return f"creados los usuarios iniciales ({', '.join(creados)}); entra con '{admin.username}'"


def inicializar(usuarios: list[UsuarioInicial] | None = None) -> list[str]:
    """Prepara BD y administrador. Devuelve las líneas de resumen.

    Lanza RuntimeError si después de preparar siguen faltando tablas.
    """
    lineas = [f"Base de datos: {DATABASE_PATH}", f"  -> {prepararBaseDatos()}"]
    faltantes = verificarTablas()
    if faltantes:
        raise RuntimeError(f"Faltan tablas en la base de datos: {faltantes}")
    lineas.append(f"Administrador: {asegurarAdmin(usuarios)}")
    return lineas
