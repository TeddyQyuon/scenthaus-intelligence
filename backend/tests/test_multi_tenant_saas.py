"""Tests for multi-tenant SaaS core architecture:
- HKDF cryptographic key separation & TOTP v1->v2 rotation
- Tenant creation, Host/header resolution, custom domains & RBAC
- Cross-tenant catalog isolation & duplicate-slug allowance across tenants
- Order lifecycle state machine, tracking metadata, restock on refund & audit trail
- Stripe Connect account binding, fee calculation & webhook status sync
- Background job queue execution & dead-letter handling
"""

import base64
import hashlib
from datetime import date
from decimal import Decimal
from uuid import uuid4

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete, select

from app.config import settings
from app.core.keys import derive_hex_key, totp_fernet
from app.database import SessionLocal, sync_postgres_sequences
from app.jobs.queue import enqueue_job, process_pending_jobs, register_task
from app.main import app, requests
from app.models import (
    AuditLog,
    BackgroundJob,
    Membership,
    Order,
    OrderItem,
    Product,
    SecurityEvent,
    Session,
    Tenant,
    TenantDomain,
    User,
    Variant,
)
from app.payments.connect import (
    apply_connect_account_event,
    build_connect_checkout_params,
    calculate_application_fee,
)
from app.tenancy.constants import DEFAULT_TENANT_ID

_CREATED_USER_IDS: list[str] = []


@pytest.fixture(autouse=True)
def _cleanup_multi_tenant_test_rows():
    _CREATED_USER_IDS.clear()
    with SessionLocal() as db:
        sync_postgres_sequences(db)
        db.commit()
    yield
    with SessionLocal() as db:
        non_default_tenants = db.scalars(
            select(Tenant.id).where(Tenant.id != DEFAULT_TENANT_ID)
        ).all()
        if non_default_tenants:
            db.execute(
                delete(OrderItem).where(
                    OrderItem.order_id.in_(
                        select(Order.id).where(Order.tenant_id.in_(non_default_tenants))
                    )
                )
            )
            db.execute(
                delete(Order).where(Order.tenant_id.in_(non_default_tenants))
            )
            db.execute(
                delete(Variant).where(Variant.tenant_id.in_(non_default_tenants))
            )
            db.execute(
                delete(Product).where(Product.tenant_id.in_(non_default_tenants))
            )
            db.execute(
                delete(AuditLog).where(AuditLog.tenant_id.in_(non_default_tenants))
            )
            db.execute(
                delete(BackgroundJob).where(
                    BackgroundJob.tenant_id.in_(non_default_tenants)
                )
            )
            db.execute(
                delete(Membership).where(
                    Membership.tenant_id.in_(non_default_tenants)
                )
            )
            db.execute(
                delete(TenantDomain).where(
                    TenantDomain.tenant_id.in_(non_default_tenants)
                )
            )
            db.execute(
                delete(Tenant).where(Tenant.id.in_(non_default_tenants))
            )
        if _CREATED_USER_IDS:
            db.execute(
                delete(SecurityEvent).where(
                    SecurityEvent.user_id.in_(_CREATED_USER_IDS)
                )
            )
            db.execute(
                delete(Session).where(Session.user_id.in_(_CREATED_USER_IDS))
            )
            db.execute(delete(User).where(User.id.in_(_CREATED_USER_IDS)))
        db.commit()


def _authenticated_client(email: str, password: str = "ValidPass#2026!") -> TestClient:
    requests.clear()
    c = TestClient(app)
    s = c.get("/auth/session")
    assert s.status_code == 200
    guest_id = s.json()["user"]["id"]
    _CREATED_USER_IDS.append(guest_id)
    c.headers.update(
        {"Origin": "http://localhost:5173", "X-CSRF-Token": s.json()["csrf"]}
    )
    reg = c.post("/auth/register", json={"email": email, "password": password})
    if reg.status_code == 409:
        reg = c.post("/auth/login", json={"email": email, "password": password})
    assert reg.status_code == 200
    _CREATED_USER_IDS.append(reg.json()["user"]["id"])
    c.headers["X-CSRF-Token"] = reg.json()["csrf"]
    return c


