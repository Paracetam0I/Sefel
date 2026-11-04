import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.db import getSession
from app.core.security import hashPassword
from app.main import app
from app.models.apu import APU
from app.models.user import User, UserRole


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
