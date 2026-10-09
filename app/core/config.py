import os
from pathlib import Path

from app.core.paths import userDataPath

ENV = os.getenv("SEFEL_ENV", "dev")  # "dev" o "production"

# Opcional: permite apuntar a otra DB (por ejemplo en pruebas)
_override = os.getenv("SEFEL_DB_PATH")
DB_PATH = Path(_override) if _override else userDataPath("sefel.db")

DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"