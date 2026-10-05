"""Run phase checks with the database selected by DATABASE_URL."""

import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str], cwd: Path = ROOT) -> None:
    subprocess.run(args, cwd=cwd, env=os.environ, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=int, default=0)
    args = parser.parse_args()
    os.environ["PYTHONPATH"] = str(ROOT / "backend") + os.pathsep + str(ROOT)
    os.environ.setdefault("ADMIN_PASSWORD", "local-fixture-only-password")
    run([sys.executable, "-m", "alembic", "upgrade", "head"], ROOT / "backend")
    if args.phase >= 1:
        run([sys.executable, "-m", "app.seed"])
    paths = ["ml/tests/test_scaffold.py"] if args.phase == 0 else ["ml/tests"]
    run([sys.executable, "-m", "pytest", *paths, "-q"])
    run([sys.executable, "-m", "ruff", "check", "."])
    if args.phase == 0:
        run(["npm", "--prefix", "frontend", "run", "build"])


if __name__ == "__main__":
    main()
