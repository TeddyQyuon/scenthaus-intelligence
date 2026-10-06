from datetime import timedelta
from sqlalchemy import delete, text
from .database import SessionLocal
from .models import Event, RecommendationRequest, Session, now
from .config import settings


def maintain():
    with SessionLocal() as db:
        cutoff = now() - timedelta(days=settings.retention_days)
        for model in [Event, RecommendationRequest]:
            db.execute(delete(model).where(model.created_at < cutoff))
        db.execute(delete(Session).where(Session.expires_at < now()))
        # Aggregate sales once and reconcile every due snapshot in one statement.
        # Daily buckets preserve each snapshot's inclusive/exclusive seven-day window,
        # including snapshots whose start date is not a Monday.
        db.execute(text("""
            WITH due AS (
                SELECT DISTINCT sku, target_week
                FROM forecast_snapshots
                WHERE actual IS NULL AND target_week <= :completed_week
            ), daily_sales AS (
                SELECT v.sku, CAST(o.created_at AS DATE) AS sale_day,
                       SUM(oi.quantity) AS quantity
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                JOIN variants v ON v.id = oi.variant_id
                GROUP BY v.sku, CAST(o.created_at AS DATE)
            ), totals AS (
                SELECT due.sku, due.target_week,
                       COALESCE(SUM(s.quantity), 0) AS actual
                FROM due
                LEFT JOIN daily_sales s ON s.sku = due.sku
                    AND s.sale_day >= due.target_week
                    AND s.sale_day < due.target_week + 7
                GROUP BY due.sku, due.target_week
            )
            UPDATE forecast_snapshots f SET actual = totals.actual
            FROM totals
            WHERE f.sku = totals.sku AND f.target_week = totals.target_week
              AND f.actual IS NULL
        """), {"completed_week": now().date() - timedelta(days=7)})
        db.commit()
