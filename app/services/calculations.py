"""Cálculos de dinero del presupuesto (moneda: peso chileno, CLP).

Reglas del proyecto:
- Todo el dinero y los cálculos usan Decimal, nunca float.
- El peso chileno no tiene centavos: subtotales y totales se redondean a pesos
  enteros. DECIMALES_MONEDA controla esto en un solo lugar.
- Redondeo: ROUND_HALF_UP (0.5 -> 1, 2.5 -> 3), como una calculadora o Excel.
- Se redondea UNA vez por ítem (el subtotal). El total es la suma de subtotales ya
  redondeados, así lo que se ve en pantalla suma exactamente.
"""

from decimal import ROUND_HALF_UP, Decimal

DECIMALES_MONEDA = 2  # CLP: pesos enteros (con 2 serían centavos)
UNIDAD_MINIMA = Decimal(1).scaleb(-DECIMALES_MONEDA)
REDONDEO = ROUND_HALF_UP
CERO = Decimal(0).quantize(UNIDAD_MINIMA)


def toDecimal(valor) -> Decimal:
    """Convierte int, str o Decimal a Decimal. Rechaza float a propósito."""
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, (int, str)) and not isinstance(valor, bool):
        return Decimal(valor)
    raise TypeError(
        f"Dinero y cantidades deben ser Decimal, int o str; llegó {type(valor).__name__}"
    )


def redondear(valor: Decimal) -> Decimal:
    """Redondea a la unidad mínima de la moneda con la política del proyecto."""
    return valor.quantize(UNIDAD_MINIMA, rounding=REDONDEO)


def calculate_item_subtotal(item) -> Decimal:
    """subtotal = cantidad (estimated_quantity) × estimated_unit_cost, redondeado."""
    cantidad = toDecimal(item.cantidad)
    costo_unitario = toDecimal(item.estimated_unit_cost)
    return redondear(cantidad * costo_unitario)


def calculate_budget_total(budget) -> Decimal:
    """total_estimated = suma de los subtotales de los ítems del presupuesto.

    Acepta un presupuesto (usa sus .detalles) o directamente una lista de ítems.
    """
    items = getattr(budget, "detalles", budget)
    return sum((calculate_item_subtotal(item) for item in items), CERO)