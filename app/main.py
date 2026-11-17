
import logging
import os
import sys
import time
from math import ceil

from typing import Annotated

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, Response
from fastapi import Depends, Form

from sqlmodel import Session, select

from starlette.middleware.sessions import SessionMiddleware

from app.core.logging import configuracionLogging
from app.core.config import SECRET_KEY
from app.core.handlers import MENSAJE_INACTIVIDAD, registerAuthHandlers
from app.core.dependencies import CurrentUser, getCurrentUser
from app.core.dependencies import MOTIVO_INACTIVIDAD, OptionalUser, marcarActividad
from app.core.bloqueo import (
    BLOQUEO_TEMPORAL,
    MENSAJE_DESACTIVADA,
    ResultadoIntento,
    bloqueoTemporalRestante,
    registrarIntentoFallido,
    registrarLoginCorrecto,
)
from app.core.security import verifyPassword
from app.core.db import getSession
from app.core.routers import admin, apu, dashboard, items, presupuestos
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
app.include_router(presupuestos.router)
app.include_router(apu.router)
app.include_router(items.router)
app.include_router(dashboard.router)

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
def mostrarLogin(request: Request, usuario: OptionalUser, motivo: str = ""):
    if usuario is not None:
        # Revisar esto luego, no redirigir al dashboard, si no que a otra ruta por defecto
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={
            "error": None,
            "aviso": MENSAJE_INACTIVIDAD if motivo == MOTIVO_INACTIVIDAD else None,
        },
    )


def _errorLogin(request: Request, mensaje: str, status_code: int):
    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={"error": mensaje},
        status_code=status_code,
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

    if usuario is None:
        return _errorLogin(request, "Usuario o contraseña incorrectos.", 401)

    # Cuenta desactivada (por intentos fallidos o por un administrador)
    if not usuario.is_active:
        mensaje = (
            MENSAJE_DESACTIVADA if usuario.lock_reason
            else "Tu cuenta está desactivada. Contacta a un administrador."
        )
        return _errorLogin(request, mensaje, 403)

    # Bloqueo temporal (solo le ocurre al único ADMIN activo)
    restante = bloqueoTemporalRestante(usuario)
    if restante is not None:
        minutos = max(1, ceil(restante.total_seconds() / 60))
        return _errorLogin(
            request,
            "Demasiados intentos fallidos. Por seguridad la cuenta queda "
            f"bloqueada temporalmente; inténtalo de nuevo en {minutos} min.",
            429,
        )

    if not verifyPassword(password, usuario.hashed_password):
        resultado, restantes = registrarIntentoFallido(session, usuario.id)
        if resultado == ResultadoIntento.DESACTIVADA:
            return _errorLogin(request, MENSAJE_DESACTIVADA, 403)
        if resultado == ResultadoIntento.BLOQUEO_TEMPORAL:
            minutos = int(BLOQUEO_TEMPORAL.total_seconds() // 60)
            return _errorLogin(
                request,
                f"Demasiados intentos fallidos. Por seguridad la cuenta queda "
                f"bloqueada temporalmente; inténtalo de nuevo en {minutos} min.",
                429,
            )
        mensaje = "Usuario o contraseña incorrectos."
        if restantes <= 2:
            mensaje += (
                f" Te queda{'n' if restantes > 1 else ''} {restantes} "
                f"intento{'s' if restantes > 1 else ''} antes de que la cuenta se desactive."
            )
        return _errorLogin(request, mensaje, 401)

    registrarLoginCorrecto(usuario)
    session.add(usuario)
    session.commit()

    request.session.clear()
    request.session["user_id"] = usuario.id # Guardamos el ID del usuario en la sesión (se escribe en una cookie)
    marcarActividad(request)

# Luego echar un ojo en este redirect, para cambiar por un next_url y poner por defecto la web de los presupuesto u otra distinta que no sea el dashboard
    return RedirectResponse(url="/dashboard", status_code=303) #status_code=303 indica que es una redirección después de un POST, para evitar que el navegador vuelva a enviar el formulario si se recarga la página


# Latido de actividad: el front lo llama cuando hay clics/teclas sin peticiones
# al servidor. CurrentUser renueva la marca de actividad (o responde 401 si venció).
@app.post("/api/sesion/actividad", status_code=204)
def registrarActividad(usuario: CurrentUser):
    return Response(status_code=204)


# Formulario para salir de sesión
@app.post("/logout")
def cerrarSesion(request: Request, motivo: str = ""):
    request.session.clear()
    destino = "/login"
    if motivo == MOTIVO_INACTIVIDAD:
        destino = f"/login?motivo={MOTIVO_INACTIVIDAD}"
    return RedirectResponse(url=destino, status_code=303)
