"""Publish cached serving state. Trained arrays are ignored by Git."""

import json, pickle, shutil, uuid
from datetime import datetime, timezone
from app.config import settings
from .core import snapshot, ARTIFACTS
from app.ml.versions import checksum, activate
from app.database import SessionLocal
from app.models import ModelRun, ForecastSnapshot
from .tracking import runtime
from app.ml.recommender import fit


def publish() -> str:
    d = snapshot()
    evaluation = json.loads((ARTIFACTS / "baselines.json").read_text())
    for name, path in [
        ("baselines", ARTIFACTS / "baselines.json"),
        ("recommender", ARTIFACTS / "recommender/metrics.json"),
        ("search", ARTIFACTS / "search.json"),
        ("forecast", ARTIFACTS / "forecast.json"),
    ]:
        if json.loads(path.read_text())["data_hash"] != d["data_hash"]:
            raise ValueError(f"{name} dataset differs; retrain before publishing")
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
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        + "-"
        + d["data_hash"][:8]
        + "-"
        + uuid.uuid4().hex[:8]
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
        "two_tower": json.loads((ARTIFACTS / "recommender/metrics.json").read_text()),
        "search": json.loads((ARTIFACTS / "search.json").read_text()),
        "version": version,
    }
    b = {
        "version": version,
        "metrics": metrics,
        "recommender": model,
        "forecast": forecast,
        "experiments": {},
        "torch_recommender": "recommender",
        "search_path": "search",
    }
    folder = settings.artifact_dir / version
    folder.mkdir(parents=True, exist_ok=False)
    payload = pickle.dumps(b, protocol=5)
    (folder / "bundle.pkl").write_bytes(payload)
    (folder / "metrics.json").write_text(json.dumps(metrics, indent=2))
    for source, names in [
        ("recommender", ["cached.npz", "weights.npz", "metrics.json"]),
        ("search", ["embeddings.npy", "index.json"]),
    ]:
        (folder / source).mkdir()
        for name in names:
            shutil.copy2(ARTIFACTS / source / name, folder / source / name)
    (folder / "runtime.json").write_text(json.dumps(runtime(), indent=2))
    manifest = {
        "version": version,
        "data_hash": d["data_hash"],
        "simulated_data": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": {
            str(p.relative_to(folder)): checksum(p)
            for p in sorted(folder.rglob("*"))
            if p.is_file()
        },
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
    run_file = ARTIFACTS / "forecast-run.json"
    run_id = json.loads(run_file.read_text())["run_id"] if run_file.exists() else None
    with SessionLocal() as db:
        db.add(
            ModelRun(
                version=version,
                metrics=metrics,
                data_hash=d["data_hash"],
                mlflow_run_id=run_id,
            )
        )
        for series in forecast["series"]:
            for f in series["forecast"]:
                db.add(
                    ForecastSnapshot(
                        version=version,
                        sku=series["sku"],
                        origin=datetime.fromisoformat(forecast["as_of"]).date(),
                        target_week=datetime.fromisoformat(f["week"]).date(),
                        **{
                            key: f[key]
                            for key in [
                                "prediction",
                                "lower80",
                                "upper80",
                                "lower95",
                                "upper95",
                            ]
                        },
                    )
                )
        db.commit()
    activate(settings.artifact_dir, version)
    print("Serving version", version, flush=True)
    return version


if __name__ == "__main__":
    publish()
