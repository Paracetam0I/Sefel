import os
from app.core.paths import userDataPath
import secrets
from dotenv import load_dotenv

load_dotenv() #en desarrollo, lee las variables de entorno desde el archivo .env

DATABASE_PATH = userDataPath("data/sefel.db")

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