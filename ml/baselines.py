"""Popularity/CF/BM25 and forecast baselines on one time-based harness."""

from .tracking import tracked

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from app.ml.recommender import fit, scores
from app.ml.calendar import features
from .core import (
    ARTIFACTS,
    config,
    snapshot,
    rank_metrics,
    forecast_metrics,
    write_report,
    save_json,
    text_products,
    BM25,
)


def rec_baseline(data: dict, cut: pd.Timestamp) -> dict:
    model, matrix, users = fit(
        data["products"], data["orders"], data["wishes"], data["events"], cut
    )
    return {"model": model, "matrix": matrix, "users": users}


def evaluate_rec(
    data: dict, cut: pd.Timestamp, end: pd.Timestamp, scorer, k: int = 10
) -> dict:
    p = data["products"]
    ids = p.id.tolist()
    ix = {pid: i for i, pid in enumerate(ids)}
    eligible = {p.id for p in p.itertuples() if pd.Timestamp(p.launch_date) < cut}
    old = (
        data["orders"][data["orders"].created_at < cut]
        .groupby("user_id")
        .product_id.agg(set)
        .to_dict()
    )
    truth = data["orders"][
        (data["orders"].created_at >= cut) & (data["orders"].created_at < end)
    ]
    outcomes = []
    coverage = set()
    diversity = []
    for uid, g in truth.groupby("user_id"):
        seen = old.get(uid, set())
        relevant = set(g.product_id) - seen
        relevant &= eligible
        if not relevant:
            continue
        values = scorer(uid)
        choices = [
            i for i, pid in enumerate(ids) if pid in eligible and pid not in seen
        ]
        rank = sorted(choices, key=lambda i: (-values[i], ids[i]))[:k]
        ranked = [ids[i] for i in rank]
        outcomes.append(rank_metrics(ranked, relevant, k))
        coverage.update(ranked)
        diversity.append(len({p.iloc[i].brand for i in rank}) / max(1, len(rank)))
    return {
        key: float(np.mean([o[key] for o in outcomes]))
        for key in ["precision", "recall", "ndcg", "mrr"]
    } | {
        "coverage": len(coverage) / max(1, len(eligible)),
        "brand_diversity": float(np.mean(diversity)),
        "users": len(outcomes),
    }


def scorer_for(baseline: dict, kind: str, weights=None):
    m = baseline["model"]
    ui = {u: i for i, u in enumerate(baseline["users"])}

    def score(uid):
        if kind == "popularity":
            return m["popularity"]
        signal = (
            {m["ids"][i]: v for i, v in enumerate(baseline["matrix"][ui[uid]]) if v}
            if uid in ui
            else {}
        )
        c, f, h = scores(m, signal, weights)
        return {"cf": f, "content": c, "hybrid": h}[kind]

    return score


def panel(data: dict) -> tuple:
    v = data["variants"]
    o = data["orders"].copy()
    o["week"] = pd.to_datetime(o.created_at).dt.to_period("W-SUN").dt.start_time
    dates = pd.date_range(
        config("data")["start"], periods=config("data")["weeks"], freq="W-MON"
    )
    units = np.array(
        [
            o[o.variant_id == r.id]
            .groupby("week")
            .quantity.sum()
            .reindex(dates, fill_value=0)
            .values
            for r in v.itertuples()
        ],
        float,
    )
    stock = data["stock"].copy()
    stock["week"] = pd.to_datetime(stock.week)
    availability = np.array(
        [
            stock[stock.variant_id == r.id]
            .set_index("week")
            .in_stock.reindex(dates, fill_value=True)
            .values
            for r in v.itertuples()
        ],
        bool,
    )
    categories = data["products"].set_index("id").category.to_dict()
    names = sorted(set(categories.values()))
    cat = np.array(
        [
            units[
                [
                    i
                    for i, r in enumerate(v.itertuples())
                    if categories[r.product_id] == c
                ]
            ].sum(0)
            for c in names
        ]
    )
    meta = [
        {
            "id": int(r.id),
            "sku": r.sku,
            "product_id": int(r.product_id),
            "size_ml": int(r.size_ml),
            "price": float(r.price),
            "category": categories[r.product_id],
            "kind": "sku",
        }
        for r in v.itertuples()
    ]
    meta += [
        {
            "id": -i - 1,
            "sku": "category:" + c,
            "product_id": 0,
            "size_ml": 0,
            "price": 0.0,
            "category": c,
            "kind": "category",
        }
        for i, c in enumerate(names)
    ]
    return (
        np.vstack([units, cat]),
        dates,
        meta,
        np.vstack([availability, np.ones(cat.shape, bool)]),
    )


def forecast_row(y, day, i, meta):
    c = config("baselines")["forecast"]
    return [
        i,
        meta["product_id"],
        meta["size_ml"],
        meta["price"],
        *[y[-lag] if len(y) >= lag else 0 for lag in c["lags"]],
        *[np.mean(y[-w:]) for w in c["rolling"]],
        *features(day),
    ]


