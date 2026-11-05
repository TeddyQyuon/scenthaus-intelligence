"""Separate expiring DNS ownership claims from active domain mappings."""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    from app.models import TenantDomainChallenge

    bind = op.get_bind()
    TenantDomainChallenge.__table__.create(bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text("ALTER TABLE tenant_domain_challenges ENABLE ROW LEVEL SECURITY")
        )
        bind.execute(
            sa.text(
                "DROP POLICY IF EXISTS tenant_isolation_policy ON tenant_domain_challenges"
            )
        )
        bind.execute(
            sa.text("""
            CREATE POLICY tenant_isolation_policy ON tenant_domain_challenges
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
        """)
        )


def downgrade():
    from app.models import TenantDomainChallenge

    TenantDomainChallenge.__table__.drop(op.get_bind(), checkfirst=True)
