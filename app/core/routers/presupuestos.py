from datetime import datetime, timedelta, timezone
from math import ceil
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.db import getSession
from app.core.dependencies import CurrentUser
from app.core.flash import flash
from app.models.user import (
    Presupuesto,
    PresupuestoValidacion,
    StatusPresupuestos,
)
from app.templates import templates


router = APIRouter(tags=["presupuestos"])

PRESUPUESTOS_POR_PAGINA = 10
LISTA_URL = "/presupuestos"


# Utilidades
# ==========================================

def _buscar(session: Session, presupuesto_id: int, usuario) -> Presupuesto | None:
    """Busca un presupuesto asegurando que pertenece al usuario actual."""
    presupuesto = session.get(Presupuesto, presupuesto_id)
    if presupuesto is None or presupuesto.id_usuario != usuario.id:
        return None
    return presupuesto


def _resumen(todos: list[Presupuesto]) -> dict:
    ahora = datetime.now(timezone.utc)

    borradores = sum(
        1 for p in todos if p.status == StatusPresupuestos.DRAFT
    )
    activos = sum(
        1 for p in todos if p.status == StatusPresupuestos.ACTIVE
    )
    cerrados = sum(
        1 for p in todos if p.status == StatusPresupuestos.CLOSE
    )

    actualizados = 0
    for presupuesto in todos:
        fecha = presupuesto.updated_at
        if fecha is not None:
            if fecha.tzinfo is None:
                fecha = fecha.replace(tzinfo=timezone.utc)
            if ahora - fecha <= timedelta(days=30):
                actualizados += 1

    return {
        "registrados": len(todos),
        "registrados_detalle": "Presupuestos registrados",
        "borradores": borradores,
        "borradores_detalle": "Presupuestos en borrador",
        "activos": activos,
        "activos_detalle": "Presupuestos activos",
        "cerrados": cerrados,
        "cerrados_detalle": "Presupuestos cerrados",
        "actualizados": actualizados,
        "actualizados_detalle": "Actualizados en los últimos 30 días",
    }


def _filtrar(
    todos: list[Presupuesto],
    q: str,
    estado: str,
) -> list[Presupuesto]:
    texto = q.strip().casefold()
    resultado = []

    for presupuesto in todos:
        if texto and texto not in (
            f"{presupuesto.code} {presupuesto.client_name}".casefold()
        ):
            continue

        if estado and presupuesto.status.value != estado:
            continue

        resultado.append(presupuesto)

    return resultado


def _datosFormulario(
    code: str = "",
    client_name: str = "",
    estimate_income: str | int = "",
    start_date: str = "",
    end_date: str = "",
    description: str = "",
    status: str = StatusPresupuestos.DRAFT.value,
) -> dict:
    return {
        "code": code,
        "client_name": client_name,
        "estimate_income": estimate_income,
        "start_date": start_date,
        "end_date": end_date,
        "description": description,
        "status": status,
    }


def _normalizar_fechas(datos: dict) -> dict:
    """Convierte cadenas vacías de fecha a None antes de validar."""
    limpio = dict(datos)
    for campo in ("start_date", "end_date"):
        if limpio.get(campo) in ("", None):
            limpio[campo] = None
    return limpio


