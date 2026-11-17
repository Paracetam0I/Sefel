"""Permisos por rol, bloqueo por intentos fallidos, inactividad y dashboard."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import select

import app.core.dependencies as dependencias
from app.core.bloqueo import MENSAJE_DESACTIVADA, MAX_INTENTOS
from app.core.config import INACTIVIDAD_MAXIMA_SEGUNDOS
from app.core.security import hashPassword
from app.models.apu import APU
from app.models.auditoria import AccionAuditoria, AuditoriaCuenta
from app.models.presupuesto import Presupuesto
from app.models.user import User, UserRole

CLAVE = "Clave12345"


def crearUsuario(session, username, role, is_active=True):
    usuario = User(
        username=username, email=f"{username}@example.com",
        hashed_password=hashPassword(CLAVE), full_name=username.title(),
        role=role, is_active=is_active,
    )
    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    return usuario


def login(client, username, password=CLAVE):
    return client.post(
        "/login", data={"username": username, "password": password},
        follow_redirects=False,
    )


def loginComo(client, session, role):
    usuario = crearUsuario(session, f"u_{role.value.lower()}", role)
    assert login(client, usuario.username).status_code == 303
    return usuario


@pytest.fixture
def presupuesto(session):
    duenio = crearUsuario(session, "duenio", UserRole.BUDGETS)
    p = Presupuesto(
        id_usuario=duenio.id, code="PRE-001", client_name="Cliente Uno",
        estimate_income=1000, start_date=datetime(2026, 11, 1),
        end_date=datetime(2026, 12, 31), description="Obra de prueba",
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


# Módulo Proyectos eliminado
# ==========================================

def test_proyectos_ya_no_existe(client, session):
    loginComo(client, session, UserRole.ADMIN)
    assert client.get("/proyectos").status_code == 404
    assert "Proyectos" not in client.get("/dashboard").text


# Permisos por rol
# ==========================================

PERMITIDO, PROHIBIDO = 200, 403

MATRIZ_LECTURA = {
    #                   /admin/users  /apu       /presupuestos /dashboard
    UserRole.ADMIN:     (PERMITIDO,   PERMITIDO, PERMITIDO,    PERMITIDO),
    UserRole.MATERIALS: (PROHIBIDO,   PERMITIDO, PROHIBIDO,    PERMITIDO),
    UserRole.BUDGETS:   (PROHIBIDO,   PROHIBIDO, PERMITIDO,    PERMITIDO),
    UserRole.BOTH:      (PROHIBIDO,   PERMITIDO, PERMITIDO,    PERMITIDO),
    UserRole.VIEWER:    (PROHIBIDO,   PROHIBIDO, PERMITIDO,    PERMITIDO),
}


@pytest.mark.parametrize("rol", list(MATRIZ_LECTURA))
def test_matriz_de_acceso_por_modulo(client, session, rol):
    loginComo(client, session, rol)
    rutas = ("/admin/users", "/apu", "/presupuestos", "/dashboard")
    obtenido = tuple(client.get(r).status_code for r in rutas)
    assert obtenido == MATRIZ_LECTURA[rol]


@pytest.mark.parametrize("rol", [UserRole.BUDGETS, UserRole.VIEWER])
def test_403_de_apu_tiene_el_mismo_formato_que_admin(client, session, rol):
    loginComo(client, session, rol)

    pagina_apu = client.get("/apu")
    pagina_admin = client.get("/admin/users")
    assert pagina_apu.status_code == pagina_admin.status_code == 403
    assert pagina_apu.text == pagina_admin.text                  # misma página 403

    htmx = {"HX-Request": "true"}
    assert client.get("/apu", headers=htmx).json() == {"detail": "Sin permiso"}
    assert client.get("/admin/users", headers=htmx).json() == {"detail": "Sin permiso"}


def test_materials_no_entra_a_presupuestos_ni_por_htmx(client, session, presupuesto):
    loginComo(client, session, UserRole.MATERIALS)
    respuesta = client.get("/presupuestos", headers={"HX-Request": "true"})
    assert respuesta.status_code == 403
    assert respuesta.json() == {"detail": "Sin permiso"}
    assert client.get(f"/presupuestos/{presupuesto.id_presupuesto}/pdf").status_code == 403


def test_viewer_solo_lectura_en_presupuestos(client, session, presupuesto):
    loginComo(client, session, UserRole.VIEWER)
    pid = presupuesto.id_presupuesto

    # Puede ver y exportar
    listado = client.get("/presupuestos")
    assert listado.status_code == 200
    assert "Nuevo presupuesto" not in listado.text
    assert f"/presupuestos/{pid}/editar" not in listado.text
    assert client.get(f"/presupuestos/{pid}/porcentajes").status_code == 200
    assert client.get("/presupuestos/exportar").status_code == 200
    assert client.get(f"/presupuestos/{pid}/pdf").status_code == 200

    # No puede crear, editar, cambiar estado ni tocar ítems (backend)
    datos = {
        "code": "PRE-X", "client_name": "C", "estimate_income": "1",
        "description": "d", "status": "DRAFT",
    }
    assert client.get("/presupuestos/nuevo").status_code == 403
    assert client.post("/presupuestos", data=datos).status_code == 403
    assert client.get(f"/presupuestos/{pid}/editar").status_code == 403
    assert client.post(f"/presupuestos/{pid}", data=datos).status_code == 403
    assert client.post(f"/presupuestos/{pid}/estado", data={"nuevo_estado": "ACTIVE"}).status_code == 403
    assert client.post(f"/presupuestos/{pid}/porcentajes", data={}).status_code == 403
    assert client.get(f"/presupuestos/{pid}/items/nuevo").status_code == 403

    session.refresh(presupuesto)
    assert presupuesto.status.value == "DRAFT"
    assert session.exec(select(Presupuesto).where(Presupuesto.code == "PRE-X")).first() is None


def test_budgets_edita_presupuestos_de_otros(client, session, presupuesto):
    loginComo(client, session, UserRole.BUDGETS)   # no es quien lo creó
    respuesta = client.post(
        f"/presupuestos/{presupuesto.id_presupuesto}",
        data={"code": "PRE-001", "client_name": "Cliente Editado", "estimate_income": "5",
              "start_date": "2026-11-01", "end_date": "2026-12-31",
              "description": "Obra", "status": "ACTIVE"},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    session.refresh(presupuesto)
    assert presupuesto.client_name == "Cliente Editado"


def test_codigo_de_presupuesto_unico_en_todo_el_sistema(client, session, presupuesto):
    loginComo(client, session, UserRole.BUDGETS)
    respuesta = client.post(
        "/presupuestos",
        data={"code": "pre-001", "client_name": "Otro", "estimate_income": "1",
              "start_date": "2026-11-01", "end_date": "2026-12-31",
              "description": "d", "status": "DRAFT"},
        headers={"HX-Request": "true"},   # el formulario real se envía por HTMX
    )
    assert "Ya existe un presupuesto con ese código" in respuesta.text


def test_sidebar_muestra_solo_modulos_permitidos(client, session):
    loginComo(client, session, UserRole.VIEWER)
    html = client.get("/dashboard").text
    assert 'href="/presupuestos"' in html
    assert 'href="/apu"' not in html
    assert 'href="/admin/users"' not in html


# Dashboard
# ==========================================

def test_dashboard_admin_ve_datos_reales_de_todos_los_modulos(client, session, presupuesto):
    loginComo(client, session, UserRole.ADMIN)
    session.add(APU(code="A-1", name="Excavación manual", unit="m3", unit_cost=1000, real_unit_cost=1100))
    session.commit()

    html = client.get("/dashboard").text
    assert "Últimos presupuestos" in html and "PRE-001" in html
    assert "Excavación manual" in html
    assert "Cuentas bloqueadas" in html and "Actividad de seguridad" in html


def test_dashboard_viewer_no_ve_usuarios_ni_apu(client, session, presupuesto):
    loginComo(client, session, UserRole.VIEWER)
    html = client.get("/dashboard").text
    assert "PRE-001" in html
    assert "Usuarios" not in html and "Cuentas bloqueadas" not in html
    assert "APU actualizados" not in html


# Bloqueo por intentos fallidos
# ==========================================

def fallar(client, username, veces):
    respuesta = None
    for _ in range(veces):
        respuesta = login(client, username, "incorrecta")
    return respuesta


def test_usuario_se_desactiva_al_quinto_intento(client, session):
    usuario = crearUsuario(session, "pepe", UserRole.BUDGETS)

    cuarto = fallar(client, "pepe", MAX_INTENTOS - 1)
    assert cuarto.status_code == 401
    assert "Te queda 1 intento" in cuarto.text

    quinto = fallar(client, "pepe", 1)
    assert quinto.status_code == 403
    assert MENSAJE_DESACTIVADA in quinto.text

    session.refresh(usuario)
    assert usuario.is_active is False
    assert usuario.lock_reason and usuario.locked_at is not None

    # Ni con la clave correcta entra; el mensaje se mantiene
    correcto = login(client, "pepe")
    assert correcto.status_code == 403
    assert MENSAJE_DESACTIVADA in correcto.text

    auditoria = session.exec(select(AuditoriaCuenta)).all()
    assert [(a.id_usuario, a.accion, a.id_actor) for a in auditoria] == [
        (usuario.id, AccionAuditoria.BLOQUEO, None)
    ]


def test_login_correcto_reinicia_el_contador(client, session):
    usuario = crearUsuario(session, "ana", UserRole.VIEWER)
    fallar(client, "ana", MAX_INTENTOS - 1)
    assert login(client, "ana").status_code == 303

    session.refresh(usuario)
    assert usuario.failed_attempts == 0
    assert usuario.is_active is True


def test_admin_se_desactiva_si_hay_otro_admin_activo(client, session):
    crearUsuario(session, "admin1", UserRole.ADMIN)
    admin2 = crearUsuario(session, "admin2", UserRole.ADMIN)

    respuesta = fallar(client, "admin2", MAX_INTENTOS)
    assert respuesta.status_code == 403
    assert MENSAJE_DESACTIVADA in respuesta.text
    session.refresh(admin2)
    assert admin2.is_active is False


def test_unico_admin_activo_no_se_desactiva(client, session):
    crearUsuario(session, "otro_admin", UserRole.ADMIN, is_active=False)  # inactivo: no cuenta
    unico = crearUsuario(session, "unico", UserRole.ADMIN)

    respuesta = fallar(client, "unico", MAX_INTENTOS)
    assert respuesta.status_code == 429
    assert "bloqueada temporalmente" in respuesta.text

    session.refresh(unico)
    assert unico.is_active is True                  # sigue usable
    assert unico.failed_attempts == 0               # contador reiniciado
    assert unico.locked_until is not None

    # Durante el bloqueo temporal ni la clave correcta entra
    assert login(client, "unico").status_code == 429

    # Vencido el bloqueo, entra normalmente
    unico.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    session.add(unico)
    session.commit()
    assert login(client, "unico").status_code == 303

    acciones = [a.accion for a in session.exec(select(AuditoriaCuenta)).all()]
    assert acciones == [AccionAuditoria.BLOQUEO_TEMPORAL]


def test_dos_admins_fallando_nunca_quedan_ambos_desactivados(client, session):
    a = crearUsuario(session, "admin_a", UserRole.ADMIN)
    b = crearUsuario(session, "admin_b", UserRole.ADMIN)

    fallar(client, "admin_a", MAX_INTENTOS)   # hay otro activo: se desactiva
    fallar(client, "admin_b", MAX_INTENTOS)   # ahora es el único: no se desactiva

    session.refresh(a)
    session.refresh(b)
    assert (a.is_active, b.is_active) == (False, True)
    assert b.locked_until is not None


def test_reactivar_desde_admin_resetea_bloqueo_y_audita(client, session):
    admin = loginComo(client, session, UserRole.ADMIN)
    bloqueado = crearUsuario(session, "bloq", UserRole.BUDGETS, is_active=False)
    bloqueado.failed_attempts = MAX_INTENTOS
    bloqueado.lock_reason = "5 intentos fallidos"
    bloqueado.locked_at = datetime.now(timezone.utc)
    session.add(bloqueado)
    session.commit()

    respuesta = client.post(f"/admin/users/{bloqueado.id}/estado", follow_redirects=False)
    assert respuesta.status_code == 303

    session.refresh(bloqueado)
    assert bloqueado.is_active is True
    assert bloqueado.failed_attempts == 0
    assert bloqueado.lock_reason is None and bloqueado.locked_at is None

    evento = session.exec(select(AuditoriaCuenta)).one()
    assert (evento.accion, evento.id_usuario, evento.id_actor) == (
        AccionAuditoria.REACTIVACION, bloqueado.id, admin.id,
    )
    assert "5 intentos fallidos" in evento.motivo


# Inactividad
# ==========================================

@pytest.fixture
def reloj(monkeypatch):
    """Permite adelantar la hora que usa el control de inactividad."""
    estado = {"ahora": 1_000_000.0}
    monkeypatch.setattr(dependencias, "marcaDeTiempo", lambda: estado["ahora"])
    return estado


def test_sesion_activa_se_renueva_con_cada_peticion(client, session, reloj):
    loginComo(client, session, UserRole.VIEWER)
    for _ in range(3):   # 3 × 20 min = 60 min, pero nunca 30 seguidos sin actividad
        reloj["ahora"] += 20 * 60
        assert client.get("/dashboard", follow_redirects=False).status_code == 200


def test_sesion_se_cierra_tras_30_min_de_inactividad(client, session, reloj):
    loginComo(client, session, UserRole.VIEWER)
    reloj["ahora"] += INACTIVIDAD_MAXIMA_SEGUNDOS + 1

    respuesta = client.get("/dashboard", follow_redirects=False)
    assert respuesta.status_code == 303
    assert respuesta.headers["location"].startswith("/login?motivo=inactividad")

    # La sesión quedó invalidada en el backend: volver atrás no la revive
    reloj["ahora"] -= INACTIVIDAD_MAXIMA_SEGUNDOS
    otra = client.get("/dashboard", follow_redirects=False)
    assert otra.status_code == 303
    assert otra.headers["location"].startswith("/login")

    pagina = client.get("/login?motivo=inactividad")
    assert "Tu sesión se ha cerrado por inactividad." in pagina.text


def test_inactividad_en_htmx_y_api(client, session, reloj):
    loginComo(client, session, UserRole.VIEWER)
    reloj["ahora"] += INACTIVIDAD_MAXIMA_SEGUNDOS + 1

    latido = client.post("/api/sesion/actividad")
    assert latido.status_code == 401
    assert latido.json() == {"detail": "Tu sesión se ha cerrado por inactividad."}


def test_htmx_redirige_al_login_con_motivo(client, session, reloj):
    loginComo(client, session, UserRole.VIEWER)
    reloj["ahora"] += INACTIVIDAD_MAXIMA_SEGUNDOS + 1
    respuesta = client.get("/presupuestos", headers={"HX-Request": "true"})
    assert respuesta.status_code == 401
    assert respuesta.headers["HX-Redirect"] == "/login?motivo=inactividad"


def test_latido_de_actividad_renueva_la_sesion(client, session, reloj):
    loginComo(client, session, UserRole.VIEWER)
    reloj["ahora"] += 25 * 60
    assert client.post("/api/sesion/actividad").status_code == 204
    reloj["ahora"] += 25 * 60
    assert client.get("/dashboard", follow_redirects=False).status_code == 200


def test_logout_por_inactividad_lleva_al_aviso(client, session):
    loginComo(client, session, UserRole.VIEWER)
    respuesta = client.post("/logout?motivo=inactividad", follow_redirects=False)
    assert respuesta.headers["location"] == "/login?motivo=inactividad"
    assert client.get("/dashboard", follow_redirects=False).status_code == 303
