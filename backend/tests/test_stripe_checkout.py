"""Offline contract/security tests use Stripe's real signature verifier, no keys."""
import hashlib
import hmac
import json
import os
import time
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
import stripe
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import stripe_service
from app.checkout import cents
from app.config import settings
from app.database import Base, get_db
from app.main import app, requests
from app.models import CartItem, Order, OrderItem, Product, StripeWebhookEvent, Variant


@pytest.fixture
def payments(monkeypatch):
    schema = "stripe_test_" + uuid4().hex
    native = os.environ.get("NATIVE_POSTGRES_TESTS") == "1"
    admin_engine = create_engine(settings.database_url) if native else None
    if native:
        with admin_engine.begin() as connection:
            connection.execute(text('CREATE SCHEMA ' + schema))
        engine = create_engine(settings.database_url, connect_args={"options": "-csearch_path=" + schema})
    else:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    def database():
        with factory() as db:
            yield db
    monkeypatch.setattr(settings, "stripe_secret_key", SecretStr("sk_test_fixture"))
    monkeypatch.setattr(settings, "stripe_webhook_secret", SecretStr("whsec_fixture"))
    monkeypatch.setattr(settings, "checkout_public_url", "https://scenthaus.example")
    with factory() as db:
        db.add(Product(id=1, slug="test-scent", name="Test scent", brand="SCENTHAUS", concentration="EDP", category="Fresh", gender="Unisex", description="Fixture only", notes=[], accords=[], seasons=[], occasions=[], longevity=5, sillage="Medium", launch_date=date(2020, 1, 1), hidden=False))
        db.add(Variant(id=1, product_id=1, sku="FIXTURE-50", size_ml=50, price=Decimal("129.90"), stock=12))
        db.commit()
    created = []
    sessions = {}
    def create(params, key):
        created.append((params, key))
        identifier = "cs_test_" + key
        sessions.setdefault(identifier, SimpleNamespace(id=identifier, url="https://checkout.stripe.com/c/pay/" + identifier, status="open", payment_status="unpaid"))
        return sessions[identifier]
    def expire(identifier):
        sessions[identifier].status = "expired"
        return sessions[identifier]
    monkeypatch.setattr(stripe_service, "create_session", create)
    monkeypatch.setattr(stripe_service, "retrieve_session", lambda identifier: sessions[identifier])
    monkeypatch.setattr(stripe_service, "expire_session", expire)
    app.dependency_overrides[get_db] = database
    requests.clear()
    with TestClient(app) as client:
        session = client.get("/auth/session").json()
        client.headers.update({"Origin": "http://localhost:5173", "X-CSRF-Token": session["csrf"]})
        assert client.put("/cart", json={"variant_id": 1, "quantity": 2}).status_code == 200
        yield SimpleNamespace(client=client, db=factory, created=created, sessions=sessions)
    app.dependency_overrides.clear()
    engine.dispose()
    if native:
        with admin_engine.begin() as connection:
            connection.execute(text('DROP SCHEMA ' + schema + ' CASCADE'))
        admin_engine.dispose()


def body(payments, key=None):
    quote = payments.client.get("/checkout/quote").json()
    return {"delivery": {"full_name": "Test Customer", "email": "test@example.com", "phone": "", "line1": "1 Test Street", "line2": "", "postal_code": "123456", "city": "Singapore", "country": "SG"},
            "items": [{key: item[key] for key in ("product_id", "variant_id", "size_ml", "quantity")} for item in quote["items"]],
            "quote_token": quote["quote_token"], "idempotency_key": key or str(uuid4())}


def create_order(payments):
    payload = body(payments)
    result = payments.client.post("/checkout/session", json=payload)
    assert result.status_code == 200, result.text
    return result.json(), payload


