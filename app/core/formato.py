"""Filtros de formato para las plantillas (se registran en app/templates.py)."""
from datetime import datetime

ETIQUETAS_ROL = {
    "ADMIN": "Administrador",
    "MATERIALS": "Materiales",
    "BUDGETS": "Presupuestos",
    "BOTH": "Materiales y presupuestos",
    "VIEWER": "Visualizador",
}


def formatearClp(valor: int | float | None) -> str:
    """184350000 -> '$ 184.350.000'."""
    if valor is None:
        return "—"
    return "$ " + f"{valor:,.0f}".replace(",", ".")


def formatearFecha(valor: datetime | None) -> str:
    """Fecha local dd/mm/aaaa; '—' si no hay fecha. Los datetime sin zona se tratan como UTC."""
    if valor is None:
        return "—"
    if valor.tzinfo is None:
        from datetime import timezone
        valor = valor.replace(tzinfo=timezone.utc)
    return valor.astimezone().strftime("%d/%m/%Y")


def etiquetaRol(rol) -> str:
    """UserRole (o su texto) -> 'Administrador', 'Visualizador', ..."""
    clave = getattr(rol, "value", rol)
    return ETIQUETAS_ROL.get(clave, str(clave))


def iniciales(nombre: str | None) -> str:
    """'Javier Muñoz' -> 'JM'."""
    partes = (nombre or "").split()[:2]
    return "".join(p[0] for p in partes).upper() or "?"
