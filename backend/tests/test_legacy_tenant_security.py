"""Isolation tests require neither PostgreSQL/RLS nor trained ML artifacts."""

from datetime import date, timedelta
from http.cookies import SimpleCookie
import pytest
from fastapi import Response
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.main import app, requests
from app.models import (
    AuditLog,
    CartItem,
    Event,
    Membership,
    Order,
    Product,
    Tenant,
    TenantDomain,
    TenantDomainChallenge,
    User,
    Variant,
    Wishlist,
    now,
)
from app.security import hasher, issue
from app.tenancy.constants import DEFAULT_TENANT_ID
from app.tenancy.queries import tenant_get, tenant_select


@pytest.fixture(scope="session", autouse=True)
def _sync_postgres_sequences():
    """Override the shared PostgreSQL fixture: every test owns a SQLite schema."""


@pytest.fixture
def isolated():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(
            [
                Tenant(id="a", slug="store-a", name="Store A"),
                Tenant(id="b", slug="store-b", name="Store B"),
            ]
        )
        for i, tid in [(1, "a"), (2, "b"), (3, DEFAULT_TENANT_ID)]:
            db.add(
                Product(
                    id=i,
                    tenant_id=tid,
                    slug="same-scent",
                    name=f"Scent {tid}",
                    brand=f"Brand {tid}",
                    concentration="EDP",
                    category="Woody",
                    description="Test scent",
                    notes={},
                    accords={},
                    seasons=[],
                    occasions=[],
                    longevity=6,
                    sillage="Moderate",
                    launch_date=date(2020, 1, 1),
                )
            )
            db.add(
                Variant(
                    id=i,
                    tenant_id=tid,
                    product_id=i,
                    sku="SAME-SKU",
                    size_ml=50,
                    price=i * 100,
                    stock=5,
                )
            )
        db.add_all(
            [
                User(id="customer-a", tenant_id="a", consent=True),
                User(id="customer-b", tenant_id="b", consent=True),
                User(id="admin-a", tenant_id="a", role="admin"),
                User(id="admin-b", tenant_id="b", role="admin"),
                User(
                    id="owner", tenant_id=DEFAULT_TENANT_ID, email="owner@example.com"
                ),
            ]
        )
        db.add(Membership(tenant_id="a", user_id="owner", role="owner"))
        db.commit()

    def database():
        with Session(engine) as db:
            yield db

    requests.clear()
    old = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = database
    yield engine
    app.dependency_overrides.clear()
    app.dependency_overrides.update(old)
    engine.dispose()


def signed_client(engine, uid, tenant="a"):
    response = Response()
    with Session(engine) as db:
        csrf = issue(db.get(User, uid), response, db)
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    c = TestClient(app)
    c.cookies.set("scenthaus_session", cookie["scenthaus_session"].value)
    c.headers.update(
        {"Origin": "http://localhost:5173", "X-CSRF-Token": csrf, "X-Tenant-ID": tenant}
    )
    return c


def test_legacy_writes_reject_foreign_ids_and_stamp_tenant(isolated):
    c = signed_client(isolated, "customer-a")
    assert c.put("/cart", json={"variant_id": 2, "quantity": 1}).status_code == 404
    assert c.post("/cart/add", json={"variant_id": 2, "quantity": 1}).status_code == 404
    assert c.put("/wishlist/2").status_code == 404
    assert c.delete("/wishlist/2").status_code == 404
    assert (
        c.post("/events", json={"product_id": 2, "event_type": "view"}).status_code
        == 404
    )
    assert c.put("/cart", json={"variant_id": 1, "quantity": 2}).status_code == 200
    assert c.put("/wishlist/1").status_code == 200
    assert (
        c.post("/events", json={"product_id": 1, "event_type": "view"}).status_code
        == 200
    )
    with Session(isolated) as db:
        for model in (CartItem, Wishlist, Event):
            rows = db.scalars(select(model)).all()
            assert rows and {row.tenant_id for row in rows} == {"a"}
        assert {e.product_id for e in db.scalars(select(Event))} == {1}


