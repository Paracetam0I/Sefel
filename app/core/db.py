from sqlalchemy import URL
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, create_engine

from app.core.config import DATABASE_PATH

DATABASE_URL = URL.create(
    drivername="sqlite",
    database=str(DATABASE_PATH),
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
)


def getSession():
    with SessionLocal() as session:
        yield session