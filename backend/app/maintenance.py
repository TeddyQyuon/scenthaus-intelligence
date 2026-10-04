from datetime import datetime, time, timedelta
from sqlalchemy import delete, select, func
from .database import SessionLocal
from .models import (
    Event,
    RecommendationRequest,
    Session,
    ForecastSnapshot,
    Order,
    OrderItem,
    Variant,
    now,
)
from .config import settings


def maintain():
    with SessionLocal() as db:
        cutoff = now() - timedelta(days=settings.retention_days)
        for model in [Event, RecommendationRequest]:
            db.execute(delete(model).where(model.created_at < cutoff))
        db.execute(delete(Session).where(Session.expires_at < now()))
        for row in db.scalars(
            select(ForecastSnapshot).where(
                ForecastSnapshot.target_week <= now().date() - timedelta(days=7),
                ForecastSnapshot.actual == None,
            )
        ):
            lo = datetime.combine(row.target_week, time())
            hi = lo + timedelta(days=7)
            row.actual = float(
                db.scalar(
                    select(func.coalesce(func.sum(OrderItem.quantity), 0))
                    .join(Order, OrderItem.order_id == Order.id)
                    .join(Variant, OrderItem.variant_id == Variant.id)
                    .where(
                        Variant.sku == row.sku,
                        Order.created_at >= lo,
                        Order.created_at < hi,
                    )
                )
            )
        db.commit()
