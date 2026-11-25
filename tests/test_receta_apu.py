"""APU como receta: recursos de la Base de datos con su cantidad, y cálculo del CDU."""
from types import SimpleNamespace

import pytest
from sqlmodel import select

from app.core.calculos import costoParcial, costosApu, costosDeApus, resumirReceta
from app.models.apu import APU
from app.models.detalle_apu import DetalleApu
from app.models.material import CategoriaRecurso, Material
from app.models.user import UserRole

HTMX = {"HX-Request": "true"}


@pytest.fixture
def apu(session):
    a = APU(code="OG-001", name="Hormigón H25", unit="m3", category="Obra gruesa")
    session.add(a)
    session.commit()
    session.refresh(a)
    return a


@pytest.fixture
def recursos(session):
    """Hormigón (material), jornal (mano de obra), betonera (equipo), y uno inactivo."""
    datos = [
        ("MAT-HOR", "Hormigón premezclado", "m3", CategoriaRecurso.MATERIALES, 78_000, 81_000, True),
        ("MO-JOR", "Jornal", "HH", CategoriaRecurso.MANO_DE_OBRA, 5_500, 5_700, True),
        ("EQ-BET", "Betonera", "día", CategoriaRecurso.EQUIPOS, 18_000, 18_000, True),
        ("MAT-VIE", "Material discontinuado", "un", CategoriaRecurso.MATERIALES, 100, 100, False),
    ]
    creados = {}
    for code, name, unit, categoria, costo, real, activo in datos:
        m = Material(code=code, name=name, unit=unit, category=categoria,
                     unit_cost=costo, real_unit_cost=real, is_active=activo)
        session.add(m)
        creados[code] = m
    session.commit()
    for m in creados.values():
        session.refresh(m)
    return creados


def agregar(client, apu, material, cantidad, unit="", headers=HTMX):
    return client.post(
        f"/apu/{apu.id}/recursos",
        data={"id_material": str(material.id), "cantidad": cantidad, "unit": unit},
        headers=headers,
    )


# Cálculo puro
# ==========================================

def test_costo_parcial_redondea_al_peso_sin_error_de_float():
    assert costoParcial(1.05, 78_000) == 81_900
    assert costoParcial(0.35, 5_500) == 1_925
    assert costoParcial(0.1, 5) == 1            # 0,5 -> 1 (mitad hacia arriba)
    assert costoParcial(2, 0) == 0


def test_resumir_receta_suma_parciales_y_agrupa_por_las_cuatro_categorias():
    def linea(cantidad, costo, real, categoria):
        return (SimpleNamespace(cantidad=cantidad),
                SimpleNamespace(unit_cost=costo, real_unit_cost=real, category=categoria))

    resumen = resumirReceta([
        linea(1.05, 78_000, 81_000, CategoriaRecurso.MATERIALES),
        linea(1.5, 5_500, 5_700, CategoriaRecurso.MANO_DE_OBRA),
        linea(0.5, 8_500, 8_900, CategoriaRecurso.MANO_DE_OBRA),
    ])

    assert resumen["unit_cost"] == 81_900 + 8_250 + 4_250
    assert resumen["real_unit_cost"] == 85_050 + 8_550 + 4_450
    por_categoria = {g["categoria"]: g for g in resumen["categorias"]}
    assert list(por_categoria) == ["Materiales", "Mano de obra", "Equipos", "Herramientas"]
    assert por_categoria["Mano de obra"]["cotizado"] == 12_500
    assert por_categoria["Mano de obra"]["cantidad_recursos"] == 2
    assert por_categoria["Equipos"]["cotizado"] == 0
    # El desglose cuadra con el total
    assert sum(g["cotizado"] for g in resumen["categorias"]) == resumen["unit_cost"]


def test_apu_sin_recursos_cuesta_cero(session, apu):
    assert costosApu(session, apu)["unit_cost"] == 0
    assert costosDeApus(session, [apu.id]) == {}


# Armar la receta
# ==========================================

def test_agregar_recursos_calcula_el_cdu(logged_in_client, session, apu, recursos):
    agregar(logged_in_client, apu, recursos["MAT-HOR"], "1,05")       # coma decimal
    respuesta = agregar(logged_in_client, apu, recursos["MO-JOR"], "1.5")

    assert respuesta.status_code == 200
    assert "$ 90.150" in respuesta.text                  # 81.900 + 8.250
    lineas = session.exec(select(DetalleApu).order_by(DetalleApu.id)).all()
    assert [(l.cantidad, l.unit) for l in lineas] == [(1.05, "m3"), (1.5, "HH")]   # unidad del recurso

    session.refresh(apu)
    costos = costosApu(session, apu)
    assert (costos["unit_cost"], costos["real_unit_cost"]) == (90_150, 85_050 + 8_550)
    assert apu.updated_at is not None


def test_el_cdu_sigue_al_precio_del_recurso(logged_in_client, session, apu, recursos):
    agregar(logged_in_client, apu, recursos["MO-JOR"], "2")

    material = recursos["MO-JOR"]
    material.unit_cost = 6_000
    session.add(material)
    session.commit()

    assert costosApu(session, apu)["unit_cost"] == 12_000


