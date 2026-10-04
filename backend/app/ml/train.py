import hashlib, json, os, pickle
from datetime import datetime, timezone
import mlflow
from sqlalchemy import select
from app.config import settings
from app.database import SessionLocal
from app.models import ModelRun, ForecastSnapshot
from .data import load, validate
from . import recommender, forecast, experiments


def train():
    with SessionLocal() as db:
        p, v, o, w, e = load(db)
        validation = validate(p, v, o)
        print("Validation passed", flush=True)
        evaluation = recommender.evaluate(p, o, w, e)
        rec, matrix, users = recommender.fit(p, o, w, e)
        rec["weights"] = evaluation["weights"]
        print("Recommender evaluated", flush=True)
        fc = forecast.train(p, v, o)
        print("Forecast evaluated", flush=True)
        stretch = experiments.train_experiments(rec, matrix, o)
        version = (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            + "-"
            + validation["data_hash"][:8]
        )
        metrics = {
            "simulated_data": True,
            "validation": validation,
            "recommender": evaluation,
            "forecast": fc["metrics"],
            "experiments": {
                "two_tower_loss": stretch["two_tower"]["loss"],
                "item2vec_loss": stretch["item2vec"]["loss"],
                "item2vec_pairs": stretch["item2vec"]["pairs"],
                "elasticity": stretch["elasticity"],
                "note": stretch["note"],
            },
            "version": version,
        }
        folder = settings.artifact_dir / version
        folder.mkdir(parents=True, exist_ok=False)
        payload = pickle.dumps(
            {
                "version": version,
                "recommender": rec,
                "forecast": fc,
                "experiments": stretch,
                "metrics": metrics,
            },
            protocol=5,
        )
        (folder / "bundle.pkl").write_bytes(payload)
        (folder / "metrics.json").write_text(
            json.dumps(metrics, indent=2, allow_nan=False)
        )
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        mlflow.set_experiment("scenthaus-simulated")
        with mlflow.start_run(run_name=version) as run:
            mlflow.log_params(
                {
                    "data_hash": validation["data_hash"],
                    "simulated": True,
                    "split": "time",
                    "users": matrix.shape[0],
                    "weights": str(rec["weights"]),
                }
            )
            mlflow.log_metrics(
                {
                    "hybrid_ndcg_5": evaluation["metrics"]["hybrid"]["ndcg_at_5"],
                    "forecast_wape": fc["metrics"]["wape"],
                    "coverage80": fc["metrics"]["coverage80"],
                    "coverage95": fc["metrics"]["coverage95"],
                }
            )
            mlflow.log_artifact(str(folder / "metrics.json"))
            mlflow.log_artifact(str(folder / "bundle.pkl"))
            run_id = run.info.run_id
        db.add(
            ModelRun(
                version=version,
                metrics=metrics,
                data_hash=validation["data_hash"],
                mlflow_run_id=run_id,
            )
        )
        origin = datetime.fromisoformat(fc["series"][0]["history"][-1]["week"]).date()
        for series in fc["series"]:
            for f in series["forecast"]:
                db.add(
                    ForecastSnapshot(
                        version=version,
                        sku=series["sku"],
                        origin=origin,
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
        manifest = {"version": version, "sha256": hashlib.sha256(payload).hexdigest()}
        temp = settings.artifact_dir / "current.tmp"
        with temp.open("w") as handle:
            json.dump(manifest, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, settings.artifact_dir / "current.json")
        (settings.artifact_dir / "evaluation.json").write_text(
            json.dumps(metrics, indent=2, allow_nan=False)
        )
        print(
            json.dumps(
                {
                    "version": version,
                    "recommender": evaluation,
                    "forecast": fc["metrics"],
                },
                indent=2,
            ),
            flush=True,
        )


if __name__ == "__main__":
    train()
