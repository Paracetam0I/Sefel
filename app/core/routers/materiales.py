"""Pestaña "Base de datos": recursos (materiales, mano de obra, equipos y
herramientas) con su precio unitario. Los APU se arman con estos recursos.

Las categorías son FIJAS (app.models.material.CategoriaRecurso). Un recurso no
se elimina: se desactiva, y un recurso inactivo no se puede agregar a un APU.
"""
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
from app.core.dependencies import CurrentUser, requireRoles
from app.core.flash import flash
from app.core.permisos import ROLES_MATERIALES
from app.core.validaciones import mensajeDe
from app.models.detalle_apu import DetalleApu
from app.models.material import (
    CATEGORIAS_RECURSO,
    LARGO_CODIGO,
    LARGO_DESCRIPCION,
    LARGO_NOMBRE,
    LARGO_UNIDAD,
    Material,
    MaterialValidacion,
)
from app.templates import templates


# Solo MATERIALS, BOTH y ADMIN: el resto recibe 403
router = APIRouter(
    tags=["base-datos"],
    dependencies=[Depends(requireRoles(*ROLES_MATERIALES))],
)

MATERIALES_POR_PAGINA = 10
LISTA_URL = "/base-datos"
CONTENEDOR = "#contenido-base-datos"
EVENTO_CERRAR_MODAL = "cerrar-modal-material"

CAMPOS = ("code", "name", "unit", "category", "unit_cost", "real_unit_cost", "description")


# Utilidades
# ==========================================

def _esHtmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _resumen(todos: list[Material]) -> dict:
    ahora = datetime.now(timezone.utc)
    activos = sum(1 for m in todos if m.is_active)

    actualizados = 0
    for material in todos:
        fecha = material.updated_at
        if fecha is not None:
            if fecha.tzinfo is None:
                fecha = fecha.replace(tzinfo=timezone.utc)
            if ahora - fecha <= timedelta(days=30):
                actualizados += 1

    return {
        "registrados": len(todos),
        "activos": activos,
        "inactivos": len(todos) - activos,
        "actualizados": actualizados,
    }


def _filtrar(todos: list[Material], q: str, categoria: str, estado: str) -> list[Material]:
    texto = q.strip().casefold()
    resultado = []
    for material in todos:
        if texto and texto not in f"{material.code} {material.name}".casefold():
            continue
        if categoria and material.category.value != categoria:
            continue
        if estado == "activo" and not material.is_active:
            continue
        if estado == "inactivo" and material.is_active:
            continue
        resultado.append(material)
    return resultado


def _datosFormulario(**valores) -> dict:
    return {campo: valores.get(campo, "") for campo in CAMPOS}


def _validar(datos: dict) -> tuple[dict, str | None]:
    datos_limpios = _datosFormulario(**datos)

    # Si no se indica costo real, parte igual al cotizado
    if str(datos_limpios["real_unit_cost"]).strip() == "":
        datos_limpios["real_unit_cost"] = datos_limpios["unit_cost"]

    try:
        validado = MaterialValidacion.model_validate(datos_limpios)
    except ValidationError as exc:
        error = exc.errors()[0]
        campo = error["loc"][0]
        tipo = error["type"]

        nombres = {
            "code": ("El código", LARGO_CODIGO),
            "name": ("El nombre", LARGO_NOMBRE),
            "unit": ("La unidad", LARGO_UNIDAD),
            "description": ("La descripción", LARGO_DESCRIPCION),
        }

        if mensajeDe(error):
            mensaje = mensajeDe(error)
        elif campo == "category":
            mensaje = "Selecciona una categoría: " + ", ".join(CATEGORIAS_RECURSO) + "."
        elif campo in ("unit_cost", "real_unit_cost"):
            nombre = "El precio unitario" if campo == "unit_cost" else "El costo real"
            if tipo == "int_parsing":
                mensaje = f"{nombre} debe ser un número entero."
            else:
                mensaje = f"{nombre} no puede ser negativo."
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

    return validado.model_dump(), None


def _codigoExistente(session: Session, code: str, excluir_id: int | None = None) -> bool:
    consulta = select(Material).where(func.lower(Material.code) == code.casefold())
    if excluir_id is not None:
        consulta = consulta.where(Material.id != excluir_id)
    return session.exec(consulta).first() is not None


