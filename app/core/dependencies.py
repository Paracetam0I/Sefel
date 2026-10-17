from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlmodel import Session

from app.core.db import getSession   # ajustá a tu módulo real
from app.models.user import User      # ajustá a tu módulo real
from app.models.user import User, UserRole


SESSION_USER_KEY = "user_id"


class LoginRequired(Exception):
    """Se lanza cuando una ruta necesita sesión válida y no la tiene."""

    def __init__(self, request: Request) -> None:
        self.request = request
        
class RoleForbidden(Exception):
    """Hay sesión válida, pero el rol del usuario no alcanza para esta ruta."""

    def __init__(self, request: Request, user: User) -> None:
        self.request = request
        self.user = user

# Handler que cargar el usuario cuando se llega a este módulo
def _cargar_usuario(request: Request, session: Session) -> User | None:
    """Devuelve el User logueado, o None si no hay sesión válida.

    Limpia la sesión si estaba corrupta o si el usuario ya no está activo.
    """
    raw_id = request.session.get(SESSION_USER_KEY)
    if raw_id is None:
        return None
    try:
        user_id = int(raw_id)
    except (TypeError, ValueError):
        request.session.clear()
        return None

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        request.session.clear()
        return None

    return user


# Función que va a responder cada que la página requiere verificar la identidad de la persona que está entrando
def getCurrentUser(
    request: Request,
    session: Annotated[Session, Depends(getSession)],
) -> User:
    """Rutas que EXIGEN login. Corta con LoginRequired si no hay usuario."""
    user = _cargar_usuario(request, session)
    if user is None:
        raise LoginRequired(request)
    return user


# Función que devuelve none cuando en una pestaña no se necesita un usuario, como en una pestaña de login
def getOptionalUser(
    request: Request,
    session: Annotated[Session, Depends(getSession)],
) -> User | None:
    """Rutas que funcionan con o sin login. Devuelve None si no hay."""
    return _cargar_usuario(request, session)

def requireRoles(*roles: UserRole):
    """Devuelve una dependency que solo deja pasar a usuarios con uno de los roles dados."""
    allowed = set(roles)

    def checkRole(request: Request, user: CurrentUser) -> User:
        if user.role not in allowed:
            raise RoleForbidden(request, user)
        return user

    return checkRole

# Alias para usar en las firmas de los endpoints
CurrentUser = Annotated[User, Depends(getCurrentUser)]
OptionalUser = Annotated[User | None, Depends(getOptionalUser)]
