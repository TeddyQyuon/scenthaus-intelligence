from fastapi.testclient import TestClient


def test_readiness_connects_to_database():
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ml_namespace_imports():
    import ml

    assert "simulated" in ml.__doc__.lower()
