"""Account security integration tests against the configured PostgreSQL fixture."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta, timezone
from uuid import uuid4

import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app import account_security
from app.database import SessionLocal, engine
from app.main import app
from app.models import User, Variant, now

PASSWORD = "local-test-password-1234"


def accept(client, result):
    assert result.status_code == 200, result.text
    client.headers["X-CSRF-Token"] = result.json()["csrf"]
    return result.json()


def register(client):
    email = f"security-{uuid4()}@example.test"
    result = accept(
        client,
        client.post("/auth/register", json={"email": email, "password": PASSWORD}),
    )
    return email, result["user"]["id"]


def guest(client):
    client.headers["Origin"] = "http://localhost:5173"
    accept(client, client.get("/auth/session"))


def enable(client, monkeypatch):
    clock = now().replace(microsecond=0)
    monkeypatch.setattr(account_security, "now", lambda: clock)
    result = client.post("/auth/2fa/setup", json={"password": PASSWORD})
    assert result.status_code == 200
    secret = result.json()["secret"]
    code = pyotp.TOTP(secret).at(clock.replace(tzinfo=timezone.utc))
    result = accept(client, client.post("/auth/2fa/confirm", json={"otp_code": code}))
    return secret, code, result["recovery_codes"]


def test_guest_security_and_csrf_are_rejected(client):
    assert client.get("/auth/security").status_code == 401
    register(client)
    assert (
        client.post(
            "/auth/2fa/setup",
            json={"password": PASSWORD},
            headers={"X-CSRF-Token": "bad"},
        ).status_code
        == 403
    )
    assert (
        client.delete(
            "/auth/sessions/others", headers={"Origin": "https://untrusted.example"}
        ).status_code
        == 403
    )


def test_security_reads_do_not_exhaust_sign_in_budget(client):
    register(client)
    for _ in range(35):
        assert client.get("/auth/security").status_code == 200
    accept(client, client.post("/auth/logout"))


def test_authentication_writes_keep_their_rate_limit(client):
    for _ in range(30):
        accept(client, client.post("/auth/logout"))
    assert client.post("/auth/logout").status_code == 429


def test_setup_requires_password_and_verified_code_and_encrypts_secret(
    client, monkeypatch
):
    _, user_id = register(client)
    assert (
        client.post("/auth/2fa/setup", json={"password": "incorrect"}).status_code
        == 401
    )
    setup = client.post("/auth/2fa/setup", json={"password": PASSWORD}).json()
    assert not client.get("/auth/security").json()["two_factor_enabled"]
    assert "otpauth://totp/" in setup["uri"]
    totp = pyotp.TOTP(setup["secret"])
    current = now().replace(tzinfo=timezone.utc)
    used = {totp.at(current + timedelta(seconds=step)) for step in [-30, 0, 30]}
    incorrect = next(
        f"{number:06d}" for number in range(20) if f"{number:06d}" not in used
    )
    assert (
        client.post("/auth/2fa/confirm", json={"otp_code": incorrect}).status_code
        == 400
    )
    assert not client.get("/auth/security").json()["two_factor_enabled"]
    raw, _, codes = enable(client, monkeypatch)
    assert len(codes) == len(set(codes)) == 10
    with SessionLocal() as db:
        account = db.get(User, user_id)
        assert account.totp_secret != raw
        assert (
            account_security.cipher().decrypt(account.totp_secret.encode()).decode()
            == raw
        )
        assert all(
            code.replace("-", "") not in account.recovery_code_hashes for code in codes
        )
    status = client.get("/auth/security").json()
    assert status["two_factor_enabled"]
    assert status["recovery_codes_remaining"] == 10
    assert "secret" not in str(status)
    exported = client.get("/privacy/export").json()
    assert exported["security_history"]
    assert raw not in str(exported)
    assert all(code not in str(exported) for code in codes)


def test_password_only_login_cannot_access_account_and_codes_are_single_use(
    client, monkeypatch
):
    email, _ = register(client)
    _, code, codes = enable(client, monkeypatch)
    with TestClient(app) as peer:
        guest(peer)
        before = peer.cookies.get("scenthaus_session")
        credentials = {"email": email, "password": PASSWORD}
        result = peer.post("/auth/login", json=credentials)
        assert result.json() == {"mfa_required": True}
        assert peer.cookies.get("scenthaus_session") == before
        assert peer.get("/auth/security").status_code == 401
        assert (
            peer.post("/auth/login", json=credentials | {"otp_code": code}).status_code
            == 401
        )
        signed_in = accept(
            peer, peer.post("/auth/login", json=credentials | {"otp_code": codes[0]})
        )
        assert signed_in["user"]["two_factor_enabled"]
        accept(peer, peer.post("/auth/logout"))
        assert (
            peer.post(
                "/auth/login", json=credentials | {"otp_code": codes[0]}
            ).status_code
            == 401
        )
    assert client.get("/auth/security").json()["recovery_codes_remaining"] == 9


def test_pending_setup_is_bound_to_session_and_expires(client, monkeypatch):
    email, _ = register(client)
    setup = client.post("/auth/2fa/setup", json={"password": PASSWORD}).json()
    code = pyotp.TOTP(setup["secret"]).now()
    with TestClient(app) as peer:
        guest(peer)
        accept(
            peer, peer.post("/auth/login", json={"email": email, "password": PASSWORD})
        )
        assert (
            peer.post("/auth/2fa/confirm", json={"otp_code": code}).status_code == 400
        )
    clock = now() + timedelta(minutes=11)
    monkeypatch.setattr(account_security, "now", lambda: clock)
    assert client.post("/auth/2fa/confirm", json={"otp_code": code}).status_code == 400


def test_sessions_show_real_metadata_and_revoke_only_owned_devices(client, monkeypatch):
    client.headers["User-Agent"] = "Mozilla/5.0 Test Browser"
    monkeypatch.setenv("VERCEL", "1")
    client.headers.update(
        {
            "x-vercel-forwarded-for": "203.0.113.7",
            "x-vercel-ip-city": "Singapore",
            "x-vercel-ip-country": "SG",
        }
    )
    email, _ = register(client)
    with TestClient(app) as peer, TestClient(app) as stranger:
        guest(peer)
        accept(
            peer, peer.post("/auth/login", json={"email": email, "password": PASSWORD})
        )
        guest(stranger)
        register(stranger)
        status = client.get("/auth/security").json()
        current = next(s for s in status["sessions"] if s["current"])
        other = next(s for s in status["sessions"] if not s["current"])
        assert current["ip_address"] == "203.0.113.7"
        assert current["location"] == "Singapore, SG"
        assert current["login_at"].endswith("Z")
        assert "token_hash" not in current
        assert stranger.delete(f"/auth/sessions/{other['id']}").status_code == 404
        assert client.delete(f"/auth/sessions/{current['id']}").status_code == 400
        assert client.delete(f"/auth/sessions/{other['id']}").status_code == 200
        assert peer.get("/auth/security").status_code == 401
        assert len(client.get("/auth/security").json()["sessions"]) == 1
        guest(peer)
        accept(
            peer, peer.post("/auth/login", json={"email": email, "password": PASSWORD})
        )
        cookie = client.cookies.get("scenthaus_session")
        assert client.delete("/auth/sessions/others").status_code == 200
        assert client.cookies.get("scenthaus_session") == cookie
        assert peer.get("/auth/security").status_code == 401
        assert client.get("/auth/security").status_code == 200


def test_untrusted_forwarded_headers_are_not_used(client, monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    client.headers.update(
        {"x-vercel-forwarded-for": "203.0.113.7", "x-vercel-ip-city": "Spoofed"}
    )
    register(client)
    current = client.get("/auth/security").json()["sessions"][0]
    assert current["ip_address"] is None
    assert current["location"] is None


def test_password_change_verifies_factor_and_invalidates_other_sessions(
    client, monkeypatch
):
    email, _ = register(client)
    _, _, codes = enable(client, monkeypatch)
    with TestClient(app) as peer:
        guest(peer)
        accept(
            peer,
            peer.post(
                "/auth/login",
                json={"email": email, "password": PASSWORD, "otp_code": codes[0]},
            ),
        )
        body = {"password": PASSWORD, "new_password": PASSWORD + "-new"}
        assert client.put("/auth/password", json=body).status_code == 401
        before = client.cookies.get("scenthaus_session")
        accept(client, client.put("/auth/password", json=body | {"otp_code": codes[1]}))
        assert client.cookies.get("scenthaus_session") != before
        assert peer.get("/auth/security").status_code == 401
        accept(peer, peer.get("/auth/session"))
        assert (
            peer.post(
                "/auth/login",
                json={"email": email, "password": PASSWORD, "otp_code": codes[2]},
            ).status_code
            == 401
        )
        accept(
            peer,
            peer.post(
                "/auth/login",
                json={
                    "email": email,
                    "password": body["new_password"],
                    "otp_code": codes[2],
                },
            ),
        )


def test_recovery_regeneration_and_disabling_require_second_factor(client, monkeypatch):
    email, _ = register(client)
    _, _, codes = enable(client, monkeypatch)
    assert (
        client.post("/auth/2fa/disable", json={"password": PASSWORD}).status_code == 401
    )
    fresh = accept(
        client,
        client.post(
            "/auth/2fa/recovery-codes",
            json={"password": PASSWORD, "otp_code": codes[0]},
        ),
    )["recovery_codes"]
    with TestClient(app) as peer:
        guest(peer)
        assert (
            peer.post(
                "/auth/login",
                json={"email": email, "password": PASSWORD, "otp_code": codes[1]},
            ).status_code
            == 401
        )
    result = accept(
        client,
        client.post(
            "/auth/2fa/disable", json={"password": PASSWORD, "otp_code": fresh[0]}
        ),
    )
    assert not result["user"]["two_factor_enabled"]
    assert client.get("/auth/security").json()["recovery_codes_remaining"] == 0


def test_failed_attempts_are_audited_and_persistently_rate_limited(client):
    email, _ = register(client)
    for _ in range(8):
        assert (
            client.post(
                "/auth/login", json={"email": email, "password": "wrong-password"}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/auth/login", json={"email": email, "password": PASSWORD}
        ).status_code
        == 429
    )
    failures = [
        event
        for event in client.get("/auth/security").json()["history"]
        if not event["success"]
    ]
    assert len(failures) == 8


def test_recovery_code_cannot_be_consumed_concurrently(client, monkeypatch):
    email, _ = register(client)
    _, _, codes = enable(client, monkeypatch)

    def sign_in(_):
        with TestClient(app) as peer:
            guest(peer)
            return peer.post(
                "/auth/login",
                json={"email": email, "password": PASSWORD, "otp_code": codes[0]},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(sign_in, range(2))) == [200, 401]


def test_quick_add_preserves_exact_quantity_and_limits(client):
    with SessionLocal() as db:
        variant = db.scalar(select(Variant).where(Variant.stock >= 10))
        variant_id = variant.id
    assert (
        client.post("/cart/add", json={"variant_id": variant_id, "quantity": 2}).json()[
            "items"
        ][0]["quantity"]
        == 2
    )
    assert (
        client.post("/cart/add", json={"variant_id": variant_id, "quantity": 3}).json()[
            "items"
        ][0]["quantity"]
        == 5
    )
    assert (
        client.post(
            "/cart/add", json={"variant_id": variant_id, "quantity": 6}
        ).status_code
        == 409
    )
    assert client.get("/cart").json()["items"][0]["quantity"] == 5


def test_migration_upgrades_old_sessions_without_inventing_login_times():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "security_migration",
        Path(__file__).parents[1] / "alembic/versions/0003_account_security.py",
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    schema = "security_migration_" + uuid4().hex
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        connection.execute(text("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY)"))
        connection.execute(
            text(
                "CREATE TABLE sessions (token_hash VARCHAR(64) PRIMARY KEY, user_id VARCHAR(36) REFERENCES users(id), expires_at TIMESTAMP NOT NULL)"
            )
        )
        connection.execute(text("INSERT INTO users VALUES ('old-user')"))
        connection.execute(
            text(
                "INSERT INTO sessions VALUES ('old-token-hash', 'old-user', CURRENT_TIMESTAMP + interval '1 day')"
            )
        )
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
        row = connection.execute(text("SELECT * FROM sessions")).mappings().one()
        assert row["token_hash"] == "old-token-hash"
        assert row["public_id"]
        assert row["created_at"] is None
        assert row["last_seen_at"] is None
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


def test_concurrent_quick_add_does_not_overwrite_existing_bag_quantity(client):
    with SessionLocal() as db:
        variant_id = db.scalar(select(Variant.id).where(Variant.stock >= 10))
    assert (
        client.post(
            "/cart/add", json={"variant_id": variant_id, "quantity": 1}
        ).status_code
        == 200
    )
    cookie = client.cookies.get("scenthaus_session")
    headers = dict(client.headers)

    def add(quantity):
        with TestClient(app) as peer:
            peer.cookies.set("scenthaus_session", cookie)
            return peer.post(
                "/cart/add",
                headers=headers,
                json={"variant_id": variant_id, "quantity": quantity},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(add, [2, 3])) == [200, 200]
    assert client.get("/cart").json()["items"][0]["quantity"] == 6