def _usosPorMaterial(session: Session) -> dict[int, int]:
    """En cuántos APU se usa cada recurso."""
    return dict(session.exec(
        select(DetalleApu.id_material, func.count(DetalleApu.id))
        .group_by(DetalleApu.id_material)
    ).all())


def _renderFormulario(
    request: Request,
    usuario,
    material,
    modo: str,
    error: str | None = None,
    status_code: int = 200,
):
    es_htmx = _esHtmx(request)
    return templates.TemplateResponse(
        request=request,
        name="partials/base_datos/formulario.html" if es_htmx else "base_datos/formulario.html",
        status_code=status_code,
        context={
            "usuario": usuario,
            "material": material,
            "modo": modo,
            "error": error,
            "categorias_recurso": CATEGORIAS_RECURSO,
        },
    )


def _paginaDe(registros: list, registro_id: int | None, por_pagina: int) -> int | None:
    if registro_id is None:
        return None
    for posicion, registro in enumerate(registros):
        if registro.id == registro_id:
            return posicion // por_pagina + 1
    return None


def _renderLista(
    request: Request,
    usuario,
    session: Session,
    *,
    q: str = "",
    categoria: str = "",
    estado: str = "",
    pagina: int = 1,
    parcial: bool = False,
    resaltar_id: int | None = None,
):
    todos = session.exec(
        select(Material).order_by(Material.created_at.desc(), Material.id.desc())
    ).all()
    filtrados = _filtrar(todos, q, categoria, estado)

    total = len(filtrados)
    paginas = max(1, ceil(total / MATERIALES_POR_PAGINA))
    pagina = _paginaDe(filtrados, resaltar_id, MATERIALES_POR_PAGINA) or pagina
    pagina = min(max(pagina, 1), paginas)

    inicio = (pagina - 1) * MATERIALES_POR_PAGINA
    visibles = filtrados[inicio:inicio + MATERIALES_POR_PAGINA]

    filtros = {k: v for k, v in {"q": q, "categoria": categoria, "estado": estado}.items() if v}
    base_url = LISTA_URL + "?" + (urlencode(filtros) + "&" if filtros else "")

    return templates.TemplateResponse(
        request=request,
        name="partials/base_datos/tabla.html" if parcial else "base_datos.html",
        context={
            "usuario": usuario,
            "materiales": visibles,
            "usos": _usosPorMaterial(session),
            "resumen": _resumen(todos),
            "categorias_recurso": CATEGORIAS_RECURSO,
            "q": q,
            "categoria": categoria,
            "estado": estado,
            "total": total,
            "desde": inicio + 1 if total else 0,
            "hasta": inicio + len(visibles),
            "pagina": pagina,
            "paginas": paginas,
            "base_url": base_url,
            "resaltar_id": resaltar_id,
        },
    )


def _respuestaGuardado(request: Request, usuario, session: Session, material: Material):
    """Tras crear/editar: HTMX recibe el listado (y cierra el modal); el navegador, un redirect."""
    if _esHtmx(request):
        respuesta = _renderLista(
            request, usuario, session, parcial=True, resaltar_id=material.id,
        )
        respuesta.headers["HX-Retarget"] = CONTENEDOR
        respuesta.headers["HX-Reswap"] = "innerHTML"
        # Cerrar el modal DESPUÉS del swap (ver la nota en routers/apu.py)
        respuesta.headers["HX-Trigger-After-Settle"] = EVENTO_CERRAR_MODAL
        return respuesta
    return RedirectResponse(LISTA_URL, status_code=303)


# Listado
# ==========================================

@router.get("/base-datos")
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
        request, usuario, session,
        q=q, categoria=categoria, estado=estado, pagina=pagina,
        parcial=_esHtmx(request),
    )


# Crear
# ==========================================

@router.get("/base-datos/nuevo")
def mostrarFormulario(request: Request, usuario: CurrentUser):
    return _renderFormulario(request, usuario, None, "crear")


