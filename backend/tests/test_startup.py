"""Storefront requests must not depend on recommendation artifacts or training imports."""
import subprocess
import sys
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app, store
from app.models import Product, Variant


def test_app_import_defers_scientific_dependencies():
    result = subprocess.run(
        [sys.executable, "-c", "import app.main, sys; assert not any(name in sys.modules for name in ('numpy', 'pandas', 'sklearn', 'onnxruntime', 'tokenizers'))"],
        check=False, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_catalogue_without_models_uses_three_queries_and_keeps_brand_filters(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        for i, brand in enumerate(["Dior", "Chanel", "Hidden", "Future"], 1):
            db.add(Product(id=i, slug=f"scent-{i}", name=f"Scent {i}", brand=brand,
                           concentration="EDP", category="Fresh", description="Test reference",
                           notes={"top": [], "heart": [], "base": []}, accords=[], seasons=[],
                           occasions=[], longevity=4, sillage="Soft", hidden=i == 3,
                           launch_date=date.today() + timedelta(days=1 if i == 4 else -1)))
            db.add(Variant(id=i, product_id=i, sku=f"SKU-{i}", size_ml=50, price=90,
                           stock=3 if i == 1 else 0))
        db.commit()
    queries = []
    event.listen(engine, "before_cursor_execute", lambda *args: queries.append(args[2]))

    def database():
        with Session(engine) as db:
            yield db

    def unavailable_models():
        raise AssertionError("Ordinary browsing must not load recommendation artifacts")

    monkeypatch.setattr(store, "get", unavailable_models)
    app.dependency_overrides[get_db] = database
    try:
        with TestClient(app) as client:
            response = client.get("/products?brand=Dior&in_stock=true")
            assert response.status_code == 200
            data = response.json()
            assert [p["brand"] for p in data["products"]] == ["Dior"]
            assert data["brands"] == ["Chanel", "Dior"]
            assert len(queries) == 3
            queries.clear()
            data = client.get("/products").json()
            assert len(data["products"]) == 2
            assert len(queries) == 3
            assert client.get("/admin/overview").status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
