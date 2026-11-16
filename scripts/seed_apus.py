"""
Seed del catálogo de APU (análisis de precios unitarios) de ejemplo.

Es idempotente: si un APU con el mismo código ya existe, no se toca.

Uso:
    python -m scripts.seed_apus
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import inspect
from sqlmodel import Session, SQLModel, select

from app.core.db import engine
from app.models.apu import APU


@dataclass(frozen=True)
class ApuSeed:
    code: str
    name: str
    unit: str
    category: str
    unit_cost: int          # costo cotizado (CLP)
    real_unit_cost: int     # costo real (CLP)
    description: str = ""
    is_active: bool = True


SEED_APUS: list[ApuSeed] = [
    # Obras preliminares
    ApuSeed("OP-001", "Instalación de faena", "GL", "Obras preliminares", 850_000, 887_250,
            "Bodega, servicios higiénicos y cierre provisorio."),
    ApuSeed("OP-002", "Trazado y niveles", "m2", "Obras preliminares", 1_200, 1_250),
    ApuSeed("OP-003", "Retiro de escombros", "m3", "Obras preliminares", 18_500, 19_800,
            "Carguío y transporte a botadero autorizado."),
    # Movimiento de tierra
    ApuSeed("MT-001", "Excavación manual", "m3", "Movimiento de tierra", 14_500, 15_200),
    ApuSeed("MT-002", "Relleno compactado", "m3", "Movimiento de tierra", 16_800, 16_100),
    # Obra gruesa
    ApuSeed("OG-001", "Hormigón H25", "m3", "Obra gruesa", 95_000, 98_500),
    ApuSeed("OG-002", "Radier G-20 e=10 cm", "m2", "Obra gruesa", 45_000, 49_620),
    ApuSeed("OG-003", "Acero A630-420H", "kg", "Obra gruesa", 1_450, 1_520),
    ApuSeed("OG-004", "Moldaje de madera", "m2", "Obra gruesa", 12_500, 12_900),
    # Pavimentos
    ApuSeed("PV-001", "Hormigón estampado", "m2", "Pavimentos", 38_000, 39_900),
    ApuSeed("PV-002", "Instalación solerilla tipo C", "ml", "Pavimentos", 21_000, 22_184),
    # Terminaciones
    ApuSeed("TE-001", "Pintura látex interior", "m2", "Terminaciones", 4_500, 4_200),
    ApuSeed("TE-002", "Cerámica de piso 45x45", "m2", "Terminaciones", 18_900, 19_500),
    ApuSeed("TE-003", "Papel mural", "m2", "Terminaciones", 6_800, 6_800,
            "Fuera de uso: se mantiene como ejemplo de APU inactivo.", is_active=False),
    # Instalaciones
    ApuSeed("IN-001", "Punto eléctrico", "un", "Instalaciones", 32_000, 33_500),
    ApuSeed("IN-002", "Punto de agua potable", "un", "Instalaciones", 45_000, 44_000),
    # Obras finales
    ApuSeed("OF-001", "Aseo y limpieza final", "GL", "Obras finales", 250_000, 250_000),
]


def verificarTablas() -> bool:
    """True si la base de datos ya tiene todas las tablas de los modelos."""
    import app.models  # noqa: F401  registra todos los modelos

    return set(SQLModel.metadata.tables) <= set(inspect(engine).get_table_names())


def sembrarApus(session: Session) -> int:
    """Crea los APU que falten. Devuelve cuántos creó (sin commit)."""
    existentes = set(session.exec(select(APU.code)).all())
    creados = 0
    for data in SEED_APUS:
        if data.code in existentes:
            print(f"  = ya existía {data.code}")
            continue
        session.add(APU(
            code=data.code,
            name=data.name,
            unit=data.unit,
            category=data.category,
            unit_cost=data.unit_cost,
            real_unit_cost=data.real_unit_cost,
            description=data.description or None,
            is_active=data.is_active,
        ))
        creados += 1
        print(f"  + creado  {data.code:<7} {data.name}")
    session.flush()
    return creados


def run() -> int:
    if not verificarTablas():
        raise SystemExit(
            "La base de datos no tiene las tablas. Ejecuta primero: "
            "python -m scripts.iniciar --solo-verificar"
        )
    print("Sembrando APU...")
    with Session(engine) as session:
        creados = sembrarApus(session)
        session.commit()
    print(f"OK: Seed de APU completado ({creados} nuevo(s)).")
    return creados


if __name__ == "__main__":
    run()
