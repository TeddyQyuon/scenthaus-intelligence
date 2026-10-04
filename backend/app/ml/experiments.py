import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.linear_model import LinearRegression


def ab_simulate(visitors=10000, baseline_rate=0.04, relative_lift=0.1, seed=42):
    rng = np.random.default_rng(seed)
    group = rng.integers(0, 2, visitors)
    rates = np.where(group == 0, baseline_rate, baseline_rate * (1 + relative_lift))
    conversions = rng.random(visitors) < rates
    n = np.bincount(group, minlength=2)
    wins = np.bincount(group, weights=conversions, minlength=2)
    p = wins / n
    pooled = wins.sum() / n.sum()
    se = np.sqrt(pooled * (1 - pooled) * sum(1 / n))
    z = (p[1] - p[0]) / se if se else 0
    diffse = np.sqrt(sum(p * (1 - p) / n))
    return {
        "simulated": True,
        "assignment": "random, 50/50",
        "visitors": n.tolist(),
        "conversions": wins.astype(int).tolist(),
        "rates": p.tolist(),
        "relative_lift": float(p[1] / p[0] - 1) if p[0] else None,
        "p_value": float(2 * norm.sf(abs(z))),
        "difference_95_ci": [
            float(p[1] - p[0] - 1.96 * diffse),
            float(p[1] - p[0] + 1.96 * diffse),
        ],
        "note": "Outcomes are sampled from the requested rates; this is not measured model uplift.",
    }


def train_experiments(model, matrix, orders):
    rng = np.random.default_rng(42)
    item = model["embeddings"]
    uf = matrix / (matrix.sum(axis=1, keepdims=True) + 1e-8)
    wu = rng.normal(0, 0.1, (uf.shape[1], 12))
    wi = rng.normal(0, 0.1, (item.shape[1], 12))
    positives = np.argwhere(matrix > 1)
    losses = []
    for epoch in range(30):
        take = positives[
            rng.choice(len(positives), min(6000, len(positives)), replace=False)
        ]
        u = np.repeat(take[:, 0], 2)
        i = np.stack(
            [take[:, 1], rng.integers(0, len(item), len(take))], axis=1
        ).ravel()
        y = np.tile([1.0, 0.0], len(take))
        a = np.tanh(uf[u] @ wu)
        b = np.tanh(item[i] @ wi)
        logits = (a * b).sum(axis=1)
        p = 1 / (1 + np.exp(-logits))
        error = (p - y)[:, None] / len(y)
        gu = uf[u].T @ (error * b * (1 - a * a)) + 0.0001 * wu
        gi = item[i].T @ (error * a * (1 - b * b)) + 0.0001 * wi
        wu -= 0.8 * gu
        wi -= 0.8 * gi
        losses.append(
            float(-np.mean(y * np.log(p + 1e-8) + (1 - y) * np.log(1 - p + 1e-8)))
        )
    emb = rng.normal(0, 0.1, (len(item), 12))
    out = rng.normal(0, 0.1, emb.shape)
    pairs = []
    for _, g in orders.sort_values("created_at").groupby("user_id"):
        seq = [model["index"][int(pid)] for pid in g.product_id]
        for n, a in enumerate(seq):
            pairs.extend(
                (a, b) for b in seq[max(0, n - 2) : n] + seq[n + 1 : n + 3] if a != b
            )
    pairarray = np.asarray(pairs, dtype=int)
    skip_losses = []
    for epoch in range(10):
        sample = pairarray[
            rng.choice(len(pairarray), min(len(pairarray), 12000), replace=False)
        ]
        a = np.repeat(sample[:, 0], 4)
        b = np.stack(
            [sample[:, 1], *rng.integers(0, len(item), (3, len(sample)))], axis=1
        ).ravel()
        labels = np.tile([1, 0, 0, 0], len(sample))
        left = emb[a].copy()
        right = out[b].copy()
        logits = np.clip((left * right).sum(axis=1), -20, 20)
        p = 1 / (1 + np.exp(-logits))
        e = (p - labels)[:, None]
        np.add.at(emb, a, -0.012 * e * right)
        np.add.at(out, b, -0.012 * e * left)
        skip_losses.append(
            float(
                -np.mean(
                    labels * np.log(p + 1e-8) + (1 - labels) * np.log(1 - p + 1e-8)
                )
            )
        )
    elasticity = []
    data = orders.copy()
    data["week"] = pd.to_datetime(data.created_at).dt.to_period("W-SUN").dt.start_time
    for sku, g in data.groupby("sku"):
        weekly = (
            g.groupby("week")
            .agg(quantity=("quantity", "sum"), price=("unit_price", "mean"))
            .sort_index()
        )
        if len(weekly) < 20 or weekly.price.astype(float).std() < 0.01:
            continue
        x = np.column_stack(
            [np.log(weekly.price.astype(float)), np.arange(len(weekly)) / len(weekly)]
        )
        fit = LinearRegression().fit(x, np.log1p(weekly.quantity))
        elasticity.append(
            {
                "sku": sku,
                "coefficient": float(fit.coef_[0]),
                "weeks": len(weekly),
                "r_squared": float(fit.score(x, np.log1p(weekly.quantity))),
            }
        )
    return {
        "two_tower": {"user_weights": wu, "item_weights": wi, "loss": losses},
        "item2vec": {"embeddings": emb, "loss": skip_losses, "pairs": len(pairs)},
        "elasticity": elasticity,
        "note": "Training diagnostics only. Neural variants have no independent held-out superiority claim. Price coefficients are observational and promotion-confounded.",
    }
