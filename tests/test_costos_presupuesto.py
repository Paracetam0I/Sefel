"""Costos cotizado/real de APU e ítems, y porcentajes del presupuesto."""
import json
from datetime import datetime

import pytest
from sqlmodel import select

from app.core.calculos import calcularMontos
from app.core.routers.materiales import _validar
from app.models.detalle_presupuesto import DetallePresupuesto
from app.models.material import Material
from app.models.presupuesto import Presupuesto
from app.models.user import UserRole


@pytest.fixture
def presupuesto(session, user):
    p = Presupuesto(
        id_usuario=user.id, code="PRE-001", client_name="Cliente",
        estimate_income=1000000,
        start_date=datetime(2026, 11, 1), end_date=datetime(2026, 12, 31),
        description="Presupuesto de prueba",
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


@pytest.fixture
def crearApu(crear_apu):
    """crearApu(code, categoría del APU, CDU cotizado, CDU real)."""
    def crear(code, category, unit_cost, real_unit_cost):
        return crear_apu(code, unit_cost, real_unit_cost, category=category)
    return crear


def agregarItem(client, presupuesto, apu, cantidad):
    # El precio no se envía: el servidor lo copia del costo calculado del APU
    return client.post(
        f"/presupuestos/{presupuesto.id_presupuesto}/items",
        data={
            "id_apu": str(apu.id),
            "unit": apu.unit,
            "cantidad": str(cantidad),
            "costo_directo": "0",
            "costo_indirecto": "0",
        },
        follow_redirects=False,
    )


# Cálculo puro
# ==========================================

def test_calcular_montos_reproduce_la_cotizacion_de_referencia():
    # Valores de ejemplo-pdf.png: GG 12%, utilidad 15%, IVA 19%
    montos = calcularMontos(17_930_895, 12, 19, 15)

    assert montos["monto_gastos_generales"] == 2_151_707        # 12% del costo directo
    assert montos["monto_utilidad"] == 2_689_634                # 15% del costo directo
    assert montos["monto_costo_neto"] == 22_772_236             # CD + GG + utilidad
    assert montos["monto_iva"] == 4_326_725                     # 19% del neto
    assert montos["monto_total"] == 27_098_961                  # neto + IVA


def test_calcular_montos_iva_sobre_costo_neto_fijo():
    montos = calcularMontos(1_000_000, 10, 19, 15, costo_neto=2_000_000)

    assert montos["monto_costo_neto"] == 1_250_000              # el calculado se conserva
    assert montos["monto_iva"] == 380_000                       # 19% del neto fijo
    assert montos["monto_total"] == 2_380_000


def test_calcular_montos_usa_costo_directo_fijo_como_base():
    montos = calcularMontos(1_000_000, 10, 0, 0, costo_directo=2_000_000)

    assert montos["monto_gastos_generales"] == 200_000
    assert montos["monto_costo_neto"] == 2_200_000
    assert montos["monto_total"] == 2_200_000


def test_calcular_montos_redondea_y_cuadra_el_desglose():
    montos = calcularMontos(333, 12.5, 19, 7.25)

    neto = 333 + montos["monto_gastos_generales"] + montos["monto_utilidad"]
    assert montos["monto_costo_neto"] == neto
    assert montos["monto_total"] == neto + montos["monto_iva"]


# Recursos (Base de datos): costo cotizado y real
# ==========================================

def test_recurso_costo_real_vacio_parte_igual_al_cotizado():
    datos, error = _validar({
        "code": "A", "name": "N", "unit": "m", "category": "Materiales",
        "unit_cost": "5000", "real_unit_cost": "",
    })
    assert error is None
    assert datos["real_unit_cost"] == 5000


def test_recurso_rechaza_costo_real_negativo():
    _, error = _validar({
        "code": "A", "name": "N", "unit": "m", "category": "Materiales",
        "unit_cost": "5000", "real_unit_cost": "-1",
    })
    assert error == "El costo real no puede ser negativo."


def test_crear_recurso_guarda_costo_cotizado_y_real(logged_in_client, session):
    response = logged_in_client.post(
        "/base-datos",
        data={
            "code": "MAT-R", "name": "Hormigón", "unit": "m3", "category": "Materiales",
            "unit_cost": "85000", "real_unit_cost": "91000",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    material = session.exec(select(Material).where(Material.code == "MAT-R")).one()
    assert material.unit_cost == 85000
    assert material.real_unit_cost == 91000

    listado = logged_in_client.get("/base-datos")
    assert "Costo real" in listado.text
    assert "$ 91.000" in listado.text


# Ítems y totales del presupuesto
# ==========================================

def test_item_calcula_subtotal_real_y_totales_del_presupuesto(
    logged_in_client, session, presupuesto, crearApu
):
    a = crearApu("A-1", "Obra gruesa", 1000, 1200)
    b = crearApu("B-1", "Terminaciones", 500, 400)

    assert agregarItem(logged_in_client, presupuesto, a, 3).status_code == 303
    assert agregarItem(logged_in_client, presupuesto, b, 2).status_code == 303

    items = session.exec(select(DetallePresupuesto).order_by(DetallePresupuesto.id)).all()
    assert [(i.subtotal, i.real_subtotal) for i in items] == [(3000, 3600), (1000, 800)]

    session.refresh(presupuesto)
    assert presupuesto.total_cotizado == 4000
    assert presupuesto.total_real == 4400
    assert presupuesto.monto_costo_neto == 4400   # sin porcentajes aún


def test_editar_item_recalcula_subtotales_y_presupuesto(
    logged_in_client, session, presupuesto, crearApu
):
    a = crearApu("A-1", "Obra gruesa", 1000, 1000)
    agregarItem(logged_in_client, presupuesto, a, 1)
    item = session.exec(select(DetallePresupuesto)).one()

    # El costo cotizado es el del APU: aunque se envíe otro, no cambia
    response = logged_in_client.post(
        f"/presupuestos/{presupuesto.id_presupuesto}/items/{item.id}",
        data={"cantidad": "4", "estimated_unit_cost": "999999", "real_unit_cost": "1500"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    session.refresh(item)
    session.refresh(presupuesto)
    assert (item.subtotal, item.real_subtotal) == (4000, 6000)
    assert (presupuesto.total_cotizado, presupuesto.total_real) == (4000, 6000)


# Porcentajes
# ==========================================

def test_guardar_porcentajes_calcula_y_almacena_montos(
    logged_in_client, session, presupuesto, crearApu
):
    a = crearApu("A-1", "Obra gruesa", 900_000, 1_000_000)
    agregarItem(logged_in_client, presupuesto, a, 1)

    response = logged_in_client.post(
        f"/presupuestos/{presupuesto.id_presupuesto}/porcentajes",
        data={
            "pct_gastos_generales": "10", "pct_iva": "19", "pct_utilidad": "15",
            "costo_directo": "0", "costo_neto": "0",
        },
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert "recargar-presupuestos" in json.loads(response.headers["HX-Trigger"])
    assert "Obra gruesa" in response.text            # totales por categoría
    assert "$ 1.487.500" in response.text            # total con IVA

    session.refresh(presupuesto)
    assert presupuesto.total_real == 1_000_000
    assert presupuesto.monto_gastos_generales == 100_000
    assert presupuesto.monto_utilidad == 150_000
    assert presupuesto.monto_costo_neto == 1_250_000
    assert presupuesto.monto_iva == 237_500
    assert presupuesto.monto_total == 1_487_500
    assert presupuesto.monto_final == 1_487_500


def test_costo_neto_fijo_reemplaza_al_calculado_y_lleva_iva(
    logged_in_client, session, presupuesto
):
    logged_in_client.post(
        f"/presupuestos/{presupuesto.id_presupuesto}/porcentajes",
        data={"pct_gastos_generales": "0", "pct_iva": "19", "pct_utilidad": "0",
              "costo_directo": "", "costo_neto": "5000000"},
    )
    session.refresh(presupuesto)
    assert presupuesto.costo_neto == 5_000_000
    assert presupuesto.monto_iva == 950_000
    assert presupuesto.monto_final == 5_950_000
    assert presupuesto.costo_directo is None


@pytest.mark.parametrize("campo", ["pct_gastos_generales", "pct_iva", "pct_utilidad"])
@pytest.mark.parametrize("valor", ["-1", "100.5", "abc"])
def test_rechaza_porcentajes_fuera_de_rango(
    logged_in_client, session, presupuesto, campo, valor
):
    datos = {"pct_gastos_generales": "0", "pct_iva": "0", "pct_utilidad": "0",
             "costo_directo": "0", "costo_neto": "0", campo: valor}

    response = logged_in_client.post(
        f"/presupuestos/{presupuesto.id_presupuesto}/porcentajes", data=datos,
    )
    assert response.status_code == 400
    assert "entre 0 y 100" in response.text

    session.refresh(presupuesto)
    assert presupuesto.pct_iva == 0


def test_acepta_coma_decimal_en_porcentajes(logged_in_client, session, presupuesto):
    logged_in_client.post(
        f"/presupuestos/{presupuesto.id_presupuesto}/porcentajes",
        data={"pct_gastos_generales": "12,5", "pct_iva": "19", "pct_utilidad": "0",
              "costo_directo": "0", "costo_neto": "0"},
    )
    session.refresh(presupuesto)
    assert presupuesto.pct_gastos_generales == 12.5


def test_viewer_puede_ver_pero_no_guardar_porcentajes(
    logged_in_client, session, user, presupuesto
):
    user.role = UserRole.VIEWER
    session.add(user)
    session.commit()

    vista = logged_in_client.get(
        f"/presupuestos/{presupuesto.id_presupuesto}/porcentajes",
        headers={"HX-Request": "true"},
    )
    assert vista.status_code == 200
    assert "solo permite consultar" in vista.text

    response = logged_in_client.post(
        f"/presupuestos/{presupuesto.id_presupuesto}/porcentajes",
        data={"pct_gastos_generales": "10", "pct_iva": "19", "pct_utilidad": "15",
              "costo_directo": "0", "costo_neto": "0"},
    )
    assert response.status_code == 403


def test_listado_muestra_totales_cotizado_real_y_monto_final(
    logged_in_client, session, presupuesto
):
    presupuesto.total_cotizado = 4000
    presupuesto.total_real = 4600
    presupuesto.monto_total = 5474
    session.add(presupuesto)
    session.commit()

    response = logged_in_client.get("/presupuestos")
    assert response.status_code == 200
    for texto in ("Total cotizado", "Total real", "Monto final",
                  "$ 4.000", "$ 4.600", "$ 5.474",
                  f"/presupuestos/{presupuesto.id_presupuesto}/porcentajes"):
        assert texto in response.text
