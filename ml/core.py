"""Shared, leakage-safe evaluation on SIMULATED behavioural data."""

from collections import Counter
from functools import lru_cache
from pathlib import Path
import json
import re
import numpy as np
import pandas as pd
import yaml
from app.catalog import ACCORDS
from app.database import SessionLocal
from app.models import QuizProfile, StockWeek, User
from app.ml.data import load, validate, frame
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "data/models"
REPORTS = ROOT / "ml/reports"


@lru_cache(maxsize=16)
def config(name: str) -> dict:
    return yaml.safe_load((ROOT / f"ml/configs/{name}.yaml").read_text())


def snapshot() -> dict:
    with SessionLocal() as db:
        p, v, o, w, e = load(db)
        validation = validate(p, v, o)
        q = frame(
            db,
            select(QuizProfile.user_id, QuizProfile.weights, QuizProfile.created_at)
            .join(User, QuizProfile.user_id == User.id)
            .where(User.consent.is_(True)),
        )
        stock = frame(db, select(StockWeek.__table__))
    d = config("data")
    start = pd.Timestamp(d["start"])
    # Both temporal cutoffs are exclusive. No random user/event splits.
    train_end = start + pd.Timedelta(weeks=d["train_weeks"])
    val_end = train_end + pd.Timedelta(weeks=d["validation_weeks"])
    end = val_end + pd.Timedelta(weeks=d["test_weeks"])
    o = o[o.created_at < end]
    w = w[w.created_at < end]
    e = e[e.created_at < end]
    q = q[q.created_at < end]
    stock = stock[pd.to_datetime(stock.week) < end]
    validation["catalog_order_hash"] = validation["data_hash"]
    import hashlib

    digest = hashlib.sha256(validation["catalog_order_hash"].encode())
    for name, rows in [("wishes", w), ("events", e), ("quiz", q), ("stock", stock)]:
        canonical = sorted(
            json.dumps(row, sort_keys=True, default=str)
            for row in rows.to_dict("records")
        )
        digest.update(name.encode())
        for row in canonical:
            digest.update(row.encode())
    validation["data_hash"] = digest.hexdigest()
    return {
        "products": p.sort_values("id").reset_index(drop=True),
        "variants": v.sort_values("id").reset_index(drop=True),
        "orders": o,
        "wishes": w,
        "events": e,
        "quiz": q,
        "stock": stock,
        "train_end": train_end,
        "val_end": val_end,
        "end": end,
        "data_hash": validation["data_hash"],
        "validation": validation,
    }


def split(
    rows: pd.DataFrame,
    train_end: pd.Timestamp,
    val_end: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple:
    ts = pd.to_datetime(rows.created_at)
    return tuple(
        rows[mask].copy()
        for mask in [
            ts < train_end,
            (ts >= train_end) & (ts < val_end),
            (ts >= val_end) & (ts < end),
        ]
    )


def text_products(products: pd.DataFrame) -> list[str]:
    return [
        " ".join(
            [
                p.brand,
                p.name,
                p.concentration,
                p.description,
                *sum(p.notes.values(), []),
                *p.accords,
                *p.occasions,
                *p.seasons,
            ]
        )
        for p in products.itertuples()
    ]


def tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


class BM25:
    def __init__(self, texts: list[str], k1: float = 1.5, b: float = 0.75):
        self.docs = [Counter(tokens(t)) for t in texts]
        self.length = np.array([sum(d.values()) for d in self.docs])
        self.avg = max(1, float(self.length.mean()))
        self.k1 = k1
        self.b = b
        df = Counter(t for d in self.docs for t in d)
        n = len(self.docs)
        self.idf = {t: np.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def score(self, query: str) -> np.ndarray:
        scores = np.zeros(len(self.docs))
        for t in tokens(query):
            freq = np.array([d[t] for d in self.docs])
            denom = freq + self.k1 * (1 - self.b + self.b * self.length / self.avg)
            scores += self.idf.get(t, 0) * freq * (self.k1 + 1) / denom
        return scores


def rank_metrics(
    ranked: list[int], relevant: set[int] | dict[int, int], k: int = 10
) -> dict:
    gains = {x: 1 for x in relevant} if isinstance(relevant, set) else relevant
    values = np.array([gains.get(x, 0) for x in ranked[:k]], float)
    hits = values > 0
    dcg = ((2**values - 1) / np.log2(np.arange(len(values)) + 2)).sum()
    ideal = np.sort(list(gains.values()))[::-1][:k]
    idcg = ((2 ** np.array(ideal) - 1) / np.log2(np.arange(len(ideal)) + 2)).sum()
    first = np.flatnonzero(hits)
    return {
        "precision": float(hits.sum() / k),
        "recall": float(hits.sum() / max(1, len(gains))),
        "ndcg": float(dcg / idcg) if idcg else 0.0,
        "mrr": float(1 / (first[0] + 1)) if len(first) else 0.0,
    }


def forecast_metrics(
    actual: np.ndarray,
    pred: np.ndarray,
    history: np.ndarray,
    lower=None,
    upper=None,
    season: int = 52,
) -> dict:
    a = np.atleast_2d(np.asarray(actual, float))
    p = np.atleast_2d(np.asarray(pred, float))
    h = np.atleast_2d(np.asarray(history, float))
    if a.shape != p.shape:
        raise ValueError("Forecast shape mismatch")
    err = np.abs(a - p)
    denom = np.abs(a) + np.abs(p)
    scales = []
    for past, error in zip(h, err):
        lag = season if len(past) > season else 1
        scale = np.abs(past[lag:] - past[:-lag]).mean()
        if np.isfinite(scale) and scale > 0:
            scales.append(float(error.mean() / scale))
    return {
        "wape": float(100 * err.sum() / np.abs(a).sum()) if np.abs(a).sum() else None,
        "smape": float(
            200 * np.divide(err, denom, out=np.zeros_like(err), where=denom > 0).mean()
        ),
        "mase": float(np.mean(scales)) if scales else None,
        "coverage80": float(np.mean((a >= lower) & (a <= upper)))
        if lower is not None
        else None,
    }


def write_report(name: str, rows: list[dict], intro: str) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame(rows)
    columns = list(table.columns)

    def value(v):
        return (
            "undefined"
            if v is None or (isinstance(v, float) and np.isnan(v))
            else f"{v:.5f}"
            if isinstance(v, float)
            else str(v)
        )

    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    lines += [
        "| " + " | ".join(value(v) for v in row) + " |"
        for row in table.itertuples(index=False, name=None)
    ]
    (REPORTS / f"{name}.md").write_text(
        f"# {name.title()}\n\nUsers, orders and events are **SIMULATED**.\n\n{intro}\n\n"
        + "\n".join(lines)
        + "\n"
    )


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str, allow_nan=False))
