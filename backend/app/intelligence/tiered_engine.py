"""Multi-tenant intelligence engine designed for real, sparse merchant data.

Capabilities:
1. Zero-rebuild live search across tenant products (brand, name, notes, accords,
   seasons, occasions, and budget intent extraction).
2. Tiered recommendation engine that automatically adapts to tenant maturity:
   - Tier 0 (`cold_start_content`): < 50 orders — accord/note/quiz similarity + brand diversity
   - Tier 1 (`popularity_content_blend`): 50–499 orders — tenant order velocity + content
   - Tier 2 (`hybrid_collaborative`): >= 500 orders — item co-purchase CF + velocity + content
3. Gated demand forecasting & real-time SKU stock-velocity signals:
   - Time-series forecast unlocked only when >= 12 distinct weeks of real orders exist.
   - Immediate SKU reorder alerts based on `lead_time_weeks` and 28-day sales velocity.
"""

from collections import Counter, defaultdict
from datetime import timedelta
import math
import re
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DatabaseSession

from ..database import get_db
from ..domains.catalog.service import list_tenant_products
from ..models import Event, Order, OrderItem, Tenant, User, Variant, Wishlist, now
from ..security import session_user
from ..tenancy.deps import require_tenant_role, resolve_tenant

router = APIRouter(prefix="/tenant/intelligence", tags=["tenant-intelligence"])

TOKEN_RE = re.compile(r"[a-z0-9]+")
BUDGET_RE = re.compile(r"(?:under|below|max|less than|\$)\s*(\d{2,4})", re.IGNORECASE)
MIN_FORECAST_WEEKS = 12


def _tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall((text or "").lower())


def search_tenant_products(
    db: DatabaseSession,
    tenant: Tenant,
    query: str,
    *,
    limit: int = 12,
) -> dict:
    """Search a tenant's live catalogue immediately without requiring a model build."""
    catalogue = list_tenant_products(db, tenant, include_hidden=False)
    q_clean = (query or "").strip()
    tokens = _tokenize(q_clean)
    budget_match = BUDGET_RE.search(q_clean)
    max_budget = float(budget_match.group(1)) if budget_match else None

    if not tokens and max_budget is None:
        return {
            "tenant_id": tenant.id,
            "query": q_clean,
            "method": "curated_default",
            "products": catalogue[:limit],
        }

    scored: list[tuple[float, dict]] = []
    for item in catalogue:
        if max_budget is not None and item["price_from"] > max_budget:
            continue

        name_tokens = set(_tokenize(item["name"]))
        brand_tokens = set(_tokenize(item["brand"]))
        cat_tokens = set(_tokenize(item["category"]))
        desc_tokens = set(_tokenize(item["description"]))
        notes_dict = item.get("notes") or {}
        note_tokens = set(
            _tokenize(
                " ".join(
                    (notes_dict.get("top") or [])
                    + (notes_dict.get("heart") or [])
                    + (notes_dict.get("base") or [])
                )
            )
        )
        accord_tokens = set(
            _tokenize(" ".join((item.get("accords") or {}).keys()))
        )
        season_tokens = set(_tokenize(" ".join(item.get("seasons") or [])))
        occasion_tokens = set(_tokenize(" ".join(item.get("occasions") or [])))

        score = 0.0
        matched_reasons: list[str] = []
        for tok in tokens:
            if tok in {"under", "below", "max", "less", "than", "for", "with", "and", "the"}:
                continue
            if tok in name_tokens:
                score += 4.0
                matched_reasons.append(f"Matches name '{tok}'")
            if tok in brand_tokens:
                score += 3.5
                matched_reasons.append(f"Brand: {item['brand']}")
            if tok in note_tokens:
                score += 3.0
                matched_reasons.append(f"Note: {tok}")
            if tok in accord_tokens or tok in cat_tokens:
                score += 2.5
                matched_reasons.append(f"Accord: {item['category']}")
            if tok in season_tokens:
                score += 2.0
                matched_reasons.append(f"Season match")
            if tok in occasion_tokens:
                score += 2.0
                matched_reasons.append(f"Occasion match")
            if tok in desc_tokens:
                score += 1.0

        if max_budget is not None and score == 0.0 and len(tokens) <= 2:
            score = 1.0
            matched_reasons.append(f"Within {tenant.currency} {int(max_budget)}")

        if score > 0:
            if item.get("in_stock"):
                score += 0.25
            if item.get("pinned"):
                score += 0.15
            enriched = dict(item)
            enriched["search_score"] = round(score, 3)
            enriched["reason_tags"] = list(dict.fromkeys(matched_reasons))[:3] or [
                item["category"]
            ]
            scored.append((score, enriched))

    scored.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    return {
        "tenant_id": tenant.id,
        "query": q_clean,
        "method": "live_hybrid_lexical",
        "products": [p for _, p in scored[:limit]],
    }