def _validar(datos: dict) -> tuple[dict, str | None]:
    datos_limpios = _datosFormulario(
        str(datos.get("code", "")),
        str(datos.get("client_name", "")),
        datos.get("estimate_income", ""),
        str(datos.get("start_date", "") or ""),
        str(datos.get("end_date", "") or ""),
        str(datos.get("description", "")),
        str(
            getattr(datos.get("status", ""), "value", datos.get("status", ""))
            or StatusPresupuestos.DRAFT.value
        ),
    )

    try:
        presupuesto_validado = PresupuestoValidacion.model_validate(
            _normalizar_fechas(datos_limpios)
        )
    except ValidationError as exc:
        error = exc.errors()[0]
        campo = error["loc"][0]
        tipo = error["type"]

        nombres = {
            "code": ("El código", 50),
            "client_name": ("El nombre del cliente", 50),
            "description": ("La descripción", 500),
        }

        if campo == "estimate_income":
            if tipo == "int_parsing":
                mensaje = "El ingreso estimado debe ser un número entero."
            else:
                mensaje = "El ingreso estimado no puede ser negativo."
        elif campo == "status":
            mensaje = "El estado seleccionado no es válido."
        elif campo in ("start_date", "end_date"):
            mensaje = "La fecha ingresada no es válida."
        elif campo in nombres:
            nombre, longitud = nombres[campo]
            if tipo in ("value_error", "string_too_short"):
                mensaje = f"{nombre} es obligatorio y no puede estar vacío."
            elif tipo == "string_too_long":
                mensaje = f"{nombre} no puede superar los {longitud} caracteres."
            else:
                mensaje = f"Revisa el campo {nombre.lower()}."
        else:
            mensaje = "Revisa los datos ingresados."

        return datos_limpios, mensaje

    return presupuesto_validado.model_dump(), None


def _codigoExistente(
    session: Session,
    code: str,
    id_usuario: int,
    excluir_id: int | None = None,
) -> bool:
    consulta = select(Presupuesto).where(
        func.lower(Presupuesto.code) == code.casefold(),
        Presupuesto.id_usuario == id_usuario,
    )
    if excluir_id is not None:
        consulta = consulta.where(Presupuesto.id_presupuesto != excluir_id)
    return session.exec(consulta).first() is not None


def _a_dict(presupuesto: Presupuesto) -> dict:
    """Convierte el modelo a dict listo para la plantilla."""
    return {
        "id_presupuesto": presupuesto.id_presupuesto,
        "code": presupuesto.code,
        "client_name": presupuesto.client_name,
        "estimate_income": presupuesto.estimate_income,
        "start_date": (
            presupuesto.start_date.strftime("%Y-%m-%d")
            if presupuesto.start_date else ""
        ),
        "end_date": (
            presupuesto.end_date.strftime("%Y-%m-%d")
            if presupuesto.end_date else ""
        ),
        "description": presupuesto.description,
        "status": (
            presupuesto.status.value
            if presupuesto.status else StatusPresupuestos.DRAFT.value
        ),
    }


def _renderFormulario(
    request: Request,
    usuario,
    presupuesto,
    modo: str,
    error: str | None = None,
    status_code: int = 200,
    es_htmx: bool = False,
):
    if presupuesto is None:
        presupuesto = _datosFormulario()
    elif not isinstance(presupuesto, dict):
        presupuesto = _a_dict(presupuesto)

    return templates.TemplateResponse(
        request=request,
        name=(
            "partials/presupuesto/formulario.html"
            if es_htmx
            else "presupuesto/formulario.html"
        ),
        status_code=status_code,
        context={
            "usuario": usuario,
            "presupuesto": presupuesto,
            "modo": modo,
            "error": error,
            "estados": list(StatusPresupuestos),
        },
    )


def _renderLista(
    request: Request,
    usuario,
    session: Session,
    *,
    q: str = "",
    estado: str = "",
    pagina: int = 1,
    es_htmx: bool = False,
):
    todos = session.exec(
        select(Presupuesto).order_by(Presupuesto.code)
    ).all()
    filtrados = _filtrar(todos, q, estado)

    total = len(filtrados)
    paginas = max(1, ceil(total / PRESUPUESTOS_POR_PAGINA))
    pagina = min(max(pagina, 1), paginas)

    inicio = (pagina - 1) * PRESUPUESTOS_POR_PAGINA
    visibles = filtrados[inicio:inicio + PRESUPUESTOS_POR_PAGINA]

    filtros = {
        k: v for k, v in {"q": q, "estado": estado}.items() if v
    }
    base_url = LISTA_URL + "?" + (
        urlencode(filtros) + "&" if filtros else ""
    )

    nombre_plantilla = (
        "partials/presupuesto/tabla.html"
        if es_htmx
        else "presupuesto.html"
    )

    return templates.TemplateResponse(
        request=request,
        name=nombre_plantilla,
        context={
            "usuario": usuario,
            "presupuestos": visibles,
            "resumen": _resumen(todos),
            "estados": list(StatusPresupuestos),
            "q": q,
            "estado": estado,
            "total": total,
            "desde": inicio + 1 if total else 0,
            "hasta": inicio + len(visibles),
            "pagina": pagina,
            "paginas": paginas,
            "base_url": base_url,
        },
    )


