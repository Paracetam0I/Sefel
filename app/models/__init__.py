# app/models/__init__.py
# Reúne todos los modelos en un solo lugar para poder importar así:
#   from app.models import APU, User, Presupuesto
# Además, al importarlos aquí, SQLModel "conoce" todas las tablas (lo necesitan
# Alembic y la creación de tablas en app/core/inicializacion.py).
from app.models.apu import APU, APUValidacion
from app.models.user import User, UserRole
from app.models.presupuesto import (
    PorcentajesValidacion,
    Presupuesto,
    PresupuestoValidacion,
    StatusPresupuestos,
)
from app.models.detalle_presupuesto import DetallePresupuesto
from app.models.auditoria import AccionAuditoria, AuditoriaCuenta

__all__ = [
    "APU", "APUValidacion",
    "User", "UserRole",
    "Presupuesto", "PresupuestoValidacion", "PorcentajesValidacion", "StatusPresupuestos",
    "DetallePresupuesto",
    "AccionAuditoria", "AuditoriaCuenta",
]
