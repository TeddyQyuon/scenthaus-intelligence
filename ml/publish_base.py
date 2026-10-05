"""Publish cached serving state. Trained arrays are ignored by Git."""

import hashlib, json, os, pickle
from datetime import datetime, timezone
from app.config import settings
from .core import snapshot, ARTIFACTS
from app.ml.recommender import fit


def publish() -> str:
    d = snapshot()
    evaluation = json.loads((ARTIFACTS / "baselines.json").read_text())
    model, _, _ = fit(d["products"], d["orders"], d["wishes"], d["events"], d["end"])
    model["weights"] = evaluation["weights"]
    forecast_path = ARTIFACTS / "forecast.json"
    forecast = (
        json.loads(forecast_path.read_text())
        if forecast_path.exists()
        else {
            "series": [],
            "inventory": [],
            "tracking": [],
            "metrics": {"pending": True},
        }
    )
    if forecast_path.exists() and forecast["data_hash"] != d["data_hash"]:
        raise ValueError("Forecast dataset differs; refit before publishing")
    version = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + d["data_hash"][:8]
    )
    metrics = {
        "simulated_data": True,
        "validation": d["validation"],
        "recommender": {
            "metrics": evaluation["recommender"],
            "split": evaluation["split"],
            "weights": evaluation["weights"],
        },
        "forecast": forecast["metrics"],
        "experiments": {},
        "version": version,
    }
    b = {
        "version": version,
        "metrics": metrics,
        "recommender": model,
        "forecast": forecast,
        "experiments": {},
        "torch_recommender": str(ARTIFACTS / "recommender"),
    }
    folder = settings.artifact_dir / version
    folder.mkdir(parents=True, exist_ok=True)
    payload = pickle.dumps(b, protocol=5)
    (folder / "bundle.pkl").write_bytes(payload)
    (folder / "metrics.json").write_text(json.dumps(metrics, indent=2))
    temporary = settings.artifact_dir / "current.tmp"
    temporary.write_text(
        json.dumps({"version": version, "sha256": hashlib.sha256(payload).hexdigest()})
    )
    os.replace(temporary, settings.artifact_dir / "current.json")
    print("Serving version", version, flush=True)
    return version


if __name__ == "__main__":
    publish()
