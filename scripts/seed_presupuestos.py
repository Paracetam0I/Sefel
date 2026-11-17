"""
Seed de presupuestos de ejemplo, con sus ítems (APU asignados) y porcentajes.

- Siembra primero el catálogo de APU (scripts.seed_apus) si falta.
- Los presupuestos quedan a nombre del usuario 'presupuestos' (o del primer
  ADMIN si no existe); requiere haber corrido scripts.seed_admin.
- Totales y montos se calculan con app.core.calculos, igual que en la app.
- Es idempotente: si un presupuesto con el mismo código ya existe, no se toca.

Uso:
    python -m scripts.seed_presupuestos
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlmodel import Session, select

from app.core.calculos import calcularSubtotales, recalcularPresupuesto
from app.core.db import engine
from app.models.apu import APU
from app.models.detalle_presupuesto import DetallePresupuesto
from app.models.presupuesto import Presupuesto, StatusPresupuestos
from app.models.user import User, UserRole
from scripts.seed_apus import sembrarApus, verificarTablas

USUARIO_DUENIO = "presupuestos"


@dataclass(frozen=True)
class PresupuestoSeed:
    code: str
    client_name: str
    description: str
    status: StatusPresupuestos
    estimate_income: int
    start_date: datetime
    end_date: datetime
    pct_gastos_generales: float
    pct_utilidad: float
    pct_iva: float
    # (código de APU, cantidad)
    items: list[tuple[str, int]] = field(default_factory=list)


SEED_PRESUPUESTOS: list[PresupuestoSeed] = [
    PresupuestoSeed(
        code="PRE-2026-001",
        client_name="Constructora Andes Ltda.",
        description="Retiro de escombros, construcción pavimento, hormigón estampado",
        status=StatusPresupuestos.ACTIVE,
        estimate_income=30_000_000,
        start_date=datetime(2026, 4, 20),
        end_date=datetime(2026, 6, 30),
        pct_gastos_generales=12, pct_utilidad=15, pct_iva=19,
        items=[("OP-001", 1), ("OP-003", 24), ("OG-002", 280),
               ("PV-001", 280), ("PV-002", 142), ("OF-001", 1)],
    ),
    PresupuestoSeed(
        code="PRE-2026-002",
        client_name="Agrícola Los Robles SpA",
        description="Ampliación de oficinas administrativas",
        status=StatusPresupuestos.DRAFT,
        estimate_income=45_000_000,
        start_date=datetime(2026, 12, 1),
        end_date=datetime(2027, 3, 31),
        pct_gastos_generales=10, pct_utilidad=12, pct_iva=19,
        items=[("OP-002", 120), ("MT-001", 40), ("MT-002", 25), ("OG-001", 18),
               ("OG-003", 1_200), ("OG-004", 90), ("TE-001", 350), ("IN-001", 24)],
    ),
    PresupuestoSeed(
        code="PRE-2026-003",
        client_name="Inmobiliaria Maule S.A.",
        description="Remodelación de baños, edificio central",
        status=StatusPresupuestos.CLOSE,
        estimate_income=8_000_000,
        start_date=datetime(2026, 2, 2),
        end_date=datetime(2026, 3, 15),
        pct_gastos_generales=12, pct_utilidad=15, pct_iva=19,
        items=[("OP-003", 6), ("TE-002", 60), ("IN-002", 8), ("TE-001", 120)],
    ),
]


def _duenio(session: Session) -> User | None:
    usuario = session.exec(select(User).where(User.username == USUARIO_DUENIO)).first()
    if usuario is not None:
        return usuario
    return session.exec(
        select(User).where(User.role == UserRole.ADMIN).order_by(User.id)
    ).first()


def sembrarPresupuestos(session: Session) -> int:
    """Crea los presupuestos que falten con sus ítems. Devuelve cuántos creó (sin commit)."""
    duenio = _duenio(session)
    if duenio is None:
        raise RuntimeError(
            "No hay usuarios para asignar los presupuestos. "
            "Ejecuta primero: python -m scripts.seed_admin"
        )

    sembrarApus(session)
    apus = {a.code: a for a in session.exec(select(APU)).all()}
    existentes = set(session.exec(select(Presupuesto.code)).all())

    creados = 0
    for data in SEED_PRESUPUESTOS:
        if data.code in existentes:
            print(f"  = ya existía {data.code}")
            continue

        presupuesto = Presupuesto(
            id_usuario=duenio.id,
            code=data.code,
            client_name=data.client_name,
            description=data.description,
            status=data.status,
            estimate_income=data.estimate_income,
            start_date=data.start_date,
            end_date=data.end_date,
            pct_gastos_generales=data.pct_gastos_generales,
            pct_utilidad=data.pct_utilidad,
            pct_iva=data.pct_iva,
        )
        session.add(presupuesto)
        session.flush()   # asigna id_presupuesto

        for codigo, cantidad in data.items:
            apu = apus[codigo]
            detalle = DetallePresupuesto(
                id_presupuesto=presupuesto.id_presupuesto,
                id_apu=apu.id,
                unit=apu.unit,
                cantidad=cantidad,
                estimated_unit_cost=apu.unit_cost,     # snapshot del catálogo
                real_unit_cost=apu.real_unit_cost,
            )
            calcularSubtotales(detalle)
            session.add(detalle)
        session.flush()

        recalcularPresupuesto(session, presupuesto)
        creados += 1
        print(
            f"  + creado  {data.code} · {data.client_name} · "
            f"{len(data.items)} ítems · total ${presupuesto.monto_total:,.0f}".replace(",", ".")
        )
    return creados


def run() -> int:
    if not verificarTablas():
        raise SystemExit(
            "La base de datos no tiene las tablas. Ejecuta primero: "
            "python -m scripts.iniciar --solo-verificar"
        )
    print("Sembrando presupuestos...")
    with Session(engine) as session:
        creados = sembrarPresupuestos(session)
        session.commit()
    print(f"OK: Seed de presupuestos completado ({creados} nuevo(s)).")
    return creados


if __name__ == "__main__":
    run()
