import numpy as np
import pandas as pd
import torch
from fastapi.testclient import TestClient
from ml.core import config, snapshot
from ml.recommender import TwoTower, inputs
from ml.rec_serving import score, load_cache
from app.main import app


def test_training_history_excludes_future_and_current_timestamp():
    d = snapshot()
    c = config("recommender")
    x = inputs(d, d["train_end"], c)
    events = d["events"]
    modified = d.copy()
    modified["events"] = pd.concat(
        [
            events,
            pd.DataFrame(
                [
                    {
                        "user_id": "future-user",
                        "product_id": 1,
                        "event_type": "purchase",
                        "created_at": d["train_end"],
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    same = inputs(modified, d["train_end"], c)
    assert np.array_equal(x["pairs"], same["pairs"])
    assert "future-user" not in x["ui"]
    assert not x["pair_recent"][0].any()
    assert np.all(x["pair_recent"] >= 0)


def test_two_tower_cold_start_and_ablations():
    c = config("recommender")
    torch.manual_seed(c["seed"])
    m = TwoTower(3, np.eye(4, 10, dtype=np.float32), c).eval()
    with torch.no_grad():
        a = m.users(
            torch.tensor([0]),
            torch.zeros((1, c["recent_items"]), dtype=torch.long),
            torch.ones((1, 8)),
        )
        b = m.items(torch.tensor([4]), torch.tensor([False]))
    assert a.shape == b.shape == (1, c["embedding_dim"])
    assert torch.isfinite(a).all() and torch.isfinite(b).all()
    assert torch.norm(a).item() > 0.9


def test_numpy_serving_matches_pytorch_user_tower():
    cache = load_cache(
        str(__import__("ml.core", fromlist=["ARTIFACTS"]).ARTIFACTS / "recommender")
    )
    c = config("recommender")
    m = TwoTower(len(cache["user_ids"]), cache["features"], c)
    state = m.state_dict()
    for key, value in cache["weights"].items():
        state[key] = torch.tensor(value)
    m.load_state_dict(state)
    m.eval()
    with torch.no_grad():
        u = m.users(
            torch.tensor([0]),
            torch.zeros((1, c["recent_items"]), dtype=torch.long),
            torch.zeros((1, 8)),
        ).numpy()[0]
    assert np.allclose(score("", {}, None), cache["items"] @ u, atol=1e-6)


def test_recommendation_endpoints_filters_reasons_and_consent():
    with TestClient(app) as client:
        identity = client.get("/auth/session").json()
        client.headers.update(
            {"Origin": "http://localhost:5173", "X-CSRF-Token": identity["csrf"]}
        )
        client.put("/privacy/consent", json={"consent": True})
        client.put("/wishlist/29")
        r = client.get(
            "/recommend/user", params={"experiment": "two_tower", "budget": 200}
        )
        assert r.status_code == 200
        assert r.json()["ranking_model"] == "two_tower" and r.json()["model_version"]
        assert r.json()["products"] and all(p["why"] for p in r.json()["products"])
        for p in r.json()["products"]:
            assert any(v["stock"] > 0 and v["price"] <= 200 for v in p["variants"])
        assert all(
            p["id"] != 29
            for p in client.get("/recommend/similar?product_id=29").json()["products"]
        )
        q = client.post(
            "/recommend/quiz",
            json={
                "mood": "fresh",
                "occasion": "office",
                "intensity": "soft",
                "budget": 200,
                "size": 50,
            },
        )
        assert q.status_code == 200 and q.json()["products"]
        assert all(0 <= p["match"] <= 100 for p in q.json()["products"])
