
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from math import ceil
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from pydantic import ValidationError
from app.core.calculos import costoVacio, costosApu, costosDeApus
from app.core.db import getSession
from app.core.dependencies import CurrentUser, requireRoles
from app.core.flash import flash
from app.core.permisos import ROLES_APU
from app.core.validaciones import mensajeDe
from app.models.apu import APU, APUValidacion
from app.models.detalle_apu import DetalleApu
from app.models.material import Material
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
    description: str = "",
) -> dict:
    # Sin costos: el APU los calcula a partir de sus recursos
    return {
        "code": code,
        "name": name,
        "unit": unit,
        "category": category,
        "description": description,
    }



def _validar(datos: dict) -> tuple[dict, str | None]:
    datos_limpios = _datosFormulario(
        str(datos.get("code", "")),
        str(datos.get("name", "")),
        str(datos.get("unit", "")),
        str(datos.get("category", "")),
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

        if mensajeDe(error):
            # Regla de app/core/validaciones.py: su mensaje ya es el definitivo
            mensaje = mensajeDe(error)

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
    es_htmx: bool = False,
):
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
            # CDU calculado con los recursos de cada APU visible
            "costos": costosDeApus(session, [apu.id for apu in visibles]),
            "costo_vacio": costoVacio(),
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
    description: str = Form(""),
    session: Session = Depends(getSession),
):
    es_htmx = request.headers.get("HX-Request") == "true"

    datos, error = _validar(
        _datosFormulario(code, name, unit, category, description)
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
    description: str = Form(""),
    session: Session = Depends(getSession),
):
    es_htmx = request.headers.get("HX-Request") == "true"

    apu = _buscar(session, apu_id)

    if apu is None:
        flash(request, "El APU solicitado ya no existe.", "error")
        return RedirectResponse(LISTA_URL, status_code=303)

    datos, error = _validar(
        _datosFormulario(code, name, unit, category, description)
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


# Receta del APU: recursos de la base de datos con su cantidad
# ==========================================
# El costo del APU (CDU) = suma de cantidad × precio de cada recurso. Solo se
# pueden agregar recursos ACTIVOS; un recurso aparece una vez por APU.

MAX_RESULTADOS_RECURSOS = 8
CANTIDAD_MAXIMA = 1_000_000
DECIMALES_CANTIDAD = 4


def _urlReceta(apu_id: int) -> str:
    return f"/apu/{apu_id}"


def _cantidad(texto: str) -> float | None:
    """'0,35' o '0.35' -> 0.35. None si no es un número > 0 razonable."""
    try:
        valor = Decimal(texto.strip().replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None
    if not valor.is_finite() or valor <= 0 or valor > CANTIDAD_MAXIMA:
        return None
    valor = round(valor, DECIMALES_CANTIDAD)
    return float(valor) if valor > 0 else None


def _unidad(texto: str) -> str | None:
    unidad = texto.strip()
    return unidad if unidad and len(unidad) <= 30 else None


def _contextoReceta(session: Session, apu: APU, **extra) -> dict:
    return {
        "apu": apu,
        "costos": costosApu(session, apu),
        "error": None,
        "seleccionado": None,
        "datos": None,
        **extra,
    }


def _renderReceta(
    request: Request,
    usuario,
    session: Session,
    apu: APU,
    *,
    parcial: bool,
    status_code: int = 200,
    **extra,
):
    return templates.TemplateResponse(
        request=request,
        name="partials/apu/receta.html" if parcial else "apu/receta.html",
        status_code=status_code,
        context={"usuario": usuario, **_contextoReceta(session, apu, **extra)},
    )


def _respuestaReceta(
    request: Request,
    usuario,
    session: Session,
    apu: APU,
    *,
    error: str | None = None,
    **extra,
):
    """HTMX: devuelve la receta actualizada (con el error, si lo hay).
    Navegador: aviso flash y vuelta a la página del APU."""
    if request.headers.get("HX-Request") == "true":
        return _renderReceta(
            request, usuario, session, apu, parcial=True, error=error, **extra,
        )
    if error:
        flash(request, error, "error")
    return RedirectResponse(_urlReceta(apu.id), status_code=303)


def _marcarApuActualizado(session: Session, apu: APU) -> None:
    # Cambiar la receta cambia el costo del APU
    apu.updated_at = datetime.now(timezone.utc)
    session.add(apu)


@router.get("/apu/{apu_id}")
def verReceta(
    apu_id: int,
    request: Request,
    usuario: CurrentUser,
    session: Session = Depends(getSession),
):
    apu = _buscar(session, apu_id)
    if apu is None:
        flash(request, "El APU solicitado no existe.", "error")
        return RedirectResponse(LISTA_URL, status_code=303)

    return _renderReceta(
        request, usuario, session, apu,
        parcial=request.headers.get("HX-Request") == "true",
    )


@router.get("/apu/{apu_id}/recursos/buscar")
def buscarRecursos(
    apu_id: int,
    request: Request,
    session: Session = Depends(getSession),
    q: str = "",
):
    """Recursos ACTIVOS que todavía no están en la receta."""
    termino = q.strip().lower()
    ya_en_receta = select(DetalleApu.id_material).where(DetalleApu.id_apu == apu_id)

    consulta = select(Material).where(
        Material.is_active.is_(True),
        Material.id.not_in(ya_en_receta),
    )
    if termino:
        consulta = consulta.where(
            or_(
                func.lower(Material.code).contains(termino, autoescape=True),
                func.lower(Material.name).contains(termino, autoescape=True),
            )
        )

    materiales = session.exec(
        consulta.order_by(Material.category, Material.name).limit(MAX_RESULTADOS_RECURSOS)
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="partials/apu/recursos_buscar.html",
        context={"materiales": materiales, "q": q.strip(), "apu_id": apu_id},
    )


@router.get("/apu/{apu_id}/recursos/seleccionar/{material_id}")
def seleccionarRecurso(
    apu_id: int,
    material_id: int,
    request: Request,
    session: Session = Depends(getSession),
):
    material = session.get(Material, material_id)
    if material is None or not material.is_active:
        raise HTTPException(status_code=404, detail="Recurso no encontrado")

    return templates.TemplateResponse(
        request=request,
        name="partials/apu/recurso_seleccionado.html",
        context={"seleccionado": material, "datos": None},
    )


@router.post("/apu/{apu_id}/recursos")
def agregarRecurso(
    apu_id: int,
    request: Request,
    usuario: CurrentUser,
    id_material: str = Form(""),
    cantidad: str = Form(""),
    unit: str = Form(""),
    session: Session = Depends(getSession),
):
    apu = _buscar(session, apu_id)
    if apu is None:
        flash(request, "El APU solicitado no existe.", "error")
        return RedirectResponse(LISTA_URL, status_code=303)

    material = session.get(Material, int(id_material)) if id_material.strip().isdigit() else None
    consumo = _cantidad(cantidad)
    unidad = _unidad(unit) if unit.strip() else (material.unit if material else None)
    datos = {"cantidad": cantidad, "unit": unit}

    error = None
    if material is None:
        error = "Selecciona un recurso de la base de datos."
    elif not material.is_active:
        error = "El recurso está inactivo: no se puede agregar a un APU."
    elif session.exec(
        select(DetalleApu).where(
            DetalleApu.id_apu == apu.id, DetalleApu.id_material == material.id
        )
    ).first() is not None:
        error = "Ese recurso ya está en la receta: edita su cantidad."
    elif consumo is None:
        error = "La cantidad debe ser un número mayor que 0 (puede tener decimales)."
    elif unidad is None:
        error = "La unidad es obligatoria (máximo 30 caracteres)."

    if error:
        seleccionado = material if material is not None and material.is_active else None
        return _respuestaReceta(
            request, usuario, session, apu,
            error=error, seleccionado=seleccionado, datos=datos,
        )

    session.add(DetalleApu(
        id_apu=apu.id, id_material=material.id, unit=unidad, cantidad=consumo,
    ))
    _marcarApuActualizado(session, apu)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return _respuestaReceta(
            request, usuario, session, apu,
            error="No se pudo agregar el recurso. Revisa que no esté repetido.",
        )

    session.refresh(apu)
    flash(request, f"Recurso '{material.code}' agregado al APU.", "success")
    return _respuestaReceta(request, usuario, session, apu)


def _lineaDeApu(session: Session, apu: APU, detalle_id: int) -> DetalleApu | None:
    detalle = session.get(DetalleApu, detalle_id)
    if detalle is None or detalle.id_apu != apu.id:
        return None
    return detalle


@router.post("/apu/{apu_id}/recursos/{detalle_id}")
def actualizarRecurso(
    apu_id: int,
    detalle_id: int,
    request: Request,
    usuario: CurrentUser,
    cantidad: str = Form(""),
    unit: str = Form(""),
    session: Session = Depends(getSession),
):
    apu = _buscar(session, apu_id)
    if apu is None:
        flash(request, "El APU solicitado no existe.", "error")
        return RedirectResponse(LISTA_URL, status_code=303)

    detalle = _lineaDeApu(session, apu, detalle_id)
    consumo = _cantidad(cantidad)
    unidad = _unidad(unit)

    if detalle is None:
        return _respuestaReceta(request, usuario, session, apu, error="El recurso ya no está en la receta.")
    if consumo is None:
        return _respuestaReceta(
            request, usuario, session, apu,
            error="La cantidad debe ser un número mayor que 0 (puede tener decimales).",
        )
    if unidad is None:
        return _respuestaReceta(
            request, usuario, session, apu,
            error="La unidad es obligatoria (máximo 30 caracteres).",
        )

    detalle.cantidad = consumo
    detalle.unit = unidad
    detalle.updated_at = datetime.now(timezone.utc)
    session.add(detalle)
    _marcarApuActualizado(session, apu)
    session.commit()
    session.refresh(apu)

    flash(request, "Cantidad actualizada.", "success")
    return _respuestaReceta(request, usuario, session, apu)


@router.post("/apu/{apu_id}/recursos/{detalle_id}/eliminar")
def quitarRecurso(
    apu_id: int,
    detalle_id: int,
    request: Request,
    usuario: CurrentUser,
    session: Session = Depends(getSession),
):
    """Quita la línea de la receta. El recurso sigue en la base de datos."""
    apu = _buscar(session, apu_id)
    if apu is None:
        flash(request, "El APU solicitado no existe.", "error")
        return RedirectResponse(LISTA_URL, status_code=303)

    detalle = _lineaDeApu(session, apu, detalle_id)
    if detalle is None:
        return _respuestaReceta(request, usuario, session, apu, error="El recurso ya no está en la receta.")

    session.delete(detalle)
    _marcarApuActualizado(session, apu)
    session.commit()
    session.refresh(apu)

    flash(request, "Recurso quitado del APU.", "success")
    return _respuestaReceta(request, usuario, session, apu)
