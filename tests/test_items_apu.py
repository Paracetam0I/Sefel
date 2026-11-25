from datetime import datetime

import pytest
from sqlmodel import select

from app.core.security import hashPassword
from app.models.detalle_presupuesto import DetallePresupuesto
from app.models.material import Material
from app.models.user import Presupuesto, User, UserRole


@pytest.fixture
def apu(crear_apu):
    # Receta de 1 recurso: CDU cotizado 2500, real 2600
    return crear_apu("APU-001", 2500, 2600, name="Barra acero A630", unit="kg")


@pytest.fixture
def apu_inactivo(crear_apu):
    return crear_apu("APU-002", 3450, name="Perno de anclaje", unit="un", is_active=False)


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


def test_buscar_muestra_el_costo_calculado_del_apu(logged_in_client, apu):
    response = logged_in_client.get("/api/apu/buscar?q=APU-001")

    assert "$ 2.500" in response.text
    assert "$ 2.600" in response.text


def test_autocompletar_devuelve_unidad_y_costo_calculado_del_apu(logged_in_client, apu):
    response = logged_in_client.get(f"/api/apu/{apu.id}/autocompletar")

    assert response.status_code == 200
    assert 'value="kg"' in response.text
    assert "$ 2.500" in response.text               # CDU cotizado (solo lectura)
    assert "$ 2.600" in response.text               # CDU real
    assert 'name="estimated_unit_cost"' not in response.text


def test_autocompletar_rechaza_apu_inactivo(logged_in_client, apu_inactivo):
    response = logged_in_client.get(f"/api/apu/{apu_inactivo.id}/autocompletar")

    assert response.status_code == 404


# Guardar el ítem
# ==========================================

def test_agregar_item_copia_el_costo_calculado_del_apu(
    logged_in_client, session, presupuesto, apu
):
    # Se intenta colar un subtotal y un costo falsos: el servidor los ignora
    datos = datosItem(apu, subtotal="1", estimated_unit_cost="1")

    response = logged_in_client.post(
        f"/presupuestos/{presupuesto.id_presupuesto}/items",
        data=datos,
        follow_redirects=False,
    )

    assert response.status_code == 303

    item = session.exec(select(DetallePresupuesto)).first()
    assert item is not None
    assert item.id_apu == apu.id
    assert item.estimated_unit_cost == 2500    # CDU de la receta del APU
    assert item.real_unit_cost == 2600
    assert item.subtotal == 7500               # 3 * 2500, calculado en el servidor
    assert item.real_subtotal == 7800
    assert item.costo_directo == 1000
    assert item.costo_indirecto == 500


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


def test_agrega_items_a_presupuesto_creado_por_otro_usuario(
    logged_in_client, session, apu
):
    # No hay exclusividad por creador: los roles de edición trabajan sobre todos
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
    item = session.exec(select(DetallePresupuesto)).one()
    assert item.id_presupuesto == ajeno.id_presupuesto


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

def test_rechaza_apu_sin_recursos(logged_in_client, session, presupuesto, crear_apu):
    vacio = crear_apu("APU-VACIO", con_recursos=False)

    response = logged_in_client.post(
        f"/presupuestos/{presupuesto.id_presupuesto}/items",
        data=datosItem(vacio),
    )

    assert response.status_code == 400
    assert "no tiene recursos" in response.text
    assert session.exec(select(DetallePresupuesto)).first() is None


def test_el_item_conserva_su_precio_hasta_actualizarlo(
    logged_in_client, session, presupuesto, apu
):
    logged_in_client.post(
        f"/presupuestos/{presupuesto.id_presupuesto}/items", data=datosItem(apu),
    )
    item = session.exec(select(DetallePresupuesto)).one()

    # Sube el precio del recurso en la Base de datos
    recurso = session.exec(select(Material).where(Material.code == "REC-APU-001")).one()
    recurso.unit_cost = 3000
    recurso.real_unit_cost = 3100
    session.add(recurso)
    session.commit()

    session.refresh(item)
    assert item.estimated_unit_cost == 2500     # el presupuesto guarda su copia

    response = logged_in_client.post(
        f"/presupuestos/{presupuesto.id_presupuesto}/items/{item.id}/actualizar-precio",
        follow_redirects=False,
    )
    assert response.status_code == 303

    session.refresh(item)
    session.refresh(presupuesto)
    assert (item.estimated_unit_cost, item.real_unit_cost) == (3000, 3100)
    assert (item.subtotal, item.real_subtotal) == (9000, 9300)
    assert (presupuesto.total_cotizado, presupuesto.total_real) == (9000, 9300)
