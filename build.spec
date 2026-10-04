# build.spec
from PyInstaller.utils.hooks import collect_submodules

hidden = collect_submodules("uvicorn") + [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
]

a = Analysis(
    ["client.py"],
    pathex=[],
    binaries=[],
    datas=[("app/static", "app/static")],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="MiApp",
    console=False,       # equivale a --windowed
    onefile=True,        # equivale a --onefile
)