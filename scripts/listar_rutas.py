"""
Lista todas las rutas de la app con sus métodos, para auditar docs/rutas.md.

Uso:
    python -m scripts.listar_rutas
"""

from app.main import app

# Rutas del esquema OpenAPI: incluye las de los routers incluidos
paginas = app.openapi()["paths"]
for path in sorted(paginas):
    metodos = sorted(m.upper() for m in paginas[path])
    print(metodos, path)

# Montajes (archivos estáticos): no aparecen en el esquema
print("\n-- Montajes --")
for ruta in app.routes:
    if type(ruta).__name__ == "Mount":
        print(ruta.path)