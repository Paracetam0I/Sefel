# app/models/__init__.py
from app.models.apu import APU, APUValidacion
from app.models.user import User, Presupuesto, UserRole
from app.models.detalle_presupuesto import DetallePresupuesto   # ← debe estar
from app.models.material import Material

__all__ = [
    "APU", "APUValidacion",
    "User", "Presupuesto", "UserRole",
    "DetallePresupuesto",
    "Material",
]