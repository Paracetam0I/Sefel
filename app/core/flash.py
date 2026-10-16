from fastapi import Request
from jinja2 import pass_context


def flash(request: Request, message: str, category: str = "info") -> None:
    """Guarda un mensaje en la sesión; se muestra una sola vez en la siguiente página."""
    request.session.setdefault("_flashes", []).append([category, message])


@pass_context
def getFlashedMessages(context, with_categories: bool = False):
    """Disponible en las plantillas como get_flashed_messages(). Vacía la cola al leerla."""
    request = context.get("request")
    mensajes = request.session.pop("_flashes", []) if request is not None else []
    if with_categories:
        return mensajes
    return [mensaje for _, mensaje in mensajes]
