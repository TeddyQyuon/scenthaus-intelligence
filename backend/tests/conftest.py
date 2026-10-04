import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        r = c.get("/auth/session")
        assert r.status_code == 200
        c.headers.update(
            {"Origin": "http://localhost:5173", "X-CSRF-Token": r.json()["csrf"]}
        )
        yield c


@pytest.fixture
def admin(client):
    from app.config import settings

    r = client.post(
        "/auth/login",
        json={"email": settings.admin_email, "password": settings.admin_password},
    )
    assert r.status_code == 200
    client.headers["X-CSRF-Token"] = r.json()["csrf"]
    return client
