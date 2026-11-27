"""Roles permitidos por módulo.

EN SIMPLE
    Es la "lista de quién puede entrar a cada sala":
      - Usuarios ............ solo ADMIN.
      - APU (materiales) .... MATERIALS, BOTH, ADMIN.
      - Presupuestos (ver) .. BUDGETS, BOTH, ADMIN y VIEWER.
      - Presupuestos (editar) BUDGETS, BOTH, ADMIN (VIEWER no).

TÉCNICO
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

# Nombre del permiso (el que se usa en las plantillas) -> roles que lo tienen.
PERMISOS = {
    "usuarios": ROLES_USUARIOS,
    "apu": ROLES_APU,
    "presupuestos": ROLES_PRESUPUESTOS_LECTURA,
    "presupuestos_edicion": ROLES_PRESUPUESTOS_EDICION,
}

# Alias para las firmas de los endpoints
# Ej.: `def listar(usuario: UsuarioApu): ...`
# FastAPI ejecuta requireRoles(...) antes del endpoint: si el rol no está en
# la lista, responde 403 y el endpoint ni siquiera se ejecuta. Si está,
# `usuario` llega con el User ya cargado.
UsuarioApu = Annotated[User, Depends(requireRoles(*ROLES_APU))]
UsuarioPresupuestosLectura = Annotated[
    User, Depends(requireRoles(*ROLES_PRESUPUESTOS_LECTURA))
]
UsuarioPresupuestosEdicion = Annotated[
    User, Depends(requireRoles(*ROLES_PRESUPUESTOS_EDICION))
]


def puede(usuario: User | None, permiso: str) -> bool:
    """En plantillas: {% if puede(usuario, "apu") %} ... {% endif %}

    True si el rol del usuario está en la lista de ese permiso. Un permiso
    desconocido devuelve False (más seguro negar que permitir).
    """
    if usuario is None:
        return False
    return usuario.role in PERMISOS.get(permiso, ())
