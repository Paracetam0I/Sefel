"""Base de datos faltante o con errores (al iniciar y en ejecución), WAL y modo red."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError

import client
from app.core import inicializacion
from app.core.db import getSession
from app.core.errores_bd import describirErrorBD, mensajeErrorBD
from app.main import app
from scripts import iniciar
from tests.test_seeds_inicio import bd_temporal  # noqa: F401  (fixture de BD temporal)

RAIZ = Path(__file__).resolve().parents[1]


def correrConBD(ruta: Path, codigo: str) -> subprocess.CompletedProcess:
    """Ejecuta Python con SEFEL_DB_PATH apuntando a `ruta` (motor real de la app)."""
    entorno = {**os.environ, "SEFEL_DB_PATH": str(ruta), "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, env=entorno,
                          capture_output=True, text=True, timeout=60)


def errorSqlite(mensaje: str) -> OperationalError:
    return OperationalError("SELECT 1", {}, sqlite3.OperationalError(mensaje))


# Motor de la app
# ==========================================

def test_el_motor_no_crea_una_base_vacia_si_falta(tmp_path):
    ruta = tmp_path / "carpeta con espacios" / "sefel.db"
    resultado = correrConBD(ruta, (
        "from sqlalchemy import text\nfrom app.core.db import engine\n"
        "try:\n    engine.connect().execute(text('select 1'))\n    print('CONECTO')\n"
        "except Exception as e:\n    print('FALLA', type(e).__name__)\n"
    ))
    assert "FALLA OperationalError" in resultado.stdout, resultado.stderr
    assert not ruta.exists()


def test_el_motor_usa_wal_y_espera_bloqueos(tmp_path):
    ruta = tmp_path / "sefel.db"
    sqlite3.connect(ruta).close()
    resultado = correrConBD(ruta, (
        "from sqlalchemy import text\nfrom app.core.db import engine\n"
        "with engine.connect() as c:\n"
        "    print(c.execute(text('pragma journal_mode')).scalar(), c.execute(text('pragma busy_timeout')).scalar())\n"
    ))
    assert resultado.stdout.split() == ["wal", "15000"], resultado.stderr


# Al iniciar
# ==========================================

def test_primera_vez_crea_la_base_y_la_registra(bd_temporal):  # noqa: F811
    inicializacion.DATABASE_PATH.unlink(missing_ok=True)
    assert inicializacion.estadoBaseDatos() == "nueva"

    assert "tablas creadas" in inicializacion.prepararBaseDatos()
    assert inicializacion.estadoBaseDatos() == "existe"
    assert inicializacion.baseConocida()


def test_si_falta_una_base_que_existia_no_crea_otra_sin_permiso(bd_temporal):  # noqa: F811
    inicializacion.prepararBaseDatos()
    bd_temporal.dispose()
    inicializacion.DATABASE_PATH.unlink()
    assert inicializacion.estadoBaseDatos() == "falta"

    with pytest.raises(inicializacion.BaseDatosFaltante) as error:
        inicializacion.prepararBaseDatos()
    assert error.value.ruta == inicializacion.DATABASE_PATH
    assert not inicializacion.DATABASE_PATH.exists()

    # Con permiso explícito sí la crea
    assert "tablas creadas" in inicializacion.prepararBaseDatos(crear_si_falta=True)
    assert inicializacion.verificarTablas() == []


class _Falta(inicializacion.BaseDatosFaltante):
    def __init__(self):
        super().__init__(Path("C:/datos/sefel.db"))


@pytest.mark.parametrize(("acepta", "esperado"), [(False, False), (True, True)])
def test_escritorio_pregunta_antes_de_crear_otra_base(monkeypatch, acepta, esperado):
    llamadas = []

    def inicializarFalso(usuarios=None, crear_si_falta=False):
        llamadas.append(crear_si_falta)
        if not crear_si_falta:
            raise _Falta()
        return ["Base de datos: nueva"]

    preguntas = []
    monkeypatch.setattr(inicializacion, "inicializar", inicializarFalso)
    monkeypatch.setattr(client, "preguntarSiNo", lambda t, m: preguntas.append(m) or acepta)
    monkeypatch.setattr(client, "mostrarError", lambda m: pytest.fail(f"no debía mostrar error: {m}"))

    assert client.prepararDatos() is esperado
    assert "C:\\datos\\sefel.db" in preguntas[0] or "C:/datos/sefel.db" in preguntas[0]
    assert llamadas == ([False, True] if acepta else [False])


def test_escritorio_explica_errores_de_bd_al_iniciar(monkeypatch):
    def fallar(usuarios=None, crear_si_falta=False):
        raise errorSqlite("file is not a database")

    mostrado = []
    monkeypatch.setattr(inicializacion, "inicializar", fallar)
    monkeypatch.setattr(client, "mostrarError", mostrado.append)

    assert client.prepararDatos() is False
    assert mostrado[0].startswith("La base de datos está dañada")


def test_script_sin_consola_no_crea_otra_base(monkeypatch):
    def faltante(crear_si_falta=False):
        if not crear_si_falta:
            raise _Falta()
        return "creada"

    monkeypatch.setattr(inicializacion, "prepararBaseDatos", faltante)
    monkeypatch.setattr(sys, "stdin", None)
    with pytest.raises(SystemExit, match="--crear-bd"):
        iniciar.prepararBaseDatos()
    assert iniciar.prepararBaseDatos(crear_si_falta=True) == "creada"


# En ejecución
# ==========================================

@pytest.fixture
def bd_caida():
    """Simula que la base desaparece o falla mientras la app corre."""
    def sesionQueFalla():
        raise errorSqlite("unable to open database file")
        yield  # pragma: no cover

    app.dependency_overrides[getSession] = sesionQueFalla
    yield
    app.dependency_overrides.pop(getSession, None)


def test_pagina_clara_si_la_base_no_esta(client, bd_caida):
    respuesta = client.get("/dashboard")
    assert respuesta.status_code == 503
    assert "No se encontró la base de datos o no se puede abrir." in respuesta.text
    assert str(inicializacion.DATABASE_PATH) in respuesta.text
    assert "Algo salió mal" not in respuesta.text


def test_htmx_recibe_aviso_sin_reemplazar_la_vista(client, bd_caida):
    respuesta = client.get("/presupuestos", headers={"HX-Request": "true"})
    assert respuesta.status_code == 503
    assert respuesta.headers["HX-Reswap"] == "none"
    assert "No se encontró la base de datos" in respuesta.headers["HX-Trigger"].encode().decode("unicode_escape")


def test_api_recibe_json(client, bd_caida):
    respuesta = client.get("/api/apu/buscar")
    assert respuesta.status_code == 503
    assert respuesta.json()["detail"].startswith("No se encontró la base de datos")


@pytest.mark.parametrize(("error", "titulo"), [
    ("unable to open database file", "No se encontró la base de datos"),
    ("no such table: user", "incompleta"),
    ("database is locked", "ocupada"),
    ("attempt to write a readonly database", "No se puede escribir"),
    ("disk I/O error", "Error del disco"),
    ("file is not a database", "dañada"),
    ("database disk image is malformed", "dañada"),
    ("algo raro", "Error al acceder"),
])
def test_cada_error_tiene_su_explicacion(error, titulo):
    assert titulo in describirErrorBD(errorSqlite(error))[0]
    assert str(inicializacion.DATABASE_PATH) in mensajeErrorBD(errorSqlite(error))


# Modo red
# ==========================================

def test_argumentos_de_red():
    assert client.parsearArgumentos(["--red"]).red is True
    assert client.parsearArgumentos(["9000", "--red"]).puerto == 9000
    assert client.parsearArgumentos([]).red is False
    assert iniciar.parsearArgumentos(["--red", "--crear-bd"]).red is True


def test_aviso_de_red_muestra_direcciones_y_firewall(monkeypatch):
    monkeypatch.setattr(client, "ipsLocales", lambda: ["192.168.1.20", "10.0.75.1"])
    aviso = client.avisoRed(8765)
    assert "http://192.168.1.20:8765" in aviso
    assert "10.0.75.1" in aviso and "Firewall" in aviso


def test_ips_locales_no_incluye_localhost():
    assert all(not ip.startswith(("127.", "169.254.")) for ip in client.ipsLocales())


def test_el_servidor_de_red_acepta_conexiones_por_la_ip_local():
    ips = client.ipsLocales()
    if not ips:
        pytest.skip("este equipo no tiene IP de red local")
    puerto = client.getUnusedPort()
    assert client.puertoDisponible(puerto, client.HOST_RED)
