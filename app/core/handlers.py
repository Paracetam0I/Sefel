from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.core.dependencies import MOTIVO_INACTIVIDAD, LoginRequired, RoleForbidden


LOGIN_URL = "/login"
MENSAJE_INACTIVIDAD = "Tu sesión se ha cerrado por inactividad."


def esHtmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def esApi(request: Request) -> bool:
    return request.url.path.startswith("/api/")


def registerAuthHandlers(app: FastAPI, templates: Jinja2Templates) -> None:
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