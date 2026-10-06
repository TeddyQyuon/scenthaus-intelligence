"""Exercise the packaged API using only Vercel runtime dependencies and httpx."""

import importlib.util
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]
os.environ["VERCEL"] = "1"
os.environ.pop("SCENTHAUS_BUILD_TRAINING", None)

for package in ["torch", "sentence_transformers", "mlflow", "lightgbm"]:
    assert importlib.util.find_spec(package) is None, package

from fastapi.testclient import TestClient
from main import app


def main() -> None:
    checks = []
    with TestClient(app, base_url="https://scenthaus-runtime.example") as client:
        health = client.get("/api/health")
        assert health.status_code == 200 and health.json()["models_ready"]
        checks.append("database health and checksum-verified model startup")

        catalogue = client.get("/api/products?in_stock=false")
        assert catalogue.status_code == 200
        data = catalogue.json()
        assert len(data["products"]) == 150 and len(data["brands"]) == 35
        checks.append("150 products and 35 brands")

        session = client.get("/api/auth/session")
        assert session.status_code == 200 and session.json()["csrf"]
        client.headers.update({
            "Origin": "http://127.0.0.1:5173",
            "X-CSRF-Token": session.json()["csrf"],
        })
        assert client.get("/api/admin/overview").status_code in {401, 403}
        assert client.get("/api/internal/maintenance").status_code == 401
        checks.append("JWT session issuance and guest/admin/cron access control")

        search = client.get("/api/search", params={"q": "fresh office scent under $150"})
        assert search.status_code == 200, search.text
        result = search.json()
        assert result["products"] and result["model_version"]
        assert result["parsed"]["budget"] == 150
        checks.append("pinned ONNX semantic search without training dependencies")

        login = client.post("/api/auth/login", json={
            "email": os.environ["ADMIN_EMAIL"],
            "password": os.environ["ADMIN_PASSWORD"],
        })
        assert login.status_code == 200, login.text
        client.headers["X-CSRF-Token"] = login.json()["csrf"]
        assert client.get("/api/admin/overview").status_code == 200
        sku = data["products"][0]["variants"][0]["sku"]
        forecast = client.get("/api/forecast/sku", params={"sku": sku})
        assert forecast.status_code == 200, forecast.text
        assert forecast.json()["model_version"] == result["model_version"]
        checks.append("JWT authentication, protected admin and model-versioned forecasts")

    Path("reports/runtime-verification.json").write_text(json.dumps({
        "source": os.environ["VERIFIED_SOURCE"],
        "environment": "isolated runtime-only venv; httpx is the test transport",
        "training_packages_absent": True,
        "model_version": result["model_version"],
        "checks": checks,
    }, indent=2))
    print("Runtime-only verification passed: " + "; ".join(checks))


if __name__ == "__main__":
    main()
