"""Preparación de la base de datos y del administrador al arrancar.

EN SIMPLE
    Es la "lista de chequeo" antes de abrir la app:
      1. ¿Existe la base de datos? Si es la primera vez, se crea. Si existía
         y desapareció, se avisa (no se crea una vacía sin preguntar, para no
         "perder" los datos sin que nadie lo note).
      2. ¿Las tablas están al día? Si hay una versión nueva, se actualizan
         (migraciones de Alembic).
      3. ¿Hay al menos un administrador activo? Si no, se crea "admin".

TÉCNICO
La usan scripts/iniciar.py (desarrollo) y client.py (también el ejecutable,
que no incluye la carpeta scripts/):

- prepararBaseDatos(): si la BD no existe o está vacía crea todas las tablas
  y la marca con la última migración; si existe, aplica las migraciones
  pendientes (así una versión nueva del .exe actualiza la BD del usuario).
- asegurarAdmin(): si no hay ningún ADMIN activo, crea los usuarios iniciales.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import inspect
from sqlmodel import Session, SQLModel, select

import app.models  # noqa: F401  registra todas las tablas en SQLModel.metadata
from app.core.config import DATABASE_PATH
from app.core.paths import userDataPath
from app.core.db import engine
from app.core.security import hashPassword
from app.models.user import User, UserRole


def _raiz() -> Path:
    """Carpeta que contiene alembic/ y alembic.ini (repo o bundle de PyInstaller)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2]


RAIZ = _raiz()

# Registro de las bases ya creadas en este PC. Sirve para distinguir la primera
# instalación (crear la base sin preguntar) de una base que existía y ya no está
# (borrada o movida): en ese caso no se crea una vacía sin avisar.
# Vive fuera de data/ para sobrevivir aunque se borre esa carpeta.
REGISTRO_INSTALACION = userDataPath("instalacion.json")


class BaseDatosFaltante(RuntimeError):
    """La base de datos existía en esta ruta y ya no está."""

    def __init__(self, ruta: Path) -> None:
        self.ruta = ruta
        super().__init__(
            f"No se encontró la base de datos en {ruta}. "
            "Ya existía antes en este PC: puede haberse borrado o movido."
        )


def _leerRegistro() -> dict:
    """Lee instalacion.json; si no existe o está dañado, devuelve {}."""
    try:
        return json.loads(REGISTRO_INSTALACION.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def baseConocida(ruta: Path | None = None) -> bool:
    """True si esta ruta ya tuvo una base de SEFEL creada en este PC."""
    ruta = (ruta or DATABASE_PATH).resolve()
    return str(ruta) in _leerRegistro().get("bases", {})


def registrarBase(ruta: Path | None = None) -> None:
    """Anota la ruta como base creada (no falla si no se puede escribir)."""
    ruta = (ruta or DATABASE_PATH).resolve()
    registro = _leerRegistro()
    bases = registro.setdefault("bases", {})
    if str(ruta) in bases:
        return
    bases[str(ruta)] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        REGISTRO_INSTALACION.parent.mkdir(parents=True, exist_ok=True)
        REGISTRO_INSTALACION.write_text(json.dumps(registro, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def estadoBaseDatos() -> str:
    """"existe", "nueva" (primera vez: se puede crear) o "falta" (existía y no está)."""
    if DATABASE_PATH.exists():
        return "existe"
    return "falta" if baseConocida() else "nueva"
ALEMBIC_INI = RAIZ / "alembic.ini"
ALEMBIC_DIR = RAIZ / "alembic"


@dataclass(frozen=True)
class UsuarioInicial:
    """Datos de un usuario a crear al iniciar (frozen = inmutable)."""
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
    """True si están alembic.ini y la carpeta alembic/ (se pueden aplicar migraciones)."""
    return ALEMBIC_INI.exists() and ALEMBIC_DIR.is_dir()


def _configAlembic():
    """Configuración de Alembic apuntando a la carpeta real (repo o .exe)."""
    # Import dentro de la función: Alembic solo se carga si de verdad se usa
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


def prepararBaseDatos(crear_si_falta: bool = False) -> str:
    """Crea o actualiza el esquema. Devuelve un resumen de lo que hizo.

    Si la base no existe y es la primera vez en esta ruta, la crea. Si ya había
    existido (está en el registro), lanza BaseDatosFaltante, salvo que
    `crear_si_falta` sea True (el usuario eligió crear una nueva).
    """
    existia = DATABASE_PATH.exists()
    if not existia:
        if baseConocida() and not crear_si_falta:
            raise BaseDatosFaltante(DATABASE_PATH)
        # El motor de la app nunca crea el archivo (mode=rw): se crea aquí
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        sqlite3.connect(DATABASE_PATH).close()

    resumen = _prepararEsquema(existia)
    registrarBase()
    return resumen


def _prepararEsquema(existia: bool) -> str:
    """Deja las tablas al día. Tres casos:

      1. BD sin tablas -> create_all() desde los modelos + "stamp head"
         (marca la BD como si ya tuviera todas las migraciones aplicadas).
      2. BD con tablas pero sin tabla alembic_version -> solo crea las que falten.
      3. BD controlada por Alembic -> "upgrade head" si hay migraciones pendientes.
    """
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
    """Primer usuario con rol ADMIN y activo, o None."""
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


def inicializar(
    usuarios: list[UsuarioInicial] | None = None, crear_si_falta: bool = False
) -> list[str]:
    """Prepara BD y administrador. Devuelve las líneas de resumen.

    Lanza RuntimeError si después de preparar siguen faltando tablas.
    """
    lineas = [f"Base de datos: {DATABASE_PATH}", f"  -> {prepararBaseDatos(crear_si_falta)}"]
    faltantes = verificarTablas()
    if faltantes:
        raise RuntimeError(f"Faltan tablas en la base de datos: {faltantes}")
    lineas.append(f"Administrador: {asegurarAdmin(usuarios)}")
    return lineas
