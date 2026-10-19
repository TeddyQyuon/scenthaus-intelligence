"""PDPA & GDPR compliance endpoints per tenant:
- Data portability export (`GET /tenant/compliance/export`)
- Right to erasure (`DELETE /tenant/compliance/account`) with financial record anonymisation
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session as DatabaseSession

from ..database import get_db
from ..models import (
    AuditLog,
    CartItem,
    Event,
    Membership,
    Order,
    QuizProfile,
    RecommendationRequest,
    Session,
    Tenant,
    User,
    Wishlist,
)
from ..security import user_required
from ..tenancy.deps import resolve_tenant, set_db_tenant_context

router = APIRouter(prefix="/tenant/compliance", tags=["tenant-compliance"])


@router.get("/export")
def export_tenant_personal_data(
    tenant: Tenant = Depends(resolve_tenant),
    user: User = Depends(user_required),
    db: DatabaseSession = Depends(get_db),
):
    set_db_tenant_context(db, tenant.id)
    wishes = db.scalars(
        select(Wishlist.product_id).where(
            Wishlist.tenant_id == tenant.id,
            Wishlist.user_id == user.id,
        )
    ).all()
    events = db.scalars(
        select(Event)
        .where(Event.tenant_id == tenant.id, Event.user_id == user.id)
        .order_by(Event.created_at.desc())
    ).all()
    orders = db.scalars(
        select(Order)
        .where(Order.tenant_id == tenant.id, Order.user_id == user.id)
        .order_by(Order.created_at.desc())
    ).all()

    return {
        "tenant": {"id": tenant.id, "slug": tenant.slug, "name": tenant.name},
        "user": {
            "id": user.id,
            "email": user.email,
            "consent": user.consent,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "wishlist_product_ids": list(wishes),
        "events": [
            {
                "event_type": e.event_type,
                "product_id": e.product_id,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
        "orders": [
            {
                "id": o.id,
                "order_number": o.order_number,
                "status": o.status,
                "total": float(o.total),
                "currency": o.currency or tenant.currency,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders
        ],
    }


@router.delete("/account")
def erase_customer_account(
    response: Response,
    tenant: Tenant = Depends(resolve_tenant),
    user: User = Depends(user_required),
    db: DatabaseSession = Depends(get_db),
):
    """Execute GDPR/PDPA Right to Erasure while preserving anonymized order ledger totals for tax compliance."""
    set_db_tenant_context(db, tenant.id)

    for model in (Wishlist, CartItem, Event, RecommendationRequest):
        db.execute(
            delete(model).where(
                model.tenant_id == tenant.id,
                model.user_id == user.id,
            )
        )
    db.execute(delete(QuizProfile).where(QuizProfile.user_id == user.id))
    db.execute(delete(Session).where(Session.user_id == user.id))
    db.execute(
        delete(Membership).where(
            Membership.tenant_id == tenant.id,
            Membership.user_id == user.id,
        )
    )

    # Anonymise PII on historical orders while retaining financial totals for tax/audit laws
    db.execute(
        update(Order)
        .where(Order.tenant_id == tenant.id, Order.user_id == user.id)
        .values(
            customer_name="Redacted Customer",
            customer_email=None,
            customer_phone=None,
            delivery_address={"redacted": True},
        )
    )

    user.email = None
    user.password_hash = None
    user.consent = False
    user.quiz_profile = None
    user.totp_secret = None
    user.recovery_code_hashes = []
    user.pending_totp_secret = None

    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor=user.id,
            action="compliance.account_erased",
            detail={"anonymized_orders": True},
        )
    )
    db.commit()
    response.delete_cookie("scenthaus_session", path="/")
    return {"erased": True, "tenant_id": tenant.id}
