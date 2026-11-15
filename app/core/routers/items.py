from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.db import getSession
from app.core.dependencies import CurrentUser, requireRoles
from app.core.flash import flash
from app.models.apu import APU
from app.models.detalle_presupuesto import DetallePresupuesto
from app.models.material import Material
from app.models.user import Presupuesto, UserRole
from app.templates import templates


# Solo los roles que arman presupuestos pueden agregar ítems
router = APIRouter(
    tags=["items"],
    dependencies=[
        Depends(requireRoles(UserRole.ADMIN, UserRole.BUDGETS, UserRole.BOTH))
    ],
)

LISTA_URL = "/presupuestos"


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


def _renderFormulario(
    request: Request,
    usuario,
    session: Session,
    presupuesto: Presupuesto,
    datos: dict | None = None,
    material: Material | None = None,
    error: str | None = None,
    status_code: int = 200,
):
    apus = session.exec(
        select(APU).where(APU.is_active.is_(True)).order_by(APU.code)
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="item_nuevo.html",
        context={
            "usuario": usuario,
            "presupuesto": presupuesto,
            "apus": apus,
            "datos": datos,
            "material": material,
            "error": error,
        },
        status_code=status_code,
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

    return _renderFormulario(request, usuario, session, presupuesto)


@router.post("/presupuestos/{presupuesto_id}/items")
def crearItem(
    presupuesto_id: int,
    request: Request,
    usuario: CurrentUser,
    id_apu: str = Form(""),
    id_material: str = Form(""),
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
        "id_apu": id_apu,
        "unit": unit,
        "estimated_unit_cost": estimated_unit_cost,
        "cantidad": cantidad,
        "costo_directo": costo_directo,
        "costo_indirecto": costo_indirecto,
        "descripcion": descripcion,
    }

    # Convertir y buscar (el navegador solo manda texto)
    apu_id = _entero(id_apu, 1)
    material_id = _entero(id_material, 1)
    costo_estimado = _entero(estimated_unit_cost)
    cant = _entero(cantidad, 1)
    directo = _entero(costo_directo)
    indirecto = _entero(costo_indirecto)
    unidad = unit.strip()

    apu = session.get(APU, apu_id) if apu_id else None
    material = session.get(Material, material_id) if material_id else None
    material_valido = material if material is not None and material.is_active else None

    # Validar, un error a la vez
    error = None
    if apu is None or not apu.is_active:
        error = "Selecciona un APU válido."
    elif material_valido is None:
        error = "Selecciona un material activo del catálogo."
    elif not unidad or len(unidad) > 30:
        error = "La unidad es obligatoria (máximo 30 caracteres)."
    elif costo_estimado is None:
        error = "El costo unitario debe ser un entero mayor o igual a 0."
    elif cant is None:
        error = "La cantidad debe ser un entero mayor o igual a 1."
    elif directo is None or indirecto is None:
        error = "Los costos directo e indirecto deben ser enteros mayores o iguales a 0."
    elif len(descripcion.strip()) > 500:
        error = "La descripción no puede superar los 500 caracteres."

    if error:
        return _renderFormulario(
            request, usuario, session, presupuesto,
            datos=datos, material=material_valido,
            error=error, status_code=400,
        )

    item = DetallePresupuesto(
        id_presupuesto=presupuesto.id_presupuesto,
        id_apu=apu.id,                         # trazabilidad
        id_material=material_valido.id,        # trazabilidad
        unit=unidad,                           # copia editable: lo que mandó el formulario
        estimated_unit_cost=costo_estimado,    # no se vuelve a leer del catálogo
        cantidad=cant,
        subtotal=cant * costo_estimado,        # lo calcula el servidor
        costo_directo=directo,
        costo_indirecto=indirecto,
        descripcion=descripcion.strip() or None,
    )
    session.add(item)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return _renderFormulario(
            request, usuario, session, presupuesto,
            datos=datos, material=material_valido,
            error="No se pudo guardar el ítem.", status_code=400,
        )

    flash(request, "Ítem agregado correctamente.", "success")
    return RedirectResponse(
        f"/presupuestos/{presupuesto.id_presupuesto}/items/nuevo",
        status_code=303,
    )