# Listado
# ==========================================

@router.get("/presupuestos")
def listar(
    request: Request,
    usuario: CurrentUser,
    session: Session = Depends(getSession),
    q: str = "",
    estado: str = "",
    pagina: int = 1,
):
    return _renderLista(
        request,
        usuario,
        session,
        q=q,
        estado=estado,
        pagina=pagina,
        es_htmx=request.headers.get("HX-Request") == "true",
    )


# Crear presupuesto
# ==========================================

@router.get("/presupuestos/nuevo")
def mostrarFormulario(
    request: Request,
    usuario: CurrentUser,
):
    return _renderFormulario(
        request,
        usuario,
        None,
        "crear",
        es_htmx=request.headers.get("HX-Request") == "true",
    )


@router.post("/presupuestos")
def crear(
    request: Request,
    usuario: CurrentUser,
    code: str = Form(...),
    client_name: str = Form(...),
    estimate_income: str = Form(...),
    start_date: str = Form(""),
    end_date: str = Form(""),
    description: str = Form(...),
    status: str = Form(StatusPresupuestos.DRAFT.value),
    session: Session = Depends(getSession),
):
    es_htmx = request.headers.get("HX-Request") == "true"

    datos, error = _validar(
        _datosFormulario(
            code, client_name, estimate_income,
            start_date, end_date, description, status,
        )
    )

    if error is None and _codigoExistente(
        session, datos["code"], usuario.id
    ):
        error = "Ya existe un presupuesto con ese código."

    if error:
        return _renderFormulario(
            request, usuario, datos, "crear", error,
            200 if es_htmx else 400,
            es_htmx=es_htmx,
        )

    nuevo = Presupuesto(**datos, id_usuario=usuario.id)
    session.add(nuevo)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return _renderFormulario(
            request, usuario, datos, "crear",
            "No se pudo guardar. Comprueba que el código no esté repetido.",
            200 if es_htmx else 400,
            es_htmx=es_htmx,
        )

    flash(request, "Presupuesto creado correctamente.", "success")

    if es_htmx:
        respuesta = _renderLista(
            request, usuario, session, es_htmx=True,
        )
        respuesta.headers["HX-Retarget"] = "#contenido-presupuesto"
        respuesta.headers["HX-Reswap"] = "innerHTML"
        respuesta.headers["HX-Trigger"] = "cerrar-modal-presupuesto"
        return respuesta

    return RedirectResponse(LISTA_URL, status_code=303)


# Editar presupuesto
# ==========================================

@router.get("/presupuestos/{presupuesto_id}/editar")
def mostrarEdicion(
    presupuesto_id: int,
    request: Request,
    usuario: CurrentUser,
    session: Session = Depends(getSession),
):
    presupuesto = _buscar(session, presupuesto_id, usuario)

    if presupuesto is None:
        flash(request, "El presupuesto solicitado no existe.", "error")
        return RedirectResponse(LISTA_URL, status_code=303)

    return _renderFormulario(
        request, usuario, presupuesto, "editar",
        es_htmx=request.headers.get("HX-Request") == "true",
    )


