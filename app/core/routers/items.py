from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.db import getSession
from app.core.dependencies import CurrentUser, requireRoles
from app.core.flash import flash
from app.models.apu import APU
from app.models.detalle_presupuesto import DetallePresupuesto
from app.models.user import Presupuesto, UserRole
from app.services.calculations import calculate_budget_total, calculate_item_subtotal
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
MAX_DECIMALES = 2
VALOR_MAXIMO = Decimal("999999999999")


# Utilidades
# ==========================================

def _esHtmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _presupuestoDelUsuario(
    session: Session, presupuesto_id: int, usuario
) -> Presupuesto | None:
    """Devuelve el presupuesto solo si pertenece al usuario actual."""
    presupuesto = session.get(Presupuesto, presupuesto_id)
    if presupuesto is None or presupuesto.id_usuario != usuario.id:
        return None
    return presupuesto


def _itemDelUsuario(
    session: Session, presupuesto_id: int, item_id: int, usuario
) -> tuple[Presupuesto | None, DetallePresupuesto | None]:
    """Devuelve (presupuesto, ítem). El ítem solo vale si pertenece a ese presupuesto."""
    presupuesto = _presupuestoDelUsuario(session, presupuesto_id, usuario)
    if presupuesto is None:
        return None, None

    item = session.get(DetallePresupuesto, item_id)
    if item is None or item.id_presupuesto != presupuesto.id_presupuesto:
        return presupuesto, None

    return presupuesto, item


def _entero(valor: str, minimo: int = 0) -> int | None:
    """Convierte texto a entero; None si no es un entero o es menor al mínimo."""
    try:
        numero = int(valor.strip())
    except (ValueError, AttributeError):
        return None
    return numero if numero >= minimo else None


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


def _validarCampos(
    unit: str,
    estimated_unit_cost: str,
    cantidad: str,
    costo_directo: str,
    costo_indirecto: str,
    descripcion: str,
) -> tuple[dict | None, str | None]:
    """Valida los campos del ítem (compartido por crear y editar).

    Devuelve (valores listos para guardar, None) o (None, mensaje de error).
    """
    unidad = unit.strip()
    costo_estimado = _decimal(estimated_unit_cost)
    cant = _decimal(cantidad)
    directo = _decimal(costo_directo)
    indirecto = _decimal(costo_indirecto)

    if not unidad or len(unidad) > 30:
        return None, "La unidad es obligatoria (máximo 30 caracteres)."
    if costo_estimado is None:
        return None, "El costo unitario debe ser un número mayor o igual a 0 (máximo 2 decimales)."
    if cant is None or cant <= 0:
        return None, "La cantidad debe ser un número mayor a 0 (máximo 2 decimales)."
    if directo is None or indirecto is None:
        return None, "Los costos directo e indirecto deben ser números mayores o iguales a 0 (máximo 2 decimales)."
    if len(descripcion.strip()) > 500:
        return None, "La descripción no puede superar los 500 caracteres."

    return {
        "unit": unidad,
        "estimated_unit_cost": costo_estimado,
        "cantidad": cant,
        "costo_directo": directo,
        "costo_indirecto": indirecto,
        "descripcion": descripcion.strip() or None,
    }, None


def _datosDeItem(item: DetallePresupuesto) -> dict:
    """Valores del ítem como texto, para precargar el formulario de edición."""
    return {
        "unit": item.unit,
        "estimated_unit_cost": format(item.estimated_unit_cost, "f"),
        "cantidad": format(item.cantidad, "f"),
        "costo_directo": format(item.costo_directo, "f"),
        "costo_indirecto": format(item.costo_indirecto, "f"),
        "descripcion": item.descripcion or "",
    }


def _contextoTabla(session: Session, presupuesto: Presupuesto) -> dict:
    """Filas y total del presupuesto. Todo sale de calculations.py."""
    items = session.exec(
        select(DetallePresupuesto)
        .where(DetallePresupuesto.id_presupuesto == presupuesto.id_presupuesto)
        .order_by(DetallePresupuesto.id)
    ).all()

    return {
        "presupuesto": presupuesto,
        "filas": [
            {"item": item, "subtotal": calculate_item_subtotal(item)} for item in items
        ],
        "total": calculate_budget_total(items),
    }


def _respuestaTabla(request: Request, session: Session, presupuesto: Presupuesto):
    """La tabla completa (filas y total juntos) y cierra el modal DESPUÉS de dibujarla."""
    respuesta = templates.TemplateResponse(
        request=request,
        name="partials/item/tabla.html",
        context=_contextoTabla(session, presupuesto),
    )
    respuesta.headers["HX-Retarget"] = "#items-presupuesto"
    respuesta.headers["HX-Reswap"] = "innerHTML"
    respuesta.headers["HX-Trigger-After-Swap"] = "cerrar-modal-presupuesto"
    return respuesta


