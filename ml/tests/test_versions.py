"""Rollback verifies every dependency, including cached arrays and paths."""

from pathlib import Path
import json
import pytest
from app.ml.versions import checksum, verify, activate, resolve_current
from ml.tracking import tracked
from ml.core import snapshot


def release(root: Path, version: str, payload: bytes) -> Path:
    folder = root / version
    folder.mkdir()
    (folder / "cached.npz").write_bytes(payload)
    (folder / "manifest.json").write_text(
        json.dumps(
            {
                "version": version,
                "files": {"cached.npz": checksum(folder / "cached.npz")},
            }
        )
    )
    return folder


def test_activation_rollback_and_corruption(tmp_path):
    a, b = "20261005T120000-1234abcd-00000001", "20261005T120001-1234abcd-00000002"
    one = release(tmp_path, a, b"first")
    two = release(tmp_path, b, b"second")
    activate(tmp_path, a)
    assert resolve_current(tmp_path)[0] == one
    activate(tmp_path, b)
    assert resolve_current(tmp_path)[0] == two
    activate(tmp_path, a)
    before = (tmp_path / "current.json").read_bytes()
    (two / "cached.npz").write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="checksum"):
        activate(tmp_path, b)
    assert (tmp_path / "current.json").read_bytes() == before
    with pytest.raises(ValueError, match="version"):
        verify(tmp_path, "../unsafe")


def test_manifest_cannot_read_outside_release(tmp_path):
    version = "20261005T120000-1234abcd-00000001"
    folder = release(tmp_path, version, b"ok")
    (tmp_path / "secret.txt").write_text("fixture")
    (folder / "manifest.json").write_text(
        json.dumps(
            {
                "version": version,
                "files": {"../secret.txt": checksum(tmp_path / "secret.txt")},
            }
        )
    )
    with pytest.raises(ValueError, match="path"):
        activate(tmp_path, version)


def test_actual_mlflow_run_records_version_params_and_metrics(tmp_path, monkeypatch):
    from app.config import settings
    from ml import tracking
    from mlflow import MlflowClient

    monkeypatch.setattr(
        settings, "mlflow_tracking_uri", f"sqlite:///{tmp_path}/tracking.db"
    )
    monkeypatch.setattr(tracking, "ARTIFACTS", tmp_path / "models")
    monkeypatch.setattr(
        tracking,
        "snapshot",
        lambda: {
            "data_hash": "verified-fixture",
            "orders": [1],
            "train_end": "2025-01-01",
            "val_end": "2025-02-01",
            "end": "2025-03-01",
        },
    )

    @tracked("test-run")
    def task():
        return {
            "results": {
                "baseline": {"ndcg": 0.4, "MRR@10": 0.5},
                "neural": {"ndcg": 0.3},
            }
        }

    assert task()["results"]["baseline"]["ndcg"] == 0.4
    client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
    runs = client.search_runs(
        [client.get_experiment_by_name("scenthaus-simulated").experiment_id]
    )
    assert len(runs) == 1 and runs[0].info.status == "FINISHED"
    assert runs[0].data.params["dataset_hash"] == "verified-fixture"
    assert runs[0].data.metrics["results.baseline.ndcg"] == 0.4
    assert runs[0].data.metrics["results.baseline.MRR_10"] == 0.5
    assert client.list_artifacts(runs[0].info.run_id, "provenance")


def test_quiz_features_respect_consent_and_hash_changes():
    from sqlalchemy import delete
    from datetime import datetime
    from app.database import SessionLocal
    from app.models import User, QuizProfile

    with SessionLocal() as db:
        user = User(consent=False)
        db.add(user)
        db.flush()
        uid = user.id
        db.add(
            QuizProfile(
                user_id=uid,
                answers={},
                weights={"fresh": 0.8},
                created_at=datetime(2025, 4, 1),
            )
        )
        db.commit()
    try:
        before = snapshot()
        assert uid not in set(before["quiz"].user_id)
        with SessionLocal() as db:
            db.get(User, uid).consent = True
            db.commit()
        after = snapshot()
        assert uid in set(after["quiz"].user_id)
        assert before["data_hash"] != after["data_hash"]
    finally:
        with SessionLocal() as db:
            db.execute(delete(QuizProfile).where(QuizProfile.user_id == uid))
            db.execute(delete(User).where(User.id == uid))
            db.commit()
