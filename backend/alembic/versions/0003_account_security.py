"""Authenticator credentials, session metadata and account security history."""

from uuid import uuid4
from alembic import op
import sqlalchemy as sa
from app.models import SecurityEvent

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    # 0001 creates current metadata on a fresh database; also support upgrades.
    fields = {
        "users": [
            sa.Column("totp_secret", sa.String(512)),
            sa.Column("totp_last_counter", sa.Integer()),
            sa.Column(
                "recovery_code_hashes", sa.JSON(), nullable=False, server_default="[]"
            ),
            sa.Column("pending_totp_secret", sa.String(512)),
            sa.Column("pending_totp_expires_at", sa.DateTime()),
            sa.Column("pending_totp_session", sa.String(64)),
        ],
        "sessions": [
            sa.Column("public_id", sa.String(36)),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("last_seen_at", sa.DateTime()),
            sa.Column("ip_address", sa.String(45)),
            sa.Column("user_agent", sa.String(512)),
            sa.Column("location", sa.String(200)),
        ],
    }
    for table, columns in fields.items():
        existing = {column["name"] for column in inspector.get_columns(table)}
        for column in columns:
            if column.name not in existing:
                op.add_column(table, column)
    # Give old sessions opaque display IDs without fabricating their login times.
    for row in bind.execute(
        sa.text("SELECT token_hash FROM sessions WHERE public_id IS NULL")
    ):
        bind.execute(
            sa.text("UPDATE sessions SET public_id = :id WHERE token_hash = :token"),
            {"id": str(uuid4()), "token": row.token_hash},
        )
    op.alter_column("sessions", "public_id", nullable=False)
    uniques = sa.inspect(bind).get_unique_constraints("sessions")
    if not any(item["column_names"] == ["public_id"] for item in uniques):
        op.create_unique_constraint("uq_sessions_public_id", "sessions", ["public_id"])
    SecurityEvent.__table__.create(bind, checkfirst=True)


def downgrade() -> None:
    op.drop_table("security_events")
    op.drop_constraint("uq_sessions_public_id", "sessions", type_="unique")
    for column in [
        "public_id",
        "created_at",
        "last_seen_at",
        "ip_address",
        "user_agent",
        "location",
    ]:
        op.drop_column("sessions", column)
    for column in [
        "totp_secret",
        "totp_last_counter",
        "recovery_code_hashes",
        "pending_totp_secret",
        "pending_totp_expires_at",
        "pending_totp_session",
    ]:
        op.drop_column("users", column)
