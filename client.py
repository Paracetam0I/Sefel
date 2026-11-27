"""Lanzador de la interfaz de escritorio (pywebview + FastAPI).

EN SIMPLE
    SEFEL es, por dentro, una página web. Este archivo la convierte en un
    "programa de escritorio":
      1. Prepara la base de datos.
      2. Enciende un servidor web local (uvicorn) en segundo plano.
      3. Abre una ventana (pywebview) que muestra esa página, como un
         navegador sin barra de direcciones.
    Al cerrar la ventana, se apaga todo.

TÉCNICO
    uvicorn corre en un hilo daemon; pywebview usa WebView2 (el motor de Edge)
    en el hilo principal. Con --red el servidor escucha en 0.0.0.0 para que
    otros PCs de la LAN entren por navegador.

Uso directo:          python client.py            (puerto libre al azar)
Con puerto concreto:  python client.py 8765
Modo red (compartido): python client.py --red     (otros PCs entran por navegador)
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

# 127.0.0.1 = "este mismo PC": nadie de afuera puede conectarse.
HOST = "127.0.0.1"

# Modo red: el servidor escucha en todas las interfaces para que otros PCs de
# la red local entren con el navegador a http://<IP de este PC>:<puerto>.
# Puerto fijo (los demás tienen que conocerlo); se cambia con --puerto.
HOST_RED = "0.0.0.0"
PUERTO_RED = 8765

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
            # basename: evita que un nombre como "../../x.pdf" apunte a otra carpeta
            nombre = os.path.basename(nombre) or "presupuesto.pdf"
            if not nombre.lower().endswith(".pdf"):
                nombre += ".pdf"
            # La página envía el PDF como texto base64; aquí vuelve a bytes.
            # Todo PDF real empieza con "%PDF-": se comprueba por seguridad.
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
    """Pide al sistema operativo un puerto libre en localhost.

    Truco: bind al puerto 0 hace que el SO elija uno libre; se lee cuál fue y
    se cierra el socket para que uvicorn lo use.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def ipsLocales() -> list[str]:
    """IPv4 de este PC en la red local (las que deben usar los otros PCs)."""
    ips: list[str] = []
    try:
        # "Conectar" un socket UDP no envía nada, pero revela la IP de la
        # interfaz de red que se usaría
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 1))
            ips.append(sock.getsockname()[0])
    except OSError:
        pass
    try:
        for *_, direccion in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.append(direccion[0])
    except OSError:
        pass
    vistas: list[str] = []
    for ip in ips:
        if ip not in vistas and not ip.startswith(("127.", "169.254.")):
            vistas.append(ip)
    return vistas


def avisoRed(port: int) -> str:
    """Texto con las direcciones que deben usar los otros PCs."""
    ips = ipsLocales()
    if not ips:
        return "Modo red: no se detectó una IP de red local en este PC."
    # La primera es la de la interfaz que usa la red; el resto suelen ser
    # adaptadores virtuales (VirtualBox, Hyper-V, VPN...)
    texto = (
        "Modo red: los demás usuarios entran desde su navegador a:\n"
        f"   http://{ips[0]}:{port}"
    )
    if len(ips) > 1:
        otras = ", ".join(ips[1:])
        texto += f"\n   (otras interfaces de este PC, si la anterior no funciona: {otras})"
    return texto + "\nSi no conectan, permite el puerto en el Firewall de Windows de este PC."


def puertoDisponible(port: int, host: str = HOST) -> bool:
    """True si se puede ocupar el puerto (nadie más lo está usando)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
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


def preguntarSiNo(titulo: str, mensaje: str) -> bool:
    """Pregunta Sí/No con un cuadro nativo de Windows (antes de abrir la ventana).

    Fuera de Windows (o si falla) responde No: nunca crea una base sin confirmación.
    """
    try:
        import ctypes

        MB_YESNO, MB_ICONWARNING, MB_DEFBUTTON2, IDYES = 0x04, 0x30, 0x100, 6
        respuesta = ctypes.windll.user32.MessageBoxW(
            None, mensaje, titulo, MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2
        )
        return respuesta == IDYES
    except (AttributeError, OSError):
        return False


def prepararDatos() -> bool:
    """Crea/migra la BD y asegura un ADMIN. Devuelve False si falló o se canceló."""
    from app.core.errores_bd import esErrorBD, mensajeErrorBD
    from app.core.inicializacion import BaseDatosFaltante, inicializar

    try:
        try:
            lineas = inicializar()
        except BaseDatosFaltante as faltante:
            avisar(str(faltante), error=True)
            crear = preguntarSiNo(
                "SEFEL - base de datos no encontrada",
                f"No se encontró la base de datos en:\n{faltante.ruta}\n\n"
                "Ya existía antes en este PC: puede haberse borrado o movido.\n\n"
                "¿Crear una base de datos NUEVA y vacía?\n\n"
                "Sí: se crea una base vacía (con el usuario admin).\n"
                "No: SEFEL se cierra para que puedas restaurar el archivo o un respaldo.",
            )
            if not crear:
                avisar("Inicio cancelado: no se creó una base nueva.", error=True)
                return False
            lineas = inicializar(crear_si_falta=True)
        for linea in lineas:
            avisar(linea)
        return True
    except Exception as exc:  # noqa: BLE001  cualquier fallo se muestra al usuario
        import traceback

        avisar(traceback.format_exc(), error=True)
        mostrarError(mensajeErrorBD(exc) if esErrorBD(exc) else f"{type(exc).__name__}: {exc}")
        return False


def main(port: int | None = None, preparar: bool = True, red: bool = False) -> None:
    """Arranca todo: BD -> servidor en segundo plano -> ventana de escritorio.

    preparar=False lo usa scripts/iniciar.py, que ya preparó la BD antes.
    """
    # Primero la BD: Alembic reconfigura el logging, así que va antes de cargar la app
    if preparar and not prepararDatos():
        return

    from app.main import app   # se importa aquí para que el lanzador cargue rápido

    host = HOST_RED if red else HOST
    port = port or (PUERTO_RED if red else getUnusedPort())
    if not puertoDisponible(port, host):
        mostrarError(f"El puerto {port} está ocupado. Cierra la otra aplicación o usa otro puerto.")
        return
    url = f"http://{HOST}:{port}"   # la ventana de este PC siempre usa localhost
    avisar(f"SEFEL escuchando en {url} (puerto {port})")
    if red:
        avisar(avisoRed(port))

    # Arranca FastAPI en un hilo daemon: se cierra junto con la ventana
    servidor = threading.Thread(
        target=uvicorn.run,
        args=(app,),
        kwargs={"host": host, "port": port, "log_level": "error"},
        daemon=True,
    )
    servidor.start()

    if not esperarServidor(port):
        avisar(f"El servidor no respondió en {ESPERA_MAXIMA_SEGUNDOS} s.", error=True)

    # Crea la ventana nativa apuntando al servidor local
    webview.create_window("APU sefel", url, js_api=ApiEscritorio())
    webview.start()


def parsearArgumentos(argv: list[str] | None = None):
    """Lee los argumentos de la línea de comandos (puerto opcional y --red)."""
    import argparse

    parser = argparse.ArgumentParser(description="Abre SEFEL en una ventana de escritorio.")
    parser.add_argument("puerto", nargs="?", type=int, help="Puerto (por defecto, uno libre).")
    parser.add_argument("--red", action="store_true",
                        help=f"Compartir en la red local (puerto {PUERTO_RED} por defecto).")
    return parser.parse_args(argv)


if __name__ == "__main__":
    argumentos = parsearArgumentos()
    main(argumentos.puerto, red=argumentos.red)
