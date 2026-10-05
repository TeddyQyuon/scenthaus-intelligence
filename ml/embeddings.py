"""Frozen MiniLM features: real pretrained embeddings, never a hashed substitute."""

from functools import lru_cache
import hashlib
import os
import numpy as np
from .core import ARTIFACTS, config, text_products, ROOT


@lru_cache(maxsize=1)
def encoder():
    os.environ.setdefault("HF_HOME", str(ROOT / "data/hf-cache"))
    from sentence_transformers import SentenceTransformer

    c = config("recommender")
    return SentenceTransformer(c["model_name"], revision=c["revision"], device="cpu")


def encode(texts: list[str]) -> np.ndarray:
    return (
        encoder()
        .encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        .astype("float32")
    )


def product_embeddings(products) -> np.ndarray:
    texts = text_products(products)
    fingerprint = hashlib.sha256(
        ("\n".join(texts) + config("recommender")["revision"]).encode()
    ).hexdigest()[:16]
    path = ARTIFACTS / f"content-{fingerprint}.npy"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, encode(texts), allow_pickle=False)
    return np.load(path, allow_pickle=False)
