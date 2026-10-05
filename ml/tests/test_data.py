"""Tests assert catalog provenance and behaviour, not hidden taste ground truth."""

from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select, func

from app.catalog import catalog, slugify
from app.database import SessionLocal
from app.main import app
from app.ml.data import load, validate
from app.models import Product, User, StockWeek
from ml.data.generate_orders import generate


def test_all_requested_brands_and_real_image_assets():
    data = catalog()
    rows = data["products"]
    assert len(rows) == 150 and len(data["brands"]) == 35
    assert set(data["brands"]) == {p["brand"] for p in rows}
    assert len({p["image_sha256"] for p in rows}) == 150
    assert len({slugify(p["name"], p["brand"]) for p in rows}) == 150
    root = Path(__file__).resolve().parents[2] / "frontend/public"
    for p in rows:
        assert p["image_source"].startswith("https://")
        assert p["source_kind"] in {"manufacturer", "retailer"}
        assert (root / p["image_path"].lstrip("/")).stat().st_size > 1000
        assert all(20 <= s <= 200 for s in p["sizes_ml"])


def test_generator_is_reproducible_and_respects_stockouts():
    p = [
        {"id": i, "accords": ["fresh"], "launch_date": date(2025, 3, 31)}
        for i in range(1, 5)
    ]
    v = [{"id": i, "product_id": i, "price": 120.0} for i in range(1, 5)]
    c = {
        "seed": 42,
        "users": 5,
        "weeks": 2,
        "start": "2025-03-31",
        "quiz_fraction": 0.4,
        "stockout_probability": 0.1,
    }
    a = generate(p, v, c)
    assert a == generate(p, v, c)
    assert all(o["status"] == "simulated" and o["simulated"] for o in a["orders"])
    assert all("taste" not in u for u in a["users"])
    orders = {o["id"]: o for o in a["orders"]}
    availability = {
        (s["variant_id"], s["week"]): s["in_stock"] for s in a["stock_weeks"]
    }
    from datetime import timedelta

    for line in a["lines"]:
        day = orders[line["order_id"]]["created_at"].date()
        monday = day - timedelta(days=day.weekday())
        assert availability[line["variant_id"], monday]


def test_seed_and_data_validation():
    with SessionLocal() as db:
        assert db.scalar(select(func.count(Product.id))) == 150
        assert (
            db.scalar(select(func.count(User.id)).where(User.simulated.is_(True)))
            == 2000
        )
        assert db.scalar(select(func.count(StockWeek.week))) > 20000
        p, v, o, _, _ = load(db)
        assert validate(p, v, o)["passed"]
        assert len({*p.brand}) == 35


def test_events_require_consent_and_valid_product():
    with TestClient(app) as client:
        session = client.get("/auth/session").json()
        client.headers.update(
            {"Origin": "http://localhost:5173", "X-CSRF-Token": session["csrf"]}
        )
        assert (
            client.post("/events", json={"product_id": 1, "event_type": "view"}).json()[
                "accepted"
            ]
            is False
        )
        assert client.put("/privacy/consent", json={"consent": True}).status_code == 200
        assert (
            client.post("/events", json={"product_id": 1, "event_type": "view"}).json()[
                "accepted"
            ]
            is True
        )
        assert (
            client.post(
                "/events", json={"product_id": 9999, "event_type": "view"}
            ).status_code
            == 404
        )
        client.cookies.set("scenthaus_session", "invalid.jwt.token")
        assert client.get("/wishlist").status_code == 401
