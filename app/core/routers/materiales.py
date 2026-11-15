from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.core.db import getSession
from app.core.dependencies import getCurrentUser
from app.models.material import Material
from app.templates import templates


# Todas las rutas de este router exigen sesión (denegar por defecto)
router = APIRouter(
    prefix="/api/materiales",
    tags=["materiales"],
    dependencies=[Depends(getCurrentUser)],
)

MAX_RESULTADOS = 8


@router.get("/buscar")
def buscarMateriales(
    request: Request,
    session: Session = Depends(getSession),
    q: str = "",
):
    termino = q.strip().lower()

    consulta = select(Material).where(Material.is_active.is_(True))
    if termino:
        consulta = consulta.where(
            or_(
                func.lower(Material.code).contains(termino, autoescape=True),
                func.lower(Material.name).contains(termino, autoescape=True),
            )
        )

    materiales = session.exec(
        consulta.order_by(Material.name).limit(MAX_RESULTADOS)
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="partials/material/resultados.html",
        context={"materiales": materiales, "q": q.strip()},
    )


@router.get("/{material_id}/autocompletar")
def autocompletarMaterial(
    material_id: int,
    request: Request,
    session: Session = Depends(getSession),
):
    material = session.get(Material, material_id)

    if material is None or not material.is_active:
        raise HTTPException(status_code=404, detail="Material no encontrado")

    return templates.TemplateResponse(
        request=request,
        name="partials/material/campos.html",
        context={"material": material},
    )