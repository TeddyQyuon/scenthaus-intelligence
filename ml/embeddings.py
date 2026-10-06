"""Frozen MiniLM features: real pretrained embeddings, never a hashed substitute."""

from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import numpy as np
from .core import ARTIFACTS, config, text_products, ROOT
from app.config import settings


@lru_cache(maxsize=1)
def encoder():
    os.environ.setdefault("HF_HOME", str(ROOT / "data/hf-cache"))
    from sentence_transformers import SentenceTransformer

    c = config("recommender")
    return SentenceTransformer(c["model_name"], revision=c["revision"], device="cpu")


def encode(texts: list[str]) -> np.ndarray:
    if os.environ.get("VERCEL") and not os.environ.get("SCENTHAUS_BUILD_TRAINING"):
        return encode_onnx(texts)
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


@lru_cache(maxsize=1)
def onnx_encoder():
    import onnxruntime as ort
    from tokenizers import Tokenizer

    cfg = config("search")
    folder = settings.artifact_dir / "encoder"
    model_path = folder / Path(cfg["vercel_encoder_file"]).name
    tokenizer_path = folder / "tokenizer.json"
    manifest_path = folder / "encoder.json"
    if (
        not model_path.is_file()
        or not tokenizer_path.is_file()
        or not manifest_path.is_file()
    ):
        raise RuntimeError(
            "Vercel search encoder assets are missing; rebuild the API service"
        )
    manifest = json.loads(manifest_path.read_text())
    for path in [model_path, tokenizer_path]:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if manifest["files"].get(path.name) != digest:
            raise RuntimeError("Vercel search encoder checksum mismatch")
    if manifest["files"].get(model_path.name) != cfg["vercel_encoder_sha256"]:
        raise RuntimeError("Vercel search encoder does not match its pinned release")
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    tokenizer.enable_truncation(max_length=256)
    tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(model_path),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    return tokenizer, session


def mean_pool(hidden: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
    mask = attention_mask.astype(np.float32)[..., None]
    pooled = (hidden * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1e-9)
    norms = np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12)
    return (pooled / norms).astype(np.float32)


def encode_onnx(texts: list[str]) -> np.ndarray:
    tokenizer, session = onnx_encoder()
    encoded = tokenizer.encode_batch(texts)
    ids = np.asarray([row.ids for row in encoded], dtype=np.int64)
    mask = np.asarray([row.attention_mask for row in encoded], dtype=np.int64)
    segments = np.asarray([row.type_ids for row in encoded], dtype=np.int64)
    available = {item.name for item in session.get_inputs()}
    feed = {"input_ids": ids, "attention_mask": mask}
    if "token_type_ids" in available:
        feed["token_type_ids"] = segments
    hidden = session.run(None, feed)[0]
    return mean_pool(hidden, mask)


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
