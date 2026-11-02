from fastapi import APIRouter, Request

from app.core.datos_demo import MATERIALES_DEMO, RESUMEN_APU_DEMO
from app.core.dependencies import CurrentUser
from app.templates import templates

router = APIRouter(tags=["apu"])


@router.get("/apu")
def listar(request: Request, usuario: CurrentUser):
    # TODO: reemplazar los datos de demo por consultas a la base de datos
    return templates.TemplateResponse(
        request=request,
        name="apu.html",
        context={
            "usuario": usuario,
            "materiales": MATERIALES_DEMO,
            "resumen": RESUMEN_APU_DEMO,
        },
    )
