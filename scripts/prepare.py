"""Migrate, seed an empty demo database and train with the shared harness."""

from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
os.environ["PYTHONPATH"] = str(ROOT / "backend") + os.pathsep + str(ROOT)
os.chdir(ROOT / "backend")  # settings read the configured backend/.env


if __name__ == "__main__":
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    subprocess.run([sys.executable, "-m", "app.seed"], check=True)
    subprocess.run([sys.executable, "-m", "ml.train_all"], check=True)
