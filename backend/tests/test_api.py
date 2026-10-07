from sqlalchemy import select, func
from app.database import SessionLocal
from app.models import Variant, Event, Wishlist, User, Order, CartItem


def test_health(client):
    assert client.get("/health").json()["models_ready"]


def test_admin_protected(client):
    for path in [
        "/admin/overview",
        "/admin/products",
        "/forecast/summary",
        "/forecast/sku?sku=SH-001-60",
    ]:
        assert client.get(path).status_code == 403


def test_csrf_and_origin(client):
    assert client.put("/wishlist/1", headers={"X-CSRF-Token": "bad"}).status_code == 403
    assert (
        client.put(
            "/wishlist/1", headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )


def test_wishlist_persists_and_isolated(client):
    assert client.put("/wishlist/1").status_code == 200
    client.put("/wishlist/1")
    assert len(client.get("/wishlist").json()["products"]) == 1
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as other:
        other.get("/auth/session")
        assert other.get("/wishlist").json()["products"] == []
    client.delete("/wishlist/1")
    assert not client.get("/wishlist").json()["products"]


def test_consent_tracking_withdrawal(client):
    assert not client.post(
        "/events", json={"product_id": 1, "event_type": "view"}
    ).json()["accepted"]
    client.put("/privacy/consent", json={"consent": True})
    assert client.post("/events", json={"product_id": 1, "event_type": "view"}).json()[
        "accepted"
    ]
    assert client.get("/privacy/export").json()["events"]
    client.put("/privacy/consent", json={"consent": False})
    assert client.get("/privacy/export").json()["events"] == []


def test_recommendation_attribution(client):
    client.put("/privacy/consent", json={"consent": True})
    r = client.get("/recommend/user").json()
    p = r["products"][0]
    assert p["reason_tags"]
    body = {
        "product_id": p["id"],
        "event_type": "impression",
        "recommendation_id": r["recommendation_id"],
    }
    assert client.post("/events", json=body).status_code == 200
    assert client.post("/events", json=body).json()["duplicate"]
    assert (
        client.post(
            "/events", json={"product_id": 1, "event_type": "click"}
        ).status_code
        == 422
    )
    assert (
        client.post("/events", json=body | {"recommendation_id": "unknown"}).status_code
        == 422
    )


def test_legacy_demo_checkout_is_removed(client):
    with SessionLocal() as db:
        stock = db.get(Variant, 1).stock
    client.put("/cart", json={"variant_id": 1, "quantity": 1})
    for _ in range(2):
        assert client.post("/checkout", json={"idempotency_key": "retired-demo-key"}).status_code == 410
    assert len(client.get("/cart").json()["items"]) == 1
    with SessionLocal() as db:
        assert db.get(Variant, 1).stock == stock


def test_retired_checkout_cannot_consume_stock(client):
    client.put("/cart", json={"variant_id": 2, "quantity": 1})
    client.put("/cart", json={"variant_id": 3, "quantity": 1})
    with SessionLocal() as db:
        v = db.get(Variant, 3)
        old = v.stock
        v.stock = 0
        before = db.get(Variant, 2).stock
        db.commit()
    try:
        assert (
            client.post(
                "/checkout", json={"idempotency_key": "test-rollback-123456"}
            ).status_code
            == 410
        )
        with SessionLocal() as db:
            assert db.get(Variant, 2).stock == before
        assert len(client.get("/cart").json()["items"]) == 2
    finally:
        with SessionLocal() as db:
            db.get(Variant, 3).stock = old
            db.commit()


def test_quiz_works_without_consent(client):
    result = client.post(
        "/recommend/quiz",
        json={
            "mood": "fresh",
            "occasion": "office",
            "intensity": "soft",
            "budget": 100,
            "size": 30,
        },
    ).json()
    assert result["products"] and all(
        0 <= p["match"] <= 100 for p in result["products"]
    )
    assert all(
        any(
            v["size_ml"] == 30 and v["price"] <= 100 and v["stock"] > 0
            for v in p["variants"]
        )
        for p in result["products"]
    )
    export = client.get("/privacy/export").json()
    assert export["quiz"] is None
    assert not any(event["type"] == "quiz_submit" for event in export["events"])


def test_quiz_storage_requires_consent_and_is_deleted_on_withdrawal(client):
    body = {
        "mood": "fresh",
        "occasion": "office",
        "intensity": "soft",
        "budget": 100,
        "size": 30,
    }
    client.post("/recommend/quiz", json=body)
    assert client.get("/privacy/export").json()["quiz"] is None

    client.put("/privacy/consent", json={"consent": True})
    client.post("/recommend/quiz", json=body)
    export = client.get("/privacy/export").json()
    assert export["quiz"]["mood"] == "fresh"
    assert any(event["type"] == "quiz_submit" for event in export["events"])

    client.put("/privacy/consent", json={"consent": False})
    export = client.get("/privacy/export").json()
    assert export["quiz"] is None
    assert export["events"] == []


def test_real_catalog_and_brand_filters(client):
    result = client.get("/products", params={"in_stock": False}).json()
    assert len(result["products"]) == 150
    assert len(result["brands"]) == 35
    assert all(p["image"].startswith("/images/products/") for p in result["products"])
    assert all(p["source"]["product_url"].startswith("https://") for p in result["products"])
    dior = client.get(
        "/products", params={"brand": "Dior", "in_stock": False}
    ).json()["products"]
    assert dior and all(p["brand"] == "Dior" for p in dior)


def test_recommendations_include_reason_tags(client):
    popular = client.get("/recommend/user").json()
    assert popular["products"]
    assert all(p["reason_tags"] for p in popular["products"])
    quiz = client.post(
        "/recommend/quiz",
        json={"mood": "fresh", "occasion": "office", "intensity": "soft", "budget": 150},
    ).json()
    assert quiz["products"] and all(p["reason_tags"] for p in quiz["products"])


def test_stock_substitutes(client):
    r = client.get("/recommend/substitutes?product_id=7").json()
    assert r["products"]
    assert all(p["id"] != 7 and p["in_stock"] for p in r["products"])


def test_natural_search(client):
    r = client.get("/search", params={"q": "fresh office scent under $150"})
    assert r.status_code == 200
    assert r.json()["parsed"]["budget"] == 150
    assert all(
        any(v["price"] <= 150 and v["stock"] > 0 for v in p["variants"])
        for p in r.json()["products"]
    )


def test_filters(client):
    r = client.get(
        "/products",
        params={"category": "Fresh", "budget": 100, "size": 30, "in_stock": True},
    ).json()["products"]
    assert r and all(p["category"] == "Fresh" for p in r)


def test_admin_controls_and_csv(admin):
    original = admin.get("/products/dior-dior-sauvage-edp").json()
    try:
        assert (
            admin.put(
                "/admin/products/1", json={"pinned": True, "hidden": True}
            ).status_code
            == 422
        )
        admin.put("/admin/products/1", json={"pinned": False, "hidden": True})
        assert admin.get("/products/dior-dior-sauvage-edp").status_code == 404
        assert all(
            p["id"] != 1 for p in admin.get("/recommend/user").json()["products"]
        )
        r = admin.get("/admin/export?kind=inventory")
        assert r.status_code == 200 and "text/csv" in r.headers["content-type"]
        assert "suggested_reorder" in r.text
    finally:
        admin.put(
            "/admin/products/1",
            json={"pinned": original["pinned"], "hidden": original["hidden"]},
        )


def test_forecast_bounds_and_horizon(admin):
    assert admin.get("/forecast/summary?horizon=3").status_code == 422
    r = admin.get("/forecast/sku?sku=SH-001-60&horizon=12").json()
    assert len(r["forecast"]) == 12
    for f in r["forecast"]:
        assert (
            0
            <= f["lower95"]
            <= f["lower80"]
            <= f["prediction"]
            <= f["upper80"]
            <= f["upper95"]
        )
    neural = admin.get(
        "/forecast/summary", params={"model": "lstm", "group": "all", "horizon": 8}
    )
    assert neural.status_code == 200
    assert neural.json()["model"] == "lstm"
    assert len(neural.json()["forecast"]) == 8
    assert admin.get("/forecast/summary?model=unknown").status_code == 422


def test_admin_analytics(admin):
    assert (
        admin.get("/admin/overview?start=2030-01-01&end=2020-01-01").status_code == 422
    )
    data = admin.get("/admin/overview").json()
    assert data["kpis"]["orders"] > 10000
    assert len(admin.get("/admin/segments").json()["segments"]) == 3


def test_register_and_login_rotation(client):
    import uuid

    email = f"{uuid.uuid4().hex}@example.test"
    password = "test-password-strong-1234"
    before = client.cookies.get("scenthaus_session")
    r = client.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code == 200
    assert client.cookies.get("scenthaus_session") != before
    client.headers["X-CSRF-Token"] = r.json()["csrf"]
    r = client.post("/auth/logout")
    client.headers["X-CSRF-Token"] = r.json()["csrf"]
    assert (
        client.post(
            "/auth/login", json={"email": email, "password": "wrong-password123"}
        ).status_code
        == 401
    )
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200


def test_neural_serving(client):
    client.put("/privacy/consent", json={"consent": True})
    client.put("/wishlist/1")
    for ex in ["two_tower"]:
        assert (
            client.get("/recommend/user", params={"experiment": ex}).status_code == 200
        )


def test_unimplemented_experiment_is_rejected(client):
    assert client.get("/recommend/user?experiment=item2vec").status_code == 422
