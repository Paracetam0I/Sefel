"""
logging.py — Registro de eventos (logs) de la aplicación.

EN SIMPLE
    Es el "diario" de la app: anota qué pasó y cuándo (inicios de sesión,
    errores, etc.) tanto en la consola como en un archivo, para poder
    revisar problemas después.

TÉCNICO
    Configura el logger "sefel" con dos salidas:
      - RotatingFileHandler: logs/sefel.log, máx. 1 MB; al llenarse rota y
        guarda hasta 3 copias antiguas (sefel.log.1, .2, .3).
      - StreamHandler: la consola.
    propagate=False evita que los mensajes se dupliquen en el logger raíz.
"""

import logging
from logging.handlers import RotatingFileHandler

from app.core.paths import userDataPath


LOG_FILE = userDataPath("logs/sefel.log")


def configuracionLogging():
    """Configura y devuelve el logger "sefel".

    Es seguro llamarla varias veces: solo agrega los handlers la primera vez
    (`if not logger.handlers`), así no se duplican las líneas del log.
    """
    log_format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    formatter = logging.Formatter(log_format)

    logger = logging.getLogger("sefel")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger
