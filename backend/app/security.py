import hashlib, hmac, secrets
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
    session = db.get(Session, digest(token)) if token else None
    return (
        db.get(User, session.user_id)
        if session and session.expires_at > now()
        else None
    )


def issue(user, response, db):
    token = secrets.token_urlsafe(48)
    db.add(
        Session(
            token_hash=digest(token),
            user_id=user.id,
            expires_at=now() + timedelta(days=7),
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
        },
        "csrf": token,
    }
