"""Cálculos de presupuestación: subtotales de ítems, totales y porcentajes.

Fórmulas (formato de la cotización; montos CLP enteros, redondeados al peso):
    base (costo directo)   = costo_directo fijo (si > 0) o total_real
    monto_gastos_generales = base * pct_gastos_generales / 100
    monto_utilidad         = base * pct_utilidad / 100
    monto_costo_neto       = base + gastos generales + utilidad
    neto                   = costo_neto fijo (si > 0) o monto_costo_neto
    monto_iva              = neto * pct_iva / 100
    monto_total            = neto + IVA
"""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlmodel import Session, select

from app.models.apu import APU
from app.models.detalle_presupuesto import DetallePresupuesto
from app.models.presupuesto import Presupuesto

SIN_CATEGORIA = "Sin categoría"


def _redondear(valor: Decimal) -> int:
    return int(valor.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _porcentaje(monto: int | Decimal, pct: float) -> Decimal:
    # str() evita arrastrar el error binario del float (19.9 -> 19.899999...)
    return Decimal(monto) * Decimal(str(pct)) / Decimal(100)


def calcularSubtotales(detalle: DetallePresupuesto) -> DetallePresupuesto:
    """Calcula subtotal cotizado y real de una línea del presupuesto."""
    detalle.subtotal = detalle.cantidad * detalle.estimated_unit_cost
    detalle.real_subtotal = detalle.cantidad * detalle.real_unit_cost
    return detalle


def calcularMontos(
    total_real: int,
    pct_gastos_generales: float,
    pct_iva: float,
    pct_utilidad: float,
    costo_directo: int | None = None,
    costo_neto: int | None = None,
) -> dict:
    """Aplica los porcentajes sobre la base y devuelve los montos derivados."""
    base = costo_directo if costo_directo else total_real

    monto_gg = _redondear(_porcentaje(base, pct_gastos_generales))
    monto_utilidad = _redondear(_porcentaje(base, pct_utilidad))
    # Suma de montos ya redondeados para que el desglose cuadre
    monto_costo_neto = base + monto_gg + monto_utilidad

    neto = costo_neto if costo_neto else monto_costo_neto
    monto_iva = _redondear(_porcentaje(neto, pct_iva))
    return {
        "monto_gastos_generales": monto_gg,
        "monto_utilidad": monto_utilidad,
        "monto_costo_neto": monto_costo_neto,
        "monto_iva": monto_iva,
        "monto_total": neto + monto_iva,
    }


def recalcularPresupuesto(session: Session, presupuesto: Presupuesto) -> Presupuesto:
    """Recalcula totales y montos del presupuesto a partir de sus ítems.

    No hace commit: el llamador decide cuándo confirmar la transacción.
    """
    detalles = session.exec(
        select(DetallePresupuesto).where(
            DetallePresupuesto.id_presupuesto == presupuesto.id_presupuesto
        )
    ).all()

    presupuesto.total_cotizado = sum(d.subtotal for d in detalles)
    presupuesto.total_real = sum(d.real_subtotal for d in detalles)

    montos = calcularMontos(
        presupuesto.total_real,
        presupuesto.pct_gastos_generales,
        presupuesto.pct_iva,
        presupuesto.pct_utilidad,
        presupuesto.costo_directo,
        presupuesto.costo_neto,
    )
    for campo, valor in montos.items():
        setattr(presupuesto, campo, valor)

    presupuesto.updated_at = datetime.now(timezone.utc)
    session.add(presupuesto)
    return presupuesto


def totalesPorCategoria(session: Session, presupuesto: Presupuesto) -> list[dict]:
    """Suma cotizado y real de los ítems agrupados por la categoría del APU."""
    filas = session.exec(
        select(DetallePresupuesto, APU.category)
        .join(APU, APU.id == DetallePresupuesto.id_apu)
        .where(DetallePresupuesto.id_presupuesto == presupuesto.id_presupuesto)
    ).all()

    grupos: dict[str, dict] = defaultdict(
        lambda: {"cantidad_items": 0, "cotizado": 0, "real": 0}
    )
    for detalle, categoria in filas:
        grupo = grupos[categoria or SIN_CATEGORIA]
        grupo["cantidad_items"] += 1
        grupo["cotizado"] += detalle.subtotal
        grupo["real"] += detalle.real_subtotal

    return [
        {"categoria": nombre, **valores}
        for nombre, valores in sorted(grupos.items())
    ]
