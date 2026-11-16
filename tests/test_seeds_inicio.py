"""Seeds de APU/presupuestos y script de inicio (scripts/iniciar.py)."""
import pytest
from sqlalchemy import inspect
from sqlmodel import Session, SQLModel, create_engine, select

import app.core.db as db
from app.models.apu import APU
from app.models.detalle_presupuesto import DetallePresupuesto
from app.models.presupuesto import Presupuesto
from app.models.user import User, UserRole
from scripts import iniciar, seed_admin
from scripts.seed_apus import SEED_APUS, sembrarApus
from scripts.seed_presupuestos import SEED_PRESUPUESTOS, sembrarPresupuestos


# Seeds
# ==========================================

def test_seed_apus_crea_el_catalogo_y_es_idempotente(session):
    assert sembrarApus(session) == len(SEED_APUS)
    session.commit()
    assert sembrarApus(session) == 0

    apus = session.exec(select(APU)).all()
    assert len(apus) == len(SEED_APUS)
    assert any(not a.is_active for a in apus)            # incluye un APU inactivo
    assert all(a.real_unit_cost >= 0 for a in apus)


def test_seed_presupuestos_requiere_usuarios(session):
    with pytest.raises(RuntimeError, match="seed_admin"):
        sembrarPresupuestos(session)


def test_seed_presupuestos_calcula_totales_y_es_idempotente(session, user):
    assert sembrarPresupuestos(session) == len(SEED_PRESUPUESTOS)
    session.commit()
    assert sembrarPresupuestos(session) == 0

    presupuestos = session.exec(select(Presupuesto)).all()
    assert {p.code for p in presupuestos} == {s.code for s in SEED_PRESUPUESTOS}

    for p in presupuestos:
        detalles = session.exec(
            select(DetallePresupuesto).where(DetallePresupuesto.id_presupuesto == p.id_presupuesto)
        ).all()
        assert p.total_real == sum(d.real_subtotal for d in detalles) > 0
        assert p.total_cotizado == sum(d.subtotal for d in detalles)
        assert p.monto_total == p.neto + p.monto_iva
        assert p.id_usuario == user.id                   # sin 'presupuestos', usa el ADMIN


# Script de inicio
# ==========================================

@pytest.fixture
def bd_temporal(tmp_path, monkeypatch):
    """Apunta el script (y el env.py de Alembic) a una BD SQLite nueva."""
    ruta = tmp_path / "sefel.db"
    motor = create_engine(f"sqlite:///{ruta}")
    monkeypatch.setattr(db, "engine", motor)
    monkeypatch.setattr(iniciar, "engine", motor)
    monkeypatch.setattr(iniciar, "DATABASE_PATH", ruta)
    yield motor
    motor.dispose()


def test_prepara_una_bd_nueva_y_luego_la_reconoce_al_dia(bd_temporal):
    resultado = iniciar.prepararBaseDatos()
    assert "tablas creadas" in resultado
    assert iniciar.verificarTablas() == []

    tablas = set(inspect(bd_temporal).get_table_names())
    assert {"user", "apu", "presupuesto", "detalle_presupuesto", "auditoria_cuentas", "alembic_version"} <= tablas

    assert iniciar.prepararBaseDatos().startswith("al día")


def test_bd_sin_alembic_solo_crea_tablas_faltantes(bd_temporal):
    User.__table__.create(bd_temporal)                  # BD creada a mano, incompleta
    resultado = iniciar.prepararBaseDatos()
    assert "sin control de Alembic" in resultado
    assert iniciar.verificarTablas() == []


def test_crea_usuarios_de_seed_si_no_hay_admin(bd_temporal):
    SQLModel.metadata.create_all(bd_temporal)
    with Session(bd_temporal) as s:
        s.add(User(username="solo_viewer", email="v@x.cl", hashed_password="x",
                   full_name="V", role=UserRole.VIEWER))
        s.commit()

    resultado = iniciar.asegurarAdmin()
    assert "creados los usuarios de seed" in resultado

    with Session(bd_temporal) as s:
        nombres = set(s.exec(select(User.username)).all())
    assert {u.username for u in seed_admin.SEED_USERS} <= nombres


def test_no_crea_usuarios_si_ya_hay_admin_activo(bd_temporal):
    SQLModel.metadata.create_all(bd_temporal)
    with Session(bd_temporal) as s:
        s.add(User(username="jefa", email="j@x.cl", hashed_password="x",
                   full_name="Jefa", role=UserRole.ADMIN))
        s.commit()

    assert "existe el administrador 'jefa'" in iniciar.asegurarAdmin()
    with Session(bd_temporal) as s:
        assert len(s.exec(select(User)).all()) == 1


def test_avisa_si_el_admin_del_seed_esta_desactivado(bd_temporal):
    SQLModel.metadata.create_all(bd_temporal)
    with Session(bd_temporal) as s:
        s.add(User(username="admin", email="admin@example.com", hashed_password="x",
                   full_name="Admin", role=UserRole.ADMIN, is_active=False))
        s.commit()

    assert iniciar.asegurarAdmin().startswith("ATENCIÓN")
