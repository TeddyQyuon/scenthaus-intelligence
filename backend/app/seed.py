"""One idempotent command initializes real catalog references + SIMULATED orders."""

import json
from pathlib import Path
from argon2 import PasswordHasher
from sqlalchemy import func, insert, select
from .config import settings
from .database import SessionLocal
from .models import (
    Product,
    Variant,
    User,
    QuizProfile,
    Order,
    OrderItem,
    Event,
    Wishlist,
    StockWeek,
)
from .catalog import seed_catalog
from ml.data.generate_orders import generate
import yaml


def insert_rows(db, model, rows: list[dict]) -> None:
    for offset in range(0, len(rows), 500):
        db.execute(insert(model.__table__).values(rows[offset : offset + 500]))


def seed() -> None:
    config = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "ml/configs/data.yaml").read_text()
    )
    with SessionLocal() as db:
        if db.scalar(select(func.count(Product.id))):
            print(
                "Catalog exists; idempotent seed skipped. Use a separate empty demo DB to change catalog versions."
            )
            return
        if len(settings.admin_password) < 12:
            raise ValueError("Set ADMIN_PASSWORD to at least 12 characters")
        seed_catalog(db)
        db.flush()
        products = db.scalars(select(Product).order_by(Product.id)).all()
        variants = db.scalars(select(Variant).order_by(Variant.id)).all()
        generated = generate(
            [
                {"id": p.id, "accords": p.accords, "launch_date": p.launch_date}
                for p in products
            ],
            [
                {"id": v.id, "product_id": v.product_id, "price": float(v.price)}
                for v in variants
            ],
            config,
        )
        for name, model in [
            ("users", User),
            ("quizzes", QuizProfile),
            ("orders", Order),
            ("lines", OrderItem),
            ("events", Event),
            ("wishes", Wishlist),
            ("stock_weeks", StockWeek),
        ]:
            insert_rows(db, model, generated[name])
            print(f"{name}: {len(generated[name])}", flush=True)
        db.add(
            User(
                email=settings.admin_email,
                password_hash=PasswordHasher().hash(settings.admin_password),
                role="admin",
            )
        )
        db.commit()
        result = {
            "simulated": True,
            "seed": config["seed"],
            "users": config["users"],
            "weeks": config["weeks"],
            "products": len(products),
            "brands": len({p.brand for p in products}),
            "skus": len(variants),
            **{k: len(v) for k, v in generated.items() if k != "users"},
        }
        settings.artifact_dir.mkdir(parents=True, exist_ok=True)
        (settings.artifact_dir / "dataset.json").write_text(
            json.dumps(result, indent=2)
        )
        print(json.dumps(result))


if __name__ == "__main__":
    seed()
