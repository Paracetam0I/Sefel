import sqlite3
from urllib.parse import quote

from sqlalchemy import URL, event
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, create_engine

from app.core.config import DATABASE_PATH

# mode=rw: si el archivo no existe, la conexión FALLA en vez de crear uno vacío.
# Así, si la base se borra o se mueve mientras la app corre, se informa el error
# en lugar de seguir con una base vacía. Crearla es una decisión explícita
# (crearArchivoBD), que toma app/core/inicializacion.py al arrancar.
DATABASE_URL = URL.create(
    drivername="sqlite",
    database=f"file:{quote(DATABASE_PATH.as_posix(), safe='/:')}?mode=rw",
    query={"uri": "true"},
)

# Segundos que una escritura espera si otra tiene la base bloqueada, antes de
# fallar con "database is locked" (el valor por defecto de SQLite es 5).
ESPERA_BLOQUEO_SEGUNDOS = 15

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": ESPERA_BLOQUEO_SEGUNDOS},
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
)

@event.listens_for(engine, "connect")
def _enable_sqlite_fks(dbapi_conn, _record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    # WAL: leer no bloquea a quien escribe ni al revés. Con varios usuarios a la
    # vez evita los "database is locked" (medido: ver README, "Capacidad").
    # Crea sefel.db-wal y sefel.db-shm junto a la base: son parte de ella.
    # Ojo: WAL no funciona si la base está en una carpeta de red compartida.
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")   # seguro con WAL y más rápido
    cursor.execute(f"PRAGMA busy_timeout={ESPERA_BLOQUEO_SEGUNDOS * 1000}")
    cursor.close()


def crearArchivoBD() -> bool:
    """Crea el archivo de la base (vacío) si no existe. Devuelve True si lo creó.

    El motor de la app nunca crea el archivo por su cuenta (mode=rw); esto se
    llama solo cuando crear una base nueva es la decisión correcta.
    """
    if DATABASE_PATH.exists():
        return False
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    sqlite3.connect(DATABASE_PATH).close()
    return True


def getSession():
    with SessionLocal() as session:
        yield session
