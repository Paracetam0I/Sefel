# SEFEL · Presupuestación y precios unitarios

Herramienta de escritorio de **SEFEL Ingeniería & Construcción** para administrar el catálogo de APU (análisis de precios unitarios), armar presupuestos con costos cotizados y reales, aplicar gastos generales, utilidad e IVA, y exportar cotizaciones en PDF.

**Stack:** FastAPI · SQLModel/SQLAlchemy · Alembic · SQLite · Jinja2 + HTMX + Alpine.js · Tailwind CSS · ReportLab · pywebview (ventana de escritorio).

---

## Índice
1. [Requisitos](#1-requisitos)
2. [Instalación](#2-instalación)
3. [Iniciar la aplicación](#3-iniciar-la-aplicación)
4. [Usuarios de prueba](#4-usuarios-de-prueba)
5. [Datos de ejemplo (seeds)](#5-datos-de-ejemplo-seeds)
6. [Dónde se guardan los datos](#6-dónde-se-guardan-los-datos)
7. [Módulos y permisos](#7-módulos-y-permisos)
8. [Cómo funciona](#8-cómo-funciona)
9. [Base de datos y migraciones](#9-base-de-datos-y-migraciones)
10. [Pruebas](#10-pruebas)
11. [Empaquetado (ejecutable)](#11-empaquetado-ejecutable)
12. [SECRET_KEY y sesiones](#12-secret_key-y-sesiones)
13. [Estructura del proyecto](#13-estructura-del-proyecto)

---

## 1. Requisitos
- Windows 10/11 (la ventana de escritorio usa WebView2, incluido en Windows).
- Python 3.12 o superior.
- Git.

## 2. Instalación
Todos los comandos se ejecutan desde la raíz del repositorio.

```powershell
# 1. Crear y activar el entorno virtual
python -m venv .venv
.venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Compilar el CSS de Tailwind (genera app/static/css/output.css)
tailwindcss -i app/static/css/input.css -o app/static/css/output.css --minify
```

> El paso 3 solo es necesario si cambias plantillas o estilos: `output.css` ya viene versionado. La primera vez, `tailwindcss` descarga su ejecutable.

## 3. Iniciar la aplicación
Un solo comando prepara todo y abre la ventana:

```powershell
python -m scripts.iniciar
```

El script `scripts/iniciar.py`:
1. **Verifica la base de datos.** Si no existe o está vacía, crea todas las tablas y la marca con la última migración. Si ya existe, aplica las migraciones pendientes.
2. **Verifica que haya un ADMIN activo.** Si no hay ninguno, crea los usuarios de `scripts/seed_admin.py` (ver [Usuarios de prueba](#4-usuarios-de-prueba)).
3. **Elige el puerto y lo muestra** (`Puerto: 54123 -> http://127.0.0.1:54123`).
4. **Abre la interfaz de escritorio** (`client.py`).

Opciones:

| Opción | Qué hace |
|---|---|
| `--puerto 8765` | Usa ese puerto en vez de uno libre al azar (falla si está ocupado). |
| `--demo` | Además siembra APU y presupuestos de ejemplo (no duplica si ya existen). |
| `--solo-servidor` | Levanta solo el servidor, sin ventana: abre la URL mostrada en el navegador. |
| `--solo-verificar` | Prepara base de datos y usuarios, y termina sin abrir la app. |
| `--red` | **Comparte la app en la red local**: otros PCs entran con el navegador (puerto 8765 si no se indica `--puerto`). Ver [Varios usuarios a la vez](#varios-usuarios-a-la-vez-modo-red). |
| `--crear-bd` | Si falta una base de datos que ya existía, crea una nueva sin preguntar. |

Ejemplo de salida:
```text
============================================================
SEFEL · inicio
============================================================
Base de datos: C:\Users\<usuario>\AppData\Local\inacap\APU sefel\data\sefel.db
  -> no existía: tablas creadas (revisión 59241f60df74)
Administrador: creados los usuarios de seed (admin, materiales, presupuestos, viewer); entra con 'admin'
Puerto: 54123  ->  http://127.0.0.1:54123
============================================================
```

Otras formas de arrancar:
```powershell
python client.py            # ventana de escritorio, puerto libre (también prepara BD y admin)
python client.py 8765       # ventana de escritorio, puerto fijo
python client.py --red      # ventana de escritorio y, además, compartida en la red local
uvicorn app.main:app --reload --port 8765   # desarrollo con recarga automática (sin verificaciones)
```

> La preparación de la base de datos y del administrador vive en `app/core/inicializacion.py`, así que también la hacen `client.py` y el ejecutable. La diferencia: `scripts.iniciar` crea **los 4 usuarios de prueba**, mientras que `client.py`/el ejecutable crean **solo `admin`** (una instalación real no necesita cuentas de prueba).

### Varios usuarios a la vez (modo red)
Cada instalación es **independiente**: sin `--red`, el servidor solo atiende al propio PC y la base de datos vive en la carpeta de ese usuario. Instalar SEFEL en 4 PCs da 4 apps con **datos separados**.

Para que varias personas trabajen **sobre los mismos datos**, un PC hace de servidor y los demás entran con el navegador:

1. En el PC servidor: `python -m scripts.iniciar --red` (o `MiApp.exe --red`). Muestra la dirección para los demás, por ejemplo `http://192.168.1.88:8765`.
2. La primera vez, Windows pregunta si se permite el acceso a la red: acepta en **redes privadas**. Si los demás no conectan, abre el puerto 8765 en el Firewall de Windows de ese PC.
3. En los otros PCs: abrir esa dirección en el navegador (no hace falta instalar nada) y entrar con su usuario.

Todos comparten la base del PC servidor; ese PC debe quedar encendido con SEFEL abierto. La conexión es HTTP sin cifrar: úsalo solo en la red local de la oficina.

> No pongas la base en una carpeta de red compartida para abrirla desde varios PCs: SQLite puede dañarse con escrituras simultáneas por red y el modo WAL no funciona ahí. Usa el modo red.

### Capacidad
Medido con usuarios virtuales que trabajan **sin pausa** (listar, filtrar, crear APU y presupuestos, agregar ítems, guardar porcentajes, exportar PDF), contra una sola instancia:

| Usuarios simultáneos | Peticiones por segundo | Errores | Tiempo típico (mediana) |
|---|---|---|---|
| 4 | 78 | 0 | 0,02–0,12 s |
| 20 | 72 | 0 | 0,2–0,3 s |
| 50 | 69 | 0 | 0,4–0,8 s |

Una persona real hace una acción cada pocos segundos, así que **4 usuarios simultáneos están muy por debajo del límite**; una oficina de decenas de usuarios también cabe. Lo que más influye es el **volumen de datos**: los listados cargan todos los registros y se vuelven más lentos con miles de APU o presupuestos.

Para soportar escrituras simultáneas, la base usa el modo **WAL** de SQLite y espera hasta 15 s si otra escritura la tiene ocupada (`app/core/db.py`). Antes de este ajuste aparecían errores `database is locked` desde unos 20 usuarios.

## 4. Usuarios de prueba
Los crea `scripts/seed_admin.py` (automáticamente desde `scripts.iniciar` si no hay ningún ADMIN, o a mano con `python -m scripts.seed_admin`).

Al abrir el ejecutable (o `python client.py`) sin ningún ADMIN activo se crea solo `admin`.

| Usuario | Contraseña | Rol |
|---|---|---|
| `admin` | `admin123` | ADMIN |
| `materiales` | `materiales123` | MATERIALS |
| `presupuestos` | `presupuestos123` | BUDGETS |
| `viewer` | `viewer123` | VIEWER |

> ⚠️ Son credenciales de desarrollo. En una instalación real cámbialas desde **Usuarios** apenas entres.

## 5. Datos de ejemplo (seeds)
Todas las seeds son **idempotentes**: se identifican por código/usuario y no duplican lo que ya existe.

```powershell
python -m scripts.seed_admin          # 4 usuarios de prueba (--create-tables crea las tablas; --update-passwords resetea claves)
python -m scripts.seed_apus           # catálogo de 17 APU en 7 categorías (uno inactivo)
python -m scripts.seed_presupuestos   # 3 presupuestos con ítems y porcentajes (siembra los APU si faltan)
```

- **APU** (`scripts/seed_apus.py`): obras preliminares, movimiento de tierra, obra gruesa, pavimentos, terminaciones, instalaciones y obras finales, con costo cotizado y real.
- **Presupuestos** (`scripts/seed_presupuestos.py`): `PRE-2026-001` (activo), `PRE-2026-002` (borrador) y `PRE-2026-003` (cerrado), a nombre del usuario `presupuestos` (o del primer ADMIN). Sus totales se calculan con la misma lógica que la app. Requiere haber corrido `seed_admin`.

Para tenerlo todo de una vez: `python -m scripts.iniciar --demo`.

## 6. Dónde se guardan los datos
En la carpeta de datos del usuario: `%LOCALAPPDATA%\inacap\APU sefel\`

| Archivo | Contenido |
|---|---|
| `data\sefel.db` | Base de datos SQLite |
| `data\sefel.db-wal`, `data\sefel.db-shm` | Parte de la base (modo WAL). Respáldalos junto a `sefel.db`, con SEFEL cerrado |
| `instalacion.json` | Registro de las bases ya creadas en este PC (para detectar una base que desapareció) |
| `logs\sefel.log` | Registro de la aplicación (rotativo) |
| `secret_key.txt` | Clave de firma de las sesiones (si no hay `SECRET_KEY` en el entorno) |

Para usar **otra base de datos** (pruebas, demos) sin tocar la tuya, define `SEFEL_DB_PATH`:
```powershell
$env:SEFEL_DB_PATH = "C:\temp\sefel-demo.db"
python -m scripts.iniciar --demo
```

### Si la base de datos no está o falla
| Situación | Qué hace SEFEL |
|---|---|
| Primera vez en este PC | Crea la base y el usuario `admin` sin preguntar. |
| Al abrir, falta una base que **ya existía** (borrada o movida) | **No** crea una vacía sin avisar. La ventana pregunta: *Sí* crea una nueva vacía, *No* cierra SEFEL para restaurar el archivo o un respaldo. `scripts.iniciar` pregunta en la consola o usa `--crear-bd`. |
| Al abrir, la base está dañada, bloqueada o sin permisos | Ventana de error con la causa, qué hacer y la ruta de la base. |
| Con SEFEL abierto | Windows bloquea el archivo: no se puede borrar ni mover mientras la app lo usa. |
| Durante el uso, la base deja de estar disponible (p. ej. un disco que se desconecta) | La app **no** crea una base vacía: responde con un aviso claro (página, notificación o JSON 503) con la causa y la ruta. El detalle técnico queda en `logs\sefel.log`. |

Las explicaciones de cada error están en `app/core/errores_bd.py`. Como la conexión de la app nunca crea el archivo, para crear la base usa `scripts.iniciar`, `client.py` o el ejecutable (`alembic upgrade head` ya no la crea si no existe).

## 7. Módulos y permisos
Los roles por módulo están en `app/core/permisos.py` y se validan en el **backend**: un rol sin permiso recibe **403** aunque entre por URL. El front solo oculta lo que el rol no puede usar.

| Módulo | Roles con acceso |
|---|---|
| Dashboard | Todos los autenticados (cada bloque según el rol) |
| APU | `MATERIALS`, `BOTH`, `ADMIN` |
| Presupuestos | `BUDGETS`, `BOTH`, `ADMIN` (todo) · `VIEWER` (solo ver y exportar) |
| Usuarios | `ADMIN` |

No hay exclusividad por creador: los roles de edición trabajan sobre todos los presupuestos. El detalle de cada ruta y cómo responde (página, HTMX o API) está en [`docs/rutas.md`](docs/rutas.md).

## 8. Cómo funciona

### Costos cotizados y reales
- **APU:** `unit_cost` es el costo cotizado; `real_unit_cost`, el costo real (si se deja vacío, parte igual al cotizado).
- **Ítems del presupuesto:** guardan una copia de ambos costos; el servidor calcula `subtotal = cantidad × cotizado` y `real_subtotal = cantidad × real`. Se agregan y editan en `/presupuestos/{id}/items/nuevo` (ícono **+** en el listado).

### Porcentajes y totales del presupuesto
Se recalculan en `app/core/calculos.py` cada vez que cambia un ítem o un porcentaje, con el formato de la cotización:

| Concepto | Cálculo |
|---|---|
| Costo directo | Costo directo fijo si es > 0; si no, `total_real` (suma de subtotales reales) |
| Gastos generales | Costo directo × % GG |
| Utilidad | Costo directo × % utilidad |
| Neto | Costo directo + GG + utilidad (o el costo neto fijo, si es > 0) |
| IVA | Neto × % IVA |
| **Total** | Neto + IVA |

Los porcentajes (0–100) y los montos fijos se editan con el botón **%** del listado, que también muestra los totales por categoría de APU.

### Validaciones (creación y edición)
Las reglas viven en `app/core/validaciones.py`: el backend las aplica siempre y los formularios usan los mismos patrones (`REGLAS_HTML`).

| Campo | Regla |
|---|---|
| Código de APU y de presupuesto | Letras (con tildes y ñ), números, espacios, `-` y `_`; se guarda **siempre en MAYÚSCULAS** (`pre-01` → `PRE-01`) |
| Nombre y categoría de APU | Letras (con tildes y ñ), números, espacios, `-` y `_` |
| Cliente y Nombre del presupuesto | Lo anterior, más `.` y `,` (p. ej. "Constructora Andes Ltda.") |
| Fecha de inicio | Obligatoria; no antes del 01/01/2026 |
| Fecha de término | Obligatoria; no antes del inicio ni después del 31/12/2500 |

En pantalla, el campo `description` del presupuesto se llama **Nombre** (en la base de datos conserva su nombre).

### Listados y notificaciones
- Los listados de APU y Presupuestos muestran **lo más reciente primero**. Al crear o editar, la lista se actualiza en el acto, salta a la página del registro y lo resalta.
- Los avisos ("APU creado correctamente.", etc.) aparecen **al instante** como notificaciones flotantes. El middleware `NotificacionesHtmx` (`app/core/flash.py`) los envía en la misma respuesta HTMX.

### Exportar a PDF
El botón **Exportar** de Presupuestos abre un selector; el servidor genera la cotización con ReportLab (`app/core/pdf_presupuesto.py`) y la descarga como `presupuesto-<id>-<aaaa-mm-dd>.pdf`. Los ítems muestran el costo real (la base de los porcentajes). Los datos de la empresa se configuran en `DATOS_EMPRESA` (`app/core/config.py`).

En la **app de escritorio** (pywebview), la descarga del navegador no funciona: WebView2 cancela las descargas si no se habilitan. Por eso el botón pide el PDF al servidor y `client.py` (`ApiEscritorio.guardarPdf`) abre el diálogo nativo de guardado en la carpeta Descargas y avisa "PDF guardado en …" o "No se pudo guardar el PDF". En el navegador se descarga como siempre.

### Seguridad
- **Inactividad:** la sesión se cierra tras 30 min sin actividad (`INACTIVIDAD_MAXIMA_SEGUNDOS`). El backend lo valida en cada petición y el front cierra la sesión y muestra *"Tu sesión se ha cerrado por inactividad."*.
- **Intentos fallidos** (`app/core/bloqueo.py`): a los 5 intentos seguidos la cuenta se desactiva. Si es el **único ADMIN activo** no se desactiva: queda bloqueada 15 min. Dos admins fallando a la vez nunca quedan ambos desactivados.
- **Reactivación:** un ADMIN la hace desde **Usuarios**; se limpia el contador y el motivo del bloqueo.
- **Auditoría:** la tabla `auditoria_cuentas` registra bloqueos, reactivaciones y desactivaciones (cuenta, quién, cuándo, motivo). Las últimas aparecen en el dashboard del ADMIN.

## 9. Base de datos y migraciones
El esquema se versiona con **Alembic**. `alembic/env.py` toma la conexión de `app/core/db.py` y los modelos de `SQLModel.metadata`.

### Flujo al cambiar un modelo
```powershell
# 1. Generar la migración
python -m alembic revision --autogenerate -m "descripcion_del_cambio"
# 2. Revisar el archivo en alembic/versions/ (autogenerate solo propone)
# 3. Aplicarla
python -m alembic upgrade head
# Ver la revisión aplicada
python -m alembic current
```

### Consideraciones
- Todo modelo nuevo debe importarse en `alembic/env.py` y en `app/models/__init__.py`.
- `env.py` usa `render_as_batch=True` (SQLite no soporta `ALTER TABLE` completo) y apaga las claves foráneas solo mientras migra, porque el modo batch recrea tablas.
- Alembic **no detecta** cambios en restricciones `CHECK`: agrégalas a mano en la migración.
- La migración inicial (`0b66029e01a1`) crea la tabla temporal `test_model`; se mantiene porque es la raíz de la cadena, y `cc5d56d0ebf4` la elimina.
- Si una base de datos ya tenía `detalle_presupuesto` (creada con `scripts.generate`) pero `alembic current` muestra `5691bba44b53`: `python -m alembic stamp cbb87f34d7fe` y luego `python -m alembic upgrade head`.

### Crear o recrear tablas sin Alembic (`scripts.generate`)
Útil para pruebas rápidas; en el día a día usa `scripts.iniciar` o Alembic.
```powershell
python -m scripts.generate           # crea solo las tablas que falten
python -m scripts.generate -d        # borra las tablas de los modelos y las recrea (pide confirmación)
python -m scripts.generate -d --all  # borra TODO, incluidas tablas ajenas
python -m scripts.generate -d -y     # sin preguntar
```

## 10. Pruebas
Usan SQLite en memoria (o archivos temporales): **no tocan** la base de datos real.

```powershell
python -m pytest -v                                   # todas (250)
python -m pytest tests/test_auth.py -v                # login y roles
python -m pytest tests/test_permisos_seguridad.py -v  # permisos, bloqueo e inactividad
python -m pytest tests/test_costos_presupuesto.py -v  # costos, porcentajes y totales
python -m pytest tests/test_exportar_pdf.py -v        # exportación a PDF
python -m pytest tests/test_seeds_inicio.py -v        # seeds y script de inicio
python -m pytest tests/test_correcciones_validaciones.py -v  # VIEWER, PDF escritorio, listados, avisos y validaciones
python -m pytest tests/test_codigos_mayusculas.py -v  # códigos en mayúsculas
python -m pytest tests/test_bd_red_errores.py -v      # base faltante/errores, WAL y modo red
```

Para revisar que `docs/rutas.md` coincide con las rutas reales: `python -m scripts.listar_rutas`.

## 11. Empaquetado (ejecutable)
Usa **siempre** el spec versionado:
```powershell
pyinstaller build.spec
```
El ejecutable queda en `dist/`. Antes de empaquetar, compila el CSS de Tailwind.

Al abrirse, el ejecutable **prepara la base de datos** en la carpeta de datos del usuario: si no existe la crea con todas las tablas, y si viene de una versión anterior aplica las migraciones pendientes (por eso `build.spec` incluye `alembic/` y `alembic.ini`). Si no hay ningún ADMIN activo crea `admin` / `admin123`. Si algo falla, muestra el error en una ventana.

> ⚠️ No ejecutes `pyinstaller client.py` directamente: genera un `.spec` automático que no debe subirse. El único válido es `build.spec`.

## 12. SECRET_KEY y sesiones
La sesión (usuario y última actividad) va en una cookie firmada con `SECRET_KEY`.

**De dónde sale la clave (en orden):**
1. Variable de entorno o archivo `.env` (desarrollo; ver `.env.example`).
2. `secret_key.txt` en la carpeta de datos del usuario (producción).
3. Si no existe ninguna, se genera sola en la primera ejecución.

**Cómo rotarla si se filtra:**
- *Desarrollo:* genera una nueva con `python -c "import secrets; print(secrets.token_hex(32))"`, reemplázala en `.env` y reinicia la app.
- *Ejecutable:* cierra la app, borra `secret_key.txt` de `%LOCALAPPDATA%\inacap\APU sefel\` y vuelve a abrirla.

Todas las sesiones activas se invalidan. Si la clave llegó a subirse a git, rotarla es obligatorio: borrarla del repositorio no basta, queda en el historial.

## 13. Estructura del proyecto
```text
app/
├── main.py                 # Aplicación FastAPI: login, logout, registro de routers
├── templates.py            # Configuración de Jinja2 (filtros y funciones globales)
├── core/
│   ├── config.py           # Rutas de datos, SECRET_KEY, inactividad, datos de la empresa
│   ├── db.py               # Motor SQLite y sesión
│   ├── dependencies.py     # Usuario actual, control de inactividad, requireRoles
│   ├── permisos.py         # Roles por módulo
│   ├── validaciones.py     # Reglas de texto y fechas (backend + patrones del front)
│   ├── bloqueo.py          # Intentos fallidos y auditoría de cuentas
│   ├── inicializacion.py   # Crear/migrar la BD, detectar una base faltante y asegurar un ADMIN
│   ├── errores_bd.py       # Explicación de cada error de base de datos
│   ├── calculos.py         # Subtotales, porcentajes y totales
│   ├── pdf_presupuesto.py  # Cotización en PDF (ReportLab)
│   └── routers/            # admin, apu, items, presupuestos, dashboard
├── models/                 # User, APU, Presupuesto, DetallePresupuesto, AuditoriaCuenta
├── templates/              # Páginas y fragmentos HTMX
└── static/                 # CSS compilado, JS (HTMX + Alpine), imágenes
alembic/                    # Migraciones
scripts/
├── iniciar.py              # Inicio: BD, admin, puerto y ventana
├── seed_admin.py           # Usuarios de prueba
├── seed_apus.py            # Catálogo de APU de ejemplo
├── seed_presupuestos.py    # Presupuestos de ejemplo
├── generate.py             # Crear/recrear tablas sin Alembic
└── listar_rutas.py         # Lista las rutas de la app
tests/                      # Pruebas (pytest)
docs/rutas.md               # Rutas y su protección
client.py                   # Lanzador de la ventana de escritorio (pywebview)
build.spec                  # Configuración de PyInstaller (¡no borrar!)
CONVENIOS.md                # Convenciones de nombres y ramas
```
