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

from app.core import inicializacion


def prepararBaseDatos() -> str:
    return inicializacion.prepararBaseDatos()


def verificarTablas() -> list[str]:
    return inicializacion.verificarTablas()


def asegurarAdmin() -> str:
    """Si no hay ningún ADMIN activo, crea TODOS los usuarios de scripts/seed_admin.py."""
    from scripts import seed_admin

    return inicializacion.asegurarAdmin(seed_admin.SEED_USERS)


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

    print(f"Base de datos: {inicializacion.DATABASE_PATH}")
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
        client.main(puerto, preparar=False)   # la BD ya quedó lista arriba
    return 0


if __name__ == "__main__":
    sys.exit(main())
