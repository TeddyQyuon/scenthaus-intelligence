from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select, func, or_
from .models import Order, OrderItem, Variant, Product, Event, User


def date_range(start=None, end=None):
    try:
        lo = datetime.fromisoformat(start) if start else datetime(2024, 9, 30)
        hi = (
            datetime.fromisoformat(end) + timedelta(days=1)
            if end
            else datetime.now(__import__("datetime").timezone.utc).replace(tzinfo=None)
            + timedelta(days=1)
        )
    except ValueError:
        raise ValueError("Use ISO dates YYYY-MM-DD")
    if lo >= hi:
        raise ValueError("Start must precede end")
    return lo, hi


def overview(db, start=None, end=None):
    lo, hi = date_range(start, end)
    orders = db.scalars(
        select(Order).where(Order.created_at >= lo, Order.created_at < hi, or_(Order.payment_status.is_(None), Order.payment_status == "paid"))
    ).all()
    ids = [o.id for o in orders]
    line_rows = (
        db.execute(
            select(OrderItem, Variant, Product)
            .join(Variant, OrderItem.variant_id == Variant.id)
            .join(Product, Variant.product_id == Product.id)
            .where(OrderItem.order_id.in_(ids))
        ).all()
        if ids
        else []
    )
    revenue = sum(float(o.total) for o in orders)
    counts = defaultdict(int)
    brands = defaultdict(float)
    sizes = defaultdict(int)
    products = defaultdict(lambda: {"units": 0, "revenue": 0})
    weekly = defaultdict(float)
    for o in orders:
        counts[o.user_id] += 1
        weekly[
            (o.created_at - timedelta(days=o.created_at.weekday())).date().isoformat()
        ] += float(o.total)
    for line, v, p in line_rows:
        amount = float(line.unit_price) * line.quantity
        brands[p.brand] += amount
        sizes[v.size_ml] += line.quantity
        products[p.name]["units"] += line.quantity
        products[p.name]["revenue"] += amount
    events = db.scalars(
        select(Event).where(Event.created_at >= lo, Event.created_at < hi)
    ).all()
    viewusers = {e.user_id for e in events if e.event_type == "view"}
    converted = viewusers & set(counts)
    slots = defaultdict(
        lambda: {
            "impressions": 0,
            "clicks": 0,
            "add_to_cart": 0,
            "attributed_revenue": 0,
        }
    )
    for e in events:
        if e.slot and e.event_type in ["impression", "click", "add_to_cart"]:
            slots[e.slot][
                {
                    "impression": "impressions",
                    "click": "clicks",
                    "add_to_cart": "add_to_cart",
                }[e.event_type]
            ] += 1
    # Last valid recommendation click within seven days; one credit per purchased line.
    clicks = [
        e for e in events if e.event_type == "click" and e.slot and e.recommendation_id
    ]
    ordermap = {o.id: o for o in orders}
    for line, v, p in line_rows:
        o = ordermap[line.order_id]
        matches = [
            c
            for c in clicks
            if c.user_id == o.user_id
            and c.product_id == p.id
            and timedelta(0) <= o.created_at - c.created_at <= timedelta(days=7)
        ]
        if matches:
            slots[max(matches, key=lambda c: c.created_at).slot][
                "attributed_revenue"
            ] += float(line.unit_price) * line.quantity
    performance = [
        {
            "slot": key,
            **s,
            "ctr": s["clicks"] / s["impressions"] if s["impressions"] else 0,
            "add_to_cart_rate": s["add_to_cart"] / s["impressions"]
            if s["impressions"]
            else 0,
        }
        for key, s in slots.items()
    ]
    return {
        "simulated_data": True,
        "date_range": [
            lo.date().isoformat(),
            (hi - timedelta(days=1)).date().isoformat(),
        ],
        "kpis": {
            "revenue": revenue,
            "orders": len(orders),
            "aov": revenue / len(orders) if orders else 0,
            "conversion": len(converted) / len(viewusers) if viewusers else 0,
            "repeat_rate": sum(c > 1 for c in counts.values()) / len(counts)
            if counts
            else 0,
        },
        "weekly": [
            {"week": week, "revenue": value} for week, value in sorted(weekly.items())
        ],
        "brands": [
            {"brand": k, "revenue": v}
            for k, v in sorted(brands.items(), key=lambda t: -t[1])
        ],
        "size_mix": [{"size_ml": k, "units": v} for k, v in sizes.items()],
        "top_products": [
            {"name": k, **v}
            for k, v in sorted(products.items(), key=lambda t: -t[1]["revenue"])[:10]
        ],
        "performance": performance,
        "attribution": "Last valid click within 7 days; consented tracked sessions only. Conversion is observed view-user conversion, not all visitors.",
    }


def segments(db):
    orders = db.execute(
        select(
            Order.user_id,
            func.max(Order.created_at),
            func.count(Order.id),
            func.sum(Order.total),
        )
        .join(User, Order.user_id == User.id)
        .where(User.consent == True, or_(Order.payment_status.is_(None), Order.payment_status == "paid"))
        .group_by(Order.user_id)
    ).all()
    if len(orders) < 3:
        return {"segments": [], "note": "At least three consenting purchasers required"}
    end = max(r[1] for r in orders)
    x = np.array([[(end - r[1]).days + 1, r[2], float(r[3])] for r in orders])
    labels = KMeans(n_clusters=3, n_init=10, random_state=42).fit_predict(
        StandardScaler().fit_transform(np.log1p(x))
    )
    stats = [
        {
            "cluster": i,
            "customers": int(sum(labels == i)),
            "recency_days": float(x[labels == i, 0].mean()),
            "orders": float(x[labels == i, 1].mean()),
            "spend": float(x[labels == i, 2].mean()),
            "aov": float(np.mean(x[labels == i, 2] / x[labels == i, 1])),
        }
        for i in range(3)
    ]
    loyal = max(stats, key=lambda s: s["orders"])
    rest = [s for s in stats if s is not loyal]
    gift = max(rest, key=lambda s: s["aov"])
    for s in stats:
        s["label"] = (
            "Loyalists"
            if s is loyal
            else "Gift buyers"
            if s is gift
            else "Deal seekers"
        )
    return {
        "segments": stats,
        "note": "RFM + K-Means clusters. Labels are human interpretations of frequency and basket value, not known customer motivations.",
    }
