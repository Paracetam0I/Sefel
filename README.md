# Sefel
Proyecto de la empresa Sefel relacionado a la herramienta de presupuestación y administración de precios unitarios

## Inicio rápido

```bash
# 1. Crear entorno virtual e instalar dependencias
python -m venv .venv
#activar venv
.venv\Scripts\activate          # Windows

#instalar requerimientos
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
* La migración inicial (`0b66029e01a1`) crea la tabla temporal `test_model`; se mantiene porque es la raíz de la cadena de migraciones, pero la migración `cc5d56d0ebf4` la elimina y el modelo ya no existe.
* `alembic/env.py` usa `render_as_batch=True` (SQLite no soporta `ALTER TABLE` completo) y apaga las claves foráneas solo mientras corre la migración, porque el modo batch recrea tablas.
* Si tu base de datos ya tenía la tabla `detalle_presupuesto` (creada con `scripts.generate`) pero `alembic current` muestra `5691bba44b53`, márcala antes de actualizar: `python -m alembic stamp cbb87f34d7fe` y luego `python -m alembic upgrade head`.

## Costos cotizados, costos reales y porcentajes

* **APU**: `unit_cost` es el costo cotizado; `real_unit_cost` el costo real (si se deja vacío en el formulario, parte igual al cotizado).
* **Ítems del presupuesto** (`DetallePresupuesto`): guardan una copia de ambos costos y el servidor calcula `subtotal = cantidad × costo cotizado` y `real_subtotal = cantidad × costo real`. Se editan en `/presupuestos/{id}/items/nuevo`.
* **Presupuesto**: cada vez que cambia un ítem o los porcentajes se recalculan (en `app/core/calculos.py`), con el formato de la cotización:
    * `total_cotizado` = suma de subtotales cotizados; `total_real` = suma de subtotales reales.
    * Costo directo (`base`) = costo directo fijo si es > 0; si no, `total_real`.
    * `monto_gastos_generales` = costo directo × % gastos generales.
    * `monto_utilidad` = costo directo × % utilidad.
    * `monto_costo_neto` (neto) = costo directo + gastos generales + utilidad. Si hay un costo neto fijo > 0, ese reemplaza al calculado.
    * `monto_iva` = neto × % IVA.
    * `monto_total` = neto + IVA (monto final del presupuesto).
* Los porcentajes (0–100) y los montos fijos se editan con el botón **%** junto a "Editar" en el listado de presupuestos, que también muestra los totales por categoría de APU.

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

**Resultado esperado:** 91 pruebas aprobadas.

## Permisos por rol
Definidos en `app/core/permisos.py` y validados en backend (403, igual que `admin/users`); el front solo oculta lo que el rol no puede usar.

| Módulo | Roles |
|---|---|
| Usuarios | `ADMIN` |
| APU | `MATERIALS`, `BOTH`, `ADMIN` |
| Presupuestos | `BUDGETS`, `BOTH`, `ADMIN` (todo); `VIEWER` (solo ver y exportar) |
| Dashboard | Todos los autenticados (cada bloque según el rol) |

No hay exclusividad por creador: los roles de edición trabajan sobre todos los presupuestos. El detalle de cada ruta está en `docs/rutas.md`.

## Seguridad de sesión y cuentas
* **Inactividad**: la sesión se cierra tras 30 min sin actividad (`INACTIVIDAD_MAXIMA_SEGUNDOS` en `app/core/config.py`). El backend guarda la marca de última actividad en la cookie firmada y la revisa en cada petición autenticada; el front (en `base.html`) cuenta el tiempo, avisa al servidor con `/api/sesion/actividad` cuando hay clics/teclas y, al vencer, cierra la sesión y muestra "Tu sesión se ha cerrado por inactividad.".
* **Intentos fallidos** (`app/core/bloqueo.py`): a los 5 intentos seguidos la cuenta se desactiva y el login muestra "Tu cuenta ha sido desactivada. Contacta a un administrador para reactivarla.". Si es el **único ADMIN activo** no se desactiva: se reinicia el contador y se bloquea 15 min. La decisión va en un único `UPDATE` condicional, así que dos admins fallando a la vez nunca quedan ambos desactivados.
* **Reactivación**: un ADMIN la hace desde `/admin/users` (interruptor o formulario); se limpian `failed_attempts` y el motivo del bloqueo.
* **Auditoría**: la tabla `auditoria_cuentas` registra bloqueos, bloqueos temporales, reactivaciones y desactivaciones (cuenta, quién, cuándo y motivo). Las últimas se ven en el dashboard del ADMIN.

## Exportar presupuestos a PDF
El botón **Exportar** de Presupuestos abre un selector; al descargar, el servidor genera la cotización con ReportLab (`app/core/pdf_presupuesto.py`) y la entrega como `presupuesto-<id>-<aaaa-mm-dd>.pdf`. Los ítems muestran el costo real (la base de los porcentajes). Los datos de la empresa se configuran en `DATOS_EMPRESA` (`app/core/config.py`).

## Comandos
```powershell
pip install -r requirements.txt     # incluye reportlab
python -m alembic upgrade head      # aplica las migraciones
python -m pytest -v                 # corre los tests
```
