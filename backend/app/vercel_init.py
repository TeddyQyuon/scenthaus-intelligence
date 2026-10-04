"""Initialize the dedicated cloud database during a Vercel build.

No training or filesystem mutation happens inside a request handler. A PostgreSQL
advisory lock serializes concurrent deployment builds; initialization never
replaces existing users, orders or catalogue edits.
"""

from datetime import datetime
from pathlib import Path
import os
from alembic import command
from alembic.config import Config
from sqlalchemy import text, create_engine
from .database import engine, SessionLocal
from .models import ModelRun, ForecastSnapshot
from .seed import seed
from .ml.serving import store


def initialize():
    if os.environ.get("VERCEL") and not os.environ.get("DATABASE_URL"):
        raise RuntimeError(
            "Set the dedicated cloud PostgreSQL DATABASE_URL before deploying SCENTHAUS"
        )
    root = Path(__file__).resolve().parents[1]
    model = store.get()
    if model is None:
        raise RuntimeError(
            "A verified trained model bundle must be committed before deployment"
        )
    # A session-level lock needs a direct connection, never a transaction pooler.
    direct_url = os.environ.get("DATABASE_URL_UNPOOLED", "")
    if direct_url.startswith(("postgres://", "postgresql://")):
        direct_url = "postgresql+psycopg://" + direct_url.split("://", 1)[1]
    lock_engine = create_engine(direct_url) if direct_url else engine
    with lock_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as lock:
        lock.execute(text("SELECT pg_advisory_lock(736284105)"))
        try:
            print("Migrating dedicated PostgreSQL schema", flush=True)
            config = Config(str(root / "alembic.ini"))
            config.set_main_option("script_location", str(root / "alembic"))
            command.upgrade(config, "head")
            seed()
            with SessionLocal() as db:
                version = model["version"]
                if not db.get(ModelRun, version):
                    db.add(
                        ModelRun(
                            version=version,
                            metrics=model["metrics"],
                            data_hash=model["metrics"]["validation"]["data_hash"],
                        )
                    )
                    for series in model["forecast"]["series"]:
                        origin = datetime.fromisoformat(
                            series["history"][-1]["week"]
                        ).date()
                        for row in series["forecast"]:
                            db.add(
                                ForecastSnapshot(
                                    version=version,
                                    sku=series["sku"],
                                    origin=origin,
                                    target_week=datetime.fromisoformat(
                                        row["week"]
                                    ).date(),
                                    **{
                                        key: row[key]
                                        for key in [
                                            "prediction",
                                            "lower80",
                                            "upper80",
                                            "lower95",
                                            "upper95",
                                        ]
                                    },
                                )
                            )
                    db.commit()
            print(
                "Database initialized; bundled model registered. Historical orders are simulated."
            )
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(736284105)"))


if __name__ == "__main__":
    initialize()
