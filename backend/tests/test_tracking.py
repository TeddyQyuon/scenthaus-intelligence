from datetime import date, datetime
from sqlalchemy import select, func
from app.database import SessionLocal
from app.models import ForecastSnapshot, Order, OrderItem, Variant
from app.worker import maintain


def test_saved_forecast_reconciles_completed_week(admin):
    with SessionLocal() as db:
        row = ForecastSnapshot(
            version="test-reconciliation",
            sku="SH-001-60",
            origin=date(2026, 7, 27),
            target_week=date(2026, 8, 3),
            prediction=2,
            lower80=0,
            upper80=5,
            lower95=0,
            upper95=7,
        )
        db.add(row)
        db.commit()
        rid = row.id
    try:
        maintain()
        with SessionLocal() as db:
            actual = db.scalar(
                select(func.coalesce(func.sum(OrderItem.quantity), 0))
                .join(Order, OrderItem.order_id == Order.id)
                .join(Variant, OrderItem.variant_id == Variant.id)
                .where(
                    Variant.sku == "SH-001-60",
                    Order.created_at >= datetime(2026, 8, 3),
                    Order.created_at < datetime(2026, 8, 10),
                )
            )
            assert db.get(ForecastSnapshot, rid).actual == actual
        rows = admin.get("/admin/tracking?sku=SH-001-60").json()["live"]
        assert any(
            r["version"] == "test-reconciliation" and r["actual"] == actual
            for r in rows
        )
        export = admin.get("/admin/export?kind=tracking")
        assert (
            export.status_code == 200
            and "live_snapshot" in export.text
            and "test-reconciliation" in export.text
        )
        assert "live_forecast_error" in admin.get("/admin/monitor").json()
    finally:
        with SessionLocal() as db:
            db.delete(db.get(ForecastSnapshot, rid))
            db.commit()
