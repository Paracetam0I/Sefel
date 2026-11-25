from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.calculos import (
    calcularSubtotales,
    costoVacio,
    costosDeApus,
    recalcularPresupuesto,
)
from app.core.db import getSession
from app.core.dependencies import CurrentUser, requireRoles
from app.core.permisos import ROLES_PRESUPUESTOS_EDICION
from app.core.flash import flash
from app.models.apu import APU
from app.models.detalle_presupuesto import DetallePresupuesto
from app.models.presupuesto import Presupuesto
from app.templates import templates


# Solo los roles que arman presupuestos pueden agregar ítems (y buscar APUs para ello)
router = APIRouter(
    tags=["items"],
    dependencies=[Depends(requireRoles(*ROLES_PRESUPUESTOS_EDICION))],
)

LISTA_URL = "/presupuestos"
MAX_RESULTADOS = 8


# Utilidades
# ==========================================

def _presupuestoDelUsuario(
    session: Session, presupuesto_id: int, usuario
) -> Presupuesto | None:
    """Devuelve el presupuesto. No hay exclusividad por creador: cualquier rol
    de edición (BUDGETS, BOTH, ADMIN) puede trabajar sobre cualquier presupuesto."""
    return session.get(Presupuesto, presupuesto_id)


def _entero(valor: str, minimo: int = 0) -> int | None:
    """Convierte texto a entero; None si no es un entero o es menor al mínimo."""
    try:
        numero = int(valor.strip())
    except (ValueError, AttributeError):
        return None
    return numero if numero >= minimo else None


def _itemsDelPresupuesto(session: Session, presupuesto: Presupuesto) -> list:
    """Ítems del presupuesto junto a su APU, para listarlos bajo el formulario."""
    return session.exec(
        select(DetallePresupuesto, APU)
        .join(APU, APU.id == DetallePresupuesto.id_apu)
        .where(DetallePresupuesto.id_presupuesto == presupuesto.id_presupuesto)
        .order_by(DetallePresupuesto.id)
    ).all()


def _costoApu(session: Session, apu: APU) -> dict:
    """CDU cotizado/real calculado con la receta del APU (y cuántos recursos tiene)."""
    return costosDeApus(session, [apu.id]).get(apu.id, costoVacio())


def _renderFormulario(
    request: Request,
    usuario,
    presupuesto: Presupuesto,
    datos: dict | None = None,
    apu: APU | None = None,
    error: str | None = None,
    status_code: int = 200,
    session: Session | None = None,
):
    return templates.TemplateResponse(
        request=request,
        name="item_nuevo.html",
        context={
            "usuario": usuario,
            "presupuesto": presupuesto,
            "datos": datos,
            "apu": apu,
            "costo": _costoApu(session, apu) if (session and apu) else None,
            "error": error,
            "items": _itemsDelPresupuesto(session, presupuesto) if session else [],
        },
        status_code=status_code,
    )


# Búsqueda y autocompletado de APU (fragmentos HTMX)
# ==========================================

@router.get("/api/apu/buscar")
def buscarApus(
    request: Request,
    session: Session = Depends(getSession),
    q: str = "",
):
    termino = q.strip().lower()

    consulta = select(APU).where(APU.is_active.is_(True))
    if termino:
        consulta = consulta.where(
            or_(
                func.lower(APU.code).contains(termino, autoescape=True),
                func.lower(APU.name).contains(termino, autoescape=True),
            )
        )

    apus = session.exec(consulta.order_by(APU.name).limit(MAX_RESULTADOS)).all()

    return templates.TemplateResponse(
        request=request,
        name="partials/apu/buscar_resultados.html",
        context={
            "apus": apus,
            "q": q.strip(),
            "costos": costosDeApus(session, [a.id for a in apus]),
            "costo_vacio": costoVacio(),
        },
    )


