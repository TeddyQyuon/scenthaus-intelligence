"""Server-backed account security. Authenticator secrets never leave setup responses."""

import base64
import hashlib
import hmac
import secrets
from datetime import timedelta, timezone

import pyotp
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session as DatabaseSession

from .config import settings
from .database import get_db
from .models import SecurityEvent, Session, User, now
from .security import (
    csrf,
    digest,
    hasher,
    identity,
    issue,
    request_details,
    user_required,
)

router = APIRouter(prefix="/auth")


class Proof(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    otp_code: str | None = Field(default=None, max_length=40)


class Confirmation(BaseModel):
    otp_code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class PasswordChange(Proof):
    new_password: str = Field(min_length=10, max_length=128)


def cipher() -> Fernet:
    key = hashlib.sha256(("scenthaus-totp-v1:" + settings.secret_key).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def record_event(
    db: DatabaseSession,
    request: Request,
    kind: str,
    success: bool,
    user: User | None = None,
    email: str | None = None,
) -> None:
    db.add(
        SecurityEvent(
            user_id=user.id if user else None,
            account_hash=csrf("account:" + email) if email else None,
            kind=kind,
            success=success,
            **request_details(request),
        )
    )


def check_rate_limit(db: DatabaseSession, request: Request, email: str) -> None:
    cutoff = now() - timedelta(minutes=15)
    account = csrf("account:" + email)
    failed = [SecurityEvent.success.is_(False), SecurityEvent.created_at > cutoff]
    count = db.scalar(
        select(func.count())
        .select_from(SecurityEvent)
        .where(*failed, SecurityEvent.account_hash == account)
    )
    address = request_details(request).get("ip_address")
    ip_count = (
        db.scalar(
            select(func.count())
            .select_from(SecurityEvent)
            .where(*failed, SecurityEvent.ip_address == address)
        )
        if address
        else 0
    )
    if count >= 8 or ip_count >= 30:
        raise HTTPException(
            429,
            "Too many failed attempts. Try again in 15 minutes.",
            headers={"Retry-After": "900"},
        )


def verify_factor(user: User, code: str | None) -> bool:
    if not user.totp_secret or not code:
        return False
    code = code.strip()
    if len(code) == 6 and code.isascii() and code.isdigit():
        totp = pyotp.TOTP(cipher().decrypt(user.totp_secret.encode()).decode())
        # now() is naive UTC, so use an explicit UTC timestamp on non-UTC hosts.
        counter = int(now().replace(tzinfo=timezone.utc).timestamp()) // 30
        for step in [counter, counter - 1, counter + 1]:
            if (
                user.totp_last_counter is None or step > user.totp_last_counter
            ) and hmac.compare_digest(totp.at(step * 30), code):
                user.totp_last_counter = step
                return True
    normalized = code.replace("-", "").replace(" ", "").upper()
    expected = csrf(f"recovery:{user.id}:{normalized}")
    hashes = list(user.recovery_code_hashes or [])
    for saved in hashes:
        if hmac.compare_digest(saved, expected):
            hashes.remove(saved)
            user.recovery_code_hashes = hashes
            return True
    return False


def account_required(user: User = Depends(user_required)) -> User:
    if not user.email:
        raise HTTPException(401, "Sign in to manage account security")
    return user


def locked_account(db: DatabaseSession, user: User) -> User:
    return db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def reauthenticate(
    db: DatabaseSession, request: Request, user: User, body: Proof
) -> None:
    check_rate_limit(db, request, user.email)
    try:
        valid = hasher.verify(user.password_hash, body.password)
    except Exception:
        valid = False
    if not valid or (user.totp_secret and not verify_factor(user, body.otp_code)):
        record_event(db, request, "verification", False, user, user.email)
        db.commit()
        raise HTTPException(
            401,
            "Check your password and verification code. Authenticator codes can be used once.",
        )


def clear_pending(user: User) -> None:
    user.pending_totp_secret = None
    user.pending_totp_expires_at = None
    user.pending_totp_session = None


def recovery_codes(user: User) -> list[str]:
    # Generate each code once before grouping it for readability.
    codes = []
    for _ in range(10):
        raw = secrets.token_hex(8).upper()
        codes.append("-".join(raw[i : i + 4] for i in range(0, 16, 4)))
    user.recovery_code_hashes = [
        csrf(f"recovery:{user.id}:{code.replace('-', '')}") for code in codes
    ]
    return codes


def rotate_account(
    db: DatabaseSession, request: Request, response: Response, user: User
) -> dict:
    db.execute(delete(Session).where(Session.user_id == user.id))
    return identity(user, issue(user, response, db, request))


def timestamp(value) -> str | None:
    return value.isoformat(timespec="seconds") + "Z" if value else None


@router.get("/security")
def security_status(
    request: Request,
    user: User = Depends(account_required),
    db: DatabaseSession = Depends(get_db),
) -> dict:
    current = digest(request.cookies["scenthaus_session"])
    sessions = db.scalars(
        select(Session)
        .where(Session.user_id == user.id, Session.expires_at > now())
        .order_by(Session.created_at.desc())
    ).all()
    events = db.scalars(
        select(SecurityEvent)
        .where(
            SecurityEvent.user_id == user.id,
            SecurityEvent.created_at >= now() - timedelta(days=90),
        )
        .order_by(SecurityEvent.created_at.desc())
        .limit(30)
    ).all()
    return {
        "two_factor_enabled": bool(user.totp_secret),
        "recovery_codes_remaining": len(user.recovery_code_hashes or []),
        "sessions": [
            {
                "id": s.public_id,
                "current": s.token_hash == current,
                "login_at": timestamp(s.created_at),
                "last_active_at": timestamp(s.last_seen_at),
                "expires_at": timestamp(s.expires_at),
                "ip_address": s.ip_address,
                "user_agent": s.user_agent,
                "location": s.location,
            }
            for s in sessions
        ],
        "history": [
            {
                "id": e.id,
                "kind": e.kind,
                "success": e.success,
                "created_at": timestamp(e.created_at),
                "ip_address": e.ip_address,
                "user_agent": e.user_agent,
                "location": e.location,
            }
            for e in events
        ],
    }


@router.post("/2fa/setup")
def setup_2fa(
    body: Proof,
    request: Request,
    user: User = Depends(account_required),
    db: DatabaseSession = Depends(get_db),
) -> dict:
    user = locked_account(db, user)
    reauthenticate(db, request, user, body)
    if user.totp_secret:
        raise HTTPException(409, "Two-factor authentication is already enabled")
    secret = pyotp.random_base32()
    user.pending_totp_secret = cipher().encrypt(secret.encode()).decode()
    user.pending_totp_expires_at = now() + timedelta(minutes=10)
    user.pending_totp_session = digest(request.cookies["scenthaus_session"])
    record_event(db, request, "2fa_setup", True, user)
    db.commit()
    return {
        "secret": secret,
        "uri": pyotp.TOTP(secret).provisioning_uri(user.email, issuer_name="SCENTHAUS"),
        "expires_at": timestamp(user.pending_totp_expires_at),
    }


@router.post("/2fa/confirm")
def confirm_2fa(
    body: Confirmation,
    request: Request,
    response: Response,
    user: User = Depends(account_required),
    db: DatabaseSession = Depends(get_db),
) -> dict:
    user = locked_account(db, user)
    check_rate_limit(db, request, user.email)
    if (
        user.totp_secret
        or not user.pending_totp_secret
        or not user.pending_totp_expires_at
        or user.pending_totp_expires_at <= now()
        or user.pending_totp_session != digest(request.cookies["scenthaus_session"])
    ):
        raise HTTPException(400, "Start a new authenticator setup on this device")
    user.totp_secret = user.pending_totp_secret
    if not verify_factor(user, body.otp_code):
        user.totp_secret = None
        record_event(db, request, "verification", False, user, user.email)
        db.commit()
        raise HTTPException(
            400, "Invalid authenticator code. Check your app and device time."
        )
    clear_pending(user)
    codes = recovery_codes(user)
    record_event(db, request, "2fa_enabled", True, user)
    return rotate_account(db, request, response, user) | {"recovery_codes": codes}


@router.post("/2fa/disable")
def disable_2fa(
    body: Proof,
    request: Request,
    response: Response,
    user: User = Depends(account_required),
    db: DatabaseSession = Depends(get_db),
) -> dict:
    user = locked_account(db, user)
    reauthenticate(db, request, user, body)
    user.totp_secret = None
    user.totp_last_counter = None
    user.recovery_code_hashes = []
    clear_pending(user)
    record_event(db, request, "2fa_disabled", True, user)
    return rotate_account(db, request, response, user)


@router.post("/2fa/recovery-codes")
def regenerate_codes(
    body: Proof,
    request: Request,
    response: Response,
    user: User = Depends(account_required),
    db: DatabaseSession = Depends(get_db),
) -> dict:
    user = locked_account(db, user)
    if not user.totp_secret:
        raise HTTPException(400, "Enable two-factor authentication first")
    reauthenticate(db, request, user, body)
    codes = recovery_codes(user)
    record_event(db, request, "recovery_codes_changed", True, user)
    return rotate_account(db, request, response, user) | {"recovery_codes": codes}


@router.put("/password")
def change_password(
    body: PasswordChange,
    request: Request,
    response: Response,
    user: User = Depends(account_required),
    db: DatabaseSession = Depends(get_db),
) -> dict:
    user = locked_account(db, user)
    reauthenticate(db, request, user, body)
    if body.password == body.new_password:
        raise HTTPException(400, "Choose a different new password")
    user.password_hash = hasher.hash(body.new_password)
    clear_pending(user)
    record_event(db, request, "password_changed", True, user)
    return rotate_account(db, request, response, user)


@router.delete("/sessions/others")
def revoke_others(
    request: Request,
    user: User = Depends(account_required),
    db: DatabaseSession = Depends(get_db),
) -> dict:
    db.execute(
        delete(Session).where(
            Session.user_id == user.id,
            Session.token_hash != digest(request.cookies["scenthaus_session"]),
        )
    )
    record_event(db, request, "other_sessions_revoked", True, user)
    db.commit()
    return {"ok": True}


@router.delete("/sessions/{session_id}")
def revoke_session(
    session_id: str,
    request: Request,
    user: User = Depends(account_required),
    db: DatabaseSession = Depends(get_db),
) -> dict:
    session = db.scalar(
        select(Session).where(
            Session.user_id == user.id, Session.public_id == session_id
        )
    )
    if not session:
        raise HTTPException(404, "Session not found")
    if session.token_hash == digest(request.cookies["scenthaus_session"]):
        raise HTTPException(400, "Use Sign out to end your current session")
    db.delete(session)
    record_event(db, request, "session_revoked", True, user)
    db.commit()
    return {"ok": True}
