
import logging
import os
import sys
import time

from typing import Annotated
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
from app.core.dependencies import CurrentUser, getCurrentUser
from app.core.dependencies import OptionalUser
from app.core.security import verifyPassword
from app.core.db import getSession
from app.core.routers import admin
from app.core.dependencies import requireRoles

from app.models.user import User, UserRole
from app.templates import templates


logger = configuracionLogging()

app = FastAPI(
    title="Proyecto APU Sefel",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="sefel_session",
    max_age=60 * 60 * 8,  # la sesión dura 8 horas
    same_site="lax",
    https_only=False,  # la app corre en http://127.0.0.1, no en https
)

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

# ==================================================
# Bloque para registros
# ==================================================
registerAuthHandlers(app, templates)
app.include_router(admin.router)

# Test de sesión 
@app.get("/protegido")
def rutaProtegida(request: Request, user: CurrentUser):
    return {"hola": user.username}

@app.get("/prueba/solo-admin")
def rutaSoloAdmin(
    #cuando se usa Annotated, el primer argumento es el tipo de dato que se espera, 
    # y el segundo argumento es la dependencia que se va a usar para obtener ese dato. 
    # En este caso, se espera un objeto User, y la dependencia es requireRoles(UserRole.ADMIN), 
    # que verifica que el usuario tenga el rol de ADMIN. Si no lo tiene, se lanza una excepción RoleForbidden.
    
    user: Annotated[User, Depends(requireRoles(UserRole.ADMIN))], 
):
    return {"hola": user.username, "rol": user.role.value}


@app.get(
    "/prueba/presupuestos",
    dependencies=[Depends(requireRoles(UserRole.ADMIN, UserRole.BUDGETS))],
)
def rutaPresupuestos():
    return {"ok": "puedes ver presupuestos"}

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

# Echarle un ojo a ver si se puede mover esta función a handlers.py para ahorrar un poco de espacio. El handlers.py se encarga de manejar errores

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
def index(request: Request, usuario: CurrentUser):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"usuario": usuario},
    )


@app.get(
    "/api/saludo",
    response_class=HTMLResponse,
    dependencies=[Depends(getCurrentUser)],
) #este endpoint es para probar que la sesión funciona, y que el usuario está logueado. Si no lo está, devuelve un 401
def saludo():
    return (
        "<p class='text-green-700 font-semibold'>"
        "¡Respuesta desde FastAPI con HTMX!</p>"
    )
    
# OptionalUser permite que la ruta pueda tener usuarios sin sesiones
# CurrentUser permite que únicamente los usuarios con sesiones puedan estar en las páginas


@app.get("/login")
def mostrarLogin(request: Request, usuario: OptionalUser):
    if usuario is not None:
        # Revisar esto luego, no redirigir al dashboard, si no que a otra ruta por defecto
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={"error": None},
    )
    
@app.post("/login")
def procesarLogin(
    request: Request,
    user: OptionalUser,
    username: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(getSession)
):
    # Si el usuario tiene sesión, lo redirige a dashboard
    if user is not None:
        return RedirectResponse("/dashboard", status_code=303)

    
    usuario = session.exec(select(User).where(User.username == username)).first()

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

    if not usuario.is_active:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={"error": "Tu cuenta está desactivada"},
            status_code=403,
            )
    usuario.last_login = datetime.now(timezone.utc)
    session.add(usuario)
    session.commit()

    request.session["user_id"] = usuario.id # Guardamos el ID del usuario en la sesión (se escribe en una cookie)

# Luego echar un ojo en este redirect, para cambiar por un next_url y poner por defecto la web de los presupuesto u otra distinta que no sea el dashboard
    return RedirectResponse(url="/dashboard", status_code=303) #status_code=303 indica que es una redirección después de un POST, para evitar que el navegador vuelva a enviar el formulario si se recarga la página

@app.get("/dashboard")
def mostrarDashboard(request: Request, usuario: CurrentUser):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"usuario": usuario},
    )

# Formulario para salir de sesión
@app.post("/logout")
def cerrarSesion(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)