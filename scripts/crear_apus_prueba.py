
from sqlmodel import Session, select

from app.core.db import engine
from app.models.apu import APU
from app.models.detalle_apu import DetalleApu
from app.models.material import CategoriaRecurso, Material

CODIGO_RECURSO_PRUEBA = "REC-TEST-001"


def _recursoDePrueba(session: Session) -> Material:
    """Recurso de la base de datos con el que se arma la receta de los APU de prueba."""
    recurso = session.exec(
        select(Material).where(Material.code == CODIGO_RECURSO_PRUEBA)
    ).first()
    if recurso is None:
        recurso = Material(
            code=CODIGO_RECURSO_PRUEBA,
            name="Recurso de prueba",
            unit="m3",
            category=CategoriaRecurso.MATERIALES,
            unit_cost=85000,
            real_unit_cost=85000,
            description="Registro temporal para probar la paginación.",
        )
        session.add(recurso)
        session.flush()
    return recurso


def main():
    with Session(engine) as session:
        recurso = _recursoDePrueba(session)
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
                    description="Registro temporal para probar la paginación.",
                    # Receta: (1 + numero/85) × recurso de $85.000 = 85.000 + numero × 1.000
                    recursos=[
                        DetalleApu(
                            id_material=recurso.id,
                            unit="m3",
                            cantidad=round(1 + numero / 85, 4),
                        )
                    ],
                )
            )

        session.add_all(apus)
        session.commit()

        print(f"Se crearon {len(apus)} APU de prueba.")


if __name__ == "__main__":
    main()
