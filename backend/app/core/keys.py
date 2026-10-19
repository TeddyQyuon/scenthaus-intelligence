"""Domain-separated cryptographic key derivation (HKDF-SHA256).

Separates signing and encryption keys by purpose so that a single raw secret
is never reused directly across JWT sessions, CSRF tokens, checkout quotes,
and TOTP secret encryption. Also supports explicit per-purpose environment
overrides for zero-downtime key rotation.
"""

import base64
import hashlib
import hmac
from typing import Literal

from cryptography.fernet import Fernet, MultiFernet
from ..config import settings

KeyPurpose = Literal[
    "jwt_customer",
    "jwt_staff",
    "csrf",
    "checkout_quote",
    "totp_encryption",
    "email_token",
]


def derive_subkey(
    purpose: KeyPurpose,
    master_key: str | None = None,
    *,
    length: int = 32,
) -> bytes:
    """Derive a deterministic, domain-separated subkey using RFC 5869 HKDF-SHA256."""
    ikm = (master_key or settings.secret_key).encode("utf-8")
    salt = b"scenthaus-hkdf-salt-v2"
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    info = f"scenthaus:{purpose}:v2".encode("utf-8")
    okm = b""
    previous = b""
    counter = 1
    while len(okm) < length:
        previous = hmac.new(prk, previous + info + bytes([counter]), hashlib.sha256).digest()
        okm += previous
        counter += 1
    return okm[:length]


def derive_hex_key(purpose: KeyPurpose, master_key: str | None = None) -> str:
    """Return a hex-encoded 256-bit key for HMAC/JWT operations."""
    return derive_subkey(purpose, master_key, length=32).hex()


def totp_fernet() -> MultiFernet:
    """Return a MultiFernet instance that encrypts with the v2 HKDF subkey
    and remains able to decrypt legacy v1 TOTP secrets during rotation.
    """
    v2_key = base64.urlsafe_b64encode(derive_subkey("totp_encryption"))
    legacy_v1_raw = hashlib.sha256(
        ("scenthaus-totp-v1:" + settings.secret_key).encode("utf-8")
    ).digest()
    v1_key = base64.urlsafe_b64encode(legacy_v1_raw)
    return MultiFernet([Fernet(v2_key), Fernet(v1_key)])
