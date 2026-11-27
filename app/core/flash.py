"""
flash.py — Mensajes de aviso ("flash") para el usuario.

EN SIMPLE
    Son los avisos tipo "Ítem agregado correctamente" o "Contraseña
    incorrecta". Funcionan como un post-it: se pega un mensaje en la sesión
    y se despega (y muestra) en la siguiente página que se vea.

TÉCNICO
    - flash(): agrega [categoría, mensaje] a la lista `_flashes` de la sesión
      (la sesión vive en una cookie firmada, ver SessionMiddleware en main.py).
    - getFlashedMessages(): función global de Jinja que lee y VACÍA la lista.
    - NotificacionesHtmx: para peticiones HTMX (que no recargan la página)
      envía los mensajes en la cabecera HX-Trigger, y base.html los muestra
      como "toast".
    Categorías usadas: "success", "error", "warning", "info".
"""
from fastapi import Request
from jinja2 import pass_context


def flash(request: Request, message: str, category: str = "info") -> None:
    """Guarda un mensaje en la sesión; se muestra una sola vez en la siguiente página."""
    request.session.setdefault("_flashes", []).append([category, message])


@pass_context
def getFlashedMessages(context, with_categories: bool = False):
    """Disponible en las plantillas como get_flashed_messages(). Vacía la cola al leerla.

    @pass_context hace que Jinja entregue el contexto de la plantilla, de donde
    se saca el `request` (y con él, la sesión).
    """
    request = context.get("request")
    mensajes = request.session.pop("_flashes", []) if request is not None else []
    if with_categories:
        return mensajes
    return [mensaje for _, mensaje in mensajes]


# Notificaciones inmediatas en respuestas HTMX
# ==========================================
# Una respuesta HTMX no recarga la página, así que el parcial de flash nunca se
# pinta y el mensaje quedaba esperando a la siguiente página completa. Este
# middleware saca los mensajes pendientes de la sesión y los manda en la misma
# respuesta (cabecera HX-Trigger, evento "notificar"); base.html los muestra
# como toast en la vista actual.

import json

from starlette.middleware.base import BaseHTTPMiddleware

EVENTO_NOTIFICAR = "notificar"


def agregarEvento(respuesta, evento: str, detalle) -> None:
    """Suma un evento a HX-Trigger sin pisar los que ya traiga (p. ej. cerrar un modal).

    HX-Trigger es una cabecera que HTMX lee para disparar eventos JavaScript en
    el navegador. Puede venir como JSON ({"evento": datos}) o como texto simple
    ("evento1, evento2"); se aceptan ambos y se devuelve siempre JSON.
    """
    actual = respuesta.headers.get("HX-Trigger")
    eventos: dict = {}
    if actual:
        try:
            eventos = json.loads(actual)
        except ValueError:
            # Formato simple: "evento1, evento2"
            eventos = {nombre.strip(): None for nombre in actual.split(",") if nombre.strip()}
    eventos[evento] = detalle
    # ensure_ascii: las cabeceras HTTP no admiten tildes sin escapar
    respuesta.headers["HX-Trigger"] = json.dumps(eventos, ensure_ascii=True)


class NotificacionesHtmx(BaseHTTPMiddleware):
    """Debe registrarse DENTRO de SessionMiddleware (antes en el código), para que
    al vaciar la cola la sesión todavía no se haya escrito en la cookie.

    Flujo: deja pasar la petición -> si era HTMX y hay mensajes pendientes,
    los saca de la sesión y los añade como evento "notificar" a la respuesta.
    """

    async def dispatch(self, request, call_next):
        respuesta = await call_next(request)
        if request.headers.get("HX-Request") != "true" or "session" not in request.scope:
            return respuesta
        mensajes = request.session.pop("_flashes", None)
        if mensajes:
            agregarEvento(respuesta, EVENTO_NOTIFICAR, {"mensajes": mensajes})
        return respuesta
