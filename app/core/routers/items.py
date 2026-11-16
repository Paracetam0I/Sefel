from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.calculos import calcularSubtotales, recalcularPresupuesto
from app.core.db import getSession
from app.core.dependencies import CurrentUser, requireRoles
from app.core.flash import flash
from app.models.apu import APU
from app.models.detalle_presupuesto import DetallePresupuesto
from app.models.presupuesto import Presupuesto
from app.models.user import UserRole
from app.templates import templates


# Solo los roles que arman presupuestos pueden agregar ítems (y buscar APUs para ello)
router = APIRouter(
    tags=["items"],
    dependencies=[
        Depends(requireRoles(UserRole.ADMIN, UserRole.BUDGETS, UserRole.BOTH))
    ],
)

LISTA_URL = "/presupuestos"
MAX_RESULTADOS = 8


# Utilidades
# ==========================================

def _presupuestoDelUsuario(
    session: Session, presupuesto_id: int, usuario
) -> Presupuesto | None:
    """Devuelve el presupuesto solo si pertenece al usuario actual."""
    presupuesto = session.get(Presupuesto, presupuesto_id)
    if presupuesto is None or presupuesto.id_usuario != usuario.id:
        return None
    return presupuesto


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
        context={"apus": apus, "q": q.strip()},
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
        context={"apu": apu},
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
    estimated_unit_cost: str = Form(""),
    real_unit_cost: str = Form(""),
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
        "estimated_unit_cost": estimated_unit_cost,
        "real_unit_cost": real_unit_cost,
        "cantidad": cantidad,
        "costo_directo": costo_directo,
        "costo_indirecto": costo_indirecto,
        "descripcion": descripcion,
    }

    # Convertir y buscar (el navegador solo manda texto)
    apu_id = _entero(id_apu, 1)
    costo_estimado = _entero(estimated_unit_cost)
    # Vacío = parte igual al costo cotizado
    costo_real = (
        _entero(real_unit_cost) if real_unit_cost.strip() else costo_estimado
    )
    cant = _entero(cantidad, 1)
    directo = _entero(costo_directo)
    indirecto = _entero(costo_indirecto)
    unidad = unit.strip()

    apu = session.get(APU, apu_id) if apu_id else None
    apu_valido = apu if apu is not None and apu.is_active else None

    # Validar, un error a la vez
    error = None
    if apu_valido is None:
        error = "Selecciona un APU activo del catálogo."
    elif not unidad or len(unidad) > 30:
        error = "La unidad es obligatoria (máximo 30 caracteres)."
    elif costo_estimado is None:
        error = "El costo unitario debe ser un entero mayor o igual a 0."
    elif costo_real is None:
        error = "El costo real unitario debe ser un entero mayor o igual a 0."
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
        estimated_unit_cost=costo_estimado,    # no se vuelve a leer del catálogo
        real_unit_cost=costo_real,
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


# Editar ítem (cantidad, costo cotizado y costo real)
# ==========================================

@router.post("/presupuestos/{presupuesto_id}/items/{item_id}")
def actualizarItem(
    presupuesto_id: int,
    item_id: int,
    request: Request,
    usuario: CurrentUser,
    cantidad: str = Form(...),
    estimated_unit_cost: str = Form(...),
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
    costo_estimado = _entero(estimated_unit_cost)
    costo_real = _entero(real_unit_cost)

    if cant is None:
        flash(request, "La cantidad debe ser un entero mayor o igual a 1.", "error")
    elif costo_estimado is None or costo_real is None:
        flash(request, "Los costos deben ser enteros mayores o iguales a 0.", "error")
    else:
        item.cantidad = cant
        item.estimated_unit_cost = costo_estimado
        item.real_unit_cost = costo_real
        calcularSubtotales(item)
        session.add(item)
        session.flush()
        recalcularPresupuesto(session, presupuesto)
        session.commit()
        flash(request, "Ítem actualizado correctamente.", "success")

    return RedirectResponse(f"{destino}#item-{item_id}", status_code=303)
