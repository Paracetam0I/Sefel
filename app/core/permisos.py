"""Roles permitidos por módulo.

Fuente única de verdad: los routers la usan con requireRoles() (403 en backend,
mismo formato que admin/users) y las plantillas con puede() para ocultar
enlaces y botones. Ocultar en el front es solo comodidad; la validación real
es la del backend.
"""
from typing import Annotated

from fastapi import Depends

from app.core.dependencies import requireRoles
from app.models.user import User, UserRole

ROLES_USUARIOS = (UserRole.ADMIN,)
ROLES_APU = (UserRole.MATERIALS, UserRole.BOTH, UserRole.ADMIN)
# VIEWER: solo lectura y exportar
ROLES_PRESUPUESTOS_LECTURA = (
    UserRole.BUDGETS, UserRole.BOTH, UserRole.ADMIN, UserRole.VIEWER,
)
ROLES_PRESUPUESTOS_EDICION = (UserRole.BUDGETS, UserRole.BOTH, UserRole.ADMIN)

PERMISOS = {
    "usuarios": ROLES_USUARIOS,
    "apu": ROLES_APU,
    "presupuestos": ROLES_PRESUPUESTOS_LECTURA,
    "presupuestos_edicion": ROLES_PRESUPUESTOS_EDICION,
}

# Alias para las firmas de los endpoints
UsuarioApu = Annotated[User, Depends(requireRoles(*ROLES_APU))]
UsuarioPresupuestosLectura = Annotated[
    User, Depends(requireRoles(*ROLES_PRESUPUESTOS_LECTURA))
]
UsuarioPresupuestosEdicion = Annotated[
    User, Depends(requireRoles(*ROLES_PRESUPUESTOS_EDICION))
]


def puede(usuario: User | None, permiso: str) -> bool:
    """En plantillas: {% if puede(usuario, "apu") %} ... {% endif %}"""
    if usuario is None:
        return False
    return usuario.role in PERMISOS.get(permiso, ())
