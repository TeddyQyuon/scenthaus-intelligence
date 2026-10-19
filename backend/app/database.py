from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import settings

engine = create_engine(
    settings.database_url, pool_pre_ping=True, pool_size=5, max_overflow=5
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


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
                    f"COALESCE((SELECT MAX(id) FROM \"{table}\"), 1), "
                    f"(SELECT MAX(id) IS NOT NULL FROM \"{table}\")"
                    f")"
                )
            )
        except Exception:
            pass
