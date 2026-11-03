
from datetime import datetime, timedelta, timezone
from math import ceil
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from pydantic import ValidationError
from app.core.db import getSession
from app.core.dependencies import CurrentUser
from app.core.flash import flash
from app.models.apu import APU, APUValidacion
from app.templates import templates


router = APIRouter(tags=["apu"])

APUS_POR_PAGINA = 10
LISTA_URL = "/apu"


# Utilidades
# ==========================================

def _buscar(session: Session, apu_id: int) -> APU | None:
    return session.get(APU, apu_id)


def _resumen(todos: list[APU]) -> dict:
    ahora = datetime.now(timezone.utc)
    activos = sum(1 for apu in todos if apu.is_active)

    actualizados = 0
    for apu in todos:
        fecha = apu.updated_at
        if fecha is not None:
            if fecha.tzinfo is None:
                fecha = fecha.replace(tzinfo=timezone.utc)
            if ahora - fecha <= timedelta(days=30):
                actualizados += 1

    return {
        "registrados": len(todos),
        "registrados_detalle": "APU registrados en el catálogo",
        "activos": activos,
        "activos_detalle": "APU disponibles",
        "inactivos": len(todos) - activos,
        "inactivos_detalle": "APU desactivados",
        "actualizados": actualizados,
        "actualizados_detalle": "Actualizados en los últimos 30 días",
    }


def _filtrar(
    todos: list[APU],
    q: str,
    categoria: str,
    estado: str,
) -> list[APU]:
    texto = q.strip().casefold()
    resultado = []

    for apu in todos:
        if texto and texto not in f"{apu.code} {apu.name}".casefold():
            continue

        if categoria and (apu.category or "") != categoria:
            continue

        if estado == "activo" and not apu.is_active:
            continue

        if estado == "inactivo" and apu.is_active:
            continue

        resultado.append(apu)

    return resultado


def _datosFormulario(
    code: str = "",
    name: str = "",
    unit: str = "",
    category: str = "",
    unit_cost: str | int = "",
    description: str = "",
) -> dict:
    return {
        "code": code,
        "name": name,
        "unit": unit,
        "category": category,
        "unit_cost": unit_cost,
        "description": description,
    }



def _validar(datos: dict) -> tuple[dict, str | None]:
    datos_limpios = _datosFormulario(
        str(datos.get("code", "")),
        str(datos.get("name", "")),
        str(datos.get("unit", "")),
        str(datos.get("category", "")),
        datos.get("unit_cost", ""),
        str(datos.get("description", "")),
    )

    try:
        apu_validado = APUValidacion.model_validate(datos_limpios)


    except ValidationError as exc:
        error = exc.errors()[0]
        campo = error["loc"][0]
        tipo = error["type"]

        nombres = {
            "code": ("El código", 50),
            "name": ("El nombre", 150),
            "unit": ("La unidad", 30),
            "category": ("La categoría", 100),
        }

        if campo == "unit_cost":
            if tipo == "int_parsing":
                mensaje = "El precio unitario debe ser un número entero."
            else:
                mensaje = "El precio unitario no puede ser negativo."

        elif campo in nombres:
            nombre, longitud = nombres[campo]

            if tipo == "value_error":
                concordancia = "obligatoria" if campo == "unit" else "obligatorio"
                mensaje = f"{nombre} es {concordancia} y no puede estar vacío."
            elif tipo == "string_too_long":
                mensaje = f"{nombre} no puede superar los {longitud} caracteres."
            else:
                mensaje = f"Revisa el campo {nombre.lower()}."

        else:
            mensaje = "Revisa los datos ingresados."

        return datos_limpios, mensaje

    return apu_validado.model_dump(), None


def _codigoExistente(
    session: Session,
    code: str,
    excluir_id: int | None = None,
) -> bool:
    consulta = select(APU).where(
        func.lower(APU.code) == code.casefold()
    )

    if excluir_id is not None:
        consulta = consulta.where(APU.id != excluir_id)

    return session.exec(consulta).first() is not None


def _renderFormulario(
    request: Request,
    usuario,
    apu,
    modo: str,
    error: str | None = None,
    status_code: int = 200,
):
    return templates.TemplateResponse(
        request=request,
        name="apu/formulario.html",
        status_code=status_code,
        context={
            "usuario": usuario,
            "apu": apu,
            "modo": modo,
            "error": error,
        },
    )