def session_event(payments, identifier, kind="checkout.session.completed", paid=True, event_id=None):
    with payments.db() as db:
        order = db.get(Order, identifier)
        obj = {"id": order.stripe_session_id, "client_reference_id": order.id, "mode": "payment", "metadata": {"order_id": order.id}, "amount_total": order.total_minor,
               "currency": "sgd", "payment_intent": "pi_test_" + order.id,
               "payment_status": "paid" if paid else "unpaid", "status": "complete" if paid else "expired"}
    return {"id": event_id or "evt_" + str(uuid4()), "type": kind, "livemode": False, "data": {"object": obj}}


def send_event(client, event, secret="whsec_fixture", timestamp=None):
    payload = json.dumps(event).encode()
    timestamp = timestamp or int(time.time())
    signature = hmac.new(secret.encode(), str(timestamp).encode() + b"." + payload, hashlib.sha256).hexdigest()
    return client.post("/stripe/webhook", content=payload, headers={"Stripe-Signature": f"t={timestamp},v1={signature}", "Content-Type": "application/json"})


def test_minor_units_and_server_authoritative_total(payments):
    assert cents(Decimal("129.90")) == 12990
    response, _ = create_order(payments)
    params, _ = payments.created[0]
    assert response["total_minor"] == 25980
    assert params["line_items"][0]["price_data"]["unit_amount"] == 12990
    assert params["line_items"][0]["quantity"] == 2
    assert params["success_url"].startswith("https://scenthaus.example/checkout/success")
    assert params["payment_intent_data"]["shipping"]["address"]["country"] == "SG"
    with payments.db() as db:
        order = db.get(Order, response["order_id"])
        assert order.order_number.startswith("SCENT-")
        assert order.payment_status == "pending" and order.status == "pending"
        assert db.get(Variant, 1).stock == 10
        assert db.scalar(select(func.count()).select_from(CartItem)) == 1


@pytest.mark.parametrize("field,value", [("total", 1), ("discount", 25980), ("unit_price", 1)])
def test_client_amount_and_discount_fields_rejected(payments, field, value):
    payload = body(payments)
    payload[field] = value
    assert payments.client.post("/checkout/session", json=payload).status_code == 422
    assert payments.created == []


@pytest.mark.parametrize("field,value", [("product_id", 999999), ("variant_id", 999999), ("size_ml", 999), ("quantity", 3)])
def test_cart_identity_or_quantity_mismatch_rejected(payments, field, value):
    payload = body(payments)
    payload["items"][0][field] = value
    assert payments.client.post("/checkout/session", json=payload).status_code == 409
    assert not payments.created


@pytest.mark.parametrize("quantity", [0, -1, 11, 1.5, True, "2"])
def test_invalid_quantities_rejected(payments, quantity):
    payload = body(payments)
    payload["items"][0]["quantity"] = quantity
    assert payments.client.post("/checkout/session", json=payload).status_code == 422


def test_changed_price_quote_and_stock_cannot_be_bypassed(payments):
    payload = body(payments)
    with payments.db() as db:
        db.get(Variant, 1).price = Decimal("139.90")
        db.commit()
    assert payments.client.post("/checkout/session", json=payload).status_code == 409
    payload = body(payments)
    with payments.db() as db:
        db.get(Variant, 1).stock = 1
        db.commit()
    assert payments.client.post("/checkout/session", json=payload).status_code == 409
    assert not payments.created


def test_repeated_submissions_reuse_one_order_and_session(payments):
    result, payload = create_order(payments)
    repeat = payments.client.post("/checkout/session", json=payload).json()
    payload["idempotency_key"] = str(uuid4())
    another_tab = payments.client.post("/checkout/session", json=payload).json()
    assert result == repeat == another_tab
    assert len(payments.created) == 1
    with payments.db() as db:
        assert db.scalar(select(func.count()).select_from(Order)) == 1
        assert db.scalar(select(func.count()).select_from(OrderItem)) == 1
        assert db.get(Variant, 1).stock == 10


