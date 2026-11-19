"""Lanzador de la interfaz de escritorio (pywebview + FastAPI).

Uso directo:          python client.py            (puerto libre al azar)
Con puerto concreto:  python client.py 8765
Recomendado:          python -m scripts.iniciar   (además ofrece --demo, etc.)

También es el punto de entrada del ejecutable (build.spec). Antes de abrir la
ventana prepara la base de datos (crea o migra) y, si no hay ningún ADMIN
activo, crea el administrador inicial (app/core/inicializacion.py).
"""
import base64
import html
import os
import socket
import sys
import threading
import time
from pathlib import Path

import uvicorn
import webview

HOST = "127.0.0.1"

# pywebview (WebView2) cancela en silencio toda descarga si esto es False
# (su valor por defecto): por eso el PDF no se descargaba en escritorio.
# Los PDF se guardan con ApiEscritorio.guardarPdf (diálogo nativo + aviso);
# esto queda como respaldo para cualquier otra descarga.
webview.settings["ALLOW_DOWNLOADS"] = True
ESPERA_MAXIMA_SEGUNDOS = 15


def carpetaDescargas() -> Path:
    """Carpeta Descargas del usuario (aunque esté redirigida, p. ej. a OneDrive)."""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        ) as clave:
            ruta = Path(winreg.QueryValueEx(clave, "{374DE290-123F-4565-9164-39C4925E467B}")[0])
            if ruta.is_dir():
                return ruta
    except (ImportError, OSError):
        pass
    ruta = Path.home() / "Downloads"
    return ruta if ruta.is_dir() else Path.home()


class ApiEscritorio:
    """Funciones de Python que la página puede llamar en la ventana de escritorio
    (window.pywebview.api.*). Solo existen dentro de la app de escritorio; en el
    navegador la página usa la descarga normal."""

    def guardarPdf(self, nombre: str, contenido_base64: str) -> dict:
        """Pide dónde guardar el PDF (diálogo nativo) y lo escribe.

        Devuelve {"ok": True, "ruta": ...}, {"ok": False, "cancelado": True}
        o {"ok": False, "error": ...}.
        """
        try:
            nombre = os.path.basename(nombre) or "presupuesto.pdf"
            if not nombre.lower().endswith(".pdf"):
                nombre += ".pdf"
            contenido = base64.b64decode(contenido_base64, validate=True)
            if not contenido.startswith(b"%PDF-"):
                return {"ok": False, "error": "El archivo recibido no es un PDF."}

            ventana = webview.windows[0] if webview.windows else None
            if ventana is None:
                return {"ok": False, "error": "No hay una ventana abierta."}
            eleccion = ventana.create_file_dialog(
                webview.FileDialog.SAVE,
                directory=str(carpetaDescargas()),
                save_filename=nombre,
                file_types=("Documento PDF (*.pdf)",),
            )
            if not eleccion:
                return {"ok": False, "cancelado": True}

            ruta = Path(eleccion if isinstance(eleccion, str) else eleccion[0])
            if ruta.suffix.lower() != ".pdf":
                ruta = ruta.with_suffix(".pdf")
            ruta.write_bytes(contenido)
            return {"ok": True, "ruta": str(ruta)}
        except Exception as exc:  # noqa: BLE001  el error se muestra en la página
            avisar(f"No se pudo guardar el PDF: {exc}", error=True)
            return {"ok": False, "error": str(exc)}


def avisar(texto: str, error: bool = False) -> None:
    """print() que no falla en el ejecutable sin consola (stdout/stderr = None)."""
    flujo = sys.stderr if error else sys.stdout
    if flujo is not None:
        print(texto, file=flujo, flush=True)


def getUnusedPort() -> int:
    """Pide al sistema operativo un puerto libre en localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def puertoDisponible(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((HOST, port))
            return True
        except OSError:
            return False


def esperarServidor(port: int, limite: float = ESPERA_MAXIMA_SEGUNDOS) -> bool:
    """Espera a que uvicorn acepte conexiones para no abrir una ventana en blanco."""
    fin = time.monotonic() + limite
    while time.monotonic() < fin:
        try:
            with socket.create_connection((HOST, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def mostrarError(mensaje: str) -> None:
    """Ventana con el error: el ejecutable no tiene consola donde leerlo."""
    webview.create_window(
        "APU sefel - error al iniciar",
        html=(
            "<body style='font-family:sans-serif;padding:24px'>"
            "<h2>No se pudo iniciar SEFEL</h2>"
            f"<pre style='white-space:pre-wrap'>{html.escape(mensaje)}</pre>"
            "</body>"
        ),
        width=720, height=420,
    )
    webview.start()


def prepararDatos() -> bool:
    """Crea/migra la BD y asegura un ADMIN. Devuelve False si falló."""
    try:
        from app.core.inicializacion import inicializar

        for linea in inicializar():
            avisar(linea)
        return True
    except Exception as exc:  # noqa: BLE001  cualquier fallo se muestra al usuario
        import traceback

        avisar(traceback.format_exc(), error=True)
        mostrarError(f"{type(exc).__name__}: {exc}")
        return False


def main(port: int | None = None, preparar: bool = True) -> None:
    # Primero la BD: Alembic reconfigura el logging, así que va antes de cargar la app
    if preparar and not prepararDatos():
        return

    from app.main import app   # se importa aquí para que el lanzador cargue rápido

    port = port or getUnusedPort()
    url = f"http://{HOST}:{port}"
    avisar(f"SEFEL escuchando en {url} (puerto {port})")

    # Arranca FastAPI en un hilo daemon: se cierra junto con la ventana
    servidor = threading.Thread(
        target=uvicorn.run,
        args=(app,),
        kwargs={"host": HOST, "port": port, "log_level": "error"},
        daemon=True,
    )
    servidor.start()

    if not esperarServidor(port):
        avisar(f"El servidor no respondió en {ESPERA_MAXIMA_SEGUNDOS} s.", error=True)

    # Crea la ventana nativa apuntando al servidor local
    webview.create_window("APU sefel", url, js_api=ApiEscritorio())
    webview.start()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
