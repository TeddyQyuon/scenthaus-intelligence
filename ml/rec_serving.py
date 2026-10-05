"""Cached NumPy two-tower inference; no torch in the recommendation request path."""

from functools import lru_cache
from pathlib import Path
import numpy as np
from app.catalog import ACCORDS
from .core import ARTIFACTS, config


@lru_cache(maxsize=2)
def load_cache(folder: str):
    root = Path(folder)
    cache = dict(np.load(root / "cached.npz", allow_pickle=False))
    cache["weights"] = dict(np.load(root / "weights.npz", allow_pickle=False))
    cache["user_index"] = {u: i + 1 for i, u in enumerate(cache["user_ids"])}
    cache["item_index"] = {int(pid): i for i, pid in enumerate(cache["product_ids"])}
    return cache


def score(
    uid: str,
    history: dict[int, float],
    quiz: dict | None,
    folder: str | None = None,
    recent_ids: list[int] | None = None,
) -> np.ndarray:
    cache = load_cache(folder or str(ARTIFACTS / "recommender"))
    w = cache["weights"]
    user = w["user_id.weight"][cache["user_index"].get(uid, 0)]
    recent = [
        cache["item_index"][pid] + 1
        for pid in (recent_ids if recent_ids is not None else list(history)[-10:])
        if pid in cache["item_index"]
    ]
    h = w["item_id.weight"][recent].mean(0) if recent else np.zeros_like(user)
    q = np.array([(quiz or {}).get(a, 0.0) for a in ACCORDS], np.float32)
    if q.sum() > 0:
        q /= q.sum()
    inp = np.concatenate([user, h, q])
    hidden = np.maximum(0, inp @ w["user_net.0.weight"].T + w["user_net.0.bias"])
    embedding = hidden @ w["user_net.2.weight"].T + w["user_net.2.bias"]
    embedding /= max(1e-8, np.linalg.norm(embedding))
    return cache["items"] @ embedding


def similar(pid: int, folder: str | None = None) -> np.ndarray:
    cache = load_cache(folder or str(ARTIFACTS / "recommender"))
    index = cache["item_index"].get(pid)
    if index is None:
        raise ValueError("Unknown product")
    return cache["items"] @ cache["items"][index]
