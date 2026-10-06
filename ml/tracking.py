"""MLflow tracking for every entrypoint; no emails, credentials or raw events."""

from functools import wraps
from pathlib import Path
import hashlib
import importlib.metadata
import json
import math
import platform
import re
import subprocess
import yaml
from typing import Callable, Any
from app.config import settings
from .core import ROOT, ARTIFACTS, REPORTS, snapshot, save_json


def runtime() -> dict:
    packages = {}
    for name in [
        "torch",
        "numpy",
        "pandas",
        "sentence-transformers",
        "lightgbm",
        "mlflow",
    ]:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = "absent"
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "packages": packages,
    }


def numeric(value: Any, prefix: str = "") -> dict[str, float]:
    result = {}
    if isinstance(value, dict):
        for key, item in value.items():
            result.update(numeric(item, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            result.update(numeric(item, f"{prefix}.{i}"))
    elif (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    ):
        result[re.sub(r"[^a-zA-Z0-9_. /:-]", "_", prefix)] = float(value)
    return result


def tracked(name: str) -> Callable:
    def decorate(function: Callable) -> Callable:
        @wraps(function)
        def run(*args: Any, **kwargs: Any) -> Any:
            import mlflow

            data = snapshot()  # validation is mandatory before starting a run
            mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
            mlflow.set_experiment("scenthaus-simulated")
            with mlflow.start_run(run_name=name) as active:
                mlflow.set_tags(
                    {"simulated_data": "true", "split": "time-based", "phase": name}
                )
                configs = {
                    p.name: p.read_text()
                    for p in sorted((ROOT / "ml/configs").glob("*.yaml"))
                }
                mlflow.log_params(
                    {
                        "dataset_hash": data["data_hash"],
                        "config_hash": hashlib.sha256(
                            json.dumps(configs, sort_keys=True).encode()
                        ).hexdigest(),
                        "order_lines": len(data["orders"]),
                        "train_end": str(data["train_end"]),
                        "validation_end": str(data["val_end"]),
                        "test_end": str(data["end"]),
                    }
                )
                if f"{name}.yaml" in configs:
                    hyperparameters = yaml.safe_load(configs[f"{name}.yaml"])
                    mlflow.log_params(
                        {
                            f"{name}.{key}": json.dumps(value, sort_keys=True)
                            if isinstance(value, (dict, list))
                            else value
                            for key, value in hyperparameters.items()
                        }
                    )
                provenance = {
                    "dataset_hash": data["data_hash"],
                    "runtime": runtime(),
                    "configs": configs,
                }
                try:
                    provenance["git_commit"] = subprocess.check_output(
                        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                    ).strip()
                except (OSError, subprocess.CalledProcessError):
                    provenance["git_commit"] = "unavailable"
                result = function(*args, **kwargs)
                if isinstance(result, dict):
                    summary = {
                        k: result[k]
                        for k in [
                            "models",
                            "results",
                            "recommender",
                            "forecast",
                            "weights",
                        ]
                        if k in result
                    }
                    if name == "forecast":
                        summary = {"results": result["results"]}
                    mlflow.log_metrics(numeric(summary))
                provenance["input_arrays"] = {
                    str(p.relative_to(ARTIFACTS)): hashlib.sha256(
                        p.read_bytes()
                    ).hexdigest()
                    for p in sorted(ARTIFACTS.rglob("*.npy"))
                }
                folder = ARTIFACTS / "runs" / active.info.run_id
                save_json(folder / "provenance.json", provenance)
                mlflow.log_artifact(str(folder / "provenance.json"), "provenance")
                mlflow.log_artifacts(str(ROOT / "ml/configs"), "configs")
                report = REPORTS / f"{name}.md"
                if report.exists():
                    mlflow.log_artifact(str(report), "reports")
                # Model checkpoints stay outside Git and are retained in the tracking artifact store.
                if name in ["recommender", "forecast"]:
                    target = ARTIFACTS / name
                    for path in sorted(target.glob("*.pt")):
                        mlflow.log_artifact(str(path), "checkpoints")
                save_json(
                    ARTIFACTS / f"{name}-run.json",
                    {"run_id": active.info.run_id, **provenance},
                )
                return result

        return run

    return decorate
