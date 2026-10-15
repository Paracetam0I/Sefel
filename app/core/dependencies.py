from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlmodel import Session

from app.core.db import getSession   # ajustá a tu módulo real
from app.models.user import User      # ajustá a tu módulo real


SESSION_USER_KEY = "user_id"


class LoginRequired(Exception):
    """Se lanza cuando una ruta necesita sesión válida y no la tiene."""

    def __init__(self, request: Request) -> None:
        self.request = request


# Función que va a responder cada que la página requiere verificar la identidad de la persona que está entrando
def getCurrentUser(
    request: Request,
    session: Annotated[Session, Depends(getSession)],
) -> User:
    raw_id = request.session.get(SESSION_USER_KEY)
    if raw_id is None:
        raise LoginRequired(request)

    # Normalizamos el id: la sesión es JSON, por si quedó como str.
    try:
        user_id = int(raw_id)
    except (TypeError, ValueError):
        # Sesión corrupta / manipulada: limpiamos y forzamos login.
        request.session.clear()
        raise LoginRequired(request)

    user = session.get(User, user_id)

    # Usuario borrado o desactivado DESPUÉS de iniciar sesión:
    # limpiamos la cookie de sesión para forzar logout real.
    if user is None or not user.is_active:
        request.session.clear()
        raise LoginRequired(request)

    return user


# Alias cómodo para anotar endpoints:
#   def dashboard(user: CurrentUser): ...
CurrentUser = Annotated[User, Depends(getCurrentUser)]