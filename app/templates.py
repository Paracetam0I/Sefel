"""
templates.py — Motor de plantillas HTML (Jinja2).

EN SIMPLE
    Las páginas HTML están en app/templates/ con "huecos" ({{ ... }}) que se
    rellenan con datos. Este archivo prepara ese motor y le da herramientas
    extra que todas las plantillas pueden usar (formatear pesos, fechas,
    revisar permisos, leer avisos).

TÉCNICO
    Crea un objeto `templates` (Jinja2Templates de FastAPI) que los routers
    usan con templates.TemplateResponse(request, "pagina.html", {...}).
    - env.globals -> funciones/variables disponibles en todas las plantillas.
    - env.filters -> filtros con la sintaxis {{ valor | filtro }}.
"""
import os
import sys

from fastapi.templating import Jinja2Templates
from app.core.flash import getFlashedMessages
from app.core.formato import etiquetaRol, formatearClp, formatearFecha, iniciales
from app.core.config import INACTIVIDAD_MAXIMA_SEGUNDOS
from app.core.permisos import puede
from app.core.validaciones import REGLAS_HTML

def getBaseDir() -> str:
    """Carpeta base donde buscar las plantillas (desarrollo o .exe)."""
    # Si PyInstaller congeló la app, los recursos están en sys._MEIPASS
    if getattr(sys, "frozen", False):
        return sys._MEIPASS  # type: ignore[attr-defined]

    # En desarrollo, usamos la ubicación de este archivo
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = getBaseDir()

TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)
# --- Globales: se usan como funciones/variables en cualquier plantilla ---
templates.env.globals["get_flashed_messages"] = getFlashedMessages  # avisos pendientes
templates.env.globals["puede"] = puede                              # {% if puede(usuario, "apu") %}
templates.env.globals["REGLAS_HTML"] = REGLAS_HTML                  # maxlength/min/max de los inputs
templates.env.globals["inactividad_ms"] = INACTIVIDAD_MAXIMA_SEGUNDOS * 1000  # aviso de cierre en JS
# --- Filtros: {{ valor | filtro }} ---
templates.env.filters["clp"] = formatearClp        # 1500 -> "$ 1.500"
templates.env.filters["fecha"] = formatearFecha    # datetime -> "26/11/2026"
templates.env.filters["rol_label"] = etiquetaRol   # "ADMIN" -> "Administrador"
templates.env.filters["iniciales"] = iniciales     # "Ana Pérez" -> "AP"
