
import logging
import os
import sys
import time

from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi import Depends, Form

from sqlmodel import Session, select

from starlette.middleware.sessions import SessionMiddleware

from app.core.logging import configuracionLogging
from app.core.config import SECRET_KEY
from app.core.handlers import registerAuthHandlers
from app.core.dependencies import CurrentUser
from app.core.db import getSession
from app.core.security import verifyPassword
from app.core.flash import getFlashedMessages
from app.models.user import User


logger = configuracionLogging()

app = FastAPI(
    title="Proyecto APU Sefel",
    version="0.1.0",
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="sefel_session",
    max_age=60 * 60 * 8,  # la sesión dura 8 horas
    same_site="lax",
    https_only=False,  # la app corre en http://127.0.0.1, no en https
)

registerAuthHandlers(app)

def getBaseDir() -> str:
    # Si PyInstaller congeló la app, los recursos están en sys._MEIPASS
    if getattr(sys, "frozen", False):
        return sys._MEIPASS  # type: ignore[attr-defined]

    # En desarrollo, usamos la ubicación de este archivo
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = getBaseDir()
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.globals["get_flashed_messages"] = getFlashedMessages

# Test de sesión 
@app.get("/protegido")
def rutaProtegida(request: Request, user: CurrentUser):
    return {"hola": user.username}

@app.on_event("startup")
async def registrarInicio():
    logger.info("Aplicacion FUNCIONANDOOOOOOOOOOOOO")


@app.middleware("http")
async def registrarSolicitudes(request: Request, call_next):
    inicio = time.perf_counter()

    response = await call_next(request)

    duracion = time.perf_counter() - inicio

    logger.info(
        "%s %s -> %s (%.3f segundos)",
        request.method,
        request.url.path,
        response.status_code,
        duracion,
    )

    return response


@app.exception_handler(Exception)
async def manejarErrorInesperado(
    request: Request,
    exc: Exception,
):
    logger.error(
        "Error inesperado en %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )

    return HTMLResponse(
        content=(
            "<!DOCTYPE html>"
            "<html lang='es'>"
            "<head><meta charset='UTF-8'><title>Error</title></head>"
            "<body><h1>Algo salió mal</h1>"
            "<p>No pudimos completar tu solicitud. "
            "Inténtalo nuevamente.</p></body></html>"
        ),
        status_code=500,
    )


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
    )


@app.get("/api/saludo")
def saludo():
    return (
        "<p class='text-green-700 font-semibold'>"
        "¡Respuesta desde FastAPI con HTMX!</p>"
    )
    
def obtenerUsuarioActual(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    if user_id is None:
        return None

    usuario = db.get(User, user_id)
    if usuario is None or not usuario.is_active:
        request.session.clear()
        return None

    return usuario


@app.get("/login")
def mostrarLogin(request: Request, db: Session = Depends(getSession)):
    if obtenerUsuarioActual(request, db):
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={"error": None},
    )
    
@app.post("/login")
def procesarLogin(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(getSession), #le pasamos la sesión de la base de datos como dependencia
):
    usuario = db.exec(select(User).where(User.username == username)).first()

    if (
        usuario is None
        or not usuario.is_active
        or not verifyPassword(password, usuario.hashed_password)
    ):
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={"error": "Usuario o contraseña incorrectos"},
            status_code=401,
        )

    usuario.last_login = datetime.now(timezone.utc)
    db.add(usuario)
    db.commit()

    request.session["user_id"] = usuario.id # Guardamos el ID del usuario en la sesión (se escribe en una cookie)
    request.session["role"] = usuario.role.value # Guardamos el rol del usuario en la sesión

    return RedirectResponse(url="/dashboard", status_code=303) #status_code=303 indica que es una redirección después de un POST, para evitar que el navegador vuelva a enviar el formulario si se recarga la página

@app.get("/dashboard")
def mostrarDashboard(request: Request, db: Session = Depends(getSession)):
    usuario = obtenerUsuarioActual(request, db)
    if usuario is None:
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"usuario": usuario},
    )


@app.post("/logout")
def cerrarSesion(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)