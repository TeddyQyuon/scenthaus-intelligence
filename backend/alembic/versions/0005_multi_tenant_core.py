"""Multi-tenant core schema, tenant domains, memberships, job queue, and Postgres RLS policies."""

from alembic import op
import sqlalchemy as sa
from app.models import BackgroundJob, Membership, Tenant, TenantDomain
from app.tenancy.constants import (
    DEFAULT_TENANT_ID,
    DEFAULT_TENANT_NAME,
    DEFAULT_TENANT_SLUG,
)

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

TENANT_TABLES = [
    "products",
    "variants",
    "users",
    "wishlists",
    "cart_items",
    "events",
    "recommendation_requests",
    "orders",
    "model_runs",
    "forecast_snapshots",
    "audit_logs",
    "background_jobs",
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for model in (Tenant, TenantDomain, Membership, BackgroundJob):
        model.__table__.create(bind, checkfirst=True)

    bind.execute(
        sa.text(
            "INSERT INTO tenants (id, slug, name, status, plan, currency, country, "
            "stripe_charges_enabled, stripe_payouts_enabled, application_fee_bps, "
            "settings_json, is_demo, created_at) "
            "VALUES (:id, :slug, :name, 'active', 'enterprise', 'SGD', 'SG', "
            "false, false, 250, '{}', true, CURRENT_TIMESTAMP) "
            "ON CONFLICT (id) DO NOTHING"
        ),
        {
            "id": DEFAULT_TENANT_ID,
            "slug": DEFAULT_TENANT_SLUG,
            "name": DEFAULT_TENANT_NAME,
        },
    )

    for table in TENANT_TABLES:
        existing_cols = {c["name"] for c in inspector.get_columns(table)}
        if "tenant_id" not in existing_cols:
            op.add_column(
                table,
                sa.Column(
                    "tenant_id",
                    sa.String(36),
                    sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                    nullable=False,
                    server_default=DEFAULT_TENANT_ID,
                ),
            )
            op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])

    # Replace single-tenant unique constraints with tenant-scoped unique constraints
    for table, col, uq_name in [
        ("products", "slug", "uq_products_tenant_slug"),
        ("variants", "sku", "uq_variants_tenant_sku"),
        ("users", "email", "uq_users_tenant_email"),
    ]:
        uniques = inspector.get_unique_constraints(table)
        for u in uniques:
            if u["column_names"] == [col] and u.get("name"):
                op.drop_constraint(u["name"], table, type_="unique")
        if not any(u["column_names"] == ["tenant_id", col] for u in uniques):
            op.create_unique_constraint(uq_name, table, ["tenant_id", col])

    # Enable Row-Level Security (RLS) on PostgreSQL
    if bind.dialect.name == "postgresql":
        policy_expr = (
            f"tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), "
            f"'{DEFAULT_TENANT_ID}')"
        )
        for table in TENANT_TABLES:
            bind.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            bind.execute(
                sa.text(
                    f'DROP POLICY IF EXISTS tenant_isolation_policy ON "{table}"'
                )
            )
            bind.execute(
                sa.text(
                    f'CREATE POLICY tenant_isolation_policy ON "{table}" '
                    f"USING ({policy_expr}) WITH CHECK ({policy_expr})"
                )
            )

        for seq_table in [
            "products",
            "variants",
            "order_items",
            "events",
            "wishlists",
            "cart_items",
            "forecast_snapshots",
            "audit_logs",
        ]:
            try:
                bind.execute(
                    sa.text(
                        f"SELECT setval("
                        f"pg_get_serial_sequence('{seq_table}', 'id'), "
                        f"COALESCE((SELECT MAX(id) FROM \"{seq_table}\"), 1), "
                        f"(SELECT MAX(id) IS NOT NULL FROM \"{seq_table}\")"
                        f")"
                    )
                )
            except Exception:
                pass


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in TENANT_TABLES:
            bind.execute(
                sa.text(
                    f'DROP POLICY IF EXISTS tenant_isolation_policy ON "{table}"'
                )
            )
            bind.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))

    for table in TENANT_TABLES:
        if table != "background_jobs":
            op.drop_column(table, "tenant_id")

    op.drop_table("background_jobs")
    op.drop_table("memberships")
    op.drop_table("tenant_domains")
    op.drop_table("tenants")