@router.get("/api/apu/{apu_id}/autocompletar")
def autocompletarApu(
    apu_id: int,
    request: Request,
    session: Session = Depends(getSession),
):
    apu = session.get(APU, apu_id)

    if apu is None or not apu.is_active:
        raise HTTPException(status_code=404, detail="APU no encontrado")

    return templates.TemplateResponse(
        request=request,
        name="partials/apu/autocompletar_campos.html",
        context={"apu": apu, "costo": _costoApu(session, apu)},
    )


# Agregar ítem
# ==========================================

@router.get("/presupuestos/{presupuesto_id}/items/nuevo")
def mostrarFormularioItem(
    presupuesto_id: int,
    request: Request,
    usuario: CurrentUser,
    session: Session = Depends(getSession),
):
    presupuesto = _presupuestoDelUsuario(session, presupuesto_id, usuario)
    if presupuesto is None:
        flash(request, "El presupuesto solicitado no existe.", "error")
        return RedirectResponse(LISTA_URL, status_code=303)

    return _renderFormulario(request, usuario, presupuesto, session=session)


@router.post("/presupuestos/{presupuesto_id}/items")
def crearItem(
    presupuesto_id: int,
    request: Request,
    usuario: CurrentUser,
    id_apu: str = Form(""),
    unit: str = Form(""),
    cantidad: str = Form("1"),
    costo_directo: str = Form("0"),
    costo_indirecto: str = Form("0"),
    descripcion: str = Form(""),
    session: Session = Depends(getSession),
):
    presupuesto = _presupuestoDelUsuario(session, presupuesto_id, usuario)
    if presupuesto is None:
        flash(request, "El presupuesto solicitado no existe.", "error")
        return RedirectResponse(LISTA_URL, status_code=303)

    # Lo que escribió la persona, para devolverlo si hay un error
    datos = {
        "unit": unit,
        "cantidad": cantidad,
        "costo_directo": costo_directo,
        "costo_indirecto": costo_indirecto,
        "descripcion": descripcion,
    }

    # Convertir y buscar (el navegador solo manda texto)
    apu_id = _entero(id_apu, 1)
    cant = _entero(cantidad, 1)
    directo = _entero(costo_directo)
    indirecto = _entero(costo_indirecto)
    unidad = unit.strip()

    apu = session.get(APU, apu_id) if apu_id else None
    apu_valido = apu if apu is not None and apu.is_active else None
    # El precio sale de la receta del APU (no se ingresa a mano)
    costo = _costoApu(session, apu_valido) if apu_valido else costoVacio()

    # Validar, un error a la vez
    error = None
    if apu_valido is None:
        error = "Selecciona un APU activo del catálogo."
    elif not costo["recursos"]:
        error = (
            "El APU no tiene recursos, así que su costo es $ 0. "
            "Agrégale recursos en su receta antes de usarlo en un presupuesto."
        )
    elif not unidad or len(unidad) > 30:
        error = "La unidad es obligatoria (máximo 30 caracteres)."
    elif cant is None:
        error = "La cantidad debe ser un entero mayor o igual a 1."
    elif directo is None or indirecto is None:
        error = "Los costos directo e indirecto deben ser enteros mayores o iguales a 0."
    elif len(descripcion.strip()) > 500:
        error = "La descripción no puede superar los 500 caracteres."

    if error:
        return _renderFormulario(
            request, usuario, presupuesto,
            datos=datos, apu=apu_valido, error=error, status_code=400,
            session=session,
        )

    item = DetallePresupuesto(
        id_presupuesto=presupuesto.id_presupuesto,
        id_apu=apu_valido.id,                  # trazabilidad: de qué APU salió
        unit=unidad,                           # copia editable: lo que mandó el formulario
        # Copia del CDU calculado del APU: si luego cambia el precio de un
        # recurso, el presupuesto no se mueve hasta "Actualizar precio"
        estimated_unit_cost=costo["unit_cost"],
        real_unit_cost=costo["real_unit_cost"],
        cantidad=cant,
        costo_directo=directo,
        costo_indirecto=indirecto,
        descripcion=descripcion.strip() or None,
    )
    calcularSubtotales(item)                   # subtotales los calcula el servidor
    session.add(item)
    session.flush()
    recalcularPresupuesto(session, presupuesto)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return _renderFormulario(
            request, usuario, presupuesto,
            datos=datos, apu=apu_valido,
            error="No se pudo guardar el ítem.", status_code=400,
            session=session,
        )

    flash(request, "Ítem agregado correctamente.", "success")
    return RedirectResponse(
        f"/presupuestos/{presupuesto.id_presupuesto}/items/nuevo",
        status_code=303,
    )


