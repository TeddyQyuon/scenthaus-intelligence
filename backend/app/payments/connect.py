"""Stripe Connect multi-tenant onboarding, application fee calculation, and webhook routing."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession

from ..database import get_db
from ..models import AuditLog, Tenant, User
from ..tenancy.deps import require_tenant_role, set_db_tenant_context

router = APIRouter(tags=["payments-connect"])


class ConnectAccountBind(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    stripe_account_id: str = Field(pattern=r"^acct_[a-zA-Z0-9]+$", max_length=64)


def calculate_application_fee(total_minor: int, fee_bps: int) -> int:
    """Calculate platform fee in minor currency units from basis points (100 bps = 1%)."""
    if total_minor <= 0 or fee_bps <= 0:
        return 0
    fee = (total_minor * fee_bps) // 10_000
    return min(fee, max(0, total_minor - 1))


def build_connect_checkout_params(tenant: Tenant, total_minor: int) -> dict:
    """Build Stripe Connect payment_intent_data for a connected merchant account."""
    if not tenant.stripe_account_id or not tenant.stripe_charges_enabled:
        return {}
    fee = calculate_application_fee(total_minor, tenant.application_fee_bps)
    payment_intent_data: dict = {
        "on_behalf_of": tenant.stripe_account_id,
        "transfer_data": {"destination": tenant.stripe_account_id},
    }
    if fee > 0:
        payment_intent_data["application_fee_amount"] = fee
    return {"payment_intent_data": payment_intent_data}


@router.post("/tenant/payments/connect")
def bind_connect_account(
    body: ConnectAccountBind,
    ctx: tuple[Tenant, User] = Depends(require_tenant_role("owner", "admin")),
    db: DatabaseSession = Depends(get_db),
):
    tenant, user = ctx
    conflict = db.scalar(
        select(Tenant).where(
            Tenant.stripe_account_id == body.stripe_account_id,
            Tenant.id != tenant.id,
        )
    )
    if conflict:
        raise HTTPException(409, "Stripe account is already linked to another tenant")

    tenant.stripe_account_id = body.stripe_account_id
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor=user.id,
            action="tenant.stripe_connected",
            detail={"stripe_account_id": body.stripe_account_id},
        )
    )
    db.commit()
    db.refresh(tenant)
    return {
        "tenant_id": tenant.id,
        "stripe_account_id": tenant.stripe_account_id,
        "charges_enabled": tenant.stripe_charges_enabled,
        "payouts_enabled": tenant.stripe_payouts_enabled,
    }


def apply_connect_account_event(event: dict, db: DatabaseSession) -> bool:
    """Process `account.updated` events from Stripe Connect to sync merchant status."""
    if event.get("type") != "account.updated":
        return False
    obj = event.get("data", {}).get("object", {})
    acct_id = obj.get("id")
    if not acct_id:
        return False
    tenant = db.scalar(
        select(Tenant).where(Tenant.stripe_account_id == acct_id).with_for_update()
    )
    if tenant is None:
        return False
    set_db_tenant_context(db, tenant.id)
    tenant.stripe_charges_enabled = bool(obj.get("charges_enabled"))
    tenant.stripe_payouts_enabled = bool(obj.get("payouts_enabled"))
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor="stripe_connect_webhook",
            action="tenant.stripe_account_updated",
            detail={
                "stripe_account_id": acct_id,
                "charges_enabled": tenant.stripe_charges_enabled,
                "payouts_enabled": tenant.stripe_payouts_enabled,
            },
        )
    )
    db.commit()
    return True
