"""Install the native development environment (Python 3.11+, Node 22+)."""

from pathlib import Path
import os
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    venv.EnvBuilder(with_pip=True).create(ROOT / ".venv")
    python = (
        ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    )
    subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "torch==2.9.0",
            "--index-url",
            "https://download.pytorch.org/whl/cpu",
        ],
        check=True,
    )
    subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "-r",
            "backend/requirements-training.txt",
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(["npm", "--prefix", "frontend", "ci"], cwd=ROOT, check=True)
    print(
        "Dependencies ready. Configure backend/.env, then run .venv/bin/python scripts/prepare.py."
    )
