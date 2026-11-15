from datetime import datetime

from sqlmodel import Session, select

from app.core.db import engine
from app.models.user import Presupuesto, User

with Session(engine) as session:
    usuario = session.exec(select(User).where(User.username == "presupuestos")).first()
    if usuario is None:
        raise SystemExit("No existe el usuario 'presupuestos'. Ejecuta: python -m scripts.seed_admin")

    presupuesto = Presupuesto(
        id_usuario=usuario.id,
        code="PRE-PRUEBA",
        client_name="Cliente de prueba",
        estimate_income=1000000,
        start_date=datetime(2026, 11, 1),
        end_date=datetime(2026, 12, 31),
        description="Presupuesto de prueba para ítems",
        ruta_reporte="",
    )
    session.add(presupuesto)
    session.commit()
    session.refresh(presupuesto)

    print("Presupuesto creado con id:", presupuesto.id_presupuesto)