from app.models.user import UserRole

def test_login_correcto(client, user):
    response = client.post(
        "/login",
        data={
            "username": user.username,
            "password": "TestPassword123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"
    assert "sefel_session" in response.cookies


def test_login_incorrecto(client, user):
    response = client.post(
        "/login",
        data={
            "username": user.username,
            "password": "ClaveIncorrecta",
        },
    )

    assert response.status_code == 401
    assert "Usuario o contraseña incorrectos" in response.text


def test_acceso_sin_sesion(client):
    response = client.get("/protegido", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


def test_acceso_con_rol_incorrecto(client, user, session):
    user.role = UserRole.VIEWER
    session.add(user)
    session.commit()

    login = client.post(
        "/login",
        data={
            "username": user.username,
            "password": "TestPassword123",
        },
        follow_redirects=False,
    )
    assert login.status_code == 303

    response = client.get("/prueba/solo-admin")

    assert response.status_code == 403

