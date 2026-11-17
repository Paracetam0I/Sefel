from sqlmodel import select

from app.models.user import Presupuesto


def test_crear_presupuesto_sin_fechas_ni_ruta_de_reporte(logged_in_client, session):
    response = logged_in_client.post(
        "/presupuestos",
        data={
            "code": "PRE-009", "client_name": "Cliente",
            "estimate_income": "1000", "description": "Sin fechas",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    presupuesto = session.exec(
        select(Presupuesto).where(Presupuesto.code == "PRE-009")
    ).one()
    assert presupuesto.start_date is None
    assert presupuesto.end_date is None
    assert presupuesto.ruta_reporte is None