def test_stale_cross_tenant_rows_do_not_enter_bag_orders_or_export(isolated):
    with Session(isolated) as db:
        db.add_all(
            [
                CartItem(tenant_id="a", user_id="customer-a", variant_id=1, quantity=1),
                CartItem(tenant_id="a", user_id="customer-a", variant_id=2, quantity=1),
                Wishlist(tenant_id="a", user_id="customer-a", product_id=2),
                Order(
                    id="foreign-order",
                    tenant_id="b",
                    user_id="customer-a",
                    total=999,
                    order_number="FOREIGN-ORDER",
                    payment_status="paid",
                ),
            ]
        )
        db.commit()
    c = signed_client(isolated, "customer-a")
    assert [r["variant_id"] for r in c.get("/cart").json()["items"]] == [1]
    quote = c.get("/checkout/quote")
    assert quote.status_code == 200 and quote.json()["total_minor"] == 10000
    assert [r["variant_id"] for r in quote.json()["items"]] == [1]
    assert c.get("/wishlist").json()["products"] == []
    assert c.get("/orders").json() == []
    assert c.get("/orders/foreign-order").status_code == 404
    exported = c.get("/privacy/export").json()
    assert exported["orders"] == [] and exported["checkout_orders"] == []
    assert exported["wishlist"] == []


def test_tenant_predicates_cover_identity_map_aggregates_and_join_targets(isolated):
    with Session(isolated) as db:
        db.add_all(
            [
                Order(tenant_id="a", user_id="customer-a", total=100),
                Order(tenant_id="b", user_id="customer-b", total=999),
                CartItem(tenant_id="b", user_id="customer-a", variant_id=1, quantity=1),
            ]
        )
        db.commit()
        foreign = db.get(Variant, 2)
        db.info["tenant_id"] = "a"
        assert foreign is not None and tenant_get(db, Variant, 2) is None
        assert db.scalar(tenant_select(db, func.count()).select_from(Order)) == 1
        assert (
            db.scalars(
                tenant_select(db, Product).join(
                    CartItem, CartItem.variant_id == Product.id
                )
            ).all()
            == []
        )


def test_customer_session_switching_and_catalog_cache_headers(isolated):
    c = signed_client(isolated, "customer-a")
    assert c.get("/cart", headers={"X-Tenant-ID": "b"}).status_code == 401
    session = c.get("/auth/session", headers={"X-Tenant-ID": "b"})
    assert session.status_code == 200
    with Session(isolated) as db:
        assert db.get(User, session.json()["user"]["id"]).tenant_id == "b"
    assert c.get("/cart", headers={"X-Tenant-ID": "b"}).status_code == 200
    for tid in ["a", "b", DEFAULT_TENANT_ID]:
        for path in ["/products", "/products/same-scent", "/storefront/config"]:
            r = c.get(path, headers={"X-Tenant-ID": tid})
            assert r.status_code == 200 and "no-store" in r.headers["cache-control"]
            if path == "/products":
                assert [p["name"] for p in r.json()["products"]] == [f"Scent {tid}"]


def test_admin_memberships_and_default_account_onboarding(isolated):
    owner = signed_client(isolated, "owner")
    boot = owner.get("/auth/session")
    assert boot.status_code == 200 and boot.json()["user"]["id"] == "owner"
    assert [p["id"] for p in owner.get("/admin/products").json()] == [1]
    assert owner.get("/admin/products", headers={"X-Tenant-ID": "b"}).status_code == 403
    assert owner.put("/admin/stock/2", json={"stock": 20}).status_code == 404
    created = owner.post(
        "/platform/tenants", json={"name": "New Store", "slug": "new-store"}
    )
    assert created.status_code == 201
    tid = created.json()["id"]
    assert (
        owner.put(
            "/tenant/settings",
            headers={"X-Tenant-ID": tid},
            json={"hero_title": "Welcome"},
        ).status_code
        == 200
    )
    assert (
        owner.get("/tenant/catalog/products", headers={"X-Tenant-ID": tid}).status_code
        == 200
    )
    assert owner.get("/admin/products", headers={"X-Tenant-ID": tid}).json() == []
    assert len(owner.get("/platform/tenants").json()["tenants"]) == 2
    admin = signed_client(isolated, "admin-a")
    assert admin.get("/admin/products", headers={"X-Tenant-ID": "b"}).status_code == 403
    assert admin.put("/admin/stock/1", json={"stock": 4}).status_code == 200
    with Session(isolated) as db:
        assert db.get(Variant, 1).stock == 4 and db.get(Variant, 2).stock == 5


