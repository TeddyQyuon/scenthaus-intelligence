"""Tenant-scoped Customers business logic & queries."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession

from ...models import Order, Tenant, User

PAID_CONFIRMED_STATUSES = {
    "confirmed",
    "paid",
    "fulfilling",
    "shipped",
    "delivered",
    "demo_completed",
}


def is_paid_or_confirmed(order: Order) -> bool:
    if order.status in {"cancelled", "expired"}:
        return False
    return order.status in PAID_CONFIRMED_STATUSES or order.payment_status == "paid"


def serialize_order_summary(order: Order, tenant: Tenant) -> dict:
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "payment_status": order.payment_status,
        "total": float(order.total),
        "total_minor": order.total_minor,
        "currency": order.currency or tenant.currency,
        "customer_name": order.customer_name,
        "customer_email": order.customer_email,
        "delivery_address": order.delivery_address,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
    }


def serialize_customer_summary(
    user: User,
    order_count: int,
    total_spend: float,
) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "consent": user.consent,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "order_count": order_count,
        "total_spend": round(float(total_spend), 2),
    }


def list_tenant_customers(
    db: DatabaseSession,
    tenant: Tenant,
    *,
    include_simulated: bool = False,
) -> list[dict]:
    stmt = select(User).where(
        User.tenant_id == tenant.id,
        User.email.is_not(None),
    )
    if not include_simulated:
        stmt = stmt.where(User.simulated.is_(False))

    users = db.scalars(stmt.order_by(User.created_at.desc())).all()
    if not users:
        return []

    user_ids = [u.id for u in users]
    order_stmt = select(Order).where(
        Order.tenant_id == tenant.id,
        Order.user_id.in_(user_ids),
    )
    if not include_simulated:
        order_stmt = order_stmt.where(Order.simulated.is_(False))

    orders = db.scalars(order_stmt.order_by(Order.created_at.desc())).all()

    orders_by_user: dict[str, list[Order]] = {uid: [] for uid in user_ids}
    for o in orders:
        orders_by_user.setdefault(o.user_id, []).append(o)

    result = []
    for u in users:
        user_orders = orders_by_user.get(u.id, [])
        paid_orders = [o for o in user_orders if is_paid_or_confirmed(o)]
        spend = sum(float(o.total) for o in paid_orders)
        result.append(serialize_customer_summary(u, len(user_orders), spend))

    return result


def get_tenant_customer(
    db: DatabaseSession,
    tenant: Tenant,
    customer_id: str,
    *,
    include_simulated: bool = False,
) -> dict:
    user = db.scalar(
        select(User).where(
            User.id == customer_id,
            User.tenant_id == tenant.id,
        )
    )
    if user is None:
        raise HTTPException(404, "Customer not found")

    order_stmt = select(Order).where(
        Order.tenant_id == tenant.id,
        Order.user_id == user.id,
    )
    if not include_simulated:
        order_stmt = order_stmt.where(Order.simulated.is_(False))

    orders = db.scalars(order_stmt.order_by(Order.created_at.desc())).all()

    paid_orders = [o for o in orders if is_paid_or_confirmed(o)]
    spend = sum(float(o.total) for o in paid_orders)
    order_summaries = [serialize_order_summary(o, tenant) for o in orders]

    profile = serialize_customer_summary(user, len(orders), spend)
    return {
        **profile,
        "customer": profile,
        "orders": order_summaries,
    }
