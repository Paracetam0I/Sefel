"""Pestaña "Base de datos": recursos con categorías fijas y precio unitario."""
import pytest
from sqlmodel import select

from app.core.routers.materiales import _validar
from app.models.material import CATEGORIAS_RECURSO, CategoriaRecurso, Material
from app.models.user import UserRole

HTMX = {"HX-Request": "true"}


def datosRecurso(**cambios):
    datos = {
        "code": "mat-001", "name": "Cemento saco 25 kg", "unit": "saco",
        "category": "Materiales", "unit_cost": "5200", "real_unit_cost": "",
        "description": "",
    }
    datos.update(cambios)
    return datos


def nuevoRecurso(session, code="MAT-001", **campos):
    material = Material(
        code=code, name=campos.pop("name", "Cemento"), unit=campos.pop("unit", "saco"),
        category=campos.pop("category", CategoriaRecurso.MATERIALES),
        unit_cost=campos.pop("unit_cost", 5200), real_unit_cost=campos.pop("real_unit_cost", 5200),
        **campos,
    )
    session.add(material)
    session.commit()
    session.refresh(material)
    return material


# Categorías fijas
# ==========================================

def test_las_categorias_son_fijas_y_las_del_informe():
    assert CATEGORIAS_RECURSO == ["Materiales", "Mano de obra", "Equipos", "Herramientas"]


@pytest.mark.parametrize("categoria", ["", "Obra gruesa", "materiales"])
def test_rechaza_categorias_fuera_de_la_lista(categoria):
    _, error = _validar(datosRecurso(category=categoria))
    assert error.startswith("Selecciona una categoría")


def test_el_formulario_ofrece_solo_las_categorias_fijas(logged_in_client):
    html = logged_in_client.get("/base-datos/nuevo", headers=HTMX).text
    for categoria in CATEGORIAS_RECURSO:
        assert f'<option value="{categoria}"' in html
    assert html.count("<option value=") == len(CATEGORIAS_RECURSO) + 1   # + "Selecciona"


# CRUD
# ==========================================

def test_crear_recurso(logged_in_client, session):
    response = logged_in_client.post("/base-datos", data=datosRecurso(), follow_redirects=False)

    assert response.status_code == 303
    material = session.exec(select(Material)).one()
    assert material.code == "MAT-001"                  # código en mayúsculas
    assert material.category == CategoriaRecurso.MATERIALES
    assert (material.unit_cost, material.real_unit_cost) == (5200, 5200)
    assert material.is_active


def test_crear_recurso_por_htmx_refresca_el_listado(logged_in_client, session):
    response = logged_in_client.post("/base-datos", data=datosRecurso(), headers=HTMX)

    assert response.headers["HX-Retarget"] == "#contenido-base-datos"
    assert response.headers["HX-Trigger-After-Settle"] == "cerrar-modal-material"
    assert "fila-nueva" in response.text and "MAT-001" in response.text


def test_rechaza_codigo_duplicado(logged_in_client, session):
    nuevoRecurso(session)

    response = logged_in_client.post("/base-datos", data=datosRecurso(code="mat-001"))

    assert response.status_code == 400
    assert "Ya existe un recurso con ese código" in response.text


@pytest.mark.parametrize(("campo", "valor", "mensaje"), [
    ("unit_cost", "-1", "El precio unitario no puede ser negativo."),
    ("unit_cost", "abc", "El precio unitario debe ser un número entero."),
    ("name", " ", "El nombre es obligatorio y no puede estar vacío."),
    ("unit", "A" * 31, "La unidad no puede superar los 30 caracteres."),
])
def test_validaciones(campo, valor, mensaje):
    _, error = _validar(datosRecurso(**{campo: valor}))
    assert error == mensaje


def test_editar_recurso_cambia_su_precio(logged_in_client, session):
    material = nuevoRecurso(session)

    response = logged_in_client.post(
        f"/base-datos/{material.id}",
        data=datosRecurso(code="MAT-001", category="Mano de obra", unit_cost="6000", real_unit_cost="6100"),
        follow_redirects=False,
    )

    assert response.status_code == 303
    session.refresh(material)
    assert material.category == CategoriaRecurso.MANO_DE_OBRA
    assert (material.unit_cost, material.real_unit_cost) == (6000, 6100)
    assert material.updated_at is not None


def test_desactivar_en_lugar_de_eliminar(logged_in_client, session):
    material = nuevoRecurso(session)

    logged_in_client.post(f"/base-datos/{material.id}/estado", data={})
    session.refresh(material)
    assert material.is_active is False

    logged_in_client.post(f"/base-datos/{material.id}/estado", data={})
    session.refresh(material)
    assert material.is_active is True


def test_filtra_por_categoria(logged_in_client, session):
    nuevoRecurso(session, "MAT-001", name="Cemento")
    nuevoRecurso(session, "MO-001", name="Jornal", unit="HH", category=CategoriaRecurso.MANO_DE_OBRA)

    html = logged_in_client.get("/base-datos?categoria=Mano de obra", headers=HTMX).text

    assert "Jornal" in html and "Cemento" not in html


def test_listado_indica_en_cuantos_apu_se_usa(logged_in_client, session, crear_apu):
    crear_apu("APU-1", 1000)                            # crea REC-APU-1 y lo usa en 1 APU

    html = logged_in_client.get("/base-datos").text

    assert "REC-APU-1" in html and "1 APU" in html


# Permisos
# ==========================================

@pytest.mark.parametrize("rol", [UserRole.BUDGETS, UserRole.VIEWER])
def test_roles_sin_permiso_reciben_403(logged_in_client, session, user, rol):
    user.role = rol
    session.add(user)
    session.commit()

    assert logged_in_client.get("/base-datos").status_code == 403
    assert logged_in_client.post("/base-datos", data=datosRecurso()).status_code == 403


def test_materials_ve_la_pestana_en_el_menu(logged_in_client, session, user):
    user.role = UserRole.MATERIALS
    session.add(user)
    session.commit()

    html = logged_in_client.get("/dashboard").text
    assert 'href="/base-datos"' in html

