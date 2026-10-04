import os
import sys
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="Proyecto APU Sefel",
    version="0.1.0"
)

def get_base_dir() -> str:
    # Si PyInstaller congeló la app, los datos están en sys._MEIPASS
    if getattr(sys, "frozen", False):
        return sys._MEIPASS  # type: ignore[attr-defined]
    # Si no, usamos la ubicación del archivo actual
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Ruta absoluta a la carpeta static, compatible con PyInstaller
@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
    )

@app.get("/api/saludo")
def saludo():
    return "<p class='text-green-700 font-semibold'>¡Respuesta desde FastAPI con HTMX!</p>"