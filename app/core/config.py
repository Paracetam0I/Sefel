import os
from pathlib import Path
from app.core.paths import userDataPath
import secrets
from dotenv import load_dotenv

load_dotenv() #en desarrollo, lee las variables de entorno desde el archivo .env

# Ruta de la base de datos. SEFEL_DB_PATH permite usar otra (pruebas, demos);
# por defecto vive en la carpeta de datos del usuario.
DATABASE_PATH = (
    Path(os.environ["SEFEL_DB_PATH"]).resolve()
    if os.getenv("SEFEL_DB_PATH")
    else userDataPath("data/sefel.db")
)
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

# La sesión se cierra tras este tiempo sin actividad (clics, navegación o
# peticiones autenticadas). Se valida en backend en cada petición.
INACTIVIDAD_MAXIMA_SEGUNDOS = 30 * 60

# Datos de la empresa para la cotización en PDF
DATOS_EMPRESA = {
    "nombre": "SEFEL LTDA.",
    "direccion": "",
    "rut": "",
    "telefono": "",
    "mail": "sefel.ltda@gmail.com",
}
VALIDEZ_COTIZACION_DIAS = 7

def obtenerSecretKey() -> str:
    # 1) Variable de entorno o .env (desarrollo)
    clave = os.getenv("SECRET_KEY")
    if clave:
        return clave

    # 2) Archivo en la carpeta de usuario (producción)
    archivo = userDataPath("secret_key.txt")
    if archivo.exists():
        return archivo.read_text(encoding="utf-8").strip()

    # 3) Primera ejecución: generar y guardar
    clave = secrets.token_hex(32)
    archivo.write_text(clave, encoding="utf-8")
    return clave


SECRET_KEY = obtenerSecretKey()