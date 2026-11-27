"""
apu.py — Catálogo de APU: listar, crear, editar y activar/desactivar.

EN SIMPLE
    Es la pantalla del "catálogo de precios". Se ve una tabla de APU con
    buscador y filtros, tarjetas de resumen arriba y un botón para crear uno
    nuevo. Crear y editar se hace en una ventana emergente (modal) sin
    recargar la página. Los APU no se borran: se desactivan.

TÉCNICO
    Rutas (todas exigen ROLES_APU, puesto en el router):
      GET  /apu                 -> lista (página completa o solo la tabla si es HTMX)
      GET  /apu/nuevo           -> formulario de creación
      POST /apu                 -> crear
      GET  /apu/{id}/editar     -> formulario de edición
      POST /apu/{id}            -> guardar edición
      POST /apu/{id}/estado     -> activar/desactivar
    Cada ruta funciona en dos modos:
      - HTMX (el modal): responde un fragmento y usa cabeceras HX-* para
        decir dónde insertarlo y cuándo cerrar el modal.
      - Normal (sin JavaScript): página completa + redirección 303.
"""

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
from app.core.dependencies import CurrentUser, requireRoles
from app.core.flash import flash
from app.core.permisos import ROLES_APU
from app.core.validaciones import mensajeDe
from app.models.apu import APU, APUValidacion
from app.templates import templates


# Solo MATERIALS, BOTH y ADMIN: el resto recibe 403 (igual que admin/users)
router = APIRouter(
    tags=["apu"],
    dependencies=[Depends(requireRoles(*ROLES_APU))],
)

APUS_POR_PAGINA = 10
LISTA_URL = "/apu"


# Utilidades
# ==========================================

def _buscar(session: Session, apu_id: int) -> APU | None:
    """APU por id (clave primaria), o None si no existe."""
    return session.get(APU, apu_id)


def _resumen(todos: list[APU]) -> dict:
    """Números de las tarjetas superiores: registrados, activos, inactivos y
    actualizados en los últimos 30 días (con su texto descriptivo)."""
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
    """Filtra la lista por texto (código o nombre), categoría y estado.

    casefold() es como lower() pero más completo para comparar sin
    distinguir mayúsculas (p. ej. la "ß" alemana).
    """
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
    real_unit_cost: str | int = "",
) -> dict:
    """Empaqueta los campos del formulario en un dict (mismo orden en todo el módulo)."""
    return {
        "code": code,
        "name": name,
        "unit": unit,
        "category": category,
        "unit_cost": unit_cost,
        "description": description,
        "real_unit_cost": real_unit_cost,
    }



def _validar(datos: dict) -> tuple[dict, str | None]:
    """Valida los datos del formulario con APUValidacion.

    Devuelve (datos, None) si todo está bien, o (datos_escritos, mensaje) con
    el PRIMER error traducido a un mensaje en español.

    En simple: pydantic revisa los datos y, si algo está mal, entrega un error
    técnico como {"loc": ("unit_cost",), "type": "int_parsing"}. Aquí se
    convierte eso en "El precio unitario debe ser un número entero."
    """
    datos_limpios = _datosFormulario(
        str(datos.get("code", "")),
        str(datos.get("name", "")),
        str(datos.get("unit", "")),
        str(datos.get("category", "")),
        datos.get("unit_cost", ""),
        str(datos.get("description", "")),
        datos.get("real_unit_cost", ""),
    )

    # Si no se indica costo real, parte igual al cotizado
    if str(datos_limpios["real_unit_cost"]).strip() == "":
        datos_limpios["real_unit_cost"] = datos_limpios["unit_cost"]

    try:
        apu_validado = APUValidacion.model_validate(datos_limpios)


    except ValidationError as exc:
        error = exc.errors()[0]   # solo el primer error: se muestra uno a la vez
        campo = error["loc"][0]   # qué campo falló
        tipo = error["type"]      # por qué (int_parsing, string_too_long, value_error...)

        nombres = {
            "code": ("El código", 50),
            "name": ("El nombre", 150),
            "unit": ("La unidad", 30),
            "category": ("La categoría", 100),
        }

        if mensajeDe(error):
            # Regla de app/core/validaciones.py: su mensaje ya es el definitivo
            mensaje = mensajeDe(error)

        elif campo == "unit_cost":
            if tipo == "int_parsing":
                mensaje = "El precio unitario debe ser un número entero."
            else:
                mensaje = "El precio unitario no puede ser negativo."

        elif campo == "real_unit_cost":
            if tipo == "int_parsing":
                mensaje = "El costo real debe ser un número entero."
            else:
                mensaje = "El costo real no puede ser negativo."

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
    """True si ya hay un APU con ese código (sin distinguir mayúsculas).

    excluir_id: al editar, se ignora el propio APU (si no, siempre "chocaría"
    consigo mismo).
    """
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
    es_htmx: bool = False,
):
    """Formulario de APU: solo el fragmento (para el modal HTMX) o la página completa.

    `apu` puede ser un objeto APU (editar) o un dict con lo escrito (tras un error).
    """
    return templates.TemplateResponse(
        request=request,
        name=(
    "partials/apu/formulario.html"
    if es_htmx
    else "apu/formulario.html"),
        status_code=status_code,
        context={
            "usuario": usuario,
            "apu": apu,
            "modo": modo,
            "error": error,
        },
    )


