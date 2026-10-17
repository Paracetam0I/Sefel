from typing import Annotated
from sqlmodel import select, Session, func
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse

from app.models.user import User, UserRole
from app.templates import templates
from app.core.dependencies import requireRoles
from app.core.db import getSession
from app.core.security import hashPassword

# prefix significa que todo lo que entra a este archivo, tendrá por defecto la ruta "/admin/users"
router = APIRouter(prefix="/admin/users", tags=["admin"])
AdminUser = Annotated[User, Depends(requireRoles(UserRole.ADMIN))]


# Listar usuarios
# ==========================================

@router.get("")
def listar(request: Request, admin: AdminUser, session: Session = Depends(getSession)):
    usuarios = session.exec(select(User).order_by(User.username)).all()
    return templates.TemplateResponse(
        request=request,
        name="admin-panel/list.html",
        context={"admin": admin, "usuarios": usuarios},
    )

# Crear usuarios
# ==========================================
@router.get("/new")
def form_crear(request: Request, admin: AdminUser):
    return templates.TemplateResponse(
        request=request,
        name="admin-panel/form.html",
        context={"admin": admin, "usuario": None, "modo": "crear", "error": None},
    )

@router.post("")
def crear(
    request: Request,
    admin: AdminUser,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: UserRole = Form(...),
    session: Session = Depends(getSession),
):
    # Validar username único
    existente = session.exec(select(User).where(User.username == username)).first()
    if existente is not None:
        return templates.TemplateResponse(
            request=request,
            name="admin-panel/form.html",
            context={
                "admin": admin,
                "usuario": None,
                "modo": "crear",
                "error": f"El username '{username}' ya existe",
            },
            status_code=400,
        )

    nuevo = User(
        username=username,
        email=email,
        password_hash=hashPassword(password),
        role=role,
        is_active=True,
    )
    session.add(nuevo)
    session.commit()
    session.refresh(nuevo)

    return RedirectResponse("/admin/users", status_code=303)   