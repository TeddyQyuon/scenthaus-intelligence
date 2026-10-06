"""MiniLM dense retrieval + BM25 RRF; draft relevance is not human ground truth."""

from .tracking import tracked

from functools import lru_cache
from pathlib import Path
import json
import re
import numpy as np
from sqlalchemy import select, cast
from sqlalchemy.dialects.postgresql import JSONB
from app.models import Product, Variant
from .core import (
    ARTIFACTS,
    ROOT,
    BM25,
    config,
    snapshot,
    text_products,
    rank_metrics,
    write_report,
    save_json,
)
from .embeddings import product_embeddings, encode


def parse_query(query: str) -> dict:
    text = query.lower().strip()
    budget = re.search(
        r"(?:under|below|less than|up to|max(?:imum)?)\s*\$?\s*(\d+(?:\.\d+)?)|\$\s*(\d+(?:\.\d+)?)",
        text,
    )
    size = re.search(r"\b(\d{1,3})\s*ml\b", text)
    gender = re.search(
        r"\b(women(?:'s)?|woman|female|ladies|men(?:'s)?|man|male|unisex)\b", text
    )
    season = re.search(r"\b(spring|summer|autumn|winter)\b", text)
    result = {
        "budget": float(next(x for x in budget.groups() if x)) if budget else None,
        "size_ml": int(size.group(1)) if size else None,
        "gender": (
            "Feminine"
            if gender.group() in ["women", "women's", "woman", "female", "ladies"]
            else "Unisex"
            if gender.group() == "unisex"
            else "Masculine"
        )
        if gender
        else None,
        "season": season.group().title() if season else None,
    }
    # Erase matched spans, never replace substrings inside brand/product names.
    for match in sorted(
        [m for m in [budget, size, gender, season] if m],
        key=lambda m: m.start(),
        reverse=True,
    ):
        text = text[: match.start()] + " " + text[match.end() :]
    result["text"] = re.sub(r"\s+", " ", text).strip() or "fragrance"
    return result


def eligible_ids(db, parsed: dict) -> set[int]:
    from datetime import date

    stmt = (
        select(Product.id)
        .join(Variant, Variant.product_id == Product.id)
        .where(
            Product.hidden.is_(False),
            Product.launch_date <= date.today(),
            Variant.stock > 0,
        )
    )
    if parsed["budget"] is not None:
        stmt = stmt.where(Variant.price <= parsed["budget"])
    if parsed["size_ml"] is not None:
        stmt = stmt.where(Variant.size_ml == parsed["size_ml"])
    if parsed["gender"]:
        stmt = stmt.where(Product.gender == parsed["gender"])
    if parsed["season"]:
        stmt = stmt.where(cast(Product.seasons, JSONB).contains([parsed["season"]]))
    return set(db.scalars(stmt.distinct()))


@lru_cache(maxsize=4)
def load_index(folder: str) -> dict:
    p = Path(folder)
    meta = json.loads((p / "index.json").read_text())
    c = config("search")
    meta["bm25"] = BM25(meta["texts"], c["bm25_k1"], c["bm25_b"])
    meta["embeddings"] = np.load(p / "embeddings.npy", allow_pickle=False)
    return meta


@lru_cache(maxsize=128)
def query_embedding(text: str) -> np.ndarray:
    return encode([text])[0]


def rank(
    index: dict, text: str, eligible: set[int], method: str = "hybrid", vector=None
) -> list[int]:
    if method not in {"bm25", "dense", "hybrid"}:
        raise ValueError("Supported methods: bm25, dense, hybrid")
    positions = np.array(
        [i for i, pid in enumerate(index["ids"]) if pid in eligible], dtype=int
    )
    if not len(positions):
        return []
    bm = index["bm25"].score(text)
    dense = (
        index["embeddings"] @ (vector if vector is not None else query_embedding(text))
        if method != "bm25"
        else np.zeros_like(bm)
    )

    def ordered(score):
        return positions[np.argsort(-score[positions], kind="stable")]

    if method == "hybrid":
        scores = np.zeros(len(bm))
        for order in [ordered(bm), ordered(dense)]:
            scores[order] += 1 / (
                config("search")["rrf_constant"] + np.arange(len(order)) + 1
            )
        order = ordered(scores)
    else:
        order = ordered(bm if method == "bm25" else dense)
    return [index["ids"][i] for i in order]


