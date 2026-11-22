"""Ronda de correcciones: VIEWER, sidebar, PDF en escritorio, listado en tiempo
real, notificaciones inmediatas y validaciones de fechas y caracteres."""
import base64
import json
import re
from datetime import datetime, timezone

import pytest
from sqlmodel import select

import client
from app.core.security import hashPassword
from app.core.validaciones import (
    PATRON_HTML_TEXTO,
    PATRON_HTML_TEXTO_PUNTUACION,
    validarTexto,
)
from app.models.apu import APU, APUValidacion
from app.models.presupuesto import Presupuesto, PresupuestoValidacion
from app.models.user import User, UserRole
from scripts.seed_apus import SEED_APUS
from scripts.seed_presupuestos import SEED_PRESUPUESTOS

HTMX = {"HX-Request": "true"}
CLAVE = "Clave12345"


def loginComo(client_http, session, rol):
    session.add(User(
        username=f"u_{rol.value.lower()}", email=f"{rol.value}@x.cl",
        hashed_password=hashPassword(CLAVE), full_name=rol.value.title(), role=rol,
    ))
    session.commit()
    client_http.post("/login", data={"username": f"u_{rol.value.lower()}", "password": CLAVE})


def nuevoPresupuesto(session, code="PRE-001", **cambios):
    p = Presupuesto(
        id_usuario=1, code=code, client_name="Cliente", estimate_income=1,
        start_date=datetime(2026, 3, 1), end_date=datetime(2026, 4, 1),
        description="Obra de prueba", **cambios,
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def datosPresupuesto(**cambios):
    datos = {
        "code": "PRE-NUEVO", "client_name": "Inmobiliaria Maule S.A.",
        "estimate_income": "1000", "start_date": "2026-03-01", "end_date": "2026-06-30",
        "description": "Remodelación de baños, edificio central", "status": "DRAFT",
    }
    datos.update(cambios)
    return datos


def datosApu(**cambios):
    datos = {"code": "OG_01-A", "name": "Hormigón H25", "unit": "m3",
             "category": "Obra gruesa", "unit_cost": "1000"}
    datos.update(cambios)
    return datos


def eventos(respuesta) -> dict:
    return json.loads(respuesta.headers.get("HX-Trigger") or "{}")


# A.1 · VIEWER solo lectura
# ==========================================

def test_viewer_ve_porcentajes_como_texto_sin_controles(client, session, user):
    p = nuevoPresupuesto(session, pct_iva=19)
    loginComo(client, session, UserRole.VIEWER)

    html = client.get(f"/presupuestos/{p.id_presupuesto}/porcentajes", headers=HTMX).text
    assert 'name="pct_iva"' not in html          # sin inputs
    assert "<form" not in html
    assert "Guardar y recalcular" not in html
    assert "19%" in html                          # pero ve los valores
    assert "solo permite consultar" in html


@pytest.mark.parametrize(("metodo", "ruta"), [
    ("POST", "/presupuestos"),
    ("POST", "/presupuestos/{id}"),
    ("POST", "/presupuestos/{id}/estado"),
    ("POST", "/presupuestos/{id}/porcentajes"),
    ("POST", "/presupuestos/{id}/items"),
    ("POST", "/presupuestos/{id}/items/1"),
    ("GET", "/presupuestos/nuevo"),
    ("GET", "/presupuestos/{id}/editar"),
    ("GET", "/presupuestos/{id}/items/nuevo"),
])
def test_viewer_recibe_403_en_toda_escritura(client, session, user, metodo, ruta):
    p = nuevoPresupuesto(session)
    loginComo(client, session, UserRole.VIEWER)
    respuesta = client.request(
        metodo, ruta.format(id=p.id_presupuesto),
        data={"pct_iva": "50", "nuevo_estado": "ACTIVE"}, headers=HTMX,
    )
    assert respuesta.status_code == 403
    assert respuesta.json() == {"detail": "Sin permiso"}
    session.refresh(p)
    assert (p.pct_iva, p.status.value) == (0, "DRAFT")


# A.2 · Sidebar
# ==========================================

def test_usuarios_aparece_al_final_del_sidebar(logged_in_client):
    html = logged_in_client.get("/dashboard").text
    posiciones = [html.index(f'href="{r}"') for r in ("/dashboard", "/apu", "/presupuestos", "/admin/users")]
    assert posiciones == sorted(posiciones)


# A.3 · PDF en escritorio y navegador
# ==========================================

def test_navegador_sigue_descargando_el_pdf(logged_in_client, session):
    p = nuevoPresupuesto(session)
    respuesta = logged_in_client.get(f"/presupuestos/{p.id_presupuesto}/pdf")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "application/pdf"
    assert respuesta.headers["content-disposition"].startswith("attachment;")


def test_boton_descargar_usa_el_guardado_de_escritorio_si_existe(logged_in_client, session):
    nuevoPresupuesto(session)
    html = logged_in_client.get("/presupuestos/exportar", headers=HTMX).text
    assert "window.sefelDescargarPdf($el.href)" in html
    pagina = logged_in_client.get("/presupuestos").text
    assert "window.sefelDescargarPdf = function" in pagina
    assert "PDF guardado en " in pagina and "No se pudo guardar el PDF" in pagina


class VentanaFalsa:
    def __init__(self, eleccion):
        self.eleccion = eleccion
        self.pedido = None

    def create_file_dialog(self, tipo, **kwargs):
        self.pedido = (tipo, kwargs)
        return self.eleccion


def test_escritorio_guarda_el_pdf_donde_elige_el_usuario(tmp_path, monkeypatch):
    destino = tmp_path / "mi-cotizacion.pdf"
    ventana = VentanaFalsa((str(destino),))
    monkeypatch.setattr(client.webview, "windows", [ventana])

    contenido = b"%PDF-1.4 prueba"
    resultado = client.ApiEscritorio().guardarPdf(
        "presupuesto-3-2026-11-18.pdf", base64.b64encode(contenido).decode()
    )

    assert resultado == {"ok": True, "ruta": str(destino)}
    assert destino.read_bytes() == contenido
    tipo, opciones = ventana.pedido
    assert tipo == client.webview.FileDialog.SAVE
    assert opciones["save_filename"] == "presupuesto-3-2026-11-18.pdf"


def test_escritorio_informa_cancelacion_y_errores(monkeypatch):
    monkeypatch.setattr(client.webview, "windows", [VentanaFalsa(None)])
    pdf = base64.b64encode(b"%PDF-1.4").decode()
    api = client.ApiEscritorio()

    assert api.guardarPdf("a.pdf", pdf) == {"ok": False, "cancelado": True}
    assert api.guardarPdf("a.pdf", base64.b64encode(b"<html>").decode())["ok"] is False
    assert api.guardarPdf("a.pdf", "no-es-base64!!")["ok"] is False


def test_escritorio_permite_descargas_en_webview():
    assert client.webview.settings["ALLOW_DOWNLOADS"] is True


# A.4 · Listado al instante
# ==========================================

def test_apu_creado_aparece_primero_y_resaltado_aunque_haya_muchos(logged_in_client, session):
    for i in range(15):
        session.add(APU(code=f"A-{i:02d}", name="x", unit="m", unit_cost=1, real_unit_cost=1))
    session.commit()

    respuesta = logged_in_client.post("/apu", data=datosApu(code="ZZ-NUEVO"), headers=HTMX)
    assert respuesta.headers["HX-Retarget"] == "#contenido-apu"
    fila = re.search(r'<tr id="apu-\d+" class="([^"]*)"[^>]*>\s*<td[^>]*>\s*ZZ-NUEVO', respuesta.text)
    assert fila and "fila-nueva" in fila.group(1)
    assert respuesta.text.index("ZZ-NUEVO") < respuesta.text.index("A-14")   # lo más nuevo arriba


def test_apu_editado_se_muestra_en_su_pagina(logged_in_client, session):
    viejo = APU(code="VIEJO-1", name="x", unit="m", unit_cost=1, real_unit_cost=1,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    session.add(viejo)
    for i in range(12):
        session.add(APU(code=f"N-{i:02d}", name="x", unit="m", unit_cost=1, real_unit_cost=1))
    session.commit()

    respuesta = logged_in_client.post(f"/apu/{viejo.id}", data=datosApu(code="VIEJO-1"), headers=HTMX)
    assert "VIEJO-1" in respuesta.text                       # está en la página 2
    assert 'aria-current="page">2<' in respuesta.text


def test_presupuesto_creado_actualiza_lista_y_resumen(logged_in_client, session):
    for i in range(11):
        nuevoPresupuesto(session, code=f"OLD-{i:02d}")

    respuesta = logged_in_client.post("/presupuestos", data=datosPresupuesto(), headers=HTMX)

    assert respuesta.headers["HX-Retarget"] == "#contenido-presupuesto"
    # El modal se cierra DESPUÉS del swap: cerrarlo antes vacía el formulario que
    # hizo la petición y HTMX descartaba el reemplazo del listado (causa de A.4)
    assert respuesta.headers["HX-Trigger-After-Settle"] == "cerrar-modal-presupuesto"
    assert "cerrar-modal-presupuesto" not in eventos(respuesta)
    assert "PRE-NUEVO" in respuesta.text and "fila-nueva" in respuesta.text
    resumen = re.search(r'<section id="resumen-presupuestos"[^>]*hx-swap-oob="true"', respuesta.text)
    assert resumen, "las tarjetas de resumen deben viajar fuera de banda"
    assert re.search(r"Presupuestos totales</p>\s*<p[^>]*>12<", respuesta.text)


def test_paginacion_de_presupuestos_navega(logged_in_client, session):
    for i in range(12):
        nuevoPresupuesto(session, code=f"P-{i:02d}")
    html = logged_in_client.get("/presupuestos").text
    assert 'href="/presupuestos?pagina=2"' in html
    pagina2 = logged_in_client.get("/presupuestos?pagina=2", headers=HTMX).text
    assert "P-00" in pagina2 and "P-11" not in pagina2       # más recientes en la página 1


# A.5 · Notificaciones inmediatas
# ==========================================

@pytest.mark.parametrize(("ruta", "datos", "mensaje"), [
    ("/apu", datosApu(), "APU creado correctamente."),
    ("/presupuestos", datosPresupuesto(), "Presupuesto creado correctamente."),
])
def test_notificacion_llega_en_la_misma_respuesta(logged_in_client, ruta, datos, mensaje):
    respuesta = logged_in_client.post(ruta, data=datos, headers=HTMX)

    assert eventos(respuesta)["notificar"] == {"mensajes": [["success", mensaje]]}
    # y ya no reaparece en la siguiente página
    assert mensaje not in logged_in_client.get("/dashboard").text


def test_sin_htmx_el_mensaje_sigue_en_la_pagina_siguiente(logged_in_client):
    respuesta = logged_in_client.post("/apu", data=datosApu(), follow_redirects=False)
    assert respuesta.status_code == 303
    assert "APU creado correctamente." in logged_in_client.get("/apu").text


def test_base_tiene_el_contenedor_de_notificaciones(logged_in_client):
    html = logged_in_client.get("/dashboard").text
    assert 'id="toasts"' in html
    assert 'document.addEventListener("notificar"' in html


# B.1 · Fechas del periodo
# ==========================================

REGLAS_FECHAS = [
    ({"start_date": ""}, "La fecha de inicio es obligatoria."),
    ({"end_date": ""}, "La fecha de término es obligatoria."),
    ({"start_date": "2025-12-31"}, "La fecha de inicio no puede ser anterior al 01/01/2026."),
    ({"end_date": "2026-02-28"}, "La fecha de término no puede ser anterior a la fecha de inicio."),
    ({"end_date": "2501-01-01"}, "La fecha de término no puede ser posterior al 31/12/2500."),
]


@pytest.mark.parametrize(("cambios", "mensaje"), REGLAS_FECHAS)
def test_fechas_al_crear(logged_in_client, session, cambios, mensaje):
    respuesta = logged_in_client.post("/presupuestos", data=datosPresupuesto(**cambios), headers=HTMX)
    assert respuesta.status_code == 200
    assert mensaje in respuesta.text
    assert "HX-Retarget" not in respuesta.headers        # el error queda en el modal
    assert session.exec(select(Presupuesto)).first() is None


@pytest.mark.parametrize(("cambios", "mensaje"), REGLAS_FECHAS)
def test_fechas_al_editar(logged_in_client, session, cambios, mensaje):
    p = nuevoPresupuesto(session)
    respuesta = logged_in_client.post(
        f"/presupuestos/{p.id_presupuesto}",
        data=datosPresupuesto(code="PRE-001", **cambios), headers=HTMX,
    )
    assert mensaje in respuesta.text
    session.refresh(p)
    assert p.start_date == datetime(2026, 3, 1) and p.end_date == datetime(2026, 4, 1)


@pytest.mark.parametrize(("inicio", "termino"), [
    ("2026-01-01", "2026-01-01"),     # mismo día y límite inferior
    ("2026-05-10", "2500-12-31"),     # límite superior
])
def test_fechas_validas_en_los_limites(logged_in_client, session, inicio, termino):
    respuesta = logged_in_client.post(
        "/presupuestos", data=datosPresupuesto(start_date=inicio, end_date=termino), headers=HTMX,
    )
    assert respuesta.headers.get("HX-Retarget") == "#contenido-presupuesto"
    assert session.exec(select(Presupuesto)).one().code == "PRE-NUEVO"


def test_formulario_limita_las_fechas(logged_in_client):
    html = logged_in_client.get("/presupuestos/nuevo", headers=HTMX).text
    assert 'min="2026-01-01"' in html and 'max="2500-12-31"' in html
    assert ":min=\"inicio ||" in html                    # el término sigue al inicio


# B.2, B.5, B.6 · Caracteres
# ==========================================

@pytest.mark.parametrize("valor", ["PRE@1", "PRE#1", "P.1", "P/1", "P 1;", "P(1)", "P'1", "P<1>"])
@pytest.mark.parametrize("ruta", ["crear", "editar"])
def test_codigo_de_presupuesto_rechaza_simbolos(logged_in_client, session, valor, ruta):
    p = nuevoPresupuesto(session)
    url = "/presupuestos" if ruta == "crear" else f"/presupuestos/{p.id_presupuesto}"
    respuesta = logged_in_client.post(url, data=datosPresupuesto(code=valor), headers=HTMX)
    assert "El código tiene caracteres no permitidos" in respuesta.text


@pytest.mark.parametrize(("campo", "etiqueta"), [("client_name", "El cliente"), ("description", "El nombre")])
@pytest.mark.parametrize("valor", ["ACME $", "Obra #2", "Obra; urgente", "Obra (fase 1)", "Obra!"])
@pytest.mark.parametrize("ruta", ["crear", "editar"])
def test_cliente_y_nombre_rechazan_simbolos(logged_in_client, session, campo, etiqueta, valor, ruta):
    p = nuevoPresupuesto(session)
    url = "/presupuestos" if ruta == "crear" else f"/presupuestos/{p.id_presupuesto}"
    datos = datosPresupuesto(**{campo: valor}, **({"code": "PRE-001"} if ruta == "editar" else {}))
    respuesta = logged_in_client.post(url, data=datos, headers=HTMX)
    assert f"{etiqueta} tiene caracteres no permitidos" in respuesta.text


def test_presupuesto_acepta_tildes_enie_guiones_puntos_y_comas(logged_in_client, session):
    datos = datosPresupuesto(code="PRE_2026-ÑOÑO", client_name="Constructora Ñuble Ltda.",
                             description="Ampliación de oficinas, etapa 2")
    respuesta = logged_in_client.post("/presupuestos", data=datos, headers=HTMX)
    assert respuesta.headers.get("HX-Retarget") == "#contenido-presupuesto"
    assert session.exec(select(Presupuesto)).one().client_name == "Constructora Ñuble Ltda."


@pytest.mark.parametrize(("campo", "etiqueta"), [("code", "El código"), ("name", "El nombre"), ("category", "La categoría")])
@pytest.mark.parametrize("valor", ["A.1", "A,1", "A@1", "A/B", "e=10", "A&B"])
@pytest.mark.parametrize("ruta", ["crear", "editar"])
def test_apu_rechaza_simbolos(logged_in_client, session, campo, etiqueta, valor, ruta):
    apu = APU(code="EXISTE", name="x", unit="m", unit_cost=1, real_unit_cost=1)
    session.add(apu)
    session.commit()
    url = "/apu" if ruta == "crear" else f"/apu/{apu.id}"
    respuesta = logged_in_client.post(url, data=datosApu(**{campo: valor}), headers=HTMX)
    assert f"{etiqueta} tiene caracteres no permitidos" in respuesta.text


def test_apu_acepta_tildes_enie_y_guiones(logged_in_client, session):
    respuesta = logged_in_client.post(
        "/apu", data=datosApu(code="ÑU_01-b", name="Excavación año 2026", category="Movimiento de tierra"),
        headers=HTMX,
    )
    assert respuesta.headers.get("HX-Retarget") == "#contenido-apu"
    assert session.exec(select(APU)).one().code == "ÑU_01-B"     # códigos siempre en mayúsculas


def test_tildes_escritas_como_dos_caracteres_se_normalizan():
    assert validarTexto("Excavación", "El nombre") == "Excavación"


def test_formularios_usan_el_patron_central(logged_in_client):
    presupuesto = logged_in_client.get("/presupuestos/nuevo", headers=HTMX).text
    apu = logged_in_client.get("/apu/nuevo", headers=HTMX).text
    assert presupuesto.count(f'pattern="{PATRON_HTML_TEXTO}"') == 1                # código
    assert presupuesto.count(f'pattern="{PATRON_HTML_TEXTO_PUNTUACION}"') == 2     # cliente y nombre
    assert apu.count(f'pattern="{PATRON_HTML_TEXTO}"') == 3                        # código, nombre, categoría


# B.4 · "Presupuesto"/"Descripción" -> "Nombre"
# ==========================================

def test_columna_y_campo_se_llaman_nombre(logged_in_client, session):
    nuevoPresupuesto(session)
    lista = logged_in_client.get("/presupuestos").text
    assert '<th class="th">Nombre</th>' in lista
    assert '<th class="th">Presupuesto</th>' not in lista

    formulario = logged_in_client.get("/presupuestos/nuevo", headers=HTMX).text
    assert ">Nombre</span>" in formulario and "Descripción" not in formulario

    vacio = logged_in_client.post("/presupuestos", data=datosPresupuesto(description=" "), headers=HTMX)
    assert "El nombre es obligatorio" in vacio.text


# Seeds
# ==========================================

def test_las_seeds_cumplen_las_validaciones():
    for a in SEED_APUS:
        APUValidacion(code=a.code, name=a.name, unit=a.unit, category=a.category,
                      unit_cost=a.unit_cost, real_unit_cost=a.real_unit_cost)
    for p in SEED_PRESUPUESTOS:
        PresupuestoValidacion(code=p.code, client_name=p.client_name, estimate_income=p.estimate_income,
                              start_date=p.start_date, end_date=p.end_date, description=p.description)
