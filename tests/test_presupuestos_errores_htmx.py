from datetime import datetime

from app.models.user import Presupuesto


def test_error_del_formulario_htmx_se_muestra_dentro_del_modal(
    logged_in_client, session, user
):
    session.add(Presupuesto(
        id_usuario=user.id, code="PRE-001", client_name="Cliente",
        estimate_income=1000000,
        start_date=datetime(2026, 11, 1), end_date=datetime(2026, 12, 31),
        description="Existente",
    ))
    session.commit()

    response = logged_in_client.post(
        "/presupuestos",
        data={
            "code": "PRE-001", "client_name": "Otro",
            "estimate_income": "5000", "description": "Repetido",
        },
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert response.headers["HX-Retarget"] == "#modal-presupuesto-body"
    assert response.headers["HX-Reswap"] == "innerHTML"
    assert "Ya existe un presupuesto con ese código." in response.text