def test_hkdf_key_separation_and_totp_rotation():
    purposes = [
        "jwt_customer",
        "jwt_staff",
        "csrf",
        "checkout_quote",
        "totp_encryption",
        "email_token",
    ]
    derived = {derive_hex_key(p) for p in purposes}  # type: ignore[arg-type]
    assert len(derived) == len(purposes)

    # Legacy v1 TOTP ciphertext must still decrypt under MultiFernet v2
    legacy_key = hashlib.sha256(
        ("scenthaus-totp-v1:" + settings.secret_key).encode("utf-8")
    ).digest()
    legacy_cipher = Fernet(base64.urlsafe_b64encode(legacy_key))
    legacy_token = legacy_cipher.encrypt(b"JBSWY3DPEHPK3PXP").decode("utf-8")

    mf = totp_fernet()
    assert mf.decrypt(legacy_token.encode("utf-8")) == b"JBSWY3DPEHPK3PXP"


def test_cross_tenant_isolation_and_custom_domain_resolution():
    suffix = uuid4().hex[:8]
    slug_a = f"maison-lumiere-{suffix}"
    slug_b = f"atelier-noir-{suffix}"

    owner_a = _authenticated_client(f"owner-a-{suffix}@example.com")
    owner_b = _authenticated_client(f"owner-b-{suffix}@example.com")

    # Create Tenant A and Tenant B
    res_a = owner_a.post(
        "/platform/tenants",
        json={
            "name": "Maison Lumiere",
            "slug": slug_a,
            "currency": "EUR",
            "country": "FR",
            "plan": "growth",
        },
    )
    assert res_a.status_code == 201
    tenant_a = res_a.json()

    res_b = owner_b.post(
        "/platform/tenants",
        json={
            "name": "Atelier Noir",
            "slug": slug_b,
            "currency": "USD",
            "country": "US",
            "plan": "starter",
        },
    )
    assert res_b.status_code == 201
    tenant_b = res_b.json()

    # Both tenants can create a product with the exact same slug and SKU
    payload = {
        "name": "Rose Oud Extrait",
        "brand": "Maison Exclusive",
        "slug": "rose-oud-extrait",
        "concentration": "Parfum",
        "category": "Woody",
        "gender": "Unisex",
        "description": "Hand-blended Damascus rose and aged Assam oud.",
        "notes": {"top": ["Bergamot"], "heart": ["Damask Rose"], "base": ["Oud"]},
        "accords": {"Woody": 0.8, "Floral": 0.6},
        "variants": [
            {"sku": "ML-ROSE-50", "size_ml": 50, "price": "240.00", "stock": 15}
        ],
    }

    prod_a = owner_a.post(
        "/tenant/catalog/products",
        headers={"X-Tenant-Slug": slug_a},
        json=payload,
    )
    assert prod_a.status_code == 201

    prod_b = owner_b.post(
        "/tenant/catalog/products",
        headers={"X-Tenant-Slug": slug_b},
        json=payload | {"description": "Atelier Noir signature edition."},
    )
    assert prod_b.status_code == 201

    # Verify strict catalog isolation between Tenant A and Tenant B
    list_a = owner_a.get(
        "/tenant/catalog/products", headers={"X-Tenant-Slug": slug_a}
    ).json()
    list_b = owner_b.get(
        "/tenant/catalog/products", headers={"X-Tenant-Slug": slug_b}
    ).json()
    assert len(list_a["products"]) == 1
    assert len(list_b["products"]) == 1
    assert list_a["products"][0]["id"] != list_b["products"][0]["id"]
    assert (
        list_b["products"][0]["description"] == "Atelier Noir signature edition."
    )

    # Owner A cannot mutate Tenant B's catalog (403 Forbidden)
    forbidden = owner_a.put(
        f"/tenant/catalog/products/{prod_b.json()['id']}",
        headers={"X-Tenant-Slug": slug_b},
        json={"name": "Hijacked Name"},
    )
    assert forbidden.status_code == 403

    # Register custom domain on Tenant A and resolve via Host header
    custom_domain = f"shop-{suffix}.maisonlumiere.fr"
    dom = owner_a.post(
        "/tenant/domains",
        headers={"X-Tenant-Slug": slug_a},
        json={"domain": custom_domain, "is_primary": True},
    )
    assert dom.status_code == 201
    assert dom.json()["dns_instructions"]["type"] == "TXT"

    cfg = owner_a.get(
        "/storefront/config",
        headers={"Host": custom_domain},
    ).json()
    assert cfg["tenant_id"] == tenant_a["id"]
    assert cfg["currency"] == "EUR"
    assert tenant_b["id"] != tenant_a["id"]


