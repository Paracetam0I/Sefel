# Sefel
Proyecto de la empresa Sefel relacionado a la herramienta de presupuestación y administración de precios unitarios

## Inicio rápido

```bash
# 1. Crear entorno virtual e instalar dependencias
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
# 2. Compilar Tailwind (genera app/static/css/output.css)
tailwindcss -i app/static/css/input.css -o app/static/css/output.css --minify
# 3. Ejecutar en desarrollo
python client.py
```


## Build (empaquetado)

Para generar el ejecutable **usa siempre el spec versionado**:
```bash
pyinstaller build.spec

El ejecutable queda en `dist/`.
```

> ⚠️ **No ejecutes `pyinstaller client.py` directamente.** PyInstaller genera un `.spec` autogenerado que no debe subirse al repositorio. El único spec válido es `build.spec`.

Antes de buildear, asegúrate de haber compilado el CSS de Tailwind (paso 2).

## Estructura
```text
app/
├── main.py              # Aplicación FastAPI
└── static/              # HTML, CSS compilado, JS (HTMX + Alpine)
client.py                # Lanzador de la ventana (pywebview)
build.spec               # Configuración de PyInstaller (¡no borrar!)
requirements.txt
```

# Sefel
Proyecto de la empresa Sefel relacionado a la herramienta de presupuestación y administración de precios unitarios

# Test
Prueba de cambios en la rama de Andres

# Prueba
Prueba Coté