import random
import socket
import threading
import webview
import uvicorn
from app.main import app

def get_unused_port():
    """Encuentra un puerto libre en localhost."""
    while True:
        port = random.randint(1024, 65535)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("localhost", port))
            sock.close()
            return port
        except OSError:
            pass

port = get_unused_port()

# Arranca FastAPI en un hilo daemon
t = threading.Thread(
    target=uvicorn.run,
    args=(app,),
    kwargs={"port": port, "log_level": "error"}
)
t.daemon = True
t.start()

# Crea la ventana nativa apuntando al servidor local
webview.create_window("Mi App", f"http://localhost:{port}")
webview.start()