def _renderFormulario(
    request: Request,
    usuario,
    presupuesto: Presupuesto,
    datos: dict | None = None,
    apu: APU | None = None,
    item: DetallePresupuesto | None = None,
    error: str | None = None,
    status_code: int = 200,
):
    es_htmx = _esHtmx(request)

    respuesta = templates.TemplateResponse(
        request=request,
        name="partials/item/formulario.html" if es_htmx else "item_nuevo.html",
        context={
            "usuario": usuario,
            "presupuesto": presupuesto,
            "datos": datos,
            "apu": apu,
            "item": item,
            "modo": "editar" if item is not None else "crear",
            "error": error,
            "modal": es_htmx,
        },
        status_code=200 if es_htmx else status_code,
    )

    # El formulario declara como destino la tabla (para el éxito). Si hay un error,
    # la respuesta debe volver a dibujarse DENTRO del modal.
    if es_htmx and error:
        respuesta.headers["HX-Retarget"] = "#modal-presupuesto-body"
        respuesta.headers["HX-Reswap"] = "innerHTML"

    return respuesta


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


# Lista de ítems
# ==========================================

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

    return templates.TemplateResponse(
        request=request,
        name="items.html",
        context={"usuario": usuario, **_contextoTabla(session, presupuesto)},
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

    # El APU llega como texto: se busca y se comprueba que siga activo
    apu_id = _entero(id_apu, 1)
    apu = session.get(APU, apu_id) if apu_id else None
    apu_valido = apu if apu is not None and apu.is_active else None

    if apu_valido is None:
        valores, error = None, "Selecciona un APU activo del catálogo."
    else:
        valores, error = _validarCampos(
            unit, estimated_unit_cost, cantidad,
            costo_directo, costo_indirecto, descripcion,
        )

    if error:
        return _renderFormulario(
            request, usuario, presupuesto,
            datos=datos, apu=apu_valido, error=error, status_code=400,
        )

    item = DetallePresupuesto(
        id_presupuesto=presupuesto.id_presupuesto,
        id_apu=apu_valido.id,        # trazabilidad: de qué APU salió
        subtotal=Decimal(0),         # se calcula en la línea siguiente
        **valores,                   # copia editable: lo que mandó el formulario
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

    if _esHtmx(request):
        return _respuestaTabla(request, session, presupuesto)

    flash(request, "Ítem agregado correctamente.", "success")
    return RedirectResponse(
        f"/presupuestos/{presupuesto.id_presupuesto}/items", status_code=303
    )


# Editar ítem (el APU no se puede cambiar: es la trazabilidad)
# ==========================================

@router.get("/presupuestos/{presupuesto_id}/items/{item_id}/editar")
def mostrarFormularioEdicion(
    presupuesto_id: int,
    item_id: int,
    request: Request,
    usuario: CurrentUser,
    session: Session = Depends(getSession),
):
    presupuesto, item = _itemDelUsuario(session, presupuesto_id, item_id, usuario)
    if item is None:
        flash(request, "El ítem solicitado no existe.", "error")
        destino = f"/presupuestos/{presupuesto_id}/items" if presupuesto else LISTA_URL
        return RedirectResponse(destino, status_code=303)

    return _renderFormulario(
        request, usuario, presupuesto,
        datos=_datosDeItem(item), apu=item.apu, item=item,
    )


@router.post("/presupuestos/{presupuesto_id}/items/{item_id}")
def actualizarItem(
    presupuesto_id: int,
    item_id: int,
    request: Request,
    usuario: CurrentUser,
    unit: str = Form(""),
    estimated_unit_cost: str = Form(""),
    cantidad: str = Form("1"),
    costo_directo: str = Form("0"),
    costo_indirecto: str = Form("0"),
    descripcion: str = Form(""),
    session: Session = Depends(getSession),
):
    presupuesto, item = _itemDelUsuario(session, presupuesto_id, item_id, usuario)
    if item is None:
        flash(request, "El ítem solicitado no existe.", "error")
        destino = f"/presupuestos/{presupuesto_id}/items" if presupuesto else LISTA_URL
        return RedirectResponse(destino, status_code=303)

    datos = {
        "unit": unit,
        "estimated_unit_cost": estimated_unit_cost,
        "cantidad": cantidad,
        "costo_directo": costo_directo,
        "costo_indirecto": costo_indirecto,
        "descripcion": descripcion,
    }

    valores, error = _validarCampos(
        unit, estimated_unit_cost, cantidad,
        costo_directo, costo_indirecto, descripcion,
    )
    if error:
        return _renderFormulario(
            request, usuario, presupuesto,
            datos=datos, apu=item.apu, item=item, error=error, status_code=400,
        )

    for campo, valor in valores.items():
        setattr(item, campo, valor)
    item.subtotal = calculate_item_subtotal(item)  # se recalcula, nunca viene del formulario
    session.add(item)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return _renderFormulario(
            request, usuario, presupuesto,
            datos=datos, apu=item.apu, item=item,
            error="No se pudieron guardar los cambios.", status_code=400,
        )

    if _esHtmx(request):
        return _respuestaTabla(request, session, presupuesto)

    flash(request, "Ítem actualizado correctamente.", "success")
    return RedirectResponse(
        f"/presupuestos/{presupuesto.id_presupuesto}/items", status_code=303
    )