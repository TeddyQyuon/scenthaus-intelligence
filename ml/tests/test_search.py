import json
import numpy as np
from fastapi.testclient import TestClient
from app.main import app
from ml.search import parse_query, rank, load_index, query_embedding
from ml.core import ROOT, ARTIFACTS


def test_parser_preserves_intent_and_all_sizes():
    p = parse_query("fresh office scent under $150 75ml for men in summer")
    assert p["budget"] == 150 and p["size_ml"] == 75
    assert p["gender"] == "Masculine" and p["season"] == "Summer"
    assert "fresh office scent" in p["text"]
    assert parse_query("Chanel Chance")["gender"] is None
    assert parse_query("rose perfume for women below $120")["gender"] == "Feminine"


def test_retrieval_filters_and_rrf():
    index = load_index(str(ARTIFACTS / "search"))
    for method in ["bm25", "dense", "hybrid"]:
        result = rank(
            index, "Creed Aventus", {29, 30}, method, np.ones(384, dtype=np.float32)
        )
        assert set(result) == {29, 30}
        assert rank(index, "test", set(), method) == []
    assert rank(index, "Creed Aventus", set(index["ids"]), "bm25")[0] == 29


def test_labels_remain_manual_review_drafts():
    labels = json.loads((ROOT / "ml/data/search_eval.json").read_text())
    assert labels["manual_review_required"] and len(labels["queries"]) == 60
    assert all(not q["reviewed"] and q["relevance"] for q in labels["queries"])


def test_semantic_search_api_and_cache():
    query_embedding.cache_clear()
    with TestClient(app) as client:
        r = client.get("/search", params={"q": "fresh office scent under $150"})
        assert r.status_code == 200
        result = r.json()
        assert (
            result["products"] and result["model_version"] and result["simulated_data"]
        )
        assert result["parsed"]["budget"] == 150
        assert all(
            any(v["stock"] > 0 and v["price"] <= 150 for v in p["variants"])
            for p in result["products"]
        )
        client.get("/search", params={"q": "fresh office scent under $150"})
        assert query_embedding.cache_info().hits >= 1
        r = client.get("/search", params={"q": "fresh scent 75ml for women in summer"})
        assert r.status_code == 200
        assert all(
            p["gender"] == "Feminine"
            and "Summer" in p["seasons"]
            and any(v["size_ml"] == 75 for v in p["variants"])
            for p in r.json()["products"]
        )
        assert client.get("/search?q=Creed&method=invalid").status_code == 422
