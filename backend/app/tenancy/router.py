"""Multi-tenant onboarding, storefront configuration, and custom domain routes."""

import re
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession

from ..database import get_db
from ..models import AuditLog, Membership, Tenant, TenantDomain, User, now
from ..security import user_required
from .deps import require_tenant_role, resolve_tenant, set_db_tenant_context

router = APIRouter(tags=["tenancy"])

SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$")
DOMAIN_PATTERN = re.compile(
    r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)


class TenantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=3, max_length=63)
    currency: str = Field(default="SGD", min_length=3, max_length=3)
    country: str = Field(default="SG", min_length=2, max_length=2)
    plan: str = Field(default="starter", pattern=r"^(starter|growth|enterprise)$")

    @field_validator("slug")
    @classmethod
    def check_slug(cls, value: str) -> str:
        slug = value.lower()
        if not SLUG_PATTERN.fullmatch(slug) or slug in {"api", "admin", "www", "platform"}:
            raise ValueError("Invalid or reserved tenant slug")
        return slug

    @field_validator("currency", "country")
    @classmethod
    def upper_code(cls, value: str) -> str:
        return value.upper()


class TenantSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=2, max_length=120)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    theme: dict[str, str] | None = None
    hero_title: str | None = Field(default=None, max_length=200)
    hero_subtitle: str | None = Field(default=None, max_length=500)
    logo_url: str | None = Field(default=None, max_length=500)
    support_email: str | None = Field(default=None, max_length=254)


class DomainRegister(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    domain: str = Field(min_length=4, max_length=253)
    is_primary: bool = True

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, value: str) -> str:
        d = value.lower()
        if not DOMAIN_PATTERN.fullmatch(d):
            raise ValueError("Enter a valid domain name (e.g. shop.brand.com)")
        return d


def serialize_tenant(tenant: Tenant) -> dict:
    return {
        "id": tenant.id,
        "slug": tenant.slug,
        "name": tenant.name,
        "status": tenant.status,
        "plan": tenant.plan,
        "currency": tenant.currency,
        "country": tenant.country,
        "is_demo": tenant.is_demo,
        "stripe_connected": bool(tenant.stripe_account_id),
        "stripe_charges_enabled": tenant.stripe_charges_enabled,
        "stripe_payouts_enabled": tenant.stripe_payouts_enabled,
        "application_fee_bps": tenant.application_fee_bps,
        "settings": tenant.settings_json or {},
    }


@router.get("/storefront/config")
def storefront_config(tenant: Tenant = Depends(resolve_tenant)):
    """Public endpoint consumed by the storefront SPA on boot to apply tenant
    branding, currency, and checkout availability.
    """
    cfg = tenant.settings_json or {}
    return {
        "tenant_id": tenant.id,
        "slug": tenant.slug,
        "name": tenant.name,
        "currency": tenant.currency,
        "country": tenant.country,
        "is_demo": tenant.is_demo,
        "charges_enabled": tenant.stripe_charges_enabled,
        "theme": cfg.get("theme", {}),
        "hero_title": cfg.get("hero_title", f"{tenant.name} — The art of finding you"),
        "hero_subtitle": cfg.get(
            "hero_subtitle",
            "Discover a scent that feels like you.",
        ),
        "logo_url": cfg.get("logo_url"),
        "support_email": cfg.get("support_email"),
    }


@router.post("/platform/tenants", status_code=201)
def create_tenant(
    body: TenantCreate,
    user: User = Depends(user_required),
    db: DatabaseSession = Depends(get_db),
):
    if user.email is None:
        raise HTTPException(403, "Sign in with a verified account to create a store")
    existing = db.scalar(select(Tenant).where(Tenant.slug == body.slug))
    if existing:
        raise HTTPException(409, "That store slug is already taken")

    tenant = Tenant(
        id=str(uuid4()),
        slug=body.slug,
        name=body.name,
        status="active",
        plan=body.plan,
        currency=body.currency,
        country=body.country,
        is_demo=False,
        settings_json={},
    )
    db.add(tenant)
    db.flush()
    db.add(
        Membership(
            tenant_id=tenant.id,
            user_id=user.id,
            role="owner",
        )
    )
    set_db_tenant_context(db, tenant.id)
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor=user.id,
            action="tenant.created",
            detail={"slug": tenant.slug, "plan": tenant.plan},
        )
    )
    db.commit()
    db.refresh(tenant)
    return serialize_tenant(tenant)


@router.get("/platform/tenants")
def list_my_tenants(
    user: User = Depends(user_required),
    db: DatabaseSession = Depends(get_db),
):
    rows = db.execute(
        select(Tenant, Membership.role)
        .join(Membership, Membership.tenant_id == Tenant.id)
        .where(Membership.user_id == user.id)
        .order_by(Tenant.created_at)
    ).all()
    return {
        "tenants": [
            serialize_tenant(tenant) | {"membership_role": role}
            for tenant, role in rows
        ]
    }


@router.put("/tenant/settings")
def update_tenant_settings(
    body: TenantSettingsUpdate,
    ctx: tuple[Tenant, User] = Depends(require_tenant_role("owner", "admin")),
    db: DatabaseSession = Depends(get_db),
):
    tenant, user = ctx
    if body.name is not None:
        tenant.name = body.name
    if body.currency is not None:
        tenant.currency = body.currency.upper()
    if body.country is not None:
        tenant.country = body.country.upper()

    cfg = dict(tenant.settings_json or {})
    for field in ("theme", "hero_title", "hero_subtitle", "logo_url", "support_email"):
        val = getattr(body, field)
        if val is not None:
            cfg[field] = val
    tenant.settings_json = cfg
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor=user.id,
            action="tenant.settings_updated",
            detail={"updated_fields": list(body.model_fields_set)},
        )
    )
    db.commit()
    db.refresh(tenant)
    return serialize_tenant(tenant)


@router.post("/tenant/domains", status_code=201)
def register_custom_domain(
    body: DomainRegister,
    ctx: tuple[Tenant, User] = Depends(require_tenant_role("owner", "admin")),
    db: DatabaseSession = Depends(get_db),
):
    tenant, user = ctx
    if db.scalar(select(TenantDomain).where(TenantDomain.domain == body.domain)):
        raise HTTPException(409, "Domain is already registered")
    domain = TenantDomain(
        tenant_id=tenant.id,
        domain=body.domain,
        is_primary=body.is_primary,
        verification_token=f"scenthaus-verify={uuid4().hex}",
    )
    db.add(domain)
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor=user.id,
            action="tenant.domain_added",
            detail={"domain": body.domain},
        )
    )
    db.commit()
    db.refresh(domain)
    return {
        "id": domain.id,
        "domain": domain.domain,
        "is_primary": domain.is_primary,
        "verified": domain.verified_at is not None,
        "dns_instructions": {
            "type": "TXT",
            "host": f"_scenthaus.{domain.domain}",
            "value": domain.verification_token,
        },
    }
