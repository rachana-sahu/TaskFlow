from tests.conftest import register


def test_login_session_and_logout_revoke_cookie(client):
    register(client)
    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "invalid"})
    assert client.get("/api/v1/auth/me").status_code == 200

    client.cookies.clear()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "dev@example.com", "password": "incorrect-password-123"},
    )
    assert response.status_code == 401
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "dev@example.com", "password": "correct-horse-battery"},
    )
    assert response.status_code == 200
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_registration_rejects_unknown_timezone(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "timezone@example.com",
            "password": "correct-horse-battery",
            "timezone": "Not/A_Time_Zone",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Unknown IANA time zone"
