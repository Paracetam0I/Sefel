
import logging
import os
import sys
import time

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.logging import configuracionLogging


logger = configuracionLogging()

app = FastAPI(
    title="Proyecto APU Sefel",
    version="0.1.0",
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
templates = Jinja2Templates(directory=TEMPLATES_DIR)


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