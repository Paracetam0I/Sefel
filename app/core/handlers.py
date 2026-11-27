"""
handlers.py — Qué responder cuando algo sale mal (sin login, sin permiso, BD caída).

EN SIMPLE
    Las dependencias (dependencies.py) solo "levantan la mano" lanzando una
    excepción. Aquí se decide qué ve el usuario en cada caso:
      - Sin sesión ......... lo manda al login (y recuerda a dónde iba).
      - Sin permiso ........ página 403.
      - Problema con la BD . página/aviso con explicación y qué hacer.

TÉCNICO
    Registra exception handlers en la app FastAPI. La respuesta cambia según
    quién pidió la página:
      - HTMX (cabecera HX-Request): no se puede devolver una página entera
        dentro de un fragmento, así que se usan cabeceras HX-Redirect /
        HX-Reswap o JSON.
      - /api/...: JSON con código HTTP (401, 403, 503).
      - Navegación normal: redirección 303 o plantilla HTML.
"""
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import DBAPIError

from app.core.config import DATABASE_PATH
from app.core.dependencies import MOTIVO_INACTIVIDAD, LoginRequired, RoleForbidden
from app.core.errores_bd import describirErrorBD, mensajeErrorBD
from app.core.flash import EVENTO_NOTIFICAR, agregarEvento
from app.core.logging import configuracionLogging


LOGIN_URL = "/login"
MENSAJE_INACTIVIDAD = "Tu sesión se ha cerrado por inactividad."


def esHtmx(request: Request) -> bool:
    """True si la petición la hizo HTMX (pide un fragmento, no una página entera)."""
    return request.headers.get("HX-Request") == "true"


def esApi(request: Request) -> bool:
    """True si es una ruta de API interna (espera JSON, no HTML)."""
    return request.url.path.startswith("/api/")


def registerAuthHandlers(app: FastAPI, templates: Jinja2Templates) -> None:
    """Conecta los tres manejadores de error a la app. Se llama desde main.py."""

    @app.exception_handler(LoginRequired)
    async def _on_login_required(request: Request, exc: LoginRequired):
        por_inactividad = exc.motivo == MOTIVO_INACTIVIDAD
        login_url = (
            f"{LOGIN_URL}?motivo={MOTIVO_INACTIVIDAD}" if por_inactividad else LOGIN_URL
        )

        # 1) HTMX: que lleve a la persona al login con la página completa
        if esHtmx(request):
            return Response(status_code=401, headers={"HX-Redirect": login_url})

        # 2) API interna: un programa espera JSON, no una página de login
        if esApi(request):
            detalle = MENSAJE_INACTIVIDAD if por_inactividad else "No autenticado"
            return JSONResponse({"detail": detalle}, status_code=401)

        # 3) Navegación normal: redirigir recordando a dónde iba
        next_url = request.url.path
        if request.url.query:
            next_url = f"{next_url}?{request.url.query}"
        separador = "&" if por_inactividad else "?"
        return RedirectResponse(
            f"{login_url}{separador}next={quote(next_url, safe='')}",
            status_code=303,
        )

    @app.exception_handler(RoleForbidden)
    async def _on_role_forbidden(request: Request, exc: RoleForbidden):
        # HTMX y API no pueden mostrar una página completa: responden 403 en JSON
        if esHtmx(request) or esApi(request):
            return JSONResponse({"detail": "Sin permiso"}, status_code=403)

        return templates.TemplateResponse(
            request=request,
            name="errors/403.html",
            context={"usuario": exc.user},
            status_code=403,
        )

    @app.exception_handler(DBAPIError)
    async def _on_error_base_datos(request: Request, exc: DBAPIError):
        """Base no encontrada, dañada, bloqueada o sin permisos durante la ejecución.

        Se responde 503 con un mensaje claro (y la ruta de la base) en lugar del
        "Algo salió mal" genérico. El detalle técnico queda en el log.
        """
        configuracionLogging().error(
            "Error de base de datos en %s %s (%s): %s",
            request.method, request.url.path, DATABASE_PATH, exc,
        )
        mensaje = mensajeErrorBD(exc)

        if esHtmx(request):
            # Sin swap; el aviso aparece como notificación en la vista actual
            respuesta = Response(status_code=503, headers={"HX-Reswap": "none"})
            agregarEvento(respuesta, EVENTO_NOTIFICAR, {"mensajes": [["error", mensaje]]})
            return respuesta

        if esApi(request):
            return JSONResponse({"detail": mensaje}, status_code=503)

        titulo, accion = describirErrorBD(exc)
        return templates.TemplateResponse(
            request=request,
            name="errors/base_datos.html",
            context={"titulo": titulo, "accion": accion, "ruta": str(DATABASE_PATH)},
            status_code=503,
        )
