import sys
from pathlib import Path
import platformdirs

APP_NAME = "APU sefel"
APP_AUTHOR = "inacap"

def resourcePath(rel: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent.parent
    return base / rel

def userDataPath(rel: str) -> Path:
    base = Path(platformdirs.user_data_dir(APP_NAME, APP_AUTHOR))
    full = base / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    return full
