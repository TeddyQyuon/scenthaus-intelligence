"""Warm local API latency. This does not measure deployed internet latency."""

import json, time
import numpy as np
from fastapi.testclient import TestClient
from app.main import app
from ml.rec_serving import score
from ml.core import REPORTS

with TestClient(app) as client:
    session = client.get("/auth/session").json()
    client.headers.update(
        {"Origin": "http://localhost:5173", "X-CSRF-Token": session["csrf"]}
    )
    client.put("/privacy/consent", json={"consent": True})
    client.put("/wishlist/29")
    times = {}
    for name, path in [
        ("user", "/recommend/user?experiment=two_tower"),
        ("similar", "/recommend/similar?product_id=29"),
    ]:
        samples = []
        for i in range(35):
            start = time.perf_counter()
            r = client.get(path)
            elapsed = (time.perf_counter() - start) * 1000
            assert r.status_code == 200 and r.json()["products"]
            if i >= 5:
                samples.append(elapsed)
        times[name] = {
            "p50_ms": float(np.percentile(samples, 50)),
            "p95_ms": float(np.percentile(samples, 95)),
        }
    samples = []
    for _ in range(100):
        start = time.perf_counter()
        score("", {}, None)
        samples.append((time.perf_counter() - start) * 1000)
    times["cached_numpy"] = {"p95_ms": float(np.percentile(samples, 95))}
print(json.dumps(times), flush=True)
assert all(v["p95_ms"] < 100 for v in times.values()), times
with (REPORTS / "recommender.md").open("a") as f:
    f.write("\n| Warm local check | p95 ms |\n|---|---:|\n")
    for key, v in times.items():
        f.write(f"| {key} | {v['p95_ms']:.2f} |\n")
    f.write(
        "\nPostgreSQL-protocol PGlite fixture + FastAPI TestClient, 30 warm API requests; not a production/network latency guarantee. Tests cover causal training history, cold start, NumPy/PyTorch parity, recommendation filters, explanations, quiz and consent.\n"
    )
