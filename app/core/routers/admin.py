from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.core.db import getSession
from app.core.dependencies import requireRoles
from app.core.flash import flash
from app.core.formato import ETIQUETAS_ROL
from app.core.security import hashPassword
from app.models.user import User, UserRole
from app.templates import templates

# prefix significa que todo lo que entra a este archivo, tendrá por defecto la ruta "/admin/users"
router = APIRouter(prefix="/admin/users", tags=["admin"])
AdminUser = Annotated[User, Depends(requireRoles(UserRole.ADMIN))]

USUARIOS_POR_PAGINA = 6
LARGO_MINIMO_PASSWORD = 8
LISTA_URL = "/admin/users"


# Utilidades
# ==========================================
def _filtrar(todos: list[User], q: str, rol: str, estado: str) -> list[User]:
    texto = q.strip().lower()
    resultado = []
    for u in todos:
        if texto and texto not in f"{u.full_name} {u.username} {u.email}".lower():
            continue
        if rol and u.role.value != rol:
            continue
        if estado == "activo" and not u.is_active:
            continue
        if estado == "inactivo" and u.is_active:
            continue
        resultado.append(u)
    return resultado


def _accesoReciente(u: User, dias: int = 7) -> bool:
    if u.last_login is None:
        return False
    ultimo = u.last_login
    if ultimo.tzinfo is None:
        ultimo = ultimo.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - ultimo <= timedelta(days=dias)


def _resumen(todos: list[User]) -> dict:
    activos = sum(1 for u in todos if u.is_active)
    return {
        "total": len(todos),
        "roles": len({u.role for u in todos}),
        "activos": activos,
        "inactivos": len(todos) - activos,
        "recientes": sum(1 for u in todos if _accesoReciente(u)),
    }


def _formDe(u: User | None) -> dict:
    if u is None:
        return {"username": "", "email": "", "full_name": "", "role": UserRole.VIEWER.value, "is_active": True}
    return {"username": u.username, "email": u.email, "full_name": u.full_name, "role": u.role.value, "is_active": u.is_active}


def _renderLista(
    request: Request,
    admin: User,
    session: Session,
    *,
    q: str = "",
    rol: str = "",
    estado: str = "",
    pagina: int = 1,
    editando: User | None = None,
    modo: str | None = None,
    form: dict | None = None,
    error: str | None = None,
    status_code: int = 200,
):
    todos = session.exec(select(User).order_by(User.full_name)).all()
    filtrados = _filtrar(todos, q, rol, estado)

    total = len(filtrados)
    paginas = max(1, ceil(total / USUARIOS_POR_PAGINA))
    pagina = min(max(pagina, 1), paginas)
    inicio = (pagina - 1) * USUARIOS_POR_PAGINA
    visibles = filtrados[inicio : inicio + USUARIOS_POR_PAGINA]

    filtros = {k: v for k, v in {"q": q, "rol": rol, "estado": estado}.items() if v}
    return templates.TemplateResponse(
        request=request,
        name="admin-panel/list.html",
        status_code=status_code,
        context={
            "usuario": admin,
            "admin": admin,
            "usuarios": visibles,
            "resumen": _resumen(todos),
            "total": total,
            "desde": inicio + 1 if total else 0,
            "hasta": inicio + len(visibles),
            "pagina": pagina,
            "paginas": paginas,
            "q": q,
            "rol": rol,
            "estado": estado,
            "roles": [(r.value, ETIQUETAS_ROL[r.value]) for r in UserRole],
            # enlaces que conservan los filtros y la página
            "qs_base": urlencode({**filtros, "pagina": pagina}),
            "base_url": f"{LISTA_URL}?" + (urlencode(filtros) + "&" if filtros else ""),
            "editando": editando,
            "modo": modo,
            "form": form if form is not None else _formDe(editando),
            "error": error,
        },
    )


def _buscar(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)


# Listar usuarios
# ==========================================
@router.get("")
def listar(
    request: Request,
    admin: AdminUser,
    session: Session = Depends(getSession),
    q: str = "",
    rol: str = "",
    estado: str = "",
    pagina: int = 1,
    editar: int | None = None,
    nuevo: bool = False,
):
    editando = _buscar(session, editar) if editar is not None else None
    modo = "editar" if editando else ("crear" if nuevo else None)
    return _renderLista(
        request, admin, session,
        q=q, rol=rol, estado=estado, pagina=pagina,
        editando=editando, modo=modo,
    )


