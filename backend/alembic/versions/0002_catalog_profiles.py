"""Real catalog source references, simulated quiz profiles and stockout history."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Inherited 0001 creates current metadata. Guards support fresh and 0001 DBs.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table, columns in {
        "products": [
            sa.Column("image_path", sa.String(500)),
            sa.Column("source_metadata", sa.JSON()),
        ],
        "users": [sa.Column("quiz_profile", sa.JSON())],
    }.items():
        existing = {c["name"] for c in inspector.get_columns(table)}
        for column in columns:
            if column.name not in existing:
                op.add_column(table, column)
    if "stock_weeks" not in inspector.get_table_names():
        op.create_table(
            "stock_weeks",
            sa.Column(
                "variant_id",
                sa.Integer(),
                sa.ForeignKey("variants.id"),
                primary_key=True,
            ),
            sa.Column("week", sa.Date(), primary_key=True),
            sa.Column("in_stock", sa.Boolean(), nullable=False),
        )
    for constraint in inspector.get_check_constraints("products"):
        if (
            "concentration" in constraint["sqltext"]
            and "Unverified" not in constraint["sqltext"]
        ):
            op.drop_constraint(constraint["name"], "products", type_="check")
            op.create_check_constraint(
                "product_concentration",
                "products",
                "concentration IN ('EDT','EDP','Parfum','Cologne','Unverified')",
            )


def downgrade() -> None:
    op.drop_table("stock_weeks")
    op.drop_column("users", "quiz_profile")
    op.drop_column("products", "image_path")
    op.drop_column("products", "source_metadata")
