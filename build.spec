# build.spec
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hidden = (
    collect_submodules("uvicorn")
    + collect_submodules("fastapi")
    + collect_submodules("starlette")
    + collect_submodules("jinja2")
    # Migraciones: Alembic carga env.py y las versiones como archivos sueltos,
    # así que PyInstaller no ve sus imports; se agregan a mano.
    + collect_submodules("alembic")
    + collect_submodules("app")
    + collect_submodules("reportlab")
    + [
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        "app.main",  
        "passlib.handlers.bcrypt",
        "logging.config",
        "sqlmodel.sql.sqltypes",
    ]
)

a = Analysis(
    ["client.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("app/static",    "static"),      
        ("app/templates", "templates"),   
        # La app crea/migra la BD al abrir (app/core/inicializacion.py)
        ("alembic",       "alembic"),
        ("alembic.ini",   "."),
    ],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="MiApp",
    debug=False,
    strip=False,
    upx=True,
    console=True,   # ← True mientras pruebas, luego False
    # onefile=True, ← ELIMINAR: no es un parámetro válido
)