def test_default_account_registration_can_create_and_manage_store(isolated):
    c = TestClient(app)
    session = c.get("/auth/session")
    assert session.status_code == 200
    c.headers.update(
        {"Origin": "http://localhost:5173", "X-CSRF-Token": session.json()["csrf"]}
    )
    registered = c.post(
        "/auth/register",
        json={"email": "new-owner@example.com", "password": "ValidPass#2026!"},
    )
    assert registered.status_code == 200
    c.headers["X-CSRF-Token"] = registered.json()["csrf"]
    store = c.post("/platform/tenants", json={"name": "New Brand", "slug": "new-brand"})
    assert store.status_code == 201
    tid = store.json()["id"]
    assert c.get("/admin/products", headers={"X-Tenant-ID": tid}).status_code == 200
    product = c.post(
        "/tenant/catalog/products",
        headers={"X-Tenant-ID": tid},
        json={
            "name": "New scent",
            "brand": "New Brand",
            "slug": "new-scent",
            "concentration": "EDP",
            "category": "Woody",
            "description": "A new scent",
            "notes": {},
            "accords": {},
            "variants": [{"sku": "NEW", "size_ml": 50, "price": "50", "stock": 5}],
        },
    )
    assert product.status_code == 201
    assert (
        c.get("/admin/products", headers={"X-Tenant-ID": tid}).json()[0]["name"]
        == "New scent"
    )


def test_login_scopes_duplicate_emails_to_selected_store(isolated):
    with Session(isolated) as db:
        for uid, pw in [
            ("customer-a", "PasswordA#2026!"),
            ("customer-b", "PasswordB#2026!"),
        ]:
            user = db.get(User, uid)
            user.email = "same@example.com"
            user.password_hash = hasher.hash(pw)
        db.commit()
    c = TestClient(app)
    c.headers["X-Tenant-ID"] = "b"
    session = c.get("/auth/session")
    c.headers.update(
        {"Origin": "http://localhost:5173", "X-CSRF-Token": session.json()["csrf"]}
    )
    assert (
        c.post(
            "/auth/login",
            json={"email": "same@example.com", "password": "PasswordA#2026!"},
        ).status_code
        == 401
    )
    login = c.post(
        "/auth/login", json={"email": "same@example.com", "password": "PasswordB#2026!"}
    )
    assert login.status_code == 200 and login.json()["user"]["id"] == "customer-b"


@pytest.mark.parametrize(
    "path",
    [
        "/intelligence",
        "/forecast/sku?sku=SAME-SKU",
        "/forecast/summary",
        "/admin/evaluation",
        "/admin/tracking",
        "/admin/inventory",
        "/admin/monitor",
        "/admin/export?kind=tracking",
        "/search?q=wood",
        "/recommend/user",
    ],
)
def test_default_training_artifacts_fail_closed_for_other_stores(isolated, path):
    assert signed_client(isolated, "admin-b", "b").get(path).status_code == 503


def test_pending_domain_cannot_route_and_other_tenant_can_prove_ownership(
    isolated, monkeypatch
):
    a = signed_client(isolated, "admin-a")
    b = signed_client(isolated, "admin-b", "b")
    domain = "shop.security-example.com"
    claim_a = a.post("/tenant/domains", json={"domain": domain})
    claim_b = b.post("/tenant/domains", json={"domain": domain})
    assert claim_a.status_code == claim_b.status_code == 201
    public = TestClient(app)
    assert (
        public.get("/storefront/config", headers={"Host": domain}).json()["tenant_id"]
        == DEFAULT_TENANT_ID
    )
    with Session(isolated) as db:
        db.add(TenantDomain(tenant_id="a", domain=domain, verified_at=None))
        db.commit()
    assert (
        public.get("/storefront/config", headers={"Host": domain}).json()["tenant_id"]
        == DEFAULT_TENANT_ID
    )
    monkeypatch.setattr(
        "app.tenancy.domains.dns_txt_values", lambda hostname: ["wrong-proof"]
    )
    assert b.post(f"/tenant/domains/{claim_b.json()['id']}/verify").status_code == 409
    assert a.post(f"/tenant/domains/{claim_b.json()['id']}/verify").status_code == 404
    monkeypatch.setattr(
        "app.tenancy.domains.dns_txt_values",
        lambda hostname: [claim_b.json()["dns_instructions"]["value"]],
    )
    verified = b.post(f"/tenant/domains/{claim_b.json()['id']}/verify")
    assert verified.status_code == 200 and verified.json()["verified"] is True
    assert "verification_token" not in verified.json()
    assert (
        public.get("/storefront/config", headers={"Host": domain}).json()["tenant_id"]
        == "b"
    )
    assert b.post(f"/tenant/domains/{claim_b.json()['id']}/verify").status_code == 404
    with Session(isolated) as db:
        assert (
            db.scalar(
                select(TenantDomain).where(TenantDomain.domain == domain)
            ).tenant_id
            == "b"
        )