# Enlace antiguo del formulario de creación
@router.get("/new")
def form_crear(admin: AdminUser):
    return RedirectResponse(f"{LISTA_URL}?nuevo=1", status_code=303)


# Crear usuarios
# ==========================================
@router.post("")
def crear(
    request: Request,
    admin: AdminUser,
    username: str = Form(...),
    email: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    role: UserRole = Form(...),
    is_active: str | None = Form(None),
    session: Session = Depends(getSession),
):
    username, email, full_name = username.strip(), email.strip(), full_name.strip()
    form = {"username": username, "email": email, "full_name": full_name, "role": role.value, "is_active": is_active is not None}

    def rechazar(mensaje: str):
        return _renderLista(request, admin, session, modo="crear", form=form, error=mensaje, status_code=400)

    if not (username and email and full_name):
        return rechazar("Completa nombre, usuario y correo.")
    if len(password) < LARGO_MINIMO_PASSWORD:
        return rechazar(f"La contraseña debe tener al menos {LARGO_MINIMO_PASSWORD} caracteres.")
    if session.exec(select(User).where(User.username == username)).first() is not None:
        return rechazar(f"El usuario '{username}' ya existe.")
    if session.exec(select(User).where(User.email == email)).first() is not None:
        return rechazar(f"El correo '{email}' ya está registrado.")

    nuevo = User(
        username=username,
        email=email,
        full_name=full_name,
        hashed_password=hashPassword(password),
        role=role,
        is_active=is_active is not None,
    )
    session.add(nuevo)
    session.commit()
    session.refresh(nuevo)

    flash(request, f"Usuario '{nuevo.username}' creado correctamente.", "success")
    return RedirectResponse(f"{LISTA_URL}?editar={nuevo.id}", status_code=303)


# Editar usuarios
# ==========================================
@router.post("/{user_id}")
def actualizar(
    user_id: int,
    request: Request,
    admin: AdminUser,
    email: str = Form(...),
    full_name: str = Form(...),
    role: UserRole = Form(...),
    password: str = Form(""),
    is_active: str | None = Form(None),
    session: Session = Depends(getSession),
):
    usuario = _buscar(session, user_id)
    if usuario is None:
        flash(request, "Ese usuario ya no existe.", "error")
        return RedirectResponse(LISTA_URL, status_code=303)

    email, full_name = email.strip(), full_name.strip()
    activo = is_active is not None
    form = {"username": usuario.username, "email": email, "full_name": full_name, "role": role.value, "is_active": activo}

    def rechazar(mensaje: str):
        return _renderLista(request, admin, session, editando=usuario, modo="editar", form=form, error=mensaje, status_code=400)

    if not (email and full_name):
        return rechazar("Completa nombre y correo.")
    if usuario.id == admin.id and (role != UserRole.ADMIN or not activo):
        return rechazar("No puedes desactivarte ni quitarte el rol de administrador a ti mismo.")
    if password and len(password) < LARGO_MINIMO_PASSWORD:
        return rechazar(f"La contraseña debe tener al menos {LARGO_MINIMO_PASSWORD} caracteres.")
    otro = session.exec(select(User).where(User.email == email, User.id != usuario.id)).first()
    if otro is not None:
        return rechazar(f"El correo '{email}' ya está registrado.")

    usuario.email = email
    usuario.full_name = full_name
    usuario.role = role
    usuario.is_active = activo
    if password:
        usuario.hashed_password = hashPassword(password)
    session.add(usuario)
    session.commit()

    flash(request, f"Cambios guardados para '{usuario.username}'.", "success")
    return RedirectResponse(f"{LISTA_URL}?editar={usuario.id}", status_code=303)


# Activar / desactivar desde el interruptor de la tabla
# ==========================================
@router.post("/{user_id}/estado")
def cambiarEstado(
    user_id: int,
    request: Request,
    admin: AdminUser,
    session: Session = Depends(getSession),
):
    usuario = _buscar(session, user_id)
    if usuario is None:
        flash(request, "Ese usuario ya no existe.", "error")
    elif usuario.id == admin.id:
        flash(request, "No puedes desactivar tu propia cuenta.", "error")
    else:
        usuario.is_active = not usuario.is_active
        session.add(usuario)
        session.commit()
        flash(
            request,
            f"'{usuario.username}' ahora está {'activo' if usuario.is_active else 'inactivo'}.",
            "success",
        )
    return RedirectResponse(LISTA_URL, status_code=303)