@pytest.mark.parametrize(("cantidad", "mensaje"), [
    ("0", "mayor que 0"), ("-1", "mayor que 0"), ("abc", "mayor que 0"), ("", "mayor que 0"),
])
def test_rechaza_cantidades_invalidas(logged_in_client, session, apu, recursos, cantidad, mensaje):
    respuesta = agregar(logged_in_client, apu, recursos["MAT-HOR"], cantidad)

    assert mensaje in respuesta.text
    assert session.exec(select(DetalleApu)).first() is None


def test_rechaza_recurso_inactivo(logged_in_client, session, apu, recursos):
    respuesta = agregar(logged_in_client, apu, recursos["MAT-VIE"], "1")

    assert "inactivo" in respuesta.text
    assert session.exec(select(DetalleApu)).first() is None


def test_un_recurso_aparece_una_vez_por_apu(logged_in_client, session, apu, recursos):
    agregar(logged_in_client, apu, recursos["MO-JOR"], "1")
    respuesta = agregar(logged_in_client, apu, recursos["MO-JOR"], "2")

    assert "ya está en la receta" in respuesta.text
    assert len(session.exec(select(DetalleApu)).all()) == 1


def test_buscar_ofrece_solo_activos_que_no_estan_en_la_receta(logged_in_client, apu, recursos):
    agregar(logged_in_client, apu, recursos["MO-JOR"], "1")

    html = logged_in_client.get(f"/apu/{apu.id}/recursos/buscar").text

    assert "MAT-HOR" in html and "EQ-BET" in html
    assert "MO-JOR" not in html                           # ya está en la receta
    assert "MAT-VIE" not in html                          # inactivo


def test_seleccionar_recurso_inactivo_responde_404(logged_in_client, apu, recursos):
    respuesta = logged_in_client.get(f"/apu/{apu.id}/recursos/seleccionar/{recursos['MAT-VIE'].id}")
    assert respuesta.status_code == 404


def test_editar_y_quitar_una_linea(logged_in_client, session, apu, recursos):
    agregar(logged_in_client, apu, recursos["MO-JOR"], "1")
    linea = session.exec(select(DetalleApu)).one()

    logged_in_client.post(
        f"/apu/{apu.id}/recursos/{linea.id}", data={"cantidad": "3", "unit": "HH"}, headers=HTMX,
    )
    session.refresh(linea)
    assert linea.cantidad == 3
    assert costosApu(session, apu)["unit_cost"] == 16_500

    logged_in_client.post(f"/apu/{apu.id}/recursos/{linea.id}/eliminar", headers=HTMX)
    session.expire_all()
    assert session.exec(select(DetalleApu)).first() is None
    assert session.get(Material, recursos["MO-JOR"].id) is not None    # el recurso no se borra


def test_no_se_edita_una_linea_de_otro_apu(logged_in_client, session, apu, recursos):
    otro = APU(code="OTRO", name="Otro", unit="m2")
    session.add(otro)
    session.commit()
    agregar(logged_in_client, apu, recursos["MO-JOR"], "1")
    linea = session.exec(select(DetalleApu)).one()

    respuesta = logged_in_client.post(
        f"/apu/{otro.id}/recursos/{linea.id}", data={"cantidad": "9", "unit": "HH"}, headers=HTMX,
    )

    assert "ya no está en la receta" in respuesta.text
    session.refresh(linea)
    assert linea.cantidad == 1


def test_borrar_el_apu_borra_su_receta(session, apu, recursos):
    session.add(DetalleApu(id_apu=apu.id, id_material=recursos["MO-JOR"].id, unit="HH", cantidad=1))
    session.commit()

    session.delete(apu)
    session.commit()

    assert session.exec(select(DetalleApu)).first() is None
    assert session.exec(select(Material)).all()                       # los recursos siguen


# Pantallas
# ==========================================

def test_pagina_de_la_receta_muestra_subtotales_por_categoria(logged_in_client, apu, recursos):
    agregar(logged_in_client, apu, recursos["MAT-HOR"], "1.05")
    agregar(logged_in_client, apu, recursos["MO-JOR"], "1.5")

    html = logged_in_client.get(f"/apu/{apu.id}").text

    for texto in ("Materiales", "Mano de obra", "Equipos", "Herramientas",
                  "$ 81.900", "$ 8.250", "Costo directo unitario (CDU)", "$ 90.150"):
        assert texto in html


def test_listado_de_apu_muestra_el_cdu_calculado(logged_in_client, apu, recursos):
    agregar(logged_in_client, apu, recursos["MO-JOR"], "2")

    html = logged_in_client.get("/apu").text

    assert "CDU cotizado" in html and "$ 11.000" in html and "$ 11.400" in html
    assert f'href="/apu/{apu.id}"' in html


def test_viewer_no_puede_ver_ni_editar_recetas(logged_in_client, session, user, apu, recursos):
    user.role = UserRole.VIEWER
    session.add(user)
    session.commit()

    assert logged_in_client.get(f"/apu/{apu.id}").status_code == 403
    assert agregar(logged_in_client, apu, recursos["MO-JOR"], "1", headers={}).status_code == 403
