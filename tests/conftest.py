import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.db import getSession
from app.core.security import hashPassword
from app.main import app
from app.models.apu import APU
from app.models.detalle_apu import DetalleApu
from app.models.material import CategoriaRecurso, Material
from app.models.user import User, UserRole


@pytest.fixture(autouse=True)
def registro_instalacion_temporal(tmp_path, monkeypatch):
    """Los tests nunca escriben en el instalacion.json real del usuario."""
    from app.core import inicializacion

    monkeypatch.setattr(inicializacion, "REGISTRO_INSTALACION", tmp_path / "instalacion.json")


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(db_engine):
    with Session(db_engine) as db:
        yield db


@pytest.fixture
def client(db_engine):
    def override_get_session():
        with Session(db_engine) as db:
            yield db

    app.dependency_overrides[getSession] = override_get_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(getSession, None)


@pytest.fixture
def user(session):
    usuario = User(
        username="testuser",
        email="testuser@example.com",
        hashed_password=hashPassword("TestPassword123"),
        full_name="Usuario de prueba",
        role=UserRole.ADMIN,
        is_active=True,
    )
    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    return usuario


@pytest.fixture
def logged_in_client(client, user):
    response = client.post(
        "/login",
        data={
            "username": user.username,
            "password": "TestPassword123",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


@pytest.fixture
def crear_apu(session):
    """Crea un APU con receta de 1 recurso, para que su CDU sea el indicado.

    crear_apu("A-1", 1000, 1200) -> APU con CDU cotizado 1000 y real 1200.
    Con con_recursos=False el APU queda sin receta (costo 0).
    """
    def crear(
        code="APU-001",
        unit_cost=1000,
        real_unit_cost=None,
        *,
        name=None,
        unit="m3",
        category=None,
        is_active=True,
        con_recursos=True,
    ):
        apu = APU(
            code=code, name=name or f"APU {code}", unit=unit,
            category=category, is_active=is_active,
        )
        session.add(apu)
        session.flush()
        if con_recursos:
            material = Material(
                code=f"REC-{code}", name=f"Recurso {code}", unit=unit,
                category=CategoriaRecurso.MATERIALES, unit_cost=unit_cost,
                real_unit_cost=unit_cost if real_unit_cost is None else real_unit_cost,
            )
            session.add(material)
            session.flush()
            session.add(DetalleApu(id_apu=apu.id, id_material=material.id, unit=unit, cantidad=1))
        session.commit()
        session.refresh(apu)
        return apu

    return crear
