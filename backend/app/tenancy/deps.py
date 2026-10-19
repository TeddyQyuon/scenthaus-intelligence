"""Tenant resolution, Postgres Row-Level Security context, and RBAC dependencies."""

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session as DatabaseSession

from ..database import get_db
from ..models import Membership, Tenant, TenantDomain, User
from ..security import user_required
from .constants import DEFAULT_TENANT_ID, DEFAULT_TENANT_NAME, DEFAULT_TENANT_SLUG


def ensure_default_tenant(db: DatabaseSession) -> Tenant:
    tenant = db.get(Tenant, DEFAULT_TENANT_ID)
    if tenant is None:
        tenant = Tenant(
            id=DEFAULT_TENANT_ID,
            slug=DEFAULT_TENANT_SLUG,
            name=DEFAULT_TENANT_NAME,
            status="active",
            plan="enterprise",
            currency="SGD",
            country="SG",
            is_demo=True,
            settings_json={},
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
    return tenant


def set_db_tenant_context(db: DatabaseSession, tenant_id: str) -> None:
    """Bind the active tenant_id to both the SQLAlchemy session and Postgres RLS."""
    db.info["tenant_id"] = tenant_id
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": tenant_id},
        )


def resolve_tenant(
    request: Request,
    db: DatabaseSession = Depends(get_db),
) -> Tenant:
    """Resolve the active tenant from headers or Host domain, and activate RLS."""
    header_id = request.headers.get("x-tenant-id", "").strip()
    header_slug = request.headers.get("x-tenant-slug", "").strip().lower()

    tenant: Tenant | None = None
    if header_id:
        tenant = db.get(Tenant, header_id)
        if tenant is None:
            raise HTTPException(404, "Tenant not found")
    elif header_slug:
        if header_slug == DEFAULT_TENANT_SLUG:
            tenant = ensure_default_tenant(db)
        else:
            tenant = db.scalar(select(Tenant).where(Tenant.slug == header_slug))
            if tenant is None:
                raise HTTPException(404, "Tenant not found")
    else:
        raw_host = request.headers.get("host", "").split(":")[0].strip().lower()
        if raw_host and raw_host not in {"localhost", "127.0.0.1", "testserver"}:
            domain_row = db.scalar(
                select(TenantDomain).where(TenantDomain.domain == raw_host)
            )
            if domain_row is not None:
                tenant = db.get(Tenant, domain_row.tenant_id)
            elif raw_host.endswith(".scenthaus.app"):
                sub = raw_host[: -len(".scenthaus.app")]
                if sub and "." not in sub:
                    tenant = db.scalar(select(Tenant).where(Tenant.slug == sub))

    if tenant is None:
        tenant = ensure_default_tenant(db)

    if tenant.status == "suspended":
        raise HTTPException(403, "This storefront is currently suspended")

    set_db_tenant_context(db, tenant.id)
    return tenant


def require_tenant_role(*allowed_roles: str):
    """Require the authenticated user to hold a Membership with one of allowed_roles
    in the active tenant (or be the tenant's admin user).
    """
    roles = set(allowed_roles) or {"owner", "admin"}

    def _dependency(
        tenant: Tenant = Depends(resolve_tenant),
        user: User = Depends(user_required),
        db: DatabaseSession = Depends(get_db),
    ) -> tuple[Tenant, User]:
        set_db_tenant_context(db, tenant.id)
        membership = db.scalar(
            select(Membership).where(
                Membership.tenant_id == tenant.id,
                Membership.user_id == user.id,
            )
        )
        if membership and membership.role in roles:
            return tenant, user
        if user.role == "admin" and user.tenant_id == tenant.id:
            return tenant, user
        raise HTTPException(403, "Insufficient tenant permissions")

    return _dependency