def test_order_state_machine_and_restock_on_refund():
    suffix = uuid4().hex[:8]
    slug = f"state-shop-{suffix}"
    owner = _authenticated_client(f"merchant-{suffix}@example.com")
    tenant = owner.post(
        "/platform/tenants",
        json={"name": "State Shop", "slug": slug, "currency": "SGD", "country": "SG"},
    ).json()

    prod = owner.post(
        "/tenant/catalog/products",
        headers={"X-Tenant-ID": tenant["id"]},
        json={
            "name": "Cedar Mist",
            "brand": "State Shop",
            "concentration": "EDP",
            "category": "Woody",
            "description": "Crisp atlas cedar and vetiver.",
            "variants": [
                {"sku": f"CED-{suffix}", "size_ml": 50, "price": "150.00", "stock": 10}
            ],
        },
    ).json()
    variant_id = prod["variants"][0]["id"]

    # Seed a confirmed order on this tenant
    with SessionLocal() as db:
        me = owner.get("/auth/session").json()["user"]
        order = Order(
            id=str(uuid4()),
            tenant_id=tenant["id"],
            user_id=me["id"],
            total=Decimal("300.00"),
            total_minor=30000,
            currency="SGD",
            status="confirmed",
            payment_status="paid",
            simulated=False,
            order_number=f"SCENT-2026-{suffix[:6].upper()}",
            customer_name="Jane Shopper",
            customer_email="jane@example.com",
        )
        db.add(order)
        db.flush()
        db.add(
            OrderItem(
                order_id=order.id,
                variant_id=variant_id,
                quantity=2,
                unit_price=Decimal("150.00"),
                product_snapshot={"product_id": prod["id"], "name": prod["name"]},
            )
        )
        db.commit()
        order_id = order.id

    # Transition confirmed -> fulfilling -> shipped -> delivered -> refunded (with restock)
    r1 = owner.post(
        f"/tenant/orders/{order_id}/transition",
        headers={"X-Tenant-ID": tenant["id"]},
        json={"target_status": "fulfilling"},
    )
    assert r1.status_code == 200 and r1.json()["status"] == "fulfilling"

    r2 = owner.post(
        f"/tenant/orders/{order_id}/transition",
        headers={"X-Tenant-ID": tenant["id"]},
        json={
            "target_status": "shipped",
            "carrier": "DHL Express",
            "tracking_number": "DHL-99887766",
        },
    )
    assert r2.status_code == 200
    assert (
        r2.json()["delivery_address"]["fulfilment"]["tracking_number"]
        == "DHL-99887766"
    )

    r3 = owner.post(
        f"/tenant/orders/{order_id}/transition",
        headers={"X-Tenant-ID": tenant["id"]},
        json={
            "target_status": "refunded",
            "reason": "Customer return",
            "restock": True,
        },
    )
    assert r3.status_code == 200
    assert r3.json()["status"] == "refunded"
    assert r3.json()["payment_status"] == "refunded"

    # Terminal state cannot transition back to shipped
    invalid = owner.post(
        f"/tenant/orders/{order_id}/transition",
        headers={"X-Tenant-ID": tenant["id"]},
        json={"target_status": "shipped"},
    )
    assert invalid.status_code == 409

    with SessionLocal() as db:
        v = db.get(Variant, variant_id)
        assert v.stock == 12  # 10 + 2 restocked
        logs = db.scalars(
            select(AuditLog).where(
                AuditLog.tenant_id == tenant["id"],
                AuditLog.action == "order.status_transition",
            )
        ).all()
        assert len(logs) == 3


