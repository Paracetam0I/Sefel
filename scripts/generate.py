# create_tables.py
import argparse
import sys

from sqlalchemy import inspect, text
from sqlalchemy.schema import Table, MetaData
from sqlmodel import SQLModel

# --- ENGINE: importar el tuyo, NO crear uno nuevo ---
from app.core.db import engine

# --- IMPORTAR TODOS LOS MODELOS (obligatorio para registrarlos en metadata) ---
from app.models.apu import APU, APUValidacion
from app.models.user import User, Presupuesto, UserRole
from app.models.detalle_presupuesto import DetallePresupuesto


# ---------------------------------------------------------------------------
# Helpers de introspección
# ---------------------------------------------------------------------------
def get_model_tables() -> set[str]:
    return set(SQLModel.metadata.tables.keys())


def get_existing_tables() -> set[str]:
    return set(inspect(engine).get_table_names())


# ---------------------------------------------------------------------------
# Drop
# ---------------------------------------------------------------------------
def drop_tables(all_tables: bool = False) -> None:
    """
    Borra tablas de la BD.

    - all_tables=False  -> solo las definidas en los modelos.
    - all_tables=True   -> también las que existen en BD pero no en modelos.
    """
    model_tables = get_model_tables()
    existing = get_existing_tables()

    if not existing:
        print("🗑️  La base de datos no tiene tablas que borrar.")
        return

    if all_tables:
        to_drop = existing
    else:
        to_drop = existing & model_tables
        extras = existing - model_tables
        if extras:
            print(f"ℹ️  Tablas en BD fuera de modelos (no se tocan): {sorted(extras)}")
            print("   Usa --all si también quieres borrarlas.")

    if not to_drop:
        print("🗑️  No hay tablas de modelos que borrar.")
        return

    # En SQLite, desactivar FK durante el drop evita errores de orden.
    is_sqlite = engine.dialect.name == "sqlite"

    with engine.begin() as conn:
        if is_sqlite:
            conn.execute(text("PRAGMA foreign_keys=OFF"))

        # 1) Tablas declaradas en metadata (orden resuelto por SQLAlchemy)
        metadata_tables = [t for name, t in SQLModel.metadata.tables.items() if name in to_drop]
        if metadata_tables:
            SQLModel.metadata.drop_all(conn, tables=metadata_tables, checkfirst=True)

        # 2) Tablas "extra" que no están en metadata (solo si --all)
        extra_names = to_drop - set(SQLModel.metadata.tables.keys())
        if extra_names:
            meta = MetaData()
            for name in extra_names:
                tbl = Table(name, meta, autoload_with=conn)
                tbl.drop(conn, checkfirst=True)

        if is_sqlite:
            conn.execute(text("PRAGMA foreign_keys=ON"))

    print(f"🗑️  Borradas {len(to_drop)} tabla(s): {sorted(to_drop)}")


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
def create_missing_tables() -> None:
    model_tables = get_model_tables()
    existing = get_existing_tables()

    missing = model_tables - existing
    already = model_tables & existing
    extra = existing - model_tables

    print("📋 Tablas definidas en modelos:", sorted(model_tables))
    print("✅ Ya existentes en BD:        ", sorted(already) or "ninguna")
    print("➕ Faltantes a crear:           ", sorted(missing) or "ninguna")
    if extra:
        print("⚠️  En BD pero no en modelos:   ", sorted(extra))

    if not missing:
        print("\nNo hay tablas nuevas por crear.")
        return

    tables_to_create = [SQLModel.metadata.tables[name] for name in missing]
    SQLModel.metadata.create_all(engine, tables=tables_to_create, checkfirst=True)
    print(f"\n✔️  Creadas {len(tables_to_create)} tabla(s): {sorted(missing)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crea (y opcionalmente recrea) las tablas SQLModel en la BD."
    )
    parser.add_argument(
        "-d", "--drop",
        action="store_true",
        help="Borra las tablas de los modelos antes de crearlas.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Con -d, borra también tablas que no están en modelos (⚠️ destructivo).",
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="No pedir confirmación al usar -d.",
    )
    return parser.parse_args()


def confirm(prompt: str) -> bool:
    try:
        return input(f"{prompt} [y/N]: ").strip().lower() in {"y", "yes", "s", "si", "sí"}
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def main() -> int:
    args = parse_args()

    if args.drop:
        scope = "TODAS las tablas (incluidas las ajenas a modelos)" if args.all else "las tablas de los modelos"
        print(f"⚠️  Vas a BORRAR {scope} de la BD: {engine.url}")
        if not args.yes and not confirm("¿Continuar?"):
            print("Cancelado.")
            return 1
        drop_tables(all_tables=args.all)

    create_missing_tables()
    return 0


if __name__ == "__main__":
    sys.exit(main())