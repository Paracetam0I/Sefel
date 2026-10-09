from collections.abc import Iterator

from sqlalchemy import event
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, create_engine

from app.core.config import DATABASE_URL

#Engine es la conexión a la base de datos, y SessionLocal es la clase que nos permite crear sesiones (una por request)
# Creamos el engine de SQLAlchemy (y por tanto de SQLModel) a partir de la URL de la DB
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # necesario con FastAPI (varios hilos)
    echo=False,  # ponerlo en True si quieres ver el SQL en la terminal
)


# SQLite trae las claves foráneas desactivadas por defecto: las activamos
@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

"""
SessionLocal es la fabrica de sesiones (cada sesión es una transacción de la DB). 
La clase SessionLocal se crea a partir del engine y de la clase Session de SQLModel. 
Es la que se usará en las dependencias de FastAPI para abrir y cerrar sesiones por request.
"""
SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,  # la Session de SQLModel
    autoflush=False,
    expire_on_commit=False,
)

'''
.getSession es lo que FastAPI usará como dependencia para abrir y cerrar sesiones por request.
Abre una sesion con SessionLocal y la cierra al terminar (gracias al with).
'''
def getSession() -> Iterator[Session]:
    """Dependency de FastAPI: abre una sesión por request y la cierra al terminar."""
    with SessionLocal() as session:
        yield session