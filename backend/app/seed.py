"""Reproducible, deliberately simulated commerce history. No real customers."""

import json
from datetime import datetime, timedelta
from uuid import uuid5, NAMESPACE_URL
import numpy as np
from sqlalchemy import select, func, insert
from argon2 import PasswordHasher
from .database import SessionLocal
from .models import User, Product, Variant, Order, OrderItem, Event, Wishlist
from .catalog import ACCORDS, seed_catalog
from .ml.calendar import features
from .config import settings


def stable(s):
    return str(uuid5(NAMESPACE_URL, "scenthaus/" + s))


def insert_rows(db, model, rows):
    """Bound SQL batches avoid one network round trip per simulated order."""
    for offset in range(0, len(rows), 1000):
        db.execute(insert(model.__table__).values(rows[offset : offset + 1000]))


def seed():
    rng = np.random.default_rng(42)
    with SessionLocal() as db:
        if db.scalar(select(func.count(Product.id))):
            print("Catalogue exists; seed is idempotent.")
            return
        if len(settings.admin_password) < 12:
            raise ValueError(
                "Set ADMIN_PASSWORD to at least 12 characters before seeding"
            )
        seed_catalog(db)
        db.flush()
        users = [
            User(
                id=stable(f"user/{i}"),
                simulated=True,
                consent=True,
                created_at=datetime(2024, 9, 1),
            )
            for i in range(2000)
        ]
        db.add_all(users)
        db.add(
            User(
                email=settings.admin_email,
                password_hash=PasswordHasher().hash(settings.admin_password),
                role="admin",
            )
        )
        db.flush()
        tastes = rng.dirichlet(np.full(8, 0.35), 2000)
        budgets = rng.uniform(80, 210, 2000)
        loyalty = rng.lognormal(0, 0.65, 2000)
        loyalty /= loyalty.sum()
        products = db.scalars(select(Product).order_by(Product.id)).all()
        variants = db.scalars(select(Variant).order_by(Variant.id)).all()
        vectors = np.array([[int(a in p.accords) for a in ACCORDS] for p in products])
        prices = np.array([float(variants[i * 3 + 1].price) for i in range(36)])
        wishset = set()
        order_count = 0
        event_count = 0
        order_rows, line_rows, event_rows, wishlist_rows = [], [], [], []
        for week in range(104):
            start = datetime(2024, 9, 30) + timedelta(weeks=week)
            calendar = features(start)
            count = rng.poisson(
                (75 + week * 0.35)
                * (
                    1
                    + sum(calendar[2:6]) * 0.8
                    + calendar[6] * 0.65
                    + calendar[7] * 0.45
                )
            )
            for n in range(count):
                u = int(rng.choice(2000, p=loyalty))
                when = start + timedelta(
                    days=int(rng.integers(0, 7)), hours=int(rng.integers(8, 23))
                )
                score = np.exp(
                    tastes[u] @ vectors.T * 8 - prices / budgets[u] * 0.65
                ) * (1 + 0.15 * np.sin(week / 11 + np.arange(36) / 3))
                score *= np.array(
                    [float(p.launch_date <= when.date()) for p in products]
                )
                score /= score.sum()
                k = int(rng.choice([1, 2, 3], p=[0.72, 0.24, 0.04]))
                chosen = list(rng.choice(36, size=k, replace=False, p=score))
                if k > 1 and rng.random() < 0.3:
                    companion = (int(chosen[0]) + 3) % 32
                    if companion not in chosen:
                        chosen[-1] = companion
                order_id = stable(f"order/{week}/{n}")
                lines = []
                total = 0
                for pi in chosen:
                    variant = variants[
                        int(pi) * 3 + int(rng.choice(3, p=[0.3, 0.5, 0.2]))
                    ]
                    qty = 2 if rng.random() < 0.07 else 1
                    price = round(
                        float(variant.price) * (0.82 if calendar[6] else 1), 2
                    )
                    total += qty * price
                    lines.append(
                        dict(
                            order_id=order_id,
                            variant_id=variant.id,
                            quantity=qty,
                            unit_price=price,
                        )
                    )
                order_rows.append(
                    dict(
                        id=order_id,
                        user_id=users[u].id,
                        created_at=when,
                        total=round(total, 2),
                        status="simulated",
                        simulated=True,
                    )
                )
                line_rows.extend(lines)
                for pi in chosen:
                    for et in ["view", "add_to_cart", "purchase"]:
                        event_rows.append(
                            dict(
                                user_id=users[u].id,
                                product_id=int(pi) + 1,
                                event_type=et,
                                created_at=when,
                            )
                        )
                        event_count += 1
                    pair = (u, int(pi) + 1)
                    if rng.random() < 0.28 and pair not in wishset:
                        wishlist_rows.append(
                            dict(
                                user_id=users[u].id, product_id=pair[1], created_at=when
                            )
                        )
                        wishset.add(pair)
                for pi in rng.choice(32, size=int(rng.integers(2, 6)), replace=False):
                    event_rows.append(
                        dict(
                            user_id=users[u].id,
                            product_id=int(pi) + 1,
                            event_type="view",
                            created_at=when,
                        )
                    )
                    event_count += 1
                order_count += 1
        for model, rows in [
            (Order, order_rows),
            (OrderItem, line_rows),
            (Event, event_rows),
            (Wishlist, wishlist_rows),
        ]:
            print(f"Initializing {model.__tablename__}: {len(rows)} rows", flush=True)
            insert_rows(db, model, rows)
        db.commit()
        result = {
            "simulated": True,
            "users": 2000,
            "orders": order_count,
            "events": event_count,
            "weeks": 104,
            "products": 36,
            "skus": 108,
            "seed": 42,
            "period": ["2024-09-30", "2026-09-27"],
        }
        settings.artifact_dir.mkdir(exist_ok=True, parents=True)
        (settings.artifact_dir / "dataset.json").write_text(
            json.dumps(result, indent=2)
        )
        print(json.dumps(result))


if __name__ == "__main__":
    seed()