def _paginaDe(registros: list, registro_id: int | None, por_pagina: int) -> int | None:
    """Página en la que queda un registro (para mostrar el recién creado/editado)."""
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
    es_htmx: bool = False,
    resaltar_id: int | None = None,
):
    """Dibuja el listado (página completa, o solo la tabla si es HTMX).

    resaltar_id: id del APU recién creado/editado; se salta a la página donde
    quedó y la plantilla lo resalta.
    """
    # Lo más reciente primero: un APU recién creado aparece arriba de la página 1
    todos = session.exec(
        select(APU).order_by(APU.created_at.desc(), APU.id.desc())
    ).all()
    filtrados = _filtrar(todos, q, categoria, estado)

    total = len(filtrados)
    paginas = max(1, ceil(total / APUS_POR_PAGINA))
    pagina = _paginaDe(filtrados, resaltar_id, APUS_POR_PAGINA) or pagina
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

    nombre_plantilla = (
        "partials/apu/tabla.html"
        if es_htmx
        else "apu.html"
    )

    return templates.TemplateResponse(
        request=request,
        name=nombre_plantilla,
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
            "resaltar_id": resaltar_id,
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
    """GET /apu. Al filtrar o paginar, HTMX pide solo la tabla (no la página entera)."""
    return _renderLista(
        request,
        usuario,
        session,
        q=q,
        categoria=categoria,
        estado=estado,
        pagina=pagina,
        es_htmx=request.headers.get("HX-Request") == "true",
    )


# Crear APU
# ==========================================

@router.get("/apu/nuevo")
def mostrarFormulario(
    request: Request,
    usuario: CurrentUser,
):
    """GET /apu/nuevo: formulario vacío."""
    return _renderFormulario(
        request,
        usuario,
        None,
        "crear",
        es_htmx=request.headers.get("HX-Request") == "true",
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
    real_unit_cost: str = Form(""),
    session: Session = Depends(getSession),
):
    """POST /apu: valida, revisa código repetido y guarda.

    Con HTMX los errores responden 200 (no 400) porque HTMX, por defecto, no
    inserta respuestas con código de error y el usuario no vería el mensaje.
    El IntegrityError es la segunda barrera: si dos personas crean el mismo
    código a la vez, el índice único de la BD rechaza el segundo.
    """
    es_htmx = request.headers.get("HX-Request") == "true"

    datos, error = _validar(
        _datosFormulario(
            code, name, unit, category, unit_cost, description,
            real_unit_cost,
        )
    )

    if error is None and _codigoExistente(session, datos["code"]):
        error = "Ya existe un APU con ese código."

    if error:
        return _renderFormulario(
            request,
            usuario,
            datos,
            "crear",
            error,
            200 if es_htmx else 400,
            es_htmx=es_htmx,
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
            200 if es_htmx else 400,
            es_htmx=es_htmx,
        )

    flash(request, "APU creado correctamente.", "success")

    if es_htmx:
        respuesta = _renderLista(
            request,
            usuario,
            session,
            es_htmx=True,
            resaltar_id=nuevo.id,
        )
        # El formulario apuntaba al modal; con estas cabeceras la respuesta
        # (la tabla actualizada) se inserta en #contenido-apu en su lugar.
        respuesta.headers["HX-Retarget"] = "#contenido-apu"
        respuesta.headers["HX-Reswap"] = "innerHTML"
        # Cerrar el modal DESPUÉS del swap: si se cierra antes, vacía el formulario
        # que hizo la petición y HTMX descarta el reemplazo del listado
        respuesta.headers["HX-Trigger-After-Settle"] = "cerrar-modal-apu"
        return respuesta

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
    """GET /apu/{id}/editar: formulario con los datos actuales del APU."""
    apu = _buscar(session, apu_id)

    if apu is None:
        flash(request, "El APU solicitado no existe.", "error")
        return RedirectResponse(LISTA_URL, status_code=303)

    return _renderFormulario(
        request,
        usuario,
        apu,
        "editar",
        es_htmx=request.headers.get("HX-Request") == "true",
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
    real_unit_cost: str = Form(""),
    session: Session = Depends(getSession),
):
    """POST /apu/{id}: igual que crear(), pero sobre un APU existente.

    Cambiar el precio de un APU NO cambia los presupuestos ya armados: sus
    ítems guardaron una copia del precio (ver DetallePresupuesto).
    """
    es_htmx = request.headers.get("HX-Request") == "true"

    apu = _buscar(session, apu_id)

    if apu is None:
        flash(request, "El APU solicitado ya no existe.", "error")
        return RedirectResponse(LISTA_URL, status_code=303)

    datos, error = _validar(
        _datosFormulario(
            code, name, unit, category, unit_cost, description,
            real_unit_cost,
        )
    )

    datos["id"] = apu_id

    if error is None and _codigoExistente(
        session, datos["code"], excluir_id=apu_id
    ):
        error = "Ya existe otro APU con ese código."

    if error:
        return _renderFormulario(
            request,
            usuario,
            datos,
            "editar",
            error,
            200 if es_htmx else 400,
            es_htmx=es_htmx,
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
            200 if es_htmx else 400,
            es_htmx=es_htmx,
        )

    flash(request, "APU actualizado correctamente.", "success")

    if es_htmx:
        respuesta = _renderLista(
            request,
            usuario,
            session,
            es_htmx=True,
            resaltar_id=apu.id,
        )
        respuesta.headers["HX-Retarget"] = "#contenido-apu"
        respuesta.headers["HX-Reswap"] = "innerHTML"
        # Cerrar el modal DESPUÉS del swap: si se cierra antes, vacía el formulario
        # que hizo la petición y HTMX descarta el reemplazo del listado
        respuesta.headers["HX-Trigger-After-Settle"] = "cerrar-modal-apu"
        return respuesta

    return RedirectResponse(LISTA_URL, status_code=303)


# Activar / desactivar APU
# ==========================================

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
    """POST /apu/{id}/estado: invierte activo <-> inactivo.

    Recibe los filtros y la página actuales para volver a la misma vista de
    la tabla. Un APU inactivo no aparece en el buscador al agregar ítems.
    """
    es_htmx = request.headers.get("HX-Request") == "true"
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

    if es_htmx:
        respuesta = _renderLista(
            request,
            usuario,
            session,
            q=q,
            categoria=categoria,
            estado=estado,
            pagina=pagina,
            es_htmx=True,
        )
        respuesta.headers["HX-Retarget"] = "#contenido-apu"
        respuesta.headers["HX-Reswap"] = "innerHTML"
        return respuesta

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
