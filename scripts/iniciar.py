"""
Inicia SEFEL en un solo paso:

1. Verifica la base de datos:
   - si no existe o está vacía, crea todas las tablas y la marca con la última
     migración de Alembic;
   - si ya existe, aplica las migraciones pendientes.
2. Verifica que exista un usuario ADMIN activo; si no hay ninguno, crea los
   usuarios de scripts/seed_admin.py.
3. (Opcional, --demo) siembra APU y presupuestos de ejemplo.
4. Elige el puerto, lo muestra y abre la interfaz de escritorio (client.py).

Uso:
    python -m scripts.iniciar                  # puerto libre al azar
    python -m scripts.iniciar --puerto 8765    # puerto fijo
    python -m scripts.iniciar --demo           # además, datos de ejemplo
    python -m scripts.iniciar --solo-servidor  # sin ventana: abrir la URL en el navegador
    python -m scripts.iniciar --solo-verificar # prepara todo y termina
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import inspect
from sqlmodel import Session, SQLModel, select

import app.models  # noqa: F401  registra todas las tablas en SQLModel.metadata
from app.core.config import DATABASE_PATH
from app.core.db import engine
from app.models.user import User, UserRole

RAIZ = Path(__file__).resolve().parent.parent
ALEMBIC_INI = RAIZ / "alembic.ini"


# Base de datos
# ==========================================

def _configAlembic():
    from alembic.config import Config

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(RAIZ / "alembic"))
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
    from alembic import command

    existia = DATABASE_PATH.exists()
    tablas = set(inspect(engine).get_table_names())
    config = _configAlembic()

    if not tablas:
        # BD nueva: el esquema sale directo de los modelos y se marca como al día
        SQLModel.metadata.create_all(engine)
        command.stamp(config, "head")
        _, head = _revisiones(config)
        return f"{'vacía' if existia else 'no existía'}: tablas creadas (revisión {head})"

    if "alembic_version" not in tablas:
        # Tablas creadas a mano sin Alembic: solo se agregan las que falten
        faltantes = set(SQLModel.metadata.tables) - tablas
        SQLModel.metadata.create_all(engine)
        aviso = (
            "existe sin control de Alembic; "
            + (f"se crearon las tablas faltantes {sorted(faltantes)}" if faltantes else "no faltan tablas")
            + ". Revisa 'python -m alembic stamp' (ver README)."
        )
        return aviso

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

def asegurarAdmin() -> str:
    """Si no hay ningún ADMIN activo, crea los usuarios de scripts/seed_admin.py."""
    from scripts import seed_admin

    with Session(engine) as session:
        admin = session.exec(
            select(User).where(User.role == UserRole.ADMIN, User.is_active.is_(True))
        ).first()
        if admin is not None:
            return f"OK, existe el administrador '{admin.username}'"

        print("No hay ningún administrador activo: creando usuarios de seed_admin...")
        for data in seed_admin.SEED_USERS:
            seed_admin.upsert_user(session, data)
        session.commit()

        admin = session.exec(
            select(User).where(User.role == UserRole.ADMIN, User.is_active.is_(True))
        ).first()

    if admin is None:
        # Ej.: el usuario 'admin' existe pero está desactivado
        return (
            "ATENCIÓN: sigue sin haber un ADMIN activo (¿el usuario 'admin' está "
            "desactivado?). Reactívalo o crea uno nuevo."
        )
    nombres = ", ".join(u.username for u in seed_admin.SEED_USERS)
    return f"creados los usuarios de seed ({nombres}); entra con '{admin.username}'"


# CLI
# ==========================================

def parsearArgumentos(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepara la base de datos y abre SEFEL.")
    parser.add_argument("--puerto", type=int, help="Puerto fijo (por defecto, uno libre al azar).")
    parser.add_argument("--demo", action="store_true", help="Siembra APU y presupuestos de ejemplo.")
    parser.add_argument("--solo-servidor", action="store_true",
                        help="Levanta solo el servidor (sin ventana de escritorio).")
    parser.add_argument("--solo-verificar", action="store_true",
                        help="Prepara BD y usuarios, y termina sin abrir la app.")
    return parser.parse_args(argv)


def _consolaSegura() -> None:
    """La consola de Windows (o una tubería) puede no ser UTF-8: nunca fallar por un símbolo."""
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _consolaSegura()
    args = parsearArgumentos(argv)
    print("=" * 60)
    print("SEFEL · inicio")
    print("=" * 60)

    print(f"Base de datos: {DATABASE_PATH}")
    print(f"  -> {prepararBaseDatos()}")
    faltantes = verificarTablas()
    if faltantes:
        print(f"  ERROR: faltan tablas: {faltantes}", file=sys.stderr)
        return 1

    print(f"Administrador: {asegurarAdmin()}")

    if args.demo:
        from scripts import seed_presupuestos
        seed_presupuestos.run()   # también siembra el catálogo de APU

    if args.solo_verificar:
        print("Listo (sin abrir la aplicación).")
        return 0

    import client

    puerto = args.puerto or client.getUnusedPort()
    if not client.puertoDisponible(puerto):
        print(f"ERROR: el puerto {puerto} está ocupado. Usa otro con --puerto.", file=sys.stderr)
        return 1

    print(f"Puerto: {puerto}  ->  http://{client.HOST}:{puerto}")
    print("=" * 60, flush=True)

    if args.solo_servidor:
        import uvicorn
        from app.main import app

        uvicorn.run(app, host=client.HOST, port=puerto)
    else:
        client.main(puerto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
