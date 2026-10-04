"""Native Postgres concurrency checks run in CI; PGlite serializes a single backend."""

import os
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Variant

pytestmark = pytest.mark.skipif(
    os.getenv("NATIVE_POSTGRES_TESTS") != "1",
    reason="Requires native Postgres; configured in GitHub Actions",
)


def test_concurrent_same_user_checkout_is_exactly_once(client):
    client.put("/cart", json={"variant_id": 4, "quantity": 1})
    with SessionLocal() as db:
        before = db.get(Variant, 4).stock
    cookie = client.cookies.get("scenthaus_session")
    headers = dict(client.headers)
    body = {"idempotency_key": "native-double-checkout-12345"}

    def checkout():
        with TestClient(app) as peer:
            peer.cookies.set("scenthaus_session", cookie)
            return peer.post("/checkout", json=body, headers=headers)

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = list(pool.map(lambda _: checkout(), range(2)))
    assert a.status_code == b.status_code == 200 and a.json()["id"] == b.json()["id"]
    with SessionLocal() as db:
        assert db.get(Variant, 4).stock == before - 1
