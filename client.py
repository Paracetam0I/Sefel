"""Lanzador de la interfaz de escritorio (pywebview + FastAPI).

Uso directo:          python client.py            (puerto libre al azar)
Con puerto concreto:  python client.py 8765
Recomendado:          python -m scripts.iniciar   (prepara la BD y llama a main())

También es el punto de entrada del ejecutable (build.spec).
"""
import socket
import sys
import threading
import time

import uvicorn
import webview

HOST = "127.0.0.1"
ESPERA_MAXIMA_SEGUNDOS = 15


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


def main(port: int | None = None) -> None:
    from app.main import app   # se importa aquí para que el lanzador cargue rápido

    port = port or getUnusedPort()
    url = f"http://{HOST}:{port}"
    print(f"SEFEL escuchando en {url} (puerto {port})", flush=True)

    # Arranca FastAPI en un hilo daemon: se cierra junto con la ventana
    servidor = threading.Thread(
        target=uvicorn.run,
        args=(app,),
        kwargs={"host": HOST, "port": port, "log_level": "error"},
        daemon=True,
    )
    servidor.start()

    if not esperarServidor(port):
        print(f"El servidor no respondió en {ESPERA_MAXIMA_SEGUNDOS} s.", file=sys.stderr)

    # Crea la ventana nativa apuntando al servidor local
    webview.create_window("APU sefel", url)
    webview.start()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
