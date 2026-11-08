from fastapi import APIRouter, Request

from app.core.datos_demo import PROYECTOS_DEMO, RESUMEN_PROYECTOS_DEMO
from app.core.dependencies import CurrentUser
from app.templates import templates

router = APIRouter(tags=["proyectos"])


@router.get("/proyectos")
def listar(request: Request, usuario: CurrentUser):
    # TODO: reemplazar los datos de demo por consultas a la base de datos
    return templates.TemplateResponse(
        request=request,
        name="proyectos.html",
        context={
            "usuario": usuario,
            "proyectos": PROYECTOS_DEMO,
            "resumen": RESUMEN_PROYECTOS_DEMO,
        },
    )
