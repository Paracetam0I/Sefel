from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from decimal import Decimal, InvalidOperation

from app.services.calculations import calculate_budget_total, calculate_item_subtotal
from app.core.db import getSession
from app.core.dependencies import CurrentUser, requireRoles
from app.core.flash import flash
from app.models.apu import APU
from app.models.detalle_presupuesto import DetallePresupuesto
from app.models.user import Presupuesto, UserRole
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


MAX_DECIMALES = 2
VALOR_MAXIMO = Decimal("999999999999")


def _decimal(valor: str) -> Decimal | None:
    """Texto -> Decimal ('12,5' o '12.5'). None si no es válido.

    Rechaza: vacío, NaN/Infinity, negativos, más de 2 decimales y valores gigantes.
    """
    try:
        numero = Decimal(valor.strip().replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None
    if not numero.is_finite() or numero < 0 or numero > VALOR_MAXIMO:
        return None
    if numero.as_tuple().exponent < -MAX_DECIMALES:
        return None
    return numero
def _renderFormulario(
    request: Request,
    usuario,
    presupuesto: Presupuesto,
    datos: dict | None = None,
    apu: APU | None = None,
    error: str | None = None,
    status_code: int = 200,
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

    return _renderFormulario(request, usuario, presupuesto)

@router.get("/presupuestos/{presupuesto_id}/items")
def listarItems(
    presupuesto_id: int,
    request: Request,
    usuario: CurrentUser,
    session: Session = Depends(getSession),
):
    presupuesto = _presupuestoDelUsuario(session, presupuesto_id, usuario)
    if presupuesto is None:
        flash(request, "El presupuesto solicitado no existe.", "error")
        return RedirectResponse(LISTA_URL, status_code=303)

    items = session.exec(
        select(DetallePresupuesto)
        .where(DetallePresupuesto.id_presupuesto == presupuesto.id_presupuesto)
        .order_by(DetallePresupuesto.id)
    ).all()

    # El subtotal que se muestra sale de la función, no del valor guardado
    filas = [{"item": item, "subtotal": calculate_item_subtotal(item)} for item in items]

    return templates.TemplateResponse(
        request=request,
        name="items.html",
        context={
            "usuario": usuario,
            "presupuesto": presupuesto,
            "filas": filas,
            "total": calculate_budget_total(items),
        },
    )

@router.post("/presupuestos/{presupuesto_id}/items")
def crearItem(
    presupuesto_id: int,
    request: Request,
    usuario: CurrentUser,
    id_apu: str = Form(""),
    unit: str = Form(""),
    estimated_unit_cost: str = Form(""),
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
        "cantidad": cantidad,
        "costo_directo": costo_directo,
        "costo_indirecto": costo_indirecto,
        "descripcion": descripcion,
    }

    # Convertir y buscar (el navegador solo manda texto)
    apu_id = _entero(id_apu, 1)
    costo_estimado = _decimal(estimated_unit_cost)
    cant = _decimal(cantidad)
    directo = _decimal(costo_directo)
    indirecto = _decimal(costo_indirecto)
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
        error = "El costo unitario debe ser un número mayor o igual a 0 (máximo 2 decimales)."
    elif cant is None or cant <= 0:
        error = "La cantidad debe ser un número mayor a 0 (máximo 2 decimales)."
    elif directo is None or indirecto is None:
        error = "Los costos directo e indirecto deben ser números mayores o iguales a 0 (máximo 2 decimales)."
    elif len(descripcion.strip()) > 500:
        error = "La descripción no puede superar los 500 caracteres."

    if error:
        return _renderFormulario(
            request, usuario, presupuesto,
            datos=datos, apu=apu_valido, error=error, status_code=400,
        )

    item = DetallePresupuesto(
        id_presupuesto=presupuesto.id_presupuesto,
        id_apu=apu_valido.id,                  # trazabilidad: de qué APU salió
        unit=unidad,                           # copia editable: lo que mandó el formulario
        estimated_unit_cost=costo_estimado,    # no se vuelve a leer del catálogo
        cantidad=cant,
        subtotal=Decimal(0),                   # se calcula en la línea siguiente
        costo_directo=directo,
        costo_indirecto=indirecto,
        descripcion=descripcion.strip() or None,
    )
    item.subtotal = calculate_item_subtotal(item)  # única fuente de verdad del cálculo
    session.add(item)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return _renderFormulario(
            request, usuario, presupuesto,
            datos=datos, apu=apu_valido,
            error="No se pudo guardar el ítem.", status_code=400,
        )

    flash(request, "Ítem agregado correctamente.", "success")
    return RedirectResponse(
        f"/presupuestos/{presupuesto.id_presupuesto}/items",
        status_code=303,
    )