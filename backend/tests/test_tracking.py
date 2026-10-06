from datetime import date, datetime
from sqlalchemy import select, func
from app.database import SessionLocal
from app.models import ForecastSnapshot, Order, OrderItem, Variant
from app.maintenance import maintain


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


def test_bulk_reconciliation_preserves_boundaries_and_uses_bounded_queries():
    from sqlalchemy import event, delete
    from app.database import engine
    from app.models import User

    versions = [f"test-bulk-{i}" for i in range(256)]
    order_ids = []
    with SessionLocal() as db:
        variant = db.scalar(select(Variant).order_by(Variant.id))
        user = db.scalar(select(User))
        sku = variant.sku
        for when, quantity in [
            (datetime(2000, 1, 4), 2),
            (datetime(2000, 1, 10, 23, 59, 59), 3),
            (datetime(2000, 1, 11), 7),
        ]:
            order = Order(user_id=user.id, created_at=when, total=quantity, simulated=True)
            db.add(order)
            db.flush()
            db.add(OrderItem(order_id=order.id, variant_id=variant.id,
                             quantity=quantity, unit_price=1))
            order_ids.append(order.id)
        for i, version in enumerate(versions):
            db.add(ForecastSnapshot(version=version, sku=sku if i != 254 else "no-sales-fixture",
                                   origin=date(1999, 12, 28),
                                   target_week=date(2100, 1, 4) if i == 255 else date(2000, 1, 4),
                                   prediction=2, lower80=0, upper80=5, lower95=0, upper95=7,
                                   actual=99 if i == 253 else None))
        db.commit()
    statements = []
    def observe(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    try:
        event.listen(engine, "before_cursor_execute", observe)
        try:
            maintain()
        finally:
            event.remove(engine, "before_cursor_execute", observe)
        # Query volume must stay bounded as snapshots grow, avoiding network round trips per row.
        assert len(statements) <= 5
        with SessionLocal() as db:
            actuals = {r.version: r.actual for r in db.scalars(
                select(ForecastSnapshot).where(ForecastSnapshot.version.in_(versions)))}
        assert all(actuals[v] == 5 for v in versions[:253])
        assert actuals[versions[253]] == 99
        assert actuals[versions[254]] == 0
        assert actuals[versions[255]] is None
    finally:
        with SessionLocal() as db:
            db.execute(delete(ForecastSnapshot).where(ForecastSnapshot.version.in_(versions)))
            db.execute(delete(Order).where(Order.id.in_(order_ids)))
            db.commit()
