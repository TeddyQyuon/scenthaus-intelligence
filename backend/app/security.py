import hashlib, hmac, secrets
import jwt
import os
from ipaddress import ip_address
from urllib.parse import unquote
from datetime import timedelta
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from argon2 import PasswordHasher
from .database import get_db
from .models import Session, User, now
from .config import settings

hasher = PasswordHasher()


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def csrf(token):
    return hmac.new(
        settings.secret_key.encode(), token.encode(), hashlib.sha256
    ).hexdigest()


def session_user(request, db):
    token = request.cookies.get("scenthaus_session", "")
    if token:
        try:
            jwt.decode(
                token, settings.secret_key, algorithms=["HS256"], audience="scenthaus"
            )
        except jwt.InvalidTokenError:
            return None
    session = db.get(Session, digest(token)) if token else None
    return (
        db.get(User, session.user_id)
        if session and session.expires_at > now()
        else None
    )


def request_details(request: Request | None) -> dict:
    if request is None:
        return {}
    # Vercel overwrites these headers. Never trust forwarded metadata locally.
    trusted_edge = os.environ.get("VERCEL") == "1"
    raw_ip = (
        request.headers.get("x-vercel-forwarded-for", "").split(",")[0].strip()
        if trusted_edge
        else request.client.host if request.client else ""
    )
    try:
        address = str(ip_address(raw_ip))
    except ValueError:
        address = None
    location = None
    if trusted_edge:
        city = unquote(request.headers.get("x-vercel-ip-city", ""))[:100]
        country = request.headers.get("x-vercel-ip-country", "")[:3]
        location = ", ".join(part for part in [city, country] if part) or None
    return {
        "ip_address": address,
        "user_agent": request.headers.get("user-agent", "")[:512] or None,
        "location": location,
    }


def issue(user, response, db, request: Request | None = None):
    token = jwt.encode(
        {
            "sub": user.id,
            "role": user.role,
            "aud": "scenthaus",
            "jti": secrets.token_urlsafe(24),
            "iat": now(),
            "exp": now() + timedelta(days=7),
        },
        settings.secret_key,
        algorithm="HS256",
    )
    db.add(
        Session(
            token_hash=digest(token),
            user_id=user.id,
            expires_at=now() + timedelta(days=7),
            created_at=now(),
            last_seen_at=now(),
            **request_details(request),
        )
    )
    db.commit()
    response.set_cookie(
        "scenthaus_session",
        token,
        max_age=604800,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        path="/",
    )
    return csrf(token)


def user_required(request: Request, db=Depends(get_db)):
    user = session_user(request, db)
    if not user:
        raise HTTPException(401, "Start a session or sign in")
    if request.method not in ["GET", "HEAD", "OPTIONS"]:
        if request.headers.get("origin") not in settings.origins:
            raise HTTPException(403, "Untrusted origin")
        if not hmac.compare_digest(
            request.headers.get("x-csrf-token", ""),
            csrf(request.cookies.get("scenthaus_session", "")),
        ):
            raise HTTPException(403, "CSRF check failed")
    session = db.get(Session, digest(request.cookies["scenthaus_session"]))
    if session.last_seen_at is None or session.last_seen_at < now() - timedelta(minutes=5):
        session.last_seen_at = now()
        db.commit()
    return user


def admin_required(user=Depends(user_required)):
    if user.role != "admin":
        raise HTTPException(403, "Admin access required")
    return user


def identity(user, token):
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "consent": user.consent,
            "guest": user.email is None,
            "two_factor_enabled": bool(user.totp_secret),
        },
        "csrf": token,
    }
