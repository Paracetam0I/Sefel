"""Errores de base de datos explicados al usuario.

Se usa al arrancar (client.py / scripts/iniciar.py) y durante la ejecución
(manejador global en app/core/handlers.py): en vez de un "Algo salió mal"
genérico, se dice qué pasó, dónde está la base y qué hacer.
"""
from sqlalchemy.exc import DBAPIError

from app.core.config import DATABASE_PATH

# (fragmento del error de SQLite, título, qué hacer)
CASOS = [
    ("unable to open database file",
     "No se encontró la base de datos o no se puede abrir.",
     "Comprueba que el archivo exista y no se haya movido. Cierra SEFEL y vuelve a abrirlo; "
     "si la base se borró, al abrir podrás crear una nueva o restaurar un respaldo."),
    ("no such table",
     "La base de datos está incompleta o no es de SEFEL.",
     "Cierra SEFEL y vuelve a abrirlo para que se revise la base. Si persiste, restaura un respaldo."),
    ("database is locked",
     "La base de datos está ocupada.",
     "Otro proceso la está usando. Espera unos segundos y vuelve a intentarlo."),
    ("readonly",
     "No se puede escribir en la base de datos.",
     "Revisa los permisos de la carpeta y que el archivo no sea de solo lectura."),
    ("disk i/o error",
     "Error del disco al leer o escribir la base de datos.",
     "Revisa que haya espacio libre y que el disco funcione; luego reinicia SEFEL."),
    ("file is not a database",
     "La base de datos está dañada o no es un archivo de SEFEL.",
     "Restaura un respaldo de la base de datos."),
    ("malformed",
     "La base de datos está dañada.",
     "Restaura un respaldo de la base de datos."),
]


def describirErrorBD(exc: BaseException) -> tuple[str, str]:
    """(título, qué hacer) para un error de base de datos."""
    texto = str(getattr(exc, "orig", None) or exc).lower()
    for fragmento, titulo, accion in CASOS:
        if fragmento in texto:
            return titulo, accion
    return ("Error al acceder a la base de datos.",
            "Vuelve a intentarlo; si persiste, reinicia SEFEL.")


def mensajeErrorBD(exc: BaseException) -> str:
    """Mensaje completo de una línea, con la ruta de la base."""
    titulo, accion = describirErrorBD(exc)
    return f"{titulo} {accion} (Base de datos: {DATABASE_PATH})"


def esErrorBD(exc: BaseException) -> bool:
    return isinstance(exc, DBAPIError)
