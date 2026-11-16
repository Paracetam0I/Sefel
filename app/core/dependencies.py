from __future__ import annotations

import time
from typing import Annotated

from fastapi import Depends, Request
from sqlmodel import Session

from app.core.config import INACTIVIDAD_MAXIMA_SEGUNDOS
from app.core.db import getSession
from app.models.user import User, UserRole


SESSION_USER_KEY = "user_id"
SESSION_ACTIVIDAD_KEY = "ultima_actividad"
MOTIVO_INACTIVIDAD = "inactividad"


def marcaDeTiempo() -> float:
    """Hora actual en segundos (función aparte para poder simularla en tests)."""
    return time.time()


def marcarActividad(request: Request) -> None:
    request.session[SESSION_ACTIVIDAD_KEY] = marcaDeTiempo()


class LoginRequired(Exception):
    """Se lanza cuando una ruta necesita sesión válida y no la tiene."""

    def __init__(self, request: Request, motivo: str | None = None) -> None:
        self.request = request
        self.motivo = motivo
        
class RoleForbidden(Exception):
    """Hay sesión válida, pero el rol del usuario no alcanza para esta ruta."""

    def __init__(self, request: Request, user: User) -> None:
        self.request = request
        self.user = user

# Handler que cargar el usuario cuando se llega a este módulo
def _cargar_usuario(request: Request, session: Session) -> User | None:
    """Devuelve el User logueado, o None si no hay sesión válida.

    Limpia la sesión si estaba corrupta, si el usuario ya no está activo o si
    pasaron más de INACTIVIDAD_MAXIMA_SEGUNDOS desde la última actividad.
    En ese último caso deja request.state.sesion_expirada = True.
    """
    raw_id = request.session.get(SESSION_USER_KEY)
    if raw_id is None:
        return None

    # Inactividad: la marca viaja en la cookie firmada, no se puede alterar
    # desde el navegador; recargar la página no la renueva si ya venció.
    ultima = request.session.get(SESSION_ACTIVIDAD_KEY)
    try:
        inactivo = marcaDeTiempo() - float(ultima) > INACTIVIDAD_MAXIMA_SEGUNDOS
    except (TypeError, ValueError):
        inactivo = True
    if inactivo:
        request.session.clear()
        request.state.sesion_expirada = ultima is not None
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

    marcarActividad(request)
    return user


# Función que va a responder cada que la página requiere verificar la identidad de la persona que está entrando
def getCurrentUser(
    request: Request,
    session: Annotated[Session, Depends(getSession)],
) -> User:
    """Rutas que EXIGEN login. Corta con LoginRequired si no hay usuario."""
    user = _cargar_usuario(request, session)
    if user is None:
        motivo = (
            MOTIVO_INACTIVIDAD
            if getattr(request.state, "sesion_expirada", False)
            else None
        )
        raise LoginRequired(request, motivo)
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
