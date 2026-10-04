from fastapi.testclient import TestClient
from main import app
from app.config import Settings


def test_vercel_mount_and_cron_auth():
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/products").status_code == 200
        assert client.get("/api/internal/maintenance").status_code == 401
        assert client.get("/api/auth/session").status_code == 200


def test_cloud_postgres_url_and_origins(monkeypatch):
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "scenthaus-example.vercel.app")
    monkeypatch.setenv("VERCEL_URL", "scenthaus-preview.vercel.app")
    settings = Settings(
        database_url="postgres://demo:demo@example.test/store?sslmode=require"
    )
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert "https://scenthaus-example.vercel.app" in settings.origins
    assert "https://scenthaus-preview.vercel.app" in settings.origins