def fit_forecast(y, dates, meta, end, availability):
    c = config("baselines")["forecast"]
    x = []
    target = []
    for i, m in enumerate(meta):
        for t in range(13, end):
            if not availability[i, t]:
                continue
            x.append(forecast_row(y[i, :t], dates[t], i, m))
            target.append(y[i, t])
    return LGBMRegressor(
        **{
            k: c[k]
            for k in [
                "n_estimators",
                "learning_rate",
                "num_leaves",
                "min_child_samples",
                "reg_lambda",
            ]
        },
        random_state=config("baselines")["seed"],
        n_jobs=2,
        verbosity=-1,
    ).fit(np.asarray(x), target)


def predict_forecast(model, y, dates, meta, end, h):
    history = [list(row[:end]) for row in y]
    out = []
    for step in range(h):
        if model is None:
            values = np.array(
                [
                    past[-52] if len(past) >= 52 else np.mean(past[-4:])
                    for past in history
                ]
            )
        else:
            x = np.array(
                [
                    forecast_row(
                        past, dates[end - 1] + pd.Timedelta(weeks=step + 1), i, meta[i]
                    )
                    for i, past in enumerate(history)
                ]
            )
            values = np.maximum(0, model.predict(x))
        out.append(values)
        for past, val in zip(history, values):
            past.append(float(val))
    return np.array(out).T


@tracked("baselines")
def train() -> dict:
    d = snapshot()
    c = config("baselines")
    k = c["k"]
    rows = []
    val = rec_baseline(d, d["train_end"])
    best = max(
        c["recommender_weights"],
        key=lambda weights: evaluate_rec(
            d, d["train_end"], d["val_end"], scorer_for(val, "hybrid", weights), k
        )["ndcg"],
    )
    test = rec_baseline(d, d["val_end"])
    rec = {
        kind: evaluate_rec(d, d["val_end"], d["end"], scorer_for(test, kind, best), k)
        for kind in ["popularity", "cf", "content", "hybrid"]
    }
    rows += [{"Task": "recommend", "Model": name, **r} for name, r in rec.items()]
    y, dates, meta, availability = panel(d)
    fc = {}
    n = len(d["variants"])
    origins = c["forecast"]["origins"]
    h = c["forecast"]["horizon"]
    for kind in ["seasonal_naive", "lightgbm"]:
        scores_all = {"sku": [], "category": []}
        # Intervals calibrated using validation origins only, before the test starts.
        residual = []
        for origin in [52, 56, 60]:
            model = (
                None
                if kind == "seasonal_naive"
                else fit_forecast(y, dates, meta, origin, availability)
            )
            pred = predict_forecast(model, y, dates, meta, origin, h)
            residual.extend(np.abs(y[:, origin : origin + h] - pred).ravel())
        width = float(np.quantile(residual, 0.8))
        for origin in origins:
            model = (
                None
                if kind == "seasonal_naive"
                else fit_forecast(y, dates, meta, origin, availability)
            )
            pred = predict_forecast(model, y, dates, meta, origin, h)
            for group, slice_ in [("sku", slice(0, n)), ("category", slice(n, None))]:
                scores_all[group].append(
                    forecast_metrics(
                        y[slice_, origin : origin + h],
                        pred[slice_],
                        y[slice_, :origin],
                        np.maximum(0, pred[slice_] - width),
                        pred[slice_] + width,
                    )
                )
        fc[kind] = {
            group: {key: float(np.mean([r[key] for r in scores])) for key in scores[0]}
            for group, scores in scores_all.items()
        }
        rows += [
            {"Task": group + " forecast", "Model": kind, **r}
            for group, r in fc[kind].items()
        ]
    result = {
        "data_hash": d["data_hash"],
        "split": {
            "train_end": str(d["train_end"]),
            "val_end": str(d["val_end"]),
            "test_end": str(d["end"]),
        },
        "k": k,
        "recommender": rec,
        "weights": best,
        "forecast": fc,
        "simulated": True,
    }
    save_json(ARTIFACTS / "baselines.json", result)
    write_report(
        "baselines",
        rows,
        f"Hash `{d['data_hash']}`. Train/validation/test: 52/13/13 weeks, exclusive cutoffs {d['train_end'].date()} / {d['val_end'].date()} / {d['end'].date()}. K={k}; novel purchase targets; no future wishlist/event signals. CF uses orders and wishlists/events. Hybrid weights {best} selected on validation only. BM25 is implemented and tested; query-quality evaluation is deferred to the manually reviewable labels in Phase 4. Forecast origins {origins}, 4-week horizon; rolling origins refit on observed prefixes. WAPE/sMAPE in percent, MASE uses 52-week seasonal scale (fallback lag 1 only for short histories), coverage of validation-residual 80% intervals. SKU and category scores are separate, not double counted; intervals pooled across heterogeneous series may be poorly calibrated. Zero-demand WAPE and constant-history MASE are undefined, never reported as zero error.",
    )
    print("Baseline reports written", d["data_hash"], flush=True)
    return result


if __name__ == "__main__":
    train()
