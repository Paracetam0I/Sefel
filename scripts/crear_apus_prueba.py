
from sqlmodel import Session, select

from app.core.db import engine
from app.models.apu import APU


def main():
    with Session(engine) as session:
        apus = []

        for numero in range(2, 13):
            codigo = f"APU-TEST-{numero:03d}"

            existente = session.exec(
                select(APU).where(APU.code == codigo)
            ).first()

            if existente:
                continue

            apus.append(
                APU(
                    code=codigo,
                    name=f"APU de prueba {numero:03d}",
                    unit="m3",
                    category="Pruebas de paginación",
                    unit_cost=85000 + numero * 1000,
                    description="Registro temporal para probar la paginación.",
                )
            )

        session.add_all(apus)
        session.commit()

        print(f"Se crearon {len(apus)} APU de prueba.")


if __name__ == "__main__":
    main()
