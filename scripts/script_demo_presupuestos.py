# script_demo.py
from datetime import datetime, timezone, timedelta

from sqlmodel import Session, select

from app.core.db import engine      
from app.models.user import User, Presupuesto


def crear_presupuesto() -> int | None:
    with Session(engine) as session:
        usuario = session.exec(
            select(User).where(User.username == "presupuestos")
        ).first()

        if usuario is None:
            print("⚠️  El usuario 'presupuestos' no existe. Corre primero tu seed.")
            return None

        ahora = datetime.now(timezone.utc)
        nuevo = Presupuesto(
            id_usuario=usuario.id,                     
            code="PRES-2026-001",
            client_name="Constructora Andina S.A.",    
            status="DRAFT",
            estimate_income=15_000_000,                
            start_date=ahora,                          
            end_date=ahora + timedelta(days=30),       
            description="Presupuesto de prueba para obra de infraestructura",
            created_at=ahora,                          
            costo_directo=8_000_000,                   
            costo_indirecto=2_000_000,                 
            ruta_reporte="/reports/pres-2026-001.pdf", 
        )
        session.add(nuevo)
        session.commit()
        session.refresh(nuevo)

        print(f"✅ Presupuesto creado: id={nuevo.id_presupuesto}, code={nuevo.code}")
        return nuevo.id_presupuesto


def leer_presupuesto(id_presupuesto: int) -> None:
    """Lee un presupuesto por su PK y muestra sus datos + su dueño."""
    with Session(engine) as session:
        p = session.get(Presupuesto, id_presupuesto)

        if p is None:
            print(f"❌ No existe presupuesto con id={id_presupuesto}")
            return

        print("\n📄 Datos del presupuesto:")
        print(f"   code         : {p.code}")
        print(f"   client_name   : {p.client_name}")
        print(f"   status       : {p.status}")
        print(f"   estimate     : {p.estimate_income:,}")
        print(f"   createdAt    : {p.created_at}")
        print(f"   costoDirecto : {p.costo_directo}")
        print(f"   costoIndirecto: {p.costo_indirecto}")


        if p.usuario is not None:
            print(f"   dueño        : {p.usuario.username} ({p.usuario.full_name})")
        else:
            print("   dueño        : (sin usuario asociado)")


def listar_presupuestos_de_usuario(username: str) -> None:
    """Usa la Relationship inversa: usuario.presupuestos."""
    with Session(engine) as session:
        usuario = session.exec(
            select(User).where(User.username == username)
        ).first()

        if usuario is None:
            print(f"❌ No existe el usuario {username}")
            return

        print(f"\n📚 Presupuestos de {usuario.username}:")
        if not usuario.presupuestos:
            print("   (ninguno)")
            return

        for p in usuario.presupuestos:
            print(f"   - [{p.id_presupuesto}] {p.code} | {p.client_name} | {p.status}")


if __name__ == "__main__":
    pid = crear_presupuesto()
    if pid is not None:
        leer_presupuesto(pid)
        listar_presupuestos_de_usuario("presupuestos")