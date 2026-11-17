"""Exportación de presupuestos a PDF."""
import re
from datetime import date, datetime

import pytest

from app.core.calculos import recalcularPresupuesto
from app.core.pdf_presupuesto import datosCotizacion, generarPdfCotizacion
from app.core.security import hashPassword
from app.models.apu import APU
from app.models.detalle_presupuesto import DetallePresupuesto
from app.models.presupuesto import Presupuesto
from app.models.user import User, UserRole


@pytest.fixture
def presupuesto(session, user):
    p = Presupuesto(
        id_usuario=user.id, code="PRE-326", client_name="Cliente <Uno> & Cía",
        estimate_income=1, start_date=datetime(2026, 4, 1), end_date=datetime(2026, 5, 1),
        description="Retiro de escombros, construcción pavimento",
        pct_gastos_generales=12, pct_utilidad=15, pct_iva=19,
    )
    session.add(p)
    session.commit()
    session.refresh(p)

    apu = APU(code="A-1", name="Radier G-20", unit="m2", unit_cost=45000, real_unit_cost=49620)
    session.add(apu)
    session.commit()
    session.refresh(apu)

    detalle = DetallePresupuesto(
        id_presupuesto=p.id_presupuesto, id_apu=apu.id, unit="m2", cantidad=280,
        estimated_unit_cost=45000, subtotal=280 * 45000,
        real_unit_cost=49620, real_subtotal=280 * 49620,
    )
    session.add(detalle)
    session.flush()
    recalcularPresupuesto(session, p)
    session.commit()
    session.refresh(p)
    return p


def test_datos_de_la_cotizacion(session, presupuesto):
    datos = datosCotizacion(session, presupuesto, fecha=date(2026, 4, 16))

    assert datos["numero"] == presupuesto.id_presupuesto
    assert datos["cliente"]["nombre"] == "Cliente <Uno> & Cía"
    assert datos["titulo_items"] == "RETIRO DE ESCOMBROS, CONSTRUCCIÓN PAVIMENTO"

    item = datos["items"][0]
    assert (item["descripcion"], item["unidad"], item["cantidad"]) == ("RADIER G-20", "M2", 280)
    assert (item["valor_unitario"], item["valor_total"]) == (49620, 13_893_600)   # costo real

    t = datos["totales"]
    assert t["costo_directo"] == 13_893_600
    assert t["gastos_generales"] == 1_667_232          # 12%
    assert t["utilidad"] == 2_084_040                  # 15%
    assert t["neto"] == 17_644_872
    assert t["iva"] == 3_352_526                       # 19% del neto
    assert t["total"] == 20_997_398


def test_genera_un_pdf_valido_con_caracteres_especiales(session, presupuesto):
    contenido = generarPdfCotizacion(datosCotizacion(session, presupuesto))
    assert contenido.startswith(b"%PDF-")
    assert contenido.rstrip().endswith(b"%%EOF")


@pytest.mark.parametrize("rol", [UserRole.ADMIN, UserRole.BUDGETS, UserRole.BOTH, UserRole.VIEWER])
def test_descarga_directa_para_roles_de_presupuestos(client, session, presupuesto, rol):
    session.add(User(
        username="lector", email="lector@example.com", hashed_password=hashPassword("Clave12345"),
        full_name="Lector", role=rol, is_active=True,
    ))
    session.commit()
    client.post("/login", data={"username": "lector", "password": "Clave12345"})

    respuesta = client.get(f"/presupuestos/{presupuesto.id_presupuesto}/pdf")

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "application/pdf"
    disposicion = respuesta.headers["content-disposition"]
    assert re.fullmatch(
        rf'attachment; filename="presupuesto-{presupuesto.id_presupuesto}-\d{{4}}-\d{{2}}-\d{{2}}\.pdf"',
        disposicion,
    )
    assert respuesta.content.startswith(b"%PDF-")


def test_presupuesto_inexistente_responde_404(logged_in_client):
    respuesta = logged_in_client.get("/presupuestos/9999/pdf")
    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Presupuesto no encontrado"}


def test_selector_de_exportacion_lista_los_presupuestos(logged_in_client, presupuesto):
    respuesta = logged_in_client.get(
        "/presupuestos/exportar", headers={"HX-Request": "true"},
    )
    assert respuesta.status_code == 200
    assert "PRE-326" in respuesta.text
    assert f"/presupuestos/{presupuesto.id_presupuesto}/pdf" in respuesta.text


def test_boton_exportar_abre_el_selector(logged_in_client):
    html = logged_in_client.get("/presupuestos").text
    assert 'hx-get="/presupuestos/exportar"' in html
