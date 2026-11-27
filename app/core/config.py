"""
config.py — Configuración general de la aplicación.

EN SIMPLE
    Es el "panel de ajustes" del programa: dónde está la base de datos,
    cuánto dura la sesión sin actividad, los datos de la empresa que salen
    en el PDF y la clave secreta que protege las sesiones.

TÉCNICO
    Se ejecuta una sola vez al importarse (Python cachea los módulos), así que
    las constantes de aquí quedan fijas mientras la app corre. Lee variables
    de entorno (o el archivo .env en desarrollo, vía python-dotenv) y, si no
    existen, usa valores por defecto dentro de la carpeta de datos del usuario.
"""
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
# Se asegura de que la carpeta exista (el archivo .db NO se crea aquí).
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
# Días que la cotización en PDF declara como vigente.
VALIDEZ_COTIZACION_DIAS = 7

def obtenerSecretKey() -> str:
    """Devuelve la clave secreta con la que se firman las cookies de sesión.

    En simple: es la "llave" que impide que alguien falsifique su sesión
    (por ejemplo, cambiarse el rol a ADMIN editando la cookie).

    Técnico: busca en este orden y usa la primera que encuentre:
      1. Variable de entorno SECRET_KEY (o .env) -> desarrollo.
      2. Archivo secret_key.txt en la carpeta de datos -> producción.
      3. Si no hay ninguna, genera 32 bytes aleatorios (64 caracteres hex),
         los guarda en ese archivo y los devuelve. Así la clave se mantiene
         igual entre reinicios y las sesiones no se invalidan.
    """
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