@router.post("/presupuestos/{presupuesto_id}")
def actualizar(
    presupuesto_id: int,
    request: Request,
    usuario: CurrentUser,
    code: str = Form(...),
    client_name: str = Form(...),
    estimate_income: str = Form(...),
    start_date: str = Form(""),
    end_date: str = Form(""),
    description: str = Form(...),
    status: str = Form(StatusPresupuestos.DRAFT.value),
    session: Session = Depends(getSession),
):
    es_htmx = request.headers.get("HX-Request") == "true"

    presupuesto = _buscar(session, presupuesto_id, usuario)

    if presupuesto is None:
        flash(request, "El presupuesto solicitado ya no existe.", "error")
        return RedirectResponse(LISTA_URL, status_code=303)

    datos, error = _validar(
        _datosFormulario(
            code, client_name, estimate_income,
            start_date, end_date, description, status,
        )
    )

    datos["id_presupuesto"] = presupuesto_id

    if error is None and _codigoExistente(
        session, datos["code"], usuario.id, excluir_id=presupuesto_id
    ):
        error = "Ya existe otro presupuesto con ese código."

    if error:
        return _renderFormulario(
            request, usuario, datos, "editar", error,
            200 if es_htmx else 400,
            es_htmx=es_htmx,
        )

    for campo, valor in datos.items():
        if campo != "id_presupuesto":
            setattr(presupuesto, campo, valor)

    presupuesto.updated_at = datetime.now(timezone.utc)
    session.add(presupuesto)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return _renderFormulario(
            request, usuario, datos, "editar",
            "No se pudieron guardar los cambios. Comprueba el código.",
            200 if es_htmx else 400,
            es_htmx=es_htmx,
        )

    flash(request, "Presupuesto actualizado correctamente.", "success")

    if es_htmx:
        respuesta = _renderLista(
            request, usuario, session, es_htmx=True,
        )
        respuesta.headers["HX-Retarget"] = "#contenido-presupuesto"
        respuesta.headers["HX-Reswap"] = "innerHTML"
        respuesta.headers["HX-Trigger"] = "cerrar-modal-presupuesto"
        return respuesta

    return RedirectResponse(LISTA_URL, status_code=303)


# Cambiar estado (reemplaza activar/desactivar de APU)
# ==========================================

@router.post("/presupuestos/{presupuesto_id}/estado")
def cambiarEstado(
    presupuesto_id: int,
    request: Request,
    usuario: CurrentUser,
    nuevo_estado: str = Form(...),
    q: str = Form(""),
    estado: str = Form(""),
    pagina: int = Form(1),
    session: Session = Depends(getSession),
):
    es_htmx = request.headers.get("HX-Request") == "true"
    presupuesto = _buscar(session, presupuesto_id, usuario)

    if presupuesto is None:
        flash(request, "El presupuesto solicitado no existe.", "error")
    else:
        try:
            presupuesto.status = StatusPresupuestos(nuevo_estado)
            presupuesto.updated_at = datetime.now(timezone.utc)
            session.add(presupuesto)
            session.commit()
            flash(
                request,
                f"El presupuesto '{presupuesto.code}' ahora está "
                f"{presupuesto.status.value}.",
                "success",
            )
        except ValueError:
            flash(request, "El estado solicitado no es válido.", "error")

    if es_htmx:
        respuesta = _renderLista(
            request, usuario, session,
            q=q, estado=estado, pagina=pagina, es_htmx=True,
        )
        respuesta.headers["HX-Retarget"] = "#contenido-presupuesto"
        respuesta.headers["HX-Reswap"] = "innerHTML"
        return respuesta

    filtros = {"q": q, "estado": estado, "pagina": pagina}
    parametros = urlencode({
        k: v for k, v in filtros.items() if v not in ("", None)
    })
    destino = f"{LISTA_URL}?{parametros}" if parametros else LISTA_URL
    return RedirectResponse(
        f"{destino}#presupuesto-{presupuesto_id}", status_code=303,
    )