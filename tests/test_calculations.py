from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.calculations import (
    calculate_budget_total,
    calculate_item_subtotal,
)


def item(cantidad, costo):
    return SimpleNamespace(cantidad=cantidad, estimated_unit_cost=costo)


def test_subtotal_con_enteros():
    assert calculate_item_subtotal(item(3, 10500)) == Decimal("31500")


def test_subtotal_acepta_cantidades_con_decimales():
    assert calculate_item_subtotal(item(Decimal("12.5"), 2500)) == Decimal("31250")


@pytest.mark.parametrize(
    "cantidad, esperado",
    [("0.5", "1"), ("1.5", "2"), ("2.5", "3"), ("2.4", "2"), ("2.6", "3")],
)
def test_redondeo_half_up(cantidad, esperado):
    # Con half-even, 0.5 daría 0 y 2.5 daría 2: estos casos fijan la política
    assert calculate_item_subtotal(item(Decimal(cantidad), 1)) == Decimal(esperado)


def test_subtotal_queda_en_pesos_enteros():
    resultado = calculate_item_subtotal(item(Decimal("2.5"), 100))
    assert resultado.as_tuple().exponent == 0


def test_total_suma_los_subtotales_ya_redondeados():
    # Cada ítem vale 0.5 -> 1. Redondear la suma (1.0) daría 1 en vez de 2.
    items = [item(Decimal("0.5"), 1), item(Decimal("0.5"), 1)]

    assert calculate_budget_total(items) == Decimal("2")


def test_total_de_un_presupuesto_con_detalles():
    budget = SimpleNamespace(detalles=[item(3, 10500), item(2, 1000)])

    assert calculate_budget_total(budget) == Decimal("33500")


def test_total_de_un_presupuesto_vacio_es_cero():
    assert calculate_budget_total(SimpleNamespace(detalles=[])) == Decimal("0")


def test_rechaza_float():
    with pytest.raises(TypeError):
        calculate_item_subtotal(item(1.5, 100))