# Editar ítem (cantidad y costo real; el cotizado sale del APU)
# ==========================================

@router.post("/presupuestos/{presupuesto_id}/items/{item_id}")
def actualizarItem(
    presupuesto_id: int,
    item_id: int,
    request: Request,
    usuario: CurrentUser,
    cantidad: str = Form(...),
    real_unit_cost: str = Form(...),
    session: Session = Depends(getSession),
):
    presupuesto = _presupuestoDelUsuario(session, presupuesto_id, usuario)
    if presupuesto is None:
        flash(request, "El presupuesto solicitado no existe.", "error")
        return RedirectResponse(LISTA_URL, status_code=303)

    destino = f"/presupuestos/{presupuesto_id}/items/nuevo"
    item = session.get(DetallePresupuesto, item_id)
    if item is None or item.id_presupuesto != presupuesto.id_presupuesto:
        flash(request, "El ítem solicitado no existe.", "error")
        return RedirectResponse(destino, status_code=303)

    cant = _entero(cantidad, 1)
    costo_real = _entero(real_unit_cost)

    if cant is None:
        flash(request, "La cantidad debe ser un entero mayor o igual a 1.", "error")
    elif costo_real is None:
        flash(request, "El costo real debe ser un entero mayor o igual a 0.", "error")
    else:
        item.cantidad = cant
        item.real_unit_cost = costo_real
        calcularSubtotales(item)
        session.add(item)
        session.flush()
        recalcularPresupuesto(session, presupuesto)
        session.commit()
        flash(request, "Ítem actualizado correctamente.", "success")

    return RedirectResponse(f"{destino}#item-{item_id}", status_code=303)


# Actualizar el precio del ítem con el costo actual del APU
# ==========================================

@router.post("/presupuestos/{presupuesto_id}/items/{item_id}/actualizar-precio")
def actualizarPrecioItem(
    presupuesto_id: int,
    item_id: int,
    request: Request,
    usuario: CurrentUser,
    session: Session = Depends(getSession),
):
    """Vuelve a copiar el CDU (cotizado y real) desde la receta del APU.

    Sirve cuando cambió el precio de algún recurso en la Base de datos y se
    quiere llevar ese cambio al presupuesto. Reemplaza el costo real editado.
    """
    presupuesto = _presupuestoDelUsuario(session, presupuesto_id, usuario)
    if presupuesto is None:
        flash(request, "El presupuesto solicitado no existe.", "error")
        return RedirectResponse(LISTA_URL, status_code=303)

    destino = f"/presupuestos/{presupuesto_id}/items/nuevo"
    item = session.get(DetallePresupuesto, item_id)
    if item is None or item.id_presupuesto != presupuesto.id_presupuesto:
        flash(request, "El ítem solicitado no existe.", "error")
        return RedirectResponse(destino, status_code=303)

    apu = session.get(APU, item.id_apu)
    costo = _costoApu(session, apu) if apu is not None else costoVacio()
    if apu is None or not costo["recursos"]:
        flash(request, "El APU no tiene recursos: no hay un precio que copiar.", "error")
        return RedirectResponse(f"{destino}#item-{item_id}", status_code=303)

    item.estimated_unit_cost = costo["unit_cost"]
    item.real_unit_cost = costo["real_unit_cost"]
    calcularSubtotales(item)
    session.add(item)
    session.flush()
    recalcularPresupuesto(session, presupuesto)
    session.commit()

    flash(request, f"Precio actualizado con el costo actual del APU '{apu.code}'.", "success")
    return RedirectResponse(f"{destino}#item-{item_id}", status_code=303)
