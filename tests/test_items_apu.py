from datetime import datetime

import pytest
from sqlmodel import select

from app.core.security import hashPassword
from app.models.apu import APU
from app.models.detalle_presupuesto import DetallePresupuesto
from app.models.user import Presupuesto, User, UserRole


@pytest.fixture
def apu(session):
    a = APU(code="APU-001", name="Barra acero A630", unit="kg", unit_cost=2500, is_active=True)
    session.add(a)
    session.commit()
    session.refresh(a)
    return a


@pytest.fixture
def apu_inactivo(session):
    a = APU(code="APU-002", name="Perno de anclaje", unit="un", unit_cost=3450, is_active=False)
    session.add(a)
    session.commit()
    session.refresh(a)
    return a


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


def datosItem(apu, **cambios):
    datos = {
        "id_apu": str(apu.id),
        "unit": "kg",
        "estimated_unit_cost": "10500",
        "cantidad": "3",
        "costo_directo": "1000",
        "costo_indirecto": "500",
    }
    datos.update(cambios)
    return datos


# Búsqueda y autocompletado
# ==========================================

def test_buscar_devuelve_solo_apus_activos(logged_in_client, apu, apu_inactivo):
    response = logged_in_client.get("/api/apu/buscar")

    assert response.status_code == 200
    assert "APU-001" in response.text
    assert "APU-002" not in response.text


def test_buscar_sin_sesion_responde_401(client):
    response = client.get("/api/apu/buscar")

    assert response.status_code == 401
    assert response.json() == {"detail": "No autenticado"}


def test_viewer_no_puede_buscar_apus(logged_in_client, session, user):
    # El rol se cambia DESPUÉS de iniciar sesión: manda la base de datos, no la cookie
    user.role = UserRole.VIEWER
    session.add(user)
    session.commit()

    response = logged_in_client.get("/api/apu/buscar")

    assert response.status_code == 403
    assert response.json() == {"detail": "Sin permiso"}


def test_autocompletar_devuelve_unidad_y_costo_del_apu(logged_in_client, apu):
    response = logged_in_client.get(f"/api/apu/{apu.id}/autocompletar")

    assert response.status_code == 200
    assert 'value="kg"' in response.text
    assert 'value="2500"' in response.text


def test_autocompletar_rechaza_apu_inactivo(logged_in_client, apu_inactivo):
    response = logged_in_client.get(f"/api/apu/{apu_inactivo.id}/autocompletar")

    assert response.status_code == 404


# Guardar el ítem
# ==========================================

def test_agregar_item_guarda_copia_editable_y_no_cambia_el_apu(
    logged_in_client, session, presupuesto, apu
):
    # Se intenta colar un subtotal falso: el servidor debe ignorarlo
    datos = datosItem(apu, subtotal="1")

    response = logged_in_client.post(
        f"/presupuestos/{presupuesto.id_presupuesto}/items",
        data=datos,
        follow_redirects=False,
    )

    assert response.status_code == 303

    item = session.exec(select(DetallePresupuesto)).first()
    assert item is not None
    assert item.id_apu == apu.id
    assert item.estimated_unit_cost == 10500   # el valor editado
    assert item.subtotal == 31500              # 3 * 10500, calculado en el servidor
    assert item.costo_directo == 1000
    assert item.costo_indirecto == 500

    session.refresh(apu)
    assert apu.unit_cost == 2500               # el catálogo no cambió


def test_rechaza_apu_inactivo_al_guardar(
    logged_in_client, session, presupuesto, apu_inactivo
):
    response = logged_in_client.post(
        f"/presupuestos/{presupuesto.id_presupuesto}/items",
        data=datosItem(apu_inactivo),
    )

    assert response.status_code == 400
    assert "APU activo" in response.text
    assert session.exec(select(DetallePresupuesto)).first() is None


def test_no_agrega_items_a_presupuesto_de_otro_usuario(
    logged_in_client, session, apu
):
    otro = User(
        username="otro", email="otro@example.com",
        hashed_password=hashPassword("Otra12345"),
        full_name="Otro usuario", role=UserRole.BUDGETS, is_active=True,
    )
    session.add(otro)
    session.commit()
    session.refresh(otro)

    ajeno = Presupuesto(
        id_usuario=otro.id, code="PRE-AJENO", client_name="Cliente",
        estimate_income=1000000,
        start_date=datetime(2026, 11, 1), end_date=datetime(2026, 12, 31),
        description="De otro usuario",
    )
    session.add(ajeno)
    session.commit()
    session.refresh(ajeno)

    response = logged_in_client.post(
        f"/presupuestos/{ajeno.id_presupuesto}/items",
        data=datosItem(apu),
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/presupuestos"
    assert session.exec(select(DetallePresupuesto)).first() is None


def test_viewer_recibe_403_al_agregar_items(
    logged_in_client, session, user, presupuesto
):
    user.role = UserRole.VIEWER
    session.add(user)
    session.commit()

    response = logged_in_client.get(
        f"/presupuestos/{presupuesto.id_presupuesto}/items/nuevo"
    )

    assert response.status_code == 403