def fit_search(d: dict) -> dict:
    folder = ARTIFACTS / "search"
    folder.mkdir(parents=True, exist_ok=True)
    np.save(
        folder / "embeddings.npy", product_embeddings(d["products"]), allow_pickle=False
    )
    save_json(
        folder / "index.json",
        {
            "ids": d["products"].id.tolist(),
            "texts": text_products(d["products"]),
            "data_hash": d["data_hash"],
            "encoder_revision": config("recommender")["revision"],
        },
    )
    load_index.cache_clear()
    return load_index(str(folder))


def draft_queries(d: dict) -> list[dict]:
    path = ROOT / "ml/data/search_eval.json"
    if path.exists():
        return json.loads(path.read_text())["queries"]
    p = d["products"]
    records = []

    def add(query, gains):
        records.append(
            {
                "id": len(records) + 1,
                "query": query,
                "relevance": {str(k): int(v) for k, v in gains.items()},
                "reviewed": False,
            }
        )

    for brand in p.brand.unique():
        add(f"{brand} perfume", {x.id: 3 for x in p.itertuples() if x.brand == brand})
    for product in p.iloc[::10].itertuples():
        add(f"{product.brand} {product.name}", {product.id: 3})
    for query, accord in [
        ("fresh office scent under $150", "fresh"),
        ("warm vanilla perfume", "sweet"),
        ("woody evening scent", "woody"),
        ("rose floral perfume", "floral"),
        ("citrus everyday fragrance", "citrus"),
        ("sensual amber perfume", "amber"),
        ("clean aquatic scent 100ml", "fresh"),
        ("summer citrus fragrance", "citrus"),
        ("unisex woody scent below $400", "woody"),
        ("soft floral scent for women", "floral"),
    ]:
        parsed = parse_query(query)
        gains = {}
        for x in p.itertuples():
            variants = d["variants"][d["variants"].product_id == x.id]
            match = any(
                (parsed["budget"] is None or v.price <= parsed["budget"])
                and (parsed["size_ml"] is None or v.size_ml == parsed["size_ml"])
                for v in variants.itertuples()
            )
            if (
                match
                and (not parsed["gender"] or x.gender == parsed["gender"])
                and (not parsed["season"] or parsed["season"] in x.seasons)
                and accord in x.accords
            ):
                gains[x.id] = 2
        add(query, gains)
    assert len(records) == 60
    save_json(
        path,
        {
            "manual_review_required": True,
            "label_source": "DRAFT catalog-rule labels; not independent human judgments. Review query intent and all positive/negative grades before claiming search quality.",
            "queries": records,
        },
    )
    return records


@tracked("search")
def main() -> dict:
    from app.database import SessionLocal

    d = snapshot()
    index = fit_search(d)
    queries = draft_queries(d)
    vectors = encode([parse_query(q["query"])["text"] for q in queries])
    rows = []
    for method in ["bm25", "dense", "hybrid"]:
        values = []
        with SessionLocal() as db:
            for q, vector in zip(queries, vectors):
                parsed = parse_query(q["query"])
                ranked = rank(
                    index, parsed["text"], eligible_ids(db, parsed), method, vector
                )
                values.append(
                    rank_metrics(
                        ranked,
                        {int(k): v for k, v in q["relevance"].items()},
                        config("search")["k"],
                    )
                )
        rows.append(
            {
                "model": method,
                "MRR@10": float(np.mean([v["mrr"] for v in values])),
                "NDCG@10": float(np.mean([v["ndcg"] for v in values])),
                "queries": len(queries),
                "reviewed": sum(q["reviewed"] for q in queries),
            }
        )
    write_report(
        "search",
        rows,
        "Actual frozen all-MiniLM-L6-v2, BM25 and reciprocal-rank fusion (constant 60), same 60 draft queries, same live SQL budget/size/gender/season/in-stock constraints. Labels are catalog-rule drafts, **manual review required**; these scores test a pipeline and do not establish real user relevance. Catalog text and label wording overlap, favoring lexical search. Query vectors cache 128 entries; product vectors precomputed. No behavioural random split or customer text is used. Hyperparameters: ml/configs/search.yaml.",
    )
    result = {
        "data_hash": d["data_hash"],
        "results": rows,
        "manual_review_required": True,
    }
    save_json(ARTIFACTS / "search.json", result)
    print(json.dumps(result), flush=True)
    return result


if __name__ == "__main__":
    main()
