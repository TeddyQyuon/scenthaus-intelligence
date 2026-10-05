"""Prepare a fresh demo database, train forecasts, publish and check Phase 5."""

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
os.environ["PYTHONPATH"] = str(ROOT / "backend") + os.pathsep + str(ROOT)
os.environ.setdefault("ADMIN_PASSWORD", "local-fixture-only-password")


def run(args: list[str], cwd: Path = ROOT) -> None:
    subprocess.run([sys.executable, *args], cwd=cwd, env=os.environ, check=True)


if __name__ == "__main__":
    run(["-m", "alembic", "upgrade", "head"], ROOT / "backend")
    run(["-m", "app.seed"])
    run(["-m", "ml.forecast"])
    run(["-m", "ml.publish_base"])
    run(
        [
            "-m",
            "pytest",
            "ml/tests/test_forecast.py",
            "ml/tests/test_metrics.py",
            "ml/tests/test_data.py",
            "ml/tests/test_scaffold.py",
            "-q",
        ]
    )
    run(["-m", "ruff", "check", "."])