def test_network_retry_uses_same_stripe_idempotency_key(payments, monkeypatch):
    original = stripe_service.create_session
    calls = []
    def flaky(params, key):
        calls.append((params, key))
        if len(calls) == 1:
            raise stripe.APIConnectionError("Test connection failure")
        return original(params, key)
    monkeypatch.setattr(stripe_service, "create_session", flaky)
    payload = body(payments)
    assert payments.client.post("/checkout/session", json=payload).status_code == 503
    assert payments.client.post("/checkout/session", json=payload).status_code == 200
    assert calls[0] == calls[1]
    with payments.db() as db:
        assert db.scalar(select(func.count()).select_from(Order)) == 1
        assert db.get(Variant, 1).stock == 10


def test_success_page_read_never_marks_paid_or_clears_cart(payments):
    result, _ = create_order(payments)
    for _ in range(3):
        detail = payments.client.get("/orders/" + result["order_id"])
        assert detail.json()["payment_status"] == "pending"
    assert payments.client.get("/orders/nonexistent").status_code == 404
    assert len(payments.client.get("/cart").json()["items"]) == 1


def test_verified_success_and_webhook_retries_update_exactly_once(payments):
    result, _ = create_order(payments)
    event = session_event(payments, result["order_id"])
    for _ in range(3):
        assert send_event(payments.client, event).status_code == 200
    another_event = {**event, "id": "evt_" + str(uuid4())}
    assert send_event(payments.client, another_event).status_code == 200
    detail = payments.client.get("/orders/" + result["order_id"]).json()
    assert detail["payment_status"] == "paid" and detail["status"] == "confirmed"
    assert payments.client.get("/cart").json()["items"] == []
    assert not any(key in detail for key in ("stripe_session_id", "stripe_payment_intent_id", "stripe_secret_key"))
    with payments.db() as db:
        assert db.scalar(select(func.count()).select_from(Order)) == 1
        assert db.get(Variant, 1).stock == 10
        assert db.scalar(select(func.count()).select_from(StripeWebhookEvent)) == 2


def test_bad_signature_replayed_timestamp_and_amount_mismatch_rejected(payments):
    result, _ = create_order(payments)
    event = session_event(payments, result["order_id"])
    assert send_event(payments.client, event, secret="wrong").status_code == 400
    assert send_event(payments.client, event, timestamp=int(time.time()) - 600).status_code == 400
    event["data"]["object"]["amount_total"] = 1
    assert send_event(payments.client, event).status_code == 400
    assert payments.client.get("/orders/" + result["order_id"]).json()["payment_status"] == "pending"


def test_cancellation_and_expiry_release_inventory_once_and_keep_bag(payments):
    result, _ = create_order(payments)
    for _ in range(2):
        response = payments.client.post("/checkout/" + result["order_id"] + "/cancel")
        assert response.json()["status"] == "cancelled"
    event = session_event(payments, result["order_id"], "checkout.session.expired", paid=False)
    assert send_event(payments.client, event).status_code == 200
    with payments.db() as db:
        assert db.get(Variant, 1).stock == 12
    assert len(payments.client.get("/cart").json()["items"]) == 1


def test_delayed_payment_is_pending_until_paid_webhook(payments):
    result, _ = create_order(payments)
    event = session_event(payments, result["order_id"], paid=False)
    event["data"]["object"]["status"] = "complete"
    assert send_event(payments.client, event).status_code == 200
    assert payments.client.get("/orders/" + result["order_id"]).json()["payment_status"] == "pending"
    assert send_event(payments.client, session_event(payments, result["order_id"], "checkout.session.async_payment_succeeded")).status_code == 200
    assert payments.client.get("/orders/" + result["order_id"]).json()["payment_status"] == "paid"


def test_async_failure_does_not_create_paid_order(payments):
    result, _ = create_order(payments)
    event = session_event(payments, result["order_id"], "checkout.session.async_payment_failed", paid=False)
    assert send_event(payments.client, event).status_code == 200
    assert payments.client.get("/orders/" + result["order_id"]).json()["payment_status"] == "failed"
    with payments.db() as db:
        assert db.get(Variant, 1).stock == 12


