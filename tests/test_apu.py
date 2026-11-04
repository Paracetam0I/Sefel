from sqlmodel import select

from app.models.apu import APU


DATOS_APU = {
    "code": "APU-001",
    "name": "Hormigón H25",
    "unit": "m3",
    "category": "Obra gruesa",
    "unit_cost": "85000",
    "description": "APU de prueba",
}


def test_crear_apu(logged_in_client, session):
    response = logged_in_client.post("/apu", data=DATOS_APU, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/apu"

    apu = session.exec(
        select(APU).where(APU.code == "APU-001")
    ).first()

    assert apu is not None
    assert apu.name == "Hormigón H25"
    assert apu.unit_cost == 85000


def test_editar_apu(logged_in_client, session):
    apu = APU(**DATOS_APU)
    session.add(apu)
    session.commit()
    session.refresh(apu)

    datos = {
        **DATOS_APU,
        "name": "Hormigón H30",
        "unit_cost": "95000",
    }

    response = logged_in_client.post(
        f"/apu/{apu.id}",
        data=datos,
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/apu"

    session.refresh(apu)
    assert apu.name == "Hormigón H30"
    assert apu.unit_cost == 95000


def test_rechazar_codigo_duplicado_al_crear(logged_in_client, session):
    session.add(APU(**DATOS_APU))
    session.commit()

    datos = {**DATOS_APU, "code": "apu-001"}

    response = logged_in_client.post("/apu", data=datos)

    assert response.status_code == 400
    assert "Ya existe un APU" in response.text


def test_rechazar_codigo_duplicado_al_editar(logged_in_client, session):
    primero = APU(**DATOS_APU)
    segundo = APU(
        **{
            **DATOS_APU,
            "code": "APU-002",
            "name": "Excavación",
        }
    )
    session.add_all([primero, segundo])
    session.commit()
    session.refresh(segundo)

    datos = {
        **DATOS_APU,
        "code": "apu-001",
        "name": "Excavación modificada",
    }

    response = logged_in_client.post(
        f"/apu/{segundo.id}",
        data=datos,
    )

    assert response.status_code == 400
    assert "Ya existe otro APU" in response.text


def test_rechazar_nombre_vacio(logged_in_client):
    datos = {**DATOS_APU, "name": "   "}

    response = logged_in_client.post("/apu", data=datos)

    assert response.status_code == 400
    assert "nombre" in response.text.lower()


def test_rechazar_costo_negativo(logged_in_client):
    datos = {**DATOS_APU, "unit_cost": "-100"}

    response = logged_in_client.post("/apu", data=datos)

    assert response.status_code == 400
    assert "negativo" in response.text.lower()




