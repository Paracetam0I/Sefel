import os
import sys

from fastapi.templating import Jinja2Templates
from app.core.flash import getFlashedMessages
from app.core.formato import etiquetaRol, formatearClp, formatearFecha, iniciales

def getBaseDir() -> str:
    # Si PyInstaller congeló la app, los recursos están en sys._MEIPASS
    if getattr(sys, "frozen", False):
        return sys._MEIPASS  # type: ignore[attr-defined]

    # En desarrollo, usamos la ubicación de este archivo
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = getBaseDir()

TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.globals["get_flashed_messages"] = getFlashedMessages
templates.env.filters["clp"] = formatearClp
templates.env.filters["fecha"] = formatearFecha
templates.env.filters["rol_label"] = etiquetaRol
templates.env.filters["iniciales"] = iniciales