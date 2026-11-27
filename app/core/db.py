"""
db.py — Conexión a la base de datos SQLite.

EN SIMPLE
    Aquí se "enchufa" la app a la base de datos. Define:
      - engine: la conexión principal (el "cable" a la base).
      - getSession(): presta una sesión a cada petición y la devuelve al
        terminar, como sacar y devolver un libro de la biblioteca.

TÉCNICO
    - SQLAlchemy/SQLModel con SQLite en modo URI (mode=rw) para NO crear un
      archivo vacío por accidente.
    - Un listener "connect" ejecuta PRAGMAs en cada conexión nueva:
      claves foráneas, modo WAL (lecturas y escrituras concurrentes) y
      tiempo de espera ante bloqueos.
    - getSession() es un generador que FastAPI usa como dependencia
      (Depends(getSession)): abre la sesión, la entrega y la cierra al final.
"""
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

# check_same_thread=False: FastAPI atiende peticiones en distintos hilos y
# SQLite, por defecto, solo permite usar la conexión en el hilo que la creó.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": ESPERA_BLOQUEO_SEGUNDOS},
)

# "Fábrica" de sesiones: cada SessionLocal() es una sesión nueva.
# autocommit=False -> hay que llamar session.commit() para guardar.
# autoflush=False  -> no envía cambios a la BD hasta el commit/flush explícito.
SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
)

@event.listens_for(engine, "connect")
def _enable_sqlite_fks(dbapi_conn, _record):
    """Configura cada conexión nueva a SQLite (se ejecuta automáticamente).

    En simple: SQLite viene con algunas protecciones apagadas; aquí se encienden.
    Técnico: foreign_keys=ON hace respetar las claves foráneas (SQLite las
    ignora por defecto); WAL + synchronous=NORMAL mejora la concurrencia;
    busy_timeout espera en vez de fallar si la base está ocupada.
    """
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
    """Dependencia de FastAPI: entrega una sesión de BD por petición.

    Uso en un endpoint: `session: Session = Depends(getSession)`.
    El `with` garantiza que la sesión se cierre aunque ocurra un error.
    """
    with SessionLocal() as session:
        yield session
