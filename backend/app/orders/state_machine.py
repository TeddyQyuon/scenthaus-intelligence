"""Explicit order lifecycle state machine with audit trail and inventory restocking."""

from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session as DatabaseSession

from ..database import get_db
from ..models import AuditLog, Order, OrderItem, Tenant, User, Variant, now
from ..tenancy.deps import require_tenant_role

router = APIRouter(prefix="/tenant/orders", tags=["orders"])

OrderState = Literal[
    "pending_payment",
    "confirmed",
    "paid",
    "fulfilling",
    "shipped",
    "delivered",
    "partially_refunded",
    "refunded",
    "cancelled",
    "expired",
]

VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending_payment": {"confirmed", "paid", "cancelled", "expired"},
    "confirmed": {"fulfilling", "shipped", "refunded", "partially_refunded", "cancelled"},
    "paid": {"fulfilling", "shipped", "refunded", "partially_refunded", "cancelled"},
    "fulfilling": {"shipped", "refunded", "partially_refunded", "cancelled"},
    "shipped": {"delivered", "refunded", "partially_refunded"},
    "delivered": {"refunded", "partially_refunded"},
    "partially_refunded": {"refunded"},
    "cancelled": set(),
    "expired": set(),
    "refunded": set(),
}


class OrderTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    target_status: OrderState
    tracking_number: str | None = Field(default=None, max_length=100)
    carrier: str | None = Field(default=None, max_length=80)
    reason: str | None = Field(default=None, max_length=300)
    restock: bool = False


def transition_order(
    db: DatabaseSession,
    order: Order,
    target_status: str,
    *,
    actor: str = "system",
    reason: str | None = None,
    tracking_number: str | None = None,
    carrier: str | None = None,
    restock: bool = False,
) -> Order:
    """Validate and apply an order state transition, recording an immutable audit log."""
    current = order.status
    if current == target_status:
        return order

    allowed = VALID_TRANSITIONS.get(current, set())
    if target_status not in allowed:
        raise HTTPException(
            409,
            f"Cannot transition order from '{current}' to '{target_status}'",
        )

    restocked_units = 0
    if restock:
        items = db.scalars(
            select(OrderItem).where(OrderItem.order_id == order.id)
        ).all()
        for item in items:
            db.execute(
                update(Variant)
                .where(
                    Variant.id == item.variant_id,
                    Variant.tenant_id == order.tenant_id,
                )
                .values(stock=Variant.stock + item.quantity)
            )
            restocked_units += item.quantity
        order.stock_reserved = False

    order.status = target_status
    if target_status == "refunded":
        order.payment_status = "refunded"
    elif target_status in {"cancelled", "expired"} and order.payment_status == "pending":
        order.payment_status = "failed"

    if tracking_number or carrier:
        addr = dict(order.delivery_address or {})
        addr["fulfilment"] = {
            "tracking_number": tracking_number,
            "carrier": carrier,
            "shipped_at": now().isoformat(),
        }
        order.delivery_address = addr

    order.updated_at = now()
    db.add(
        AuditLog(
            tenant_id=order.tenant_id,
            actor=actor,
            action="order.status_transition",
            detail={
                "order_id": order.id,
                "order_number": order.order_number,
                "from": current,
                "to": target_status,
                "reason": reason,
                "tracking_number": tracking_number,
                "carrier": carrier,
                "restocked_units": restocked_units,
            },
        )
    )
    return order


@router.get("")
def list_tenant_orders(
    status: str | None = Query(default=None),
    include_simulated: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    ctx: tuple[Tenant, User] = Depends(
        require_tenant_role("owner", "admin", "manager", "analyst")
    ),
    db: DatabaseSession = Depends(get_db),
):
    tenant, _ = ctx
    stmt = select(Order).where(Order.tenant_id == tenant.id)
    if not include_simulated:
        stmt = stmt.where(Order.simulated.is_(False))
    if status:
        stmt = stmt.where(Order.status == status)
    rows = db.scalars(stmt.order_by(Order.created_at.desc()).limit(limit)).all()
    return {
        "orders": [
            {
                "id": o.id,
                "order_number": o.order_number,
                "status": o.status,
                "payment_status": o.payment_status,
                "total": float(o.total),
                "total_minor": o.total_minor,
                "currency": o.currency or tenant.currency,
                "customer_name": o.customer_name,
                "customer_email": o.customer_email,
                "delivery_address": o.delivery_address,
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "paid_at": o.paid_at.isoformat() if o.paid_at else None,
            }
            for o in rows
        ]
    }


@router.post("/{order_id}/transition")
def transition_tenant_order(
    order_id: str,
    body: OrderTransitionRequest,
    ctx: tuple[Tenant, User] = Depends(
        require_tenant_role("owner", "admin", "manager")
    ),
    db: DatabaseSession = Depends(get_db),
):
    tenant, user = ctx
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.tenant_id == tenant.id)
        .with_for_update()
    )
    if order is None:
        raise HTTPException(404, "Order not found")

    transition_order(
        db,
        order,
        body.target_status,
        actor=user.id,
        reason=body.reason,
        tracking_number=body.tracking_number,
        carrier=body.carrier,
        restock=body.restock,
    )
    db.commit()
    db.refresh(order)
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "payment_status": order.payment_status,
        "delivery_address": order.delivery_address,
        "updated_at": order.updated_at.isoformat(),
    }
