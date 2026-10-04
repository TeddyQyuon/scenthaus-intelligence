import json, time
import numpy as np
from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as c:
    session = c.get("/auth/session").json()
    c.headers.update(
        {"Origin": "http://localhost:5173", "X-CSRF-Token": session["csrf"]}
    )
    results = {}
    for path in ["/recommend/similar?product_id=1", "/recommend/user"]:
        for _ in range(5):
            assert c.get(path).status_code == 200
        times = []
        for _ in range(40):
            start = time.perf_counter()
            r = c.get(path)
            assert r.status_code == 200
            times.append((time.perf_counter() - start) * 1000)
        results[path] = {
            "samples": len(times),
            "p50_ms": float(np.percentile(times, 50)),
            "p95_ms": float(np.percentile(times, 95)),
        }
    print(
        json.dumps(
            {
                "scope": "Warm in-process TestClient with local PGlite PostgreSQL-WASM, no internet latency or load concurrency",
                "results": results,
            },
            indent=2,
        )
    )