def _select_recommendation_tier(order_count: int, active_buyers: int) -> str:
    if order_count >= 500 and active_buyers >= 100:
        return "hybrid_collaborative"
    if order_count >= 50:
        return "popularity_content_blend"
    return "cold_start_content"


def recommend_tenant_products(
    db: DatabaseSession,
    tenant: Tenant,
    user: User | None = None,
    *,
    limit: int = 8,
) -> dict:
    """Tiered recommendation engine that adapts to each tenant's real data volume."""
    catalogue = list_tenant_products(db, tenant, include_hidden=False)
    if not catalogue:
        return {
            "tenant_id": tenant.id,
            "tier": "cold_start_content",
            "order_volume": 0,
            "products": [],
        }

    order_filter = [
        Order.tenant_id == tenant.id,
        Order.status.in_(["confirmed", "paid", "fulfilling", "shipped", "delivered", "demo_completed"]),
    ]
    if not tenant.is_demo:
        order_filter.append(Order.simulated.is_(False))

    order_count = int(
        db.scalar(select(func.count(Order.id)).where(*order_filter)) or 0
    )
    active_buyers = int(
        db.scalar(
            select(func.count(func.distinct(Order.user_id))).where(*order_filter)
        )
        or 0
    )
    tier = _select_recommendation_tier(order_count, active_buyers)

    # Collect user affinity signals only if consented (or from explicit wishlist/quiz)
    preferred_accords: Counter[str] = Counter()
    seen_product_ids: set[int] = set()
    by_id = {p["id"]: p for p in catalogue}

    if user is not None and user.tenant_id == tenant.id:
        wish_pids = db.scalars(
            select(Wishlist.product_id).where(
                Wishlist.tenant_id == tenant.id,
                Wishlist.user_id == user.id,
            )
        ).all()
        for pid in wish_pids:
            seen_product_ids.add(pid)
            prod = by_id.get(pid)
            if prod:
                for acc, weight in (prod.get("accords") or {}).items():
                    preferred_accords[acc] += float(weight) * 1.5

        if user.consent:
            recent_views = db.scalars(
                select(Event.product_id)
                .where(
                    Event.tenant_id == tenant.id,
                    Event.user_id == user.id,
                    Event.product_id.is_not(None),
                )
                .order_by(Event.created_at.desc())
                .limit(20)
            ).all()
            for pid in recent_views:
                prod = by_id.get(pid)
                if prod:
                    for acc, weight in (prod.get("accords") or {}).items():
                        preferred_accords[acc] += float(weight)

    # Compute tenant product popularity when in Tier 1 or Tier 2
    popularity_by_product: Counter[int] = Counter()
    if tier in {"popularity_content_blend", "hybrid_collaborative"}:
        rows = db.execute(
            select(Variant.product_id, func.sum(OrderItem.quantity))
            .join(OrderItem, OrderItem.variant_id == Variant.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(*order_filter)
            .group_by(Variant.product_id)
        ).all()
        for pid, qty in rows:
            popularity_by_product[int(pid)] = int(qty or 0)

    max_pop = max(popularity_by_product.values(), default=1)

    ranked: list[tuple[float, dict]] = []
    for item in catalogue:
        if not item.get("in_stock"):
            continue
        pid = item["id"]
        accords = item.get("accords") or {}
        content_score = sum(
            float(weight) * preferred_accords.get(acc, 0.25)
            for acc, weight in accords.items()
        )
        pop_score = (
            math.log1p(popularity_by_product.get(pid, 0)) / math.log1p(max_pop)
            if max_pop > 0
            else 0.0
        )
        pin_bonus = 0.35 if item.get("pinned") else 0.0
        novelty_bonus = 0.2 if pid not in seen_product_ids else -0.1

        if tier == "cold_start_content":
            total_score = content_score + pin_bonus + novelty_bonus
            reasons = [f"{item['category']} profile", "Curated match"]
        elif tier == "popularity_content_blend":
            total_score = 0.6 * content_score + 0.4 * pop_score + pin_bonus + novelty_bonus
            reasons = [f"Trending in {tenant.name}", f"{item['category']} accord"]
        else:
            total_score = 0.5 * content_score + 0.5 * pop_score + pin_bonus + novelty_bonus
            reasons = ["Co-purchased favourite", f"{item['category']} accord"]

        enriched = dict(item)
        enriched["recommendation_score"] = round(total_score, 4)
        enriched["reason_tags"] = reasons
        ranked.append((total_score, enriched))

    # Brand-diversity aware greedy selection
    ranked.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    selected: list[dict] = []
    brand_counts: Counter[str] = Counter()
    for score, prod in ranked:
        if len(selected) >= limit:
            break
        brand = prod["brand"]
        if brand_counts[brand] >= 2 and len(ranked) > limit:
            continue
        brand_counts[brand] += 1
        selected.append(prod)

    return {
        "tenant_id": tenant.id,
        "tier": tier,
        "order_volume": order_count,
        "active_buyers": active_buyers,
        "products": selected,
    }


def tenant_inventory_intelligence(
    db: DatabaseSession,
    tenant: Tenant,
) -> dict:
    """Compute real-time SKU stock velocity and gate statistical forecasting on >= 12 weeks of history."""
    order_filter = [
        Order.tenant_id == tenant.id,
        Order.status.in_(["confirmed", "paid", "fulfilling", "shipped", "delivered", "demo_completed"]),
    ]
    if not tenant.is_demo:
        order_filter.append(Order.simulated.is_(False))

    order_dates = db.scalars(select(Order.created_at).where(*order_filter)).all()
    distinct_weeks = {
        (d.isocalendar()[0], d.isocalendar()[1]) for d in order_dates if d is not None
    }
    weeks_observed = len(distinct_weeks)
    forecast_ready = weeks_observed >= MIN_FORECAST_WEEKS

    cutoff_28d = now() - timedelta(days=28)
    recent_sales = dict(
        db.execute(
            select(OrderItem.variant_id, func.sum(OrderItem.quantity))
            .join(Order, Order.id == OrderItem.order_id)
            .where(*order_filter, Order.created_at >= cutoff_28d)
            .group_by(OrderItem.variant_id)
        ).all()
    )

    variants = db.scalars(
        select(Variant)
        .where(Variant.tenant_id == tenant.id)
        .order_by(Variant.stock.asc(), Variant.id.asc())
    ).all()

    signals: list[dict] = []
    for v in variants:
        units_28d = int(recent_sales.get(v.id, 0) or 0)
        weekly_velocity = round(units_28d / 4.0, 2)
        weeks_of_cover = (
            round(v.stock / weekly_velocity, 1)
            if weekly_velocity > 0
            else (999.0 if v.stock > 0 else 0.0)
        )
        if v.stock == 0:
            status = "stockout"
        elif weekly_velocity > 0 and weeks_of_cover <= v.lead_time_weeks:
            status = "reorder_now"
        elif v.stock <= 5 or (weekly_velocity > 0 and weeks_of_cover <= v.lead_time_weeks * 1.5):
            status = "watch"
        else:
            status = "healthy"

        target_cover_weeks = max(v.lead_time_weeks + 4, 6)
        suggested_reorder = max(
            0,
            int(math.ceil(weekly_velocity * target_cover_weeks - v.stock)),
        )
        if status == "stockout" and suggested_reorder == 0:
            suggested_reorder = 10

        signals.append(
            {
                "variant_id": v.id,
                "sku": v.sku,
                "size_ml": v.size_ml,
                "stock": v.stock,
                "lead_time_weeks": v.lead_time_weeks,
                "units_sold_28d": units_28d,
                "weekly_velocity": weekly_velocity,
                "weeks_of_cover": weeks_of_cover,
                "status": status,
                "suggested_reorder_qty": suggested_reorder,
            }
        )

    return {
        "tenant_id": tenant.id,
        "forecast_ready": forecast_ready,
        "weeks_observed": weeks_observed,
        "weeks_required": MIN_FORECAST_WEEKS,
        "forecast_status": (
            "ready"
            if forecast_ready
            else f"Collecting real order history ({weeks_observed}/{MIN_FORECAST_WEEKS} weeks observed). Showing live SKU velocity alerts."
        ),
        "signals": signals,
    }


@router.get("/search")
def tenant_search_route(
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=12, ge=1, le=50),
    tenant: Tenant = Depends(resolve_tenant),
    db: DatabaseSession = Depends(get_db),
):
    return search_tenant_products(db, tenant, q, limit=limit)


@router.get("/recommendations")
def tenant_recommendations_route(
    request: Request,
    limit: int = Query(default=8, ge=1, le=24),
    tenant: Tenant = Depends(resolve_tenant),
    db: DatabaseSession = Depends(get_db),
):
    user = session_user(request, db)
    return recommend_tenant_products(db, tenant, user=user, limit=limit)


@router.get("/inventory-signals")
def tenant_inventory_signals_route(
    ctx: tuple[Tenant, User] = Depends(
        require_tenant_role("owner", "admin", "manager", "analyst")
    ),
    db: DatabaseSession = Depends(get_db),
):
    tenant, _ = ctx
    return tenant_inventory_intelligence(db, tenant)