def test_stripe_connect_binding_and_job_queue():
    suffix = uuid4().hex[:8]
    owner = _authenticated_client(f"connect-{suffix}@example.com")
    tenant_res = owner.post(
        "/platform/tenants",
        json={"name": "Connect Brand", "slug": f"connect-{suffix}"},
    ).json()
    tid = tenant_res["id"]

    acct_id = f"acct_{suffix}1234"
    bind_res = owner.post(
        "/tenant/payments/connect",
        headers={"X-Tenant-ID": tid},
        json={"stripe_account_id": acct_id},
    )
    assert bind_res.status_code == 200
    assert not bind_res.json()["charges_enabled"]

    with SessionLocal() as db:
        updated = apply_connect_account_event(
            {
                "type": "account.updated",
                "data": {
                    "object": {
                        "id": acct_id,
                        "charges_enabled": True,
                        "payouts_enabled": True,
                    }
                },
            },
            db,
        )
        assert updated
        from app.models import Tenant

        t = db.get(Tenant, tid)
        params = build_connect_checkout_params(t, 20000)
        assert params["payment_intent_data"]["on_behalf_of"] == acct_id
        assert (
            params["payment_intent_data"]["application_fee_amount"]
            == calculate_application_fee(20000, 250)
            == 500
        )

    # Background job queue test
    executed: list[tuple[str, dict]] = []

    @register_task(f"test.echo.{suffix}")
    def _handle_echo(db, job_tenant_id: str, payload: dict):
        executed.append((job_tenant_id, payload))

    @register_task(f"test.fail.{suffix}")
    def _handle_fail(db, job_tenant_id: str, payload: dict):
        raise RuntimeError("Simulated delivery error")

    with SessionLocal() as db:
        enqueue_job(
            db, f"test.echo.{suffix}", {"order": "123"}, tenant_id=tid, max_attempts=2
        )
        enqueue_job(
            db, f"test.fail.{suffix}", {"order": "999"}, tenant_id=tid, max_attempts=1
        )
        db.commit()
        stats = process_pending_jobs(db, limit=10)
        assert stats["completed"] >= 1
        assert stats["dead_letter"] >= 1
        assert executed == [(tid, {"order": "123"})]


def test_tiered_intelligence_csv_customers_and_gdpr():
    suffix = uuid4().hex[:8]
    owner = _authenticated_client(f"intel-{suffix}@example.com")
    tenant = owner.post(
        "/platform/tenants",
        json={"name": "Maison Intel", "slug": f"intel-{suffix}", "currency": "SGD"},
    ).json()
    tid = tenant["id"]
    headers = {"X-Tenant-ID": tid}

    # Import products via CSV (including a formula-injection test string '=SUM(1,2)')
    csv_payload = (
        "slug,name,brand,concentration,category,gender,sku,size_ml,price,stock\n"
        f"vetiver-soleil,Vetiver Soleil,=MaisonFormula,EDP,Fresh,Unisex,VS-{suffix}-50,50,165.00,3\n"
        f"amber-nuit,Amber Nuit,Maison Intel,Parfum,Woody,Unisex,AN-{suffix}-100,100,290.00,0\n"
    )
    imp = owner.post(
        "/tenant/catalog/import",
        headers=headers,
        json={"csv_text": csv_payload},
    )
    assert imp.status_code == 200
    assert imp.json()["imported_rows"] == 2

    exp = owner.get("/tenant/catalog/export.csv", headers=headers)
    assert exp.status_code == 200
    assert "'=MaisonFormula" in exp.text  # Formula injection escaped

    # Immediate live search without offline model rebuild
    search_res = owner.get(
        "/tenant/intelligence/search?q=vetiver+fresh+under+200",
        headers=headers,
    ).json()
    assert len(search_res["products"]) == 1
    assert search_res["products"][0]["slug"] == "vetiver-soleil"

    # Cold-start recommendations (Tier 0)
    rec_res = owner.get(
        "/tenant/intelligence/recommendations",
        headers=headers,
    ).json()
    assert rec_res["tier"] == "cold_start_content"
    assert len(rec_res["products"]) == 1  # Only in-stock item recommended

    # Gated inventory signals (< 12 weeks -> forecast_ready is False, live velocity signals returned)
    inv_res = owner.get(
        "/tenant/intelligence/inventory-signals",
        headers=headers,
    ).json()
    assert not inv_res["forecast_ready"]
    assert inv_res["weeks_required"] == 12
    statuses = {s["sku"]: s["status"] for s in inv_res["signals"]}
    assert statuses[f"AN-{suffix}-100"] == "stockout"
    assert statuses[f"VS-{suffix}-50"] == "watch"

    # Notification template rendering test
    from app.notifications.emails import render_email_template

    mail = render_email_template(
        "order_shipped",
        "Maison Intel",
        {
            "order_number": "SCENT-2026-000001",
            "carrier": "DHL",
            "tracking_number": "123456",
        },
    )
    assert "SCENT-2026-000001" in mail["subject"]
    assert "DHL" in mail["html"]

    # GDPR / PDPA export & account erasure
    export_data = owner.get("/tenant/compliance/export", headers=headers).json()
    assert export_data["tenant"]["id"] == tid
    erased = owner.delete("/tenant/compliance/account", headers=headers)
    assert erased.status_code == 200
    assert erased.json()["erased"] is True

