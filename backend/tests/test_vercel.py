import pytest
from fastapi.testclient import TestClient
from main import app
from app.config import Settings
from app.database import SessionLocal
from app.models import Product
from app.vercel_init import package_runtime_ml, verify_catalog


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


def test_release_catalog_gate_is_read_only(client):
    with SessionLocal() as db:
        verify_catalog(db)
        product = db.get(Product, 1)
        original = product.image_path
        product.image_path = "/images/legacy-product.png"
        db.commit()
        try:
            with pytest.raises(RuntimeError, match="requires the 150 real-product catalogue"):
                verify_catalog(db)
            db.refresh(product)
            assert product.image_path == "/images/legacy-product.png"
        finally:
            product.image_path = original
            db.commit()


def test_vercel_ml_packaging_is_self_contained_and_omits_training_data(tmp_path):
    source = tmp_path / "repository" / "ml"
    (source / "configs").mkdir(parents=True)
    (source / "tests").mkdir()
    (source / "reports").mkdir()
    (source / "data").mkdir()
    for name in [
        "__init__.py",
        "core.py",
        "embeddings.py",
        "rec_serving.py",
        "search.py",
        "tracking.py",
        "train_all.py",
    ]:
        (source / name).write_text("# fixture\n")
    (source / "configs" / "search.yaml").write_text("k: 10\n")
    (source / "tests" / "test_runtime.py").write_text("assert True\n")
    (source / "reports" / "search.md").write_text("report\n")
    (source / "data" / "fixture.json").write_text("{}\n")

    service_root = tmp_path / "backend"
    service_root.mkdir()
    destination = package_runtime_ml(service_root, tmp_path / "repository")

    assert (destination / "core.py").is_file()
    assert (destination / "configs" / "search.yaml").is_file()
    assert (destination / "search.py").is_file()
    assert not (destination / "train_all.py").exists()