@router.post("/base-datos")
def crear(
    request: Request,
    usuario: CurrentUser,
    code: str = Form(...),
    name: str = Form(...),
    unit: str = Form(...),
    category: str = Form(""),
    unit_cost: str = Form(...),
    real_unit_cost: str = Form(""),
    description: str = Form(""),
    session: Session = Depends(getSession),
):
    codigo_status = 200 if _esHtmx(request) else 400
    datos, error = _validar(_datosFormulario(
        code=code, name=name, unit=unit, category=category,
        unit_cost=unit_cost, real_unit_cost=real_unit_cost, description=description,
    ))

    if error is None and _codigoExistente(session, datos["code"]):
        error = "Ya existe un recurso con ese código."

    if error:
        return _renderFormulario(request, usuario, datos, "crear", error, codigo_status)

    nuevo = Material(**datos)
    session.add(nuevo)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return _renderFormulario(
            request, usuario, datos, "crear",
            "No se pudo guardar. Comprueba que el código no esté repetido.", codigo_status,
        )

    flash(request, "Recurso creado correctamente.", "success")
    return _respuestaGuardado(request, usuario, session, nuevo)


# Editar
# ==========================================

@router.get("/base-datos/{material_id}/editar")
def mostrarEdicion(
    material_id: int,
    request: Request,
    usuario: CurrentUser,
    session: Session = Depends(getSession),
):
    material = session.get(Material, material_id)
    if material is None:
        flash(request, "El recurso solicitado no existe.", "error")
        return RedirectResponse(LISTA_URL, status_code=303)
    return _renderFormulario(request, usuario, material, "editar")


@router.post("/base-datos/{material_id}")
def actualizar(
    material_id: int,
    request: Request,
    usuario: CurrentUser,
    code: str = Form(...),
    name: str = Form(...),
    unit: str = Form(...),
    category: str = Form(""),
    unit_cost: str = Form(...),
    real_unit_cost: str = Form(""),
    description: str = Form(""),
    session: Session = Depends(getSession),
):
    codigo_status = 200 if _esHtmx(request) else 400
    material = session.get(Material, material_id)
    if material is None:
        flash(request, "El recurso solicitado ya no existe.", "error")
        return RedirectResponse(LISTA_URL, status_code=303)

    datos, error = _validar(_datosFormulario(
        code=code, name=name, unit=unit, category=category,
        unit_cost=unit_cost, real_unit_cost=real_unit_cost, description=description,
    ))
    datos["id"] = material_id

    if error is None and _codigoExistente(session, datos["code"], excluir_id=material_id):
        error = "Ya existe otro recurso con ese código."

    if error:
        return _renderFormulario(request, usuario, datos, "editar", error, codigo_status)

    for campo, valor in datos.items():
        if campo != "id":
            setattr(material, campo, valor)
    material.updated_at = datetime.now(timezone.utc)
    session.add(material)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return _renderFormulario(
            request, usuario, datos, "editar",
            "No se pudieron guardar los cambios. Comprueba el código.", codigo_status,
        )

    # Los APU calculan su costo en vivo: el cambio de precio se refleja solo.
    # Los presupuestos guardan una copia y no cambian.
    flash(request, "Recurso actualizado correctamente.", "success")
    return _respuestaGuardado(request, usuario, session, material)


# Activar / desactivar (no se elimina: RN-07)
# ==========================================

@router.post("/base-datos/{material_id}/estado")
def cambiarEstado(
    material_id: int,
    request: Request,
    usuario: CurrentUser,
    q: str = Form(""),
    categoria: str = Form(""),
    estado: str = Form(""),
    pagina: int = Form(1),
    session: Session = Depends(getSession),
):
    material = session.get(Material, material_id)

    if material is None:
        flash(request, "El recurso solicitado no existe.", "error")
    else:
        material.is_active = not material.is_active
        material.updated_at = datetime.now(timezone.utc)
        session.add(material)
        session.commit()
        estado_actual = "activo" if material.is_active else "inactivo"
        flash(request, f"El recurso '{material.code}' ahora está {estado_actual}.", "success")

    if _esHtmx(request):
        respuesta = _renderLista(
            request, usuario, session,
            q=q, categoria=categoria, estado=estado, pagina=pagina, parcial=True,
        )
        respuesta.headers["HX-Retarget"] = CONTENEDOR
        respuesta.headers["HX-Reswap"] = "innerHTML"
        return respuesta

    parametros = urlencode({
        clave: valor
        for clave, valor in {"q": q, "categoria": categoria, "estado": estado, "pagina": pagina}.items()
        if valor not in ("", None)
    })
    destino = f"{LISTA_URL}?{parametros}" if parametros else LISTA_URL
    return RedirectResponse(f"{destino}#material-{material_id}", status_code=303)
