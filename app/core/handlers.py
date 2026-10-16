from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import LoginRequired, RoleForbidden


LOGIN_URL = "/login"


def registerAuthHandlers(app: FastAPI, templates: Jinja2Templates) -> None:
    @app.exception_handler(LoginRequired)
    async def _on_login_required(request: Request, exc: LoginRequired):
        next_url = request.url.path
        if request.url.query:
            next_url = f"{next_url}?{request.url.query}"
        return RedirectResponse(
            f"{LOGIN_URL}?next={quote(next_url, safe='')}",
            status_code=303,
        )

    @app.exception_handler(RoleForbidden)
    async def _on_role_forbidden(request: Request, exc: RoleForbidden):
        return templates.TemplateResponse(
            request=request,
            name="errors/403.html",
            context={"usuario": exc.user},
            status_code=403,
        )