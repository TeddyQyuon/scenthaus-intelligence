"""Seeded synthetic behaviour, not real customer demand or authenticity evidence."""

from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, uuid5
from collections import defaultdict
import numpy as np
from app.catalog import ACCORDS
from app.ml.calendar import features


def stable(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, "scenthaus-v2/" + value))


def generate(products: list[dict], variants: list[dict], config: dict) -> dict:
    rng = np.random.default_rng(config["seed"])
    count = int(config["users"])
    start = datetime.fromisoformat(config["start"])
    tastes = rng.dirichlet(np.full(8, 0.4), count)  # hidden; never exported
    budgets = rng.uniform(120, 380, count)
    loyalty = rng.lognormal(0, 0.65, count)
    loyalty /= loyalty.sum()
    ids = np.array([p["id"] for p in products])
    vectors = np.array([[int(a in p["accords"]) for a in ACCORDS] for p in products])
    by_product = defaultdict(list)
    for v in variants:
        by_product[v["product_id"]].append(v)
    prices = np.array([min(v["price"] for v in by_product[p["id"]]) for p in products])
    users, quizzes, orders, lines, events, wishes, stock_weeks = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    for i in range(count):
        uid = stable(f"user/{i}")
        profile = None
        if rng.random() < config["quiz_fraction"]:
            noisy = np.maximum(0, tastes[i] + rng.normal(0, 0.15, 8))
            noisy /= noisy.sum()
            profile = dict(zip(ACCORDS, map(float, noisy)))
            quizzes.append(
                {
                    "user_id": uid,
                    "answers": {"simulated": True},
                    "weights": profile,
                    "created_at": start - timedelta(days=1),
                }
            )
            events.append(
                {
                    "user_id": uid,
                    "product_id": None,
                    "event_type": "quiz_submit",
                    "created_at": start - timedelta(days=1),
                }
            )
        users.append(
            {
                "id": uid,
                "simulated": True,
                "consent": True,
                "quiz_profile": profile,
                "created_at": start - timedelta(days=30),
            }
        )
    wishset = set()
    for week in range(config["weeks"]):
        day = start + timedelta(weeks=week)
        calendar = features(day)
        stock = {
            v["id"]: bool(rng.random() >= config["stockout_probability"])
            for v in variants
        }
        stock_weeks.extend(
            {"variant_id": v["id"], "week": day.date(), "in_stock": stock[v["id"]]}
            for v in variants
        )
        active = np.array(
            [
                p["launch_date"] <= day.date()
                and any(stock[v["id"]] for v in by_product[p["id"]])
                for p in products
            ]
        )
        demand = rng.poisson(
            (130 + week * 0.4)
            * (1 + sum(calendar[2:6]) * 0.65 + calendar[6] * 0.65 + calendar[7] * 0.4)
        )
        for n in range(demand):
            u = int(rng.choice(count, p=loyalty))
            uid = users[u]["id"]
            when = day + timedelta(
                days=int(rng.integers(7)), hours=int(rng.integers(8, 23))
            )
            affinity = np.exp(tastes[u] @ vectors.T * 7 - prices / budgets[u] * 0.6)
            affinity *= 1 + 0.25 * np.sin(week / 12 + np.arange(len(ids)) / 9)
            affinity *= active
            affinity /= affinity.sum()
            chosen = rng.choice(
                len(ids),
                size=int(rng.choice([1, 2, 3], p=[0.74, 0.23, 0.03])),
                replace=False,
                p=affinity,
            )
            order_id = stable(f"order/{week}/{n}")
            total = 0.0
            for pi in chosen:
                pid = int(ids[pi])
                options = [v for v in by_product[pid] if stock[v["id"]]]
                v = options[int(rng.integers(len(options)))]
                qty = 2 if rng.random() < 0.07 else 1
                price = round(v["price"] * (0.82 if calendar[6] else 1), 2)
                total += price * qty
                lines.append(
                    {
                        "order_id": order_id,
                        "variant_id": v["id"],
                        "quantity": qty,
                        "unit_price": price,
                    }
                )
                events.extend(
                    {
                        "user_id": uid,
                        "product_id": pid,
                        "event_type": et,
                        "created_at": when,
                    }
                    for et in ["view", "add_to_cart", "purchase"]
                )
                if rng.random() < 0.25 and (uid, pid) not in wishset:
                    wishset.add((uid, pid))
                    wishes.append(
                        {"user_id": uid, "product_id": pid, "created_at": when}
                    )
                    events.append(
                        {
                            "user_id": uid,
                            "product_id": pid,
                            "event_type": "wishlist_add",
                            "created_at": when,
                        }
                    )
            orders.append(
                {
                    "id": order_id,
                    "user_id": uid,
                    "created_at": when,
                    "total": round(total, 2),
                    "status": "simulated",
                    "simulated": True,
                }
            )
            for pi in rng.choice(len(ids), size=2, replace=False, p=affinity):
                events.append(
                    {
                        "user_id": uid,
                        "product_id": int(ids[pi]),
                        "event_type": "view",
                        "created_at": when,
                    }
                )
    return {
        "users": users,
        "quizzes": quizzes,
        "orders": orders,
        "lines": lines,
        "events": events,
        "wishes": wishes,
        "stock_weeks": stock_weeks,
    }


if __name__ == "__main__":
    from app.seed import seed

    seed()
