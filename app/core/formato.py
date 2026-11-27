"""Filtros de formato para las plantillas (se registran en app/templates.py).

EN SIMPLE
    Convierten datos "crudos" en texto bonito para mostrar:
    184350000 -> "$ 184.350.000", un datetime -> "26/11/2026", "ADMIN" ->
    "Administrador".

TÉCNICO
    Son funciones puras (no tocan la BD). En Jinja se usan como filtros:
    {{ presupuesto.total | clp }}, {{ fecha | fecha }}, {{ rol | rol_label }}.
"""
from datetime import datetime

# Traducción de los valores de UserRole (en inglés, guardados en la BD)
# a etiquetas legibles en español para la interfaz.
ETIQUETAS_ROL = {
    "ADMIN": "Administrador",
    "MATERIALS": "Materiales",
    "BUDGETS": "Presupuestos",
    "BOTH": "Materiales y presupuestos",
    "VIEWER": "Visualizador",
}


def formatearClp(valor: int | float | None) -> str:
    """184350000 -> '$ 184.350.000'.

    Técnico: f"{valor:,.0f}" usa coma de miles y sin decimales (formato
    inglés); luego se cambia la coma por punto (formato chileno).
    """
    if valor is None:
        return "—"
    return "$ " + f"{valor:,.0f}".replace(",", ".")


def formatearFecha(valor: datetime | None) -> str:
    """Fecha local dd/mm/aaaa; '—' si no hay fecha. Los datetime sin zona se tratan como UTC.

    Técnico: la BD guarda fechas en UTC; astimezone() las pasa a la zona
    horaria del equipo antes de formatear.
    """
    if valor is None:
        return "—"
    if valor.tzinfo is None:
        from datetime import timezone
        valor = valor.replace(tzinfo=timezone.utc)
    return valor.astimezone().strftime("%d/%m/%Y")


def etiquetaRol(rol) -> str:
    """UserRole (o su texto) -> 'Administrador', 'Visualizador', ...

    Acepta tanto el enum (usa su .value) como el texto directo.
    """
    clave = getattr(rol, "value", rol)
    return ETIQUETAS_ROL.get(clave, str(clave))


def iniciales(nombre: str | None) -> str:
    """'Javier Muñoz' -> 'JM'. Se usa en el avatar del menú. '?' si no hay nombre."""
    partes = (nombre or "").split()[:2]
    return "".join(p[0] for p in partes).upper() or "?"
