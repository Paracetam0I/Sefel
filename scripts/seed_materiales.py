"""
Seed del catálogo de materiales (datos de prueba).

Uso:
    python -m scripts.seed_materiales
"""

from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, select

from app.core.db import engine
from app.models.material import Material

# (code, name, category, unit, unit_cost, is_active)
SEED_MATERIALES = [
    ("MAT-0101", "Perfil C 150x50x3 mm", "Acero", "ml", 9850, True),
    ("MAT-0102", "Plancha acero A37 e=6 mm", "Acero", "m²", 58200, True),
    ("MAT-0115", "Hormigón premezclado H-25", "Hormigón", "m³", 112400, True),
    ("MAT-0116", "Barra acero A630 Ø12 mm", "Acero", "kg", 1180, True),
    ("MAT-0124", "Panel PIR 100 mm", "Panel", "m²", 31600, True),
    ("MAT-0130", "Pintura anticorrosiva epóxica", "Pintura", "gl", 42900, True),
    ("MAT-0131", 'Perno de anclaje 3/4" galv.', "Fijación", "un", 3450, False),
    ("MAT-0142", "Ladrillo fiscal 29x14x7 cm", "Albañilería", "un", 390, False),
]


def run() -> None:
    print("Sembrando materiales...")
    with Session(engine) as session:
        for code, name, category, unit, unit_cost, is_active in SEED_MATERIALES:
            existing = session.exec(
                select(Material).where(func.lower(Material.code) == code.lower())
            ).first()

            if existing is not None:
                print(f"  = ya existía {code} (sin cambios)")
                continue

            session.add(
                Material(
                    code=code,
                    name=name,
                    category=category,
                    unit=unit,
                    unit_cost=unit_cost,
                    is_active=is_active,
                )
            )
            print(f"  + creado  {code:<10} {name}")

        session.commit()

    print("✔ Seed de materiales completado.")


if __name__ == "__main__":
    run()