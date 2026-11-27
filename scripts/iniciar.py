"""
Inicia SEFEL en un solo paso:

EN SIMPLE
    Es el "botón de encendido" para desarrollo: revisa la base de datos y los
    usuarios, y abre la app. Igual que client.py, pero con más opciones y
    mensajes por consola.

TÉCNICO

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
    python -m scripts.iniciar --red            # compartir en la red local (puerto 8765)
"""

from __future__ import annotations

import argparse
import sys

from app.core import inicializacion


def prepararBaseDatos(crear_si_falta: bool = False) -> str:
    """Como inicializacion.prepararBaseDatos, pero si falta una base que ya
    existía pregunta en la consola (o usa --crear-bd) antes de crear una nueva."""
    try:
        return inicializacion.prepararBaseDatos(crear_si_falta)
    except inicializacion.BaseDatosFaltante as faltante:
        print(f"  ATENCIÓN: {faltante}", file=sys.stderr)
        if not sys.stdin or not sys.stdin.isatty():
            raise SystemExit(
                "  No se creó una base nueva. Restaura el archivo, o vuelve a ejecutar "
                "con --crear-bd para crear una vacía."
            )
        try:
            respuesta = input("  ¿Crear una base de datos NUEVA y vacía? [s/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            respuesta = ""   # sin respuesta = No
            print()
        if respuesta not in {"s", "si", "sí", "y", "yes"}:
            raise SystemExit("  Cancelado: no se creó una base nueva.")
        return inicializacion.prepararBaseDatos(crear_si_falta=True)


def verificarTablas() -> list[str]:
    """Tablas que faltan en la BD (lista vacía = todo bien)."""
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
    parser.add_argument("--crear-bd", action="store_true",
                        help="Si falta una base que ya existía, crear una nueva sin preguntar.")
    parser.add_argument("--red", action="store_true",
                        help="Compartir en la red local: otros PCs entran por navegador "
                             "(puerto 8765 si no se indica --puerto).")
    return parser.parse_args(argv)


def _consolaSegura() -> None:
    """La consola de Windows (o una tubería) puede no ser UTF-8: nunca fallar por un símbolo."""
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    """Ejecuta los pasos del docstring. Devuelve 0 si todo fue bien, 1 si hubo error."""
    _consolaSegura()
    args = parsearArgumentos(argv)
    print("=" * 60)
    print("SEFEL · inicio")
    print("=" * 60)

    print(f"Base de datos: {inicializacion.DATABASE_PATH}")
    try:
        print(f"  -> {prepararBaseDatos(args.crear_bd)}")
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        from app.core.errores_bd import esErrorBD, mensajeErrorBD
        if not esErrorBD(exc):
            raise
        print(f"  ERROR: {mensajeErrorBD(exc)}", file=sys.stderr)
        return 1
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

    host = client.HOST_RED if args.red else client.HOST
    puerto = args.puerto or (client.PUERTO_RED if args.red else client.getUnusedPort())
    if not client.puertoDisponible(puerto, host):
        print(f"ERROR: el puerto {puerto} está ocupado. Usa otro con --puerto.", file=sys.stderr)
        return 1

    print(f"Puerto: {puerto}  ->  http://{client.HOST}:{puerto}")
    if args.red:
        print(client.avisoRed(puerto))
    print("=" * 60, flush=True)

    if args.solo_servidor:
        import uvicorn
        from app.main import app

        uvicorn.run(app, host=host, port=puerto)
    else:
        # la BD ya quedó lista arriba
        client.main(puerto, preparar=False, red=args.red)
    return 0


if __name__ == "__main__":
    sys.exit(main())