def _renderLista(
    request: Request,
    usuario,
    session: Session,
    *,
    q: str = "",
    categoria: str = "",
    estado: str = "",
    pagina: int = 1,
):
    todos = session.exec(select(APU).order_by(APU.code)).all()
    filtrados = _filtrar(todos, q, categoria, estado)

    total = len(filtrados)
    paginas = max(1, ceil(total / APUS_POR_PAGINA))
    pagina = min(max(pagina, 1), paginas)

    inicio = (pagina - 1) * APUS_POR_PAGINA
    visibles = filtrados[inicio:inicio + APUS_POR_PAGINA]

    filtros = {
        k: v
        for k, v in {
            "q": q,
            "categoria": categoria,
            "estado": estado,
        }.items()
        if v
    }

    base_url = LISTA_URL + "?" + (
        urlencode(filtros) + "&" if filtros else ""
    )

    categorias = sorted({
        apu.category
        for apu in todos
        if apu.category
    })

    return templates.TemplateResponse(
        request=request,
        name="apu.html",
        context={
            "usuario": usuario,
            "apus": visibles,
            "resumen": _resumen(todos),
            "categorias": categorias,
            "q": q,
            "categoria": categoria,
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

@router.get("/apu")
def listar(
    request: Request,
    usuario: CurrentUser,
    session: Session = Depends(getSession),
    q: str = "",
    categoria: str = "",
    estado: str = "",
    pagina: int = 1,
):
    return _renderLista(
        request,
        usuario,
        session,
        q=q,
        categoria=categoria,
        estado=estado,
        pagina=pagina,
    )


# Crear APU
# ==========================================

@router.get("/apu/nuevo")
def mostrarFormulario(
    request: Request,
    usuario: CurrentUser,
):
    return _renderFormulario(
        request, usuario, None, "crear"
    )


@router.post("/apu")
def crear(
    request: Request,
    usuario: CurrentUser,
    code: str = Form(...),
    name: str = Form(...),
    unit: str = Form(...),
    category: str = Form(""),
    unit_cost: str = Form(...),
    description: str = Form(""),
    session: Session = Depends(getSession),
):
    datos, error = _validar(_datosFormulario(
        code, name, unit, category, unit_cost, description
    ))

    if error is None and _codigoExistente(session, datos["code"]):
        error = "Ya existe un APU con ese código."

    if error:
        return _renderFormulario(
            request, usuario, datos, "crear", error, 400
        )

    nuevo = APU(**datos)
    session.add(nuevo)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return _renderFormulario(
            request,
            usuario,
            datos,
            "crear",
            "No se pudo guardar. Comprueba que el código no esté repetido.",
            400,
        )

    flash(request, "APU creado correctamente.", "success")
    return RedirectResponse(LISTA_URL, status_code=303)


# Editar APU
# ==========================================

@router.get("/apu/{apu_id}/editar")
def mostrarEdicion(
    apu_id: int,
    request: Request,
    usuario: CurrentUser,
    session: Session = Depends(getSession),
):
    apu = _buscar(session, apu_id)

    if apu is None:
        flash(request, "El APU solicitado no existe.", "error")
        return RedirectResponse(LISTA_URL, status_code=303)

    return _renderFormulario(
        request, usuario, apu, "editar"
    )


@router.post("/apu/{apu_id}")
def actualizar(
    apu_id: int,
    request: Request,
    usuario: CurrentUser,
    code: str = Form(...),
    name: str = Form(...),
    unit: str = Form(...),
    category: str = Form(""),
    unit_cost: str = Form(...),
    description: str = Form(""),
    session: Session = Depends(getSession),
):
    apu = _buscar(session, apu_id)

    if apu is None:
        flash(request, "El APU solicitado ya no existe.", "error")
        return RedirectResponse(LISTA_URL, status_code=303)

    datos, error = _validar(_datosFormulario(
        code, name, unit, category, unit_cost, description
    ))

    datos["id"] = apu_id

    if error is None and _codigoExistente(
        session, datos["code"], excluir_id=apu_id
    ):
        error = "Ya existe otro APU con ese código."

    if error:
        return _renderFormulario(
            request, usuario, datos, "editar", error, 400
        )

    for campo, valor in datos.items():
        if campo != "id":
            setattr(apu, campo, valor)

    apu.updated_at = datetime.now(timezone.utc)
    session.add(apu)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return _renderFormulario(
            request,
            usuario,
            datos,
            "editar",
            "No se pudieron guardar los cambios. Comprueba el código.",
            400,
        )

    flash(request, "APU actualizado correctamente.", "success")
    return RedirectResponse(LISTA_URL, status_code=303)


# Activar / desactivar APU
# ==========================================

@router.post("/apu/{apu_id}/estado")


@router.post("/apu/{apu_id}/estado")
def cambiarEstado(
    apu_id: int,
    request: Request,
    usuario: CurrentUser,
    q: str = Form(""),
    categoria: str = Form(""),
    estado: str = Form(""),
    pagina: int = Form(1),
    session: Session = Depends(getSession),
):
    apu = _buscar(session, apu_id)

    if apu is None:
        flash(request, "El APU solicitado no existe.", "error")
    else:
        apu.is_active = not apu.is_active
        apu.updated_at = datetime.now(timezone.utc)
        session.add(apu)
        session.commit()

        estado_actual = "activo" if apu.is_active else "inactivo"
        flash(
            request,
            f"El APU '{apu.code}' ahora está {estado_actual}.",
            "success",
        )

    filtros = {
        "q": q,
        "categoria": categoria,
        "estado": estado,
        "pagina": pagina,
    }

    parametros = urlencode({
        clave: valor
        for clave, valor in filtros.items()
        if valor not in ("", None)
    })

    destino = f"{LISTA_URL}?{parametros}" if parametros else LISTA_URL

    return RedirectResponse(
        f"{destino}#apu-{apu_id}",
        status_code=303,
    )
