from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse

from app.core.dependencies import LoginRequired


LOGIN_URL = "/login"


def registerAuthHandlers(app: FastAPI) -> None:
    @app.exception_handler(LoginRequired)
    async def _on_login_required(request: Request, exc: LoginRequired):
        next_url = request.url.path
        if request.url.query:
            next_url = f"{next_url}?{request.url.query}"
        return RedirectResponse(
            f"{LOGIN_URL}?next={quote(next_url, safe='')}",
            status_code=303,
        )