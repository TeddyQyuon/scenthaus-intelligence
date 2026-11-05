"""Bounded public DNS proof for custom domains, with concurrent tenant claims."""

import hmac
from datetime import timedelta
import secrets

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from ..models import AuditLog, TenantDomain, TenantDomainChallenge, now

CLAIM_LIFETIME = timedelta(hours=24)


def dns_txt_values(domain):
    import dns.exception
    import dns.resolver

    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = 2
        resolver.lifetime = 5
        answer = resolver.resolve(f"_scenthaus.{domain}", "TXT", search=False)
        return [
            b"".join(record.strings).decode("ascii", errors="strict")
            for record in answer
        ]
    except (dns.exception.DNSException, UnicodeError):
        raise HTTPException(
            409, "DNS ownership could not be verified. Check the TXT record and retry."
        ) from None


def register_domain_claim(db, tenant, user, domain, is_primary):
    # A pending claim never reserves a domain globally. Another tenant can prove
    # ownership immediately, even if a squatter registered that name first.
    db.execute(
        delete(TenantDomainChallenge).where(
            TenantDomainChallenge.tenant_id == tenant.id,
            TenantDomainChallenge.expires_at <= now(),
        )
    )
    claim = db.scalar(
        select(TenantDomainChallenge).where(
            TenantDomainChallenge.tenant_id == tenant.id,
            TenantDomainChallenge.domain == domain,
        )
    )
    if claim is None:
        claim = TenantDomainChallenge(
            tenant_id=tenant.id,
            domain=domain,
            is_primary=is_primary,
            verification_token="scenthaus-verify=" + secrets.token_urlsafe(32),
            expires_at=now() + CLAIM_LIFETIME,
        )
        db.add(claim)
    else:
        claim.is_primary = is_primary
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor=user.id,
            action="tenant.domain_claimed",
            detail={"domain": domain},
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A claim already exists. Retry the request.") from None
    db.refresh(claim)
    return {
        "id": claim.id,
        "domain": claim.domain,
        "is_primary": claim.is_primary,
        "verified": False,
        "expires_at": claim.expires_at.isoformat() + "Z",
        "dns_instructions": {
            "type": "TXT",
            "host": f"_scenthaus.{claim.domain}",
            "value": claim.verification_token,
        },
    }


def verify_domain_claim(db, tenant, user, claim_id):
    claim = db.scalar(
        select(TenantDomainChallenge).where(
            TenantDomainChallenge.id == claim_id,
            TenantDomainChallenge.tenant_id == tenant.id,
            TenantDomainChallenge.expires_at > now(),
        )
    )
    if claim is None:
        raise HTTPException(404, "Domain claim not found or expired")
    domain, token = claim.domain, claim.verification_token
    db.commit()  # DNS must not hold a database transaction/row lock open.
    values = dns_txt_values(domain)
    if not any(hmac.compare_digest(token, value) for value in values):
        raise HTTPException(
            409, "DNS ownership could not be verified. Check the TXT record and retry."
        )
    claim = db.scalar(
        select(TenantDomainChallenge)
        .where(
            TenantDomainChallenge.id == claim_id,
            TenantDomainChallenge.tenant_id == tenant.id,
            TenantDomainChallenge.expires_at > now(),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if claim is None or not hmac.compare_digest(claim.verification_token, token):
        raise HTTPException(409, "Domain claim changed or expired. Start a new claim.")
    mapping = db.scalar(
        select(TenantDomain).where(TenantDomain.domain == domain).with_for_update()
    )
    if mapping is None:
        mapping = TenantDomain(domain=domain)
        db.add(mapping)
    # Current DNS ownership also permits recovery of a stale or squatted claim.
    mapping.tenant_id = tenant.id
    mapping.verification_token = token
    mapping.is_primary = claim.is_primary
    mapping.verified_at = now()
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor=user.id,
            action="tenant.domain_verified",
            detail={"domain": domain},
        )
    )
    db.delete(claim)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "Domain mapping changed. Retry verification."
        ) from None
    return {
        "id": mapping.id,
        "domain": domain,
        "is_primary": mapping.is_primary,
        "verified": True,
    }