def test_unconfigured_payment_and_legacy_demo_checkout_fail_closed(payments, monkeypatch):
    payload = body(payments)
    monkeypatch.setattr(settings, "stripe_webhook_secret", SecretStr(""))
    assert payments.client.post("/checkout/session", json=payload).status_code == 503
    assert payments.client.post("/checkout").status_code == 410
    assert not payments.created


def test_order_ownership_and_csrf_are_enforced(payments):
    result, payload = create_order(payments)
    with TestClient(app) as other:
        other.get("/auth/session")
        assert other.get("/orders/" + result["order_id"]).status_code == 404
    original = payments.client.headers.pop("X-CSRF-Token")
    assert payments.client.post("/checkout/session", json=payload).status_code == 403
    payments.client.headers["X-CSRF-Token"] = original


def test_card_decline_is_retryable_and_cannot_downgrade_paid_order(payments):
    result, payload = create_order(payments)
    identifier = result['order_id']
    event = {'id': 'evt_decline', 'type': 'payment_intent.payment_failed', 'livemode': False,
             'data': {'object': {'id': 'pi_test_' + identifier, 'metadata': {'order_id': identifier},
                                'currency': 'sgd', 'amount': 25980}}}
    assert send_event(payments.client, event).status_code == 200
    assert payments.client.get('/orders/' + identifier).json()['payment_status'] == 'failed'
    assert payments.client.post('/checkout/session', json=payload).json()['order_id'] == identifier
    assert len(payments.created) == 1
    assert send_event(payments.client, session_event(payments, identifier)).status_code == 200
    assert send_event(payments.client, {**event, 'id': 'evt_late_decline'}).status_code == 200
    assert payments.client.get('/orders/' + identifier).json()['payment_status'] == 'paid'


def test_partial_and_full_refunds_are_monotonic_and_idempotent(payments):
    result, _ = create_order(payments)
    identifier = result['order_id']
    assert send_event(payments.client, session_event(payments, identifier)).status_code == 200
    obj = {'payment_intent': 'pi_test_' + identifier, 'amount': 25980, 'currency': 'sgd', 'amount_refunded': 12990}
    event = {'id': 'evt_partial', 'type': 'charge.refunded', 'livemode': False, 'data': {'object': obj}}
    assert send_event(payments.client, event).status_code == 200
    detail = payments.client.get('/orders/' + identifier).json()
    assert detail['payment_status'] == 'paid' and detail['refunded_minor'] == 12990
    full = {**event, 'id': 'evt_full', 'data': {'object': {**obj, 'amount_refunded': 25980}}}
    for _ in range(2):
        assert send_event(payments.client, full).status_code == 200
    assert send_event(payments.client, {**event, 'id': 'evt_old_partial'}).status_code == 200
    detail = payments.client.get('/orders/' + identifier).json()
    assert detail['payment_status'] == 'refunded' and detail['refunded_minor'] == 25980
    with payments.db() as db:
        assert db.get(Variant, 1).stock == 10  # Refund does not imply returned physical inventory.


def test_paid_webhook_preserves_additional_bag_quantities(payments):
    result, _ = create_order(payments)
    assert payments.client.put('/cart', json={'variant_id': 1, 'quantity': 4}).status_code == 200
    assert send_event(payments.client, session_event(payments, result['order_id'])).status_code == 200
    assert payments.client.get('/cart').json()['items'][0]['quantity'] == 2


def test_live_mode_event_cannot_confirm_test_order(payments):
    result, _ = create_order(payments)
    event = {**session_event(payments, result['order_id']), 'livemode': True}
    assert send_event(payments.client, event).status_code == 400
    assert payments.client.get('/orders/' + result['order_id']).json()['payment_status'] == 'pending'


