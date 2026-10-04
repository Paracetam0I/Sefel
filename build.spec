# build.spec
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hidden = (
    collect_submodules("uvicorn")
    + collect_submodules("fastapi")
    + collect_submodules("starlette")
    + collect_submodules("jinja2")
    + [
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        "app.main",  
    ]
)

a = Analysis(
    ["client.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("app/static",    "static"),      
        ("app/templates", "templates"),   
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