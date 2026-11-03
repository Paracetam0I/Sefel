
import pytest
from sqlmodel import Session, create_engine

from app.core.routers.apu import _codigoExistente, _validar
from app.models.apu import APU


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    APU.__table__.create(engine)

    with Session(engine) as db:
        yield db

    engine.dispose()


def datos_validos(**cambios):
    datos = {
        "code": "APU-001",
        "name": "Excavación",
        "unit": "m3",
        "category": "",
        "unit_cost": "10000",
        "description": "",
    }
    datos.update(cambios)
    return datos


def test_codigo_obligatorio():
    _, error = _validar(datos_validos(code=" "))
    assert error == "El código es obligatorio y no puede estar vacío."


def test_nombre_obligatorio():
    _, error = _validar(datos_validos(name=" "))
    assert error == "El nombre es obligatorio y no puede estar vacío."


def test_unidad_obligatoria():
    _, error = _validar(datos_validos(unit=" "))
    assert error == "La unidad es obligatoria y no puede estar vacío."


def test_costo_no_negativo():
    _, error = _validar(datos_validos(unit_cost="-1"))
    assert error == "El precio unitario no puede ser negativo."


def test_costo_debe_ser_entero():
    _, error = _validar(datos_validos(unit_cost="abc"))
    assert error == "El precio unitario debe ser un número entero."


@pytest.mark.parametrize(
    ("campo", "valor", "mensaje"),
    [
        ("code", "A" * 51, "El código no puede superar los 50 caracteres."),
        ("name", "A" * 151, "El nombre no puede superar los 150 caracteres."),
        ("unit", "A" * 31, "La unidad no puede superar los 30 caracteres."),
        ("category", "A" * 101, "La categoría no puede superar los 100 caracteres."),
    ],
)
def test_longitud_maxima(campo, valor, mensaje):
    _, error = _validar(datos_validos(**{campo: valor}))
    assert error == mensaje


def test_elimina_espacios_externos():
    datos, error = _validar(
        datos_validos(
            code=" APU-001 ",
            name=" Excavación ",
            unit=" m3 ",
        )
    )

    assert error is None
    assert datos["code"] == "APU-001"
    assert datos["name"] == "Excavación"
    assert datos["unit"] == "m3"


def test_codigo_duplicado_sin_distinguir_mayusculas(session):
    apu = APU(
        code="APU-001",
        name="Excavación",
        unit="m3",
        unit_cost=10000,
    )
    session.add(apu)
    session.commit()

    assert _codigoExistente(session, "apu-001") is True


def test_codigo_no_duplicado(session):
    assert _codigoExistente(session, "APU-002") is False


def test_edicion_no_detecta_su_propio_codigo_como_duplicado(session):
    apu = APU(
        code="APU-001",
        name="Excavación",
        unit="m3",
        unit_cost=10000,
    )
    session.add(apu)
    session.commit()

    assert _codigoExistente(
        session,
        "apu-001",
        excluir_id=apu.id,
    ) is False