def test_saved_checkout_cannot_silently_change_delivery(payments):
    result, payload = create_order(payments)
    payload['delivery']['line1'] = '2 Another Street'
    assert payments.client.post('/checkout/session', json=payload).status_code == 409
    assert len(payments.created) == 1
    quote = payments.client.get('/checkout/quote').json()
    assert quote['pending_order']['delivery']['line1'] == '1 Test Street'
    assert quote['pending_order']['order_id'] == result['order_id']


def test_expired_stock_reconciliation_requires_stripe_evidence(payments, monkeypatch):
    from datetime import timedelta
    from app.models import now
    result, _ = create_order(payments)
    with payments.db() as db:
        order = db.get(Order, result['order_id'])
        order.expires_at = now() - timedelta(minutes=10)
        session_id = order.stripe_session_id
        db.commit()
    original = stripe_service.retrieve_session
    def unavailable(identifier):
        raise stripe.APIConnectionError('fixture only')
    monkeypatch.setattr(stripe_service, 'retrieve_session', unavailable)
    assert payments.client.get('/checkout/quote').json()['pending_order']['order_id'] == result['order_id']
    with payments.db() as db:
        assert db.get(Variant, 1).stock == 10
    monkeypatch.setattr(stripe_service, 'retrieve_session', original)
    payments.sessions[session_id].status = 'expired'
    quote = payments.client.get('/checkout/quote').json()
    assert 'pending_order' not in quote
    with payments.db() as db:
        assert db.get(Variant, 1).stock == 12


def test_lost_creation_response_reconciliation_does_not_guess(payments, monkeypatch):
    from datetime import timedelta
    from app.models import now
    result, _ = create_order(payments)
    with payments.db() as db:
        order = db.get(Order, result['order_id'])
        order.expires_at = now() - timedelta(minutes=10)
        order.stripe_session_id = None
        db.commit()
    monkeypatch.setattr(stripe_service, 'find_session', lambda order: (None, False))
    assert 'pending_order' in payments.client.get('/checkout/quote').json()
    monkeypatch.setattr(stripe_service, 'find_session', lambda order: (None, True))
    assert 'pending_order' not in payments.client.get('/checkout/quote').json()
    with payments.db() as db:
        assert db.get(Variant, 1).stock == 12


def test_fractional_minor_unit_price_is_not_rounded_silently():
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        cents(Decimal('12.345'))


def test_concurrent_pay_requests_share_one_order(payments):
    # PostgreSQL's real row locks are exercised in native CI; SQLite cannot
    # simulate cross-connection FOR UPDATE and uses the sequential retry contract.
    from concurrent.futures import ThreadPoolExecutor
    payload = body(payments)
    if os.environ.get('NATIVE_POSTGRES_TESTS') == '1':
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: payments.client.post('/checkout/session', json=payload), range(2)))
    else:
        responses = [payments.client.post('/checkout/session', json=payload) for _ in range(2)]
    assert all(response.status_code == 200 for response in responses)
    assert len({response.json()['order_id'] for response in responses}) == 1
    assert len({key for _, key in payments.created}) == 1
    with payments.db() as db:
        assert db.scalar(select(func.count()).select_from(Order)) == 1
        assert db.get(Variant, 1).stock == 10


def test_simultaneous_distinct_paid_events_have_one_purchase_effect(payments):
    from concurrent.futures import ThreadPoolExecutor
    from app.models import Event, User
    result, _ = create_order(payments)
    with payments.db() as db:
        order = db.get(Order, result['order_id'])
        db.get(User, order.user_id).consent = True
        db.commit()
    events = [session_event(payments, result['order_id']) for _ in range(2)]
    if os.environ.get('NATIVE_POSTGRES_TESTS') == '1':
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda event: send_event(payments.client, event), events))
    else:
        responses = [send_event(payments.client, event) for event in events]
    assert all(response.status_code == 200 for response in responses)
    with payments.db() as db:
        assert db.scalar(select(func.count()).select_from(Event).where(Event.event_type == 'purchase')) == 1
        assert db.get(Variant, 1).stock == 10
        assert db.scalar(select(func.count()).select_from(Order)) == 1
