"""Add payment snapshots and verified Stripe order state without rewriting history."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    existing = {column["name"] for column in inspector.get_columns("orders")}
    columns = [
        ("order_number", sa.String(32)), ("customer_name", sa.String(120)),
        ("customer_email", sa.String(254)), ("customer_phone", sa.String(24)),
        ("delivery_address", sa.JSON()), ("subtotal_minor", sa.Integer()),
        ("shipping_minor", sa.Integer()), ("discount_minor", sa.Integer()),
        ("tax_minor", sa.Integer()), ("total_minor", sa.Integer()),
        ("currency", sa.String(3)), ("payment_status", sa.String(20)),
        ("stripe_session_id", sa.String(255)),
        ("stripe_payment_intent_id", sa.String(255)),
        ("stripe_checkout_url", sa.String(2048)),
        ("checkout_fingerprint", sa.String(64)), ("payment_mode", sa.String(4)),
        ("expires_at", sa.DateTime()), ("paid_at", sa.DateTime()),
    ]
    for name, kind in columns:
        if name not in existing:
            op.add_column("orders", sa.Column(name, kind))
    if "stock_reserved" not in existing:
        op.add_column("orders", sa.Column("stock_reserved", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "updated_at" not in existing:
        op.add_column("orders", sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    if "refunded_minor" not in existing:
        op.add_column("orders", sa.Column("refunded_minor", sa.Integer(), nullable=False, server_default="0"))
    for name in ("order_number", "stripe_session_id", "stripe_payment_intent_id"):
        if not any(u["column_names"] == [name] for u in inspector.get_unique_constraints("orders")):
            op.create_unique_constraint("uq_orders_" + name, "orders", [name])
    if "product_snapshot" not in {c["name"] for c in inspector.get_columns("order_items")}:
        op.add_column("order_items", sa.Column("product_snapshot", sa.JSON()))
    if not inspector.has_table("order_number_counters"):
        op.create_table("order_number_counters", sa.Column("year", sa.Integer(), primary_key=True), sa.Column("value", sa.Integer(), nullable=False))
    if not inspector.has_table("stripe_webhook_events"):
        op.create_table("stripe_webhook_events",
                    sa.Column("id", sa.String(255), primary_key=True),
                    sa.Column("event_type", sa.String(100), nullable=False),
                    sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
                    sa.Column("created_at", sa.DateTime(), nullable=False))


def downgrade():
    op.drop_table("stripe_webhook_events")
    op.drop_table("order_number_counters")
    op.drop_column("order_items", "product_snapshot")
    for name in ("order_number", "stripe_session_id", "stripe_payment_intent_id"):
        for constraint in sa.inspect(op.get_bind()).get_unique_constraints("orders"):
            if constraint["column_names"] == [name]:
                op.drop_constraint(constraint["name"], "orders", type_="unique")
    for name in ("order_number", "customer_name", "customer_email", "customer_phone", "delivery_address", "subtotal_minor", "shipping_minor", "discount_minor", "tax_minor", "total_minor", "currency", "payment_status", "stripe_session_id", "stripe_payment_intent_id", "stripe_checkout_url", "checkout_fingerprint", "payment_mode", "expires_at", "paid_at", "stock_reserved", "updated_at", "refunded_minor"):
        op.drop_column("orders", name)
