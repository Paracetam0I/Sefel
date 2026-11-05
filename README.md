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

## Sesiones y rotación de la SECRET_KEY

La app guarda `user_id` y rol en una cookie firmada con `SECRET_KEY`.

**De dónde sale la clave (en orden):**
1. Variable de entorno o archivo `.env` (desarrollo).
2. Archivo `secret_key.txt` en la carpeta de datos del usuario (producción).
3. Si no existe ninguna, se genera sola en la primera ejecución.

**Cómo rotarla si se filtra:**

- *Desarrollo:*
  1. Generar una nueva: `python -c "import secrets; print(secrets.token_hex(32))"`
  2. Reemplazar el valor de `SECRET_KEY` en `.env`.
  3. Reiniciar la app.

- *Producción (ejecutable):*
  1. Cerrar la app.
  2. Borrar `secret_key.txt` en la carpeta de datos del usuario
     (`%LOCALAPPDATA%\inacap\APU sefel\`).
  3. Abrir la app: se genera una clave nueva automáticamente.

**Efecto:** todas las sesiones activas se invalidan y los usuarios deben iniciar sesión de nuevo.

**Si la clave llegó a subirse a git:** rotarla es obligatorio. Borrar el archivo del repositorio no basta, porque la clave queda en el historial.

## Creación de tablas

# Solo crear las que falten (comportamiento anterior)
python -m scripts.generate

# Borrar tablas de modelos y recrear
python -m scripts.generate -d

# Borrar TODO (incluidas tablas ajenas) y recrear
python -m scripts.generate -d --all

# Sin preguntar (CI / scripts)
python -m scripts.generate -d -y

## Seed
En la raiz del proyecto existe un seed_admin.py que crea 4 usuarios básicos y los ingresa a la base de datos para hacer pruebas.

Para generar los usuarios Y la tabla de usuario:
```batch
python -m scripts.seed_admin --create-tables
```
Para generar los usuarios, pero ya con la tabla creada:
```batch
python -m scripts.seed_admin
```

## Ejecución de pruebas automatizadas

### Instalar dependencias

    python -m pip install -r requirements.txt

### Ejecutar todas las pruebas

    python -m pytest -v

### Ejecutar pruebas por área

**Autenticación y roles:**

    python -m pytest tests/test_auth.py -v

**CRUD APU:**

    python -m pytest tests/test_apu.py -v

**Validaciones APU:**

    python -m pytest tests/test_apu_validaciones.py -v

Las pruebas utilizan una base de datos SQLite en memoria, por lo que no modifican la base de datos real de la aplicación.

**Resultado esperado:** 23 pruebas aprobadas.

