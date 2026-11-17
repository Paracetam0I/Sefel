from decimal import Decimal

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, select, text

from app.core.money import DecimalText


@pytest.fixture
def tabla():
    engine = create_engine("sqlite://")
    metadata = MetaData()
    prueba = Table(
        "prueba", metadata,
        Column("id", Integer, primary_key=True),
        Column("monto", DecimalText()),
    )
    metadata.create_all(engine)
    return engine, prueba


def test_guarda_y_lee_decimal_sin_perder_exactitud(tabla):
    engine, prueba = tabla
    with engine.begin() as conn:
        conn.execute(prueba.insert().values(monto=Decimal("0.1")))
        conn.execute(prueba.insert().values(monto=Decimal("12345678901234567890.12345")))
        valores = [f.monto for f in conn.execute(select(prueba.c.monto).order_by(prueba.c.id))]

    assert valores == [Decimal("0.1"), Decimal("12345678901234567890.12345")]
    assert all(isinstance(v, Decimal) for v in valores)


def test_en_la_base_queda_como_texto(tabla):
    engine, prueba = tabla
    with engine.begin() as conn:
        conn.execute(prueba.insert().values(monto=Decimal("10500.50")))
        tipo, valor = conn.execute(text("SELECT typeof(monto), monto FROM prueba")).one()

    assert tipo == "text"
    assert valor == "10500.50"


def test_acepta_int_y_str(tabla):
    engine, prueba = tabla
    with engine.begin() as conn:
        conn.execute(prueba.insert().values(monto=10500))
        conn.execute(prueba.insert().values(monto="12.5"))
        valores = [f.monto for f in conn.execute(select(prueba.c.monto).order_by(prueba.c.id))]

    assert valores == [Decimal("10500"), Decimal("12.5")]


def test_rechaza_float(tabla):
    engine, prueba = tabla
    with pytest.raises(Exception) as error:
        with engine.begin() as conn:
            conn.execute(prueba.insert().values(monto=1.5))

    assert "float" in str(error.value)


def test_none_se_conserva(tabla):
    engine, prueba = tabla
    with engine.begin() as conn:
        conn.execute(prueba.insert().values(monto=None))
        valor = conn.execute(select(prueba.c.monto)).scalar_one()

    assert valor is None