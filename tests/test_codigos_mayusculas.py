"""Los códigos de APU y presupuestos se guardan siempre en MAYÚSCULAS."""
from datetime import datetime

import pytest
from alembic import command
from sqlmodel import Session, select

from app.core import inicializacion
from app.core.validaciones import validarCodigo
from app.models.apu import APU
from app.models.presupuesto import Presupuesto
from tests.test_seeds_inicio import bd_temporal  # noqa: F401  (fixture de BD temporal)

HTMX = {"HX-Request": "true"}


def datosApu(**cambios):
    datos = {"code": "og_01-a", "name": "Hormigón", "unit": "m3", "unit_cost": "1000"}
    datos.update(cambios)
    return datos


def datosPresupuesto(**cambios):
    datos = {"code": "pre-ñandú_1", "client_name": "Cliente", "estimate_income": "1",
             "start_date": "2026-03-01", "end_date": "2026-04-01",
             "description": "Obra", "status": "DRAFT"}
    datos.update(cambios)
    return datos


@pytest.mark.parametrize(("entrada", "esperado"), [
    ("pre-01", "PRE-01"), ("  og_01-a ", "OG_01-A"), ("ñandú-año", "ÑANDÚ-AÑO"), ("YA-ESTA", "YA-ESTA"),
])
def test_validar_codigo_convierte_a_mayusculas(entrada, esperado):
    assert validarCodigo(entrada) == esperado


def test_apu_se_guarda_en_mayusculas_al_crear_y_editar(logged_in_client, session):
    logged_in_client.post("/apu", data=datosApu(), headers=HTMX)
    apu = session.exec(select(APU)).one()
    assert apu.code == "OG_01-A"

    logged_in_client.post(f"/apu/{apu.id}", data=datosApu(code="og_01-b"), headers=HTMX)
    session.refresh(apu)
    assert apu.code == "OG_01-B"


def test_presupuesto_se_guarda_en_mayusculas_al_crear_y_editar(logged_in_client, session):
    logged_in_client.post("/presupuestos", data=datosPresupuesto(), headers=HTMX)
    presupuesto = session.exec(select(Presupuesto)).one()
    assert presupuesto.code == "PRE-ÑANDÚ_1"

    logged_in_client.post(f"/presupuestos/{presupuesto.id_presupuesto}",
                          data=datosPresupuesto(code="pre-2"), headers=HTMX)
    session.refresh(presupuesto)
    assert presupuesto.code == "PRE-2"


def test_minusculas_no_esquivan_el_control_de_duplicados(logged_in_client, session):
    logged_in_client.post("/apu", data=datosApu(code="DUP-1"), headers=HTMX)
    respuesta = logged_in_client.post("/apu", data=datosApu(code="dup-1"), headers=HTMX)
    assert "Ya existe un APU con ese código." in respuesta.text
    assert len(session.exec(select(APU)).all()) == 1


def test_formularios_muestran_el_codigo_en_mayusculas(logged_in_client):
    assert 'class="field w-full uppercase"' in logged_in_client.get("/apu/nuevo", headers=HTMX).text
    assert 'class="field w-full uppercase"' in logged_in_client.get("/presupuestos/nuevo", headers=HTMX).text


def test_migracion_pasa_a_mayusculas_los_codigos_existentes(bd_temporal):  # noqa: F811
    inicializacion.prepararBaseDatos()
    inicializacion.asegurarAdmin()                    # dueño del presupuesto (id 1)
    config = inicializacion._configAlembic()
    command.downgrade(config, "59241f60df74")         # BD de la versión anterior

    with Session(bd_temporal) as s:
        s.add(APU(code="og-ñ1", name="x", unit="m", unit_cost=1, real_unit_cost=1))
        s.add(Presupuesto(id_usuario=1, code="pre-año", client_name="C", estimate_income=1,
                          start_date=datetime(2026, 3, 1), end_date=datetime(2026, 4, 1), description="d"))
        s.commit()

    command.upgrade(config, "head")

    with Session(bd_temporal) as s:
        assert s.exec(select(APU.code)).one() == "OG-Ñ1"
        assert s.exec(select(Presupuesto.code)).one() == "PRE-AÑO"
