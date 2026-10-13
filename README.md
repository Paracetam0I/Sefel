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

## Migraciones de base de datos (Alembic)

SEFEL utiliza Alembic para versionar los cambios en el esquema de la base de datos. La configuración de conexión se obtiene desde `app/core/db.py` mediante `alembic/env.py`, que importa los modelos de SQLModel y utiliza `SQLModel.metadata`.

### Flujo de trabajo

1. **Generar una migración** después de modificar o crear modelos:

   ```powershell
   python -m alembic revision --autogenerate -m "descripcion_del_cambio"
   ```

2. **Revisar el archivo generado** dentro de `alembic/versions/`. Comprobar que las operaciones coincidan con los cambios esperados antes de aplicarlas.

3. **Aplicar las migraciones pendientes**:

   ```powershell
   python -m alembic upgrade head
   ```

4. **Consultar la revisión aplicada**:

   ```powershell
   python -m alembic current
   ```

### Consideraciones

* Los modelos deben importarse en `alembic/env.py` para que Alembic los detecte.
* La opción `--autogenerate` propone cambios; siempre se debe revisar la migración antes de aplicarla.
* La migración inicial de prueba crea la tabla `test_model`. Este modelo es temporal y deberá retirarse cuando se definan los modelos definitivos de SEFEL.
