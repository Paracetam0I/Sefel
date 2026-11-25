"""
Seed de ejemplo de la Base de datos de recursos y de los APU (recetas).

1. Recursos (tabla materiales) con categorías fijas: Materiales, Mano de obra,
   Equipos y Herramientas.
2. APU que combinan esos recursos con su cantidad por unidad. El costo de cada
   APU NO se siembra: se calcula con app.core.calculos, igual que en la app.

Es idempotente: si un recurso o un APU con el mismo código ya existe, no se
toca (tampoco su receta).

Uso:
    python -m scripts.seed_apus
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import inspect
from sqlmodel import Session, SQLModel, select

from app.core.db import engine
from app.models.apu import APU
from app.models.detalle_apu import DetalleApu
from app.models.material import CategoriaRecurso, Material

MAT = CategoriaRecurso.MATERIALES
MO = CategoriaRecurso.MANO_DE_OBRA
EQ = CategoriaRecurso.EQUIPOS
HE = CategoriaRecurso.HERRAMIENTAS


@dataclass(frozen=True)
class MaterialSeed:
    code: str
    name: str
    unit: str
    category: CategoriaRecurso
    unit_cost: int          # precio unitario cotizado (CLP)
    real_unit_cost: int     # costo real (CLP)
    description: str = ""
    is_active: bool = True


@dataclass(frozen=True)
class ApuSeed:
    code: str
    name: str
    unit: str
    category: str
    # (código del recurso, cantidad por unidad de APU)
    recursos: list[tuple[str, float]] = field(default_factory=list)
    description: str = ""
    is_active: bool = True


SEED_MATERIALES: list[MaterialSeed] = [
    # Materiales
    MaterialSeed("MAT-HOR", "Hormigón premezclado H25", "m3", MAT, 78_000, 81_000),
    MaterialSeed("MAT-CEM", "Cemento saco 25 kg", "saco", MAT, 5_200, 5_450),
    MaterialSeed("MAT-ARE", "Arena gruesa", "m3", MAT, 22_000, 23_500),
    MaterialSeed("MAT-EST", "Base estabilizada", "m3", MAT, 9_500, 9_900),
    MaterialSeed("MAT-ACE", "Barra de acero A630-420H", "kg", MAT, 1_050, 1_100),
    MaterialSeed("MAT-ALA", "Alambre negro 18", "kg", MAT, 1_900, 1_950),
    MaterialSeed("MAT-MAL", "Malla electrosoldada C92", "m2", MAT, 3_900, 4_050),
    MaterialSeed("MAT-TAB", "Tabla pino bruto 1x6", "m", MAT, 1_150, 1_200),
    MaterialSeed("MAT-CLA", "Clavos corrientes", "kg", MAT, 2_300, 2_300),
    MaterialSeed("MAT-MOL", "Desmoldante y endurecedor para estampado", "m2", MAT, 6_500, 7_100),
    MaterialSeed("MAT-SOL", "Solerilla tipo C", "un", MAT, 4_800, 5_100),
    MaterialSeed("MAT-PIN", "Pintura látex", "gl", MAT, 18_500, 17_800),
    MaterialSeed("MAT-CER", "Cerámica de piso 45x45", "m2", MAT, 9_800, 10_200),
    MaterialSeed("MAT-ADH", "Adhesivo cerámico saco 25 kg", "saco", MAT, 6_200, 6_400),
    MaterialSeed("MAT-PAP", "Papel mural", "m2", MAT, 3_900, 3_900,
                 "Fuera de uso: se mantiene como ejemplo de recurso inactivo.", is_active=False),
    MaterialSeed("MAT-CAB", "Cable eléctrico THHN 14 AWG", "m", MAT, 650, 690),
    MaterialSeed("MAT-CAJ", "Caja de derivación y accesorios", "un", MAT, 3_500, 3_600),
    MaterialSeed("MAT-PPR", "Tubería PPR 20 mm y fittings", "m", MAT, 2_900, 2_800),
    # Mano de obra
    MaterialSeed("MO-JOR", "Jornal", "HH", MO, 5_500, 5_700),
    MaterialSeed("MO-MAE", "Maestro de primera", "HH", MO, 8_500, 8_900),
    MaterialSeed("MO-ELE", "Electricista", "HH", MO, 9_500, 9_800),
    MaterialSeed("MO-GAS", "Gasfíter", "HH", MO, 9_000, 8_800),
    # Equipos
    MaterialSeed("EQ-BOD", "Contenedor bodega y baño químico", "mes", EQ, 380_000, 395_000),
    MaterialSeed("EQ-CAM", "Camión tolva viaje a botadero", "vje", EQ, 85_000, 92_000),
    MaterialSeed("EQ-PLA", "Placa compactadora", "día", EQ, 25_000, 26_000),
    MaterialSeed("EQ-BET", "Betonera 150 L", "día", EQ, 18_000, 18_000),
    MaterialSeed("EQ-NIV", "Nivel láser", "día", EQ, 12_000, 12_000),
    # Herramientas
    MaterialSeed("HE-MEN", "Herramientas menores", "día", HE, 3_000, 3_000,
                 "Desgaste diario de palas, carretillas y similares."),
    MaterialSeed("HE-ROD", "Rodillo y brocha", "un", HE, 2_500, 2_700),
]


SEED_APUS: list[ApuSeed] = [
    # Obras preliminares
    ApuSeed("OP-001", "Instalación de faena", "GL", "Obras preliminares",
            [("EQ-BOD", 2), ("MO-JOR", 16)],
            "Bodega, servicios higiénicos y cierre provisorio."),
    ApuSeed("OP-002", "Trazado y niveles", "m2", "Obras preliminares",
            [("MO-MAE", 0.08), ("MO-JOR", 0.08), ("EQ-NIV", 0.005), ("MAT-TAB", 0.05)]),
    ApuSeed("OP-003", "Retiro de escombros", "m3", "Obras preliminares",
            [("EQ-CAM", 0.15), ("MO-JOR", 1)],
            "Carguío y transporte a botadero autorizado."),
    # Movimiento de tierra
    ApuSeed("MT-001", "Excavación manual", "m3", "Movimiento de tierra",
            [("MO-JOR", 2.5), ("HE-MEN", 0.25)]),
    ApuSeed("MT-002", "Relleno compactado", "m3", "Movimiento de tierra",
            [("MAT-EST", 1.2), ("MO-JOR", 0.8), ("EQ-PLA", 0.04)]),
    # Obra gruesa
    ApuSeed("OG-001", "Hormigón H25", "m3", "Obra gruesa",
            [("MAT-HOR", 1.05), ("MO-JOR", 1.5), ("MO-MAE", 0.5), ("HE-MEN", 0.2)]),
    ApuSeed("OG-002", "Radier G-20 espesor 10 cm", "m2", "Obra gruesa",
            [("MAT-HOR", 0.105), ("MAT-EST", 0.1), ("MAT-MAL", 1.1),
             ("MO-JOR", 1.2), ("MO-MAE", 0.6), ("EQ-PLA", 0.02)]),
    ApuSeed("OG-003", "Acero A630-420H", "kg", "Obra gruesa",
            [("MAT-ACE", 1.05), ("MAT-ALA", 0.02), ("MO-MAE", 0.02), ("MO-JOR", 0.02)]),
    ApuSeed("OG-004", "Moldaje de madera", "m2", "Obra gruesa",
            [("MAT-TAB", 6), ("MAT-CLA", 0.2), ("MO-MAE", 0.4), ("MO-JOR", 0.3)]),
    # Pavimentos
    ApuSeed("PV-001", "Hormigón estampado", "m2", "Pavimentos",
            [("MAT-HOR", 0.1), ("MAT-MOL", 1), ("MO-MAE", 1.5), ("MO-JOR", 1.5), ("HE-MEN", 0.1)]),
    ApuSeed("PV-002", "Instalación solerilla tipo C", "ml", "Pavimentos",
            [("MAT-SOL", 1), ("MAT-HOR", 0.03), ("MO-MAE", 0.9), ("MO-JOR", 0.9)]),
    # Terminaciones
    ApuSeed("TE-001", "Pintura látex interior", "m2", "Terminaciones",
            [("MAT-PIN", 0.09), ("MO-MAE", 0.3), ("HE-ROD", 0.05)]),
    ApuSeed("TE-002", "Cerámica de piso 45x45", "m2", "Terminaciones",
            [("MAT-CER", 1.05), ("MAT-ADH", 0.2), ("MO-MAE", 0.7), ("MO-JOR", 0.3)]),
    ApuSeed("TE-003", "Papel mural", "m2", "Terminaciones",
            [("MAT-PAP", 1.1), ("MO-MAE", 0.3)],
            "Fuera de uso: se mantiene como ejemplo de APU inactivo.", is_active=False),
    # Instalaciones
    ApuSeed("IN-001", "Punto eléctrico", "un", "Instalaciones",
            [("MAT-CAB", 12), ("MAT-CAJ", 1), ("MO-ELE", 2)]),
    ApuSeed("IN-002", "Punto de agua potable", "un", "Instalaciones",
            [("MAT-PPR", 6), ("MO-GAS", 3)]),
    # Obras finales
    ApuSeed("OF-001", "Aseo y limpieza final", "GL", "Obras finales",
            [("MO-JOR", 40), ("EQ-CAM", 0.3)]),
]


def verificarTablas() -> bool:
    """True si la base de datos ya tiene todas las tablas de los modelos."""
    import app.models  # noqa: F401  registra todos los modelos

    try:
        return set(SQLModel.metadata.tables) <= set(inspect(engine).get_table_names())
    except Exception:  # noqa: BLE001  p. ej. el archivo de la base no existe
        return False


def sembrarMateriales(session: Session) -> int:
    """Crea los recursos que falten. Devuelve cuántos creó (sin commit)."""
    existentes = set(session.exec(select(Material.code)).all())
    creados = 0
    for data in SEED_MATERIALES:
        if data.code in existentes:
            continue
        session.add(Material(
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
        print(f"  + recurso {data.code:<8} {data.name}")
    session.flush()
    return creados


def sembrarApus(session: Session) -> int:
    """Crea los recursos y los APU (con su receta) que falten.

    Devuelve cuántos APU creó (sin commit).
    """
    sembrarMateriales(session)
    materiales = {m.code: m for m in session.exec(select(Material)).all()}
    existentes = set(session.exec(select(APU.code)).all())

    creados = 0
    for data in SEED_APUS:
        if data.code in existentes:
            print(f"  = ya existía {data.code}")
            continue
        apu = APU(
            code=data.code,
            name=data.name,
            unit=data.unit,
            category=data.category,
            description=data.description or None,
            is_active=data.is_active,
        )
        session.add(apu)
        session.flush()   # asigna apu.id

        for codigo, cantidad in data.recursos:
            material = materiales[codigo]
            session.add(DetalleApu(
                id_apu=apu.id,
                id_material=material.id,
                unit=material.unit,
                cantidad=cantidad,
            ))
        creados += 1
        print(f"  + APU     {data.code:<8} {data.name} ({len(data.recursos)} recursos)")
    session.flush()
    return creados


def run() -> int:
    if not verificarTablas():
        raise SystemExit(
            "La base de datos no tiene las tablas. Ejecuta primero: "
            "python -m scripts.iniciar --solo-verificar"
        )
    print("Sembrando base de datos de recursos y APU...")
    with Session(engine) as session:
        creados = sembrarApus(session)
        session.commit()
    print(f"OK: Seed de APU completado ({creados} nuevo(s)).")
    return creados


if __name__ == "__main__":
    run()
