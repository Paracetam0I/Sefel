"""
paths.py — Rutas de archivos según dónde corre la app.

EN SIMPLE
    La app puede correr de dos formas: como código fuente (desarrollo) o como
    un .exe empaquetado. Cada forma guarda sus archivos en un lugar distinto.
    Este módulo responde dos preguntas:
      - "¿Dónde están mis plantillas/CSS?"      -> resourcePath()
      - "¿Dónde guardo la base de datos/logs?"  -> userDataPath()

TÉCNICO
    - Recursos (solo lectura): con PyInstaller, sys.frozen = True y los
      archivos se descomprimen en una carpeta temporal sys._MEIPASS.
    - Datos (lectura/escritura): platformdirs da la carpeta estándar del
      sistema operativo, p. ej. en Windows
      C:/Users/<usuario>/AppData/Local/inacap/APU sefel/
"""
import sys
from pathlib import Path
import platformdirs

APP_NAME = "APU sefel"
APP_AUTHOR = "inacap"

def resourcePath(rel: str) -> Path:
    """Ruta absoluta a un recurso incluido con la app (plantillas, estáticos).

    Si la app está congelada por PyInstaller usa sys._MEIPASS; si no, la
    carpeta app/ del proyecto.
    """
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent.parent
    return base / rel

def userDataPath(rel: str) -> Path:
    """Ruta absoluta dentro de la carpeta de datos del usuario.

    Crea las carpetas intermedias si no existen (no crea el archivo final).
    Ej.: userDataPath("data/sefel.db") -> .../APU sefel/data/sefel.db
    """
    base = Path(platformdirs.user_data_dir(APP_NAME, APP_AUTHOR))
    full = base / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    return full