def test_expired_domain_claim_is_rejected_and_renewal_rotates_proof(
    isolated, monkeypatch
):
    c = signed_client(isolated, "admin-a")
    first = c.post(
        "/tenant/domains", json={"domain": "expired.security-example.com"}
    ).json()
    with Session(isolated) as db:
        db.get(TenantDomainChallenge, first["id"]).expires_at = now() - timedelta(
            seconds=1
        )
        db.commit()
    monkeypatch.setattr(
        "app.tenancy.domains.dns_txt_values",
        lambda hostname: [first["dns_instructions"]["value"]],
    )
    assert c.post(f"/tenant/domains/{first['id']}/verify").status_code == 404
    second = c.post(
        "/tenant/domains", json={"domain": "expired.security-example.com"}
    ).json()
    assert first["id"] != second["id"]
    assert first["dns_instructions"]["value"] != second["dns_instructions"]["value"]
    assert c.post(f"/tenant/domains/{second['id']}/verify").status_code == 409


def test_legacy_analytics_and_csv_only_include_active_tenant(isolated):
    with Session(isolated) as db:
        db.add_all(
            [
                Order(tenant_id="a", user_id="customer-a", total=100),
                Order(tenant_id="b", user_id="customer-b", total=999),
            ]
        )
        db.commit()
    c = signed_client(isolated, "admin-a")
    overview = c.get("/admin/overview")
    assert overview.status_code == 200
    assert overview.json()["kpis"]["revenue"] == 100
    assert overview.json()["kpis"]["orders"] == 1
    exported = c.get("/admin/export?kind=sales")
    assert exported.status_code == 200
    assert "100.0" in exported.text and "999" not in exported.text


def test_domain_claim_expiring_during_dns_lookup_is_not_activated(
    isolated, monkeypatch
):
    c = signed_client(isolated, "admin-a")
    claim = c.post(
        "/tenant/domains", json={"domain": "racing.security-example.com"}
    ).json()

    def expire_during_lookup(host):
        with Session(isolated) as db:
            db.get(TenantDomainChallenge, claim["id"]).expires_at = now() - timedelta(
                seconds=1
            )
            db.commit()
        return [claim["dns_instructions"]["value"]]

    monkeypatch.setattr("app.tenancy.domains.dns_txt_values", expire_during_lookup)
    assert c.post(f"/tenant/domains/{claim['id']}/verify").status_code == 409
    with Session(isolated) as db:
        assert (
            db.scalar(
                select(TenantDomain).where(TenantDomain.domain == claim["domain"])
            )
            is None
        )


def test_domain_dns_timeout_fails_closed_and_lookup_is_bounded(isolated, monkeypatch):
    import dns.exception
    from app.tenancy import domains

    c = signed_client(isolated, "admin-a")
    claim = c.post(
        "/tenant/domains", json={"domain": "timeout.security-example.com"}
    ).json()

    class Resolver:
        def resolve(self, host, record_type, search):
            assert host == "_scenthaus.timeout.security-example.com"
            assert record_type == "TXT" and search is False
            assert self.timeout == 2 and self.lifetime == 5
            raise dns.exception.Timeout()

    monkeypatch.setattr("dns.resolver.Resolver", Resolver)
    assert c.post(f"/tenant/domains/{claim['id']}/verify").status_code == 409
    with Session(isolated) as db:
        assert db.scalar(select(TenantDomain)) is None
        assert db.get(TenantDomainChallenge, claim["id"]) is not None


def test_domain_challenge_migration_is_repeatable(isolated):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = (
        Path(__file__).parents[1]
        / "alembic/versions/0006_domain_ownership_challenges.py"
    )
    spec = importlib.util.spec_from_file_location("domain_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with isolated.begin() as connection:
        TenantDomainChallenge.__table__.drop(connection)
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
        assert (
            "tenant_domain_challenges"
            in __import__("sqlalchemy").inspect(connection).get_table_names()
        )
