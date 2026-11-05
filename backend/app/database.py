from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from .config import settings

engine_options = {"pool_pre_ping": True}
if not settings.database_url.startswith("sqlite"):
    engine_options.update(pool_size=5, max_overflow=5)
engine = create_engine(settings.database_url, **engine_options)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


@event.listens_for(Session, "after_begin")
def restore_tenant_context(session, transaction, connection):
    # SET LOCAL expires at commit. Preserve the scope on the next transaction,
    # including after authentication updates last_seen_at or a service commits.
    tenant_id = session.info.get("tenant_id")
    if tenant_id and connection.dialect.name == "postgresql":
        connection.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": tenant_id}
        )


def get_db():
    with SessionLocal() as db:
        yield db


def sync_postgres_sequences(conn_or_session) -> None:
    """Ensure PostgreSQL sequences for tables with explicit seed IDs are in sync with MAX(id)."""
    from sqlalchemy import text

    bind = getattr(conn_or_session, "bind", conn_or_session)
    if bind is None and hasattr(conn_or_session, "get_bind"):
        bind = conn_or_session.get_bind()
    dialect = getattr(bind, "dialect", None)
    if dialect is None or dialect.name != "postgresql":
        return

    tables = [
        "products",
        "variants",
        "order_items",
        "events",
        "wishlists",
        "cart_items",
        "forecast_snapshots",
        "audit_logs",
    ]
    for table in tables:
        try:
            conn_or_session.execute(
                text(
                    f"SELECT setval("
                    f"pg_get_serial_sequence('{table}', 'id'), "
                    f'COALESCE((SELECT MAX(id) FROM "{table}"), 1), '
                    f'(SELECT MAX(id) IS NOT NULL FROM "{table}")'
                    f")"
                )
            )
        except Exception:
            pass
