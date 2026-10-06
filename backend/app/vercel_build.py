"""Create untracked serving artifacts in an isolated Vercel build environment."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import venv


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"


def main():
    if not os.environ.get("DATABASE_URL"):
        raise RuntimeError("Set DATABASE_URL before building the SCENTHAUS API")
    if os.environ.get("VERCEL") and not os.environ.get("DATABASE_URL_UNPOOLED"):
        raise RuntimeError(
            "Set DATABASE_URL_UNPOOLED to a direct PostgreSQL URL for safe Vercel initialization"
        )

    training_env = Path(tempfile.gettempdir()) / "scenthaus-vercel-training"
    if training_env.exists():
        shutil.rmtree(training_env)
    venv.EnvBuilder(with_pip=True).create(training_env)
    python = training_env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "torch==2.9.0",
            "--index-url",
            "https://download.pytorch.org/whl/cpu",
        ],
        check=True,
        cwd=BACKEND,
    )
    subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "-r",
            str(BACKEND / "requirements-training.txt"),
        ],
        check=True,
        cwd=BACKEND,
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(BACKEND), str(ROOT), environment.get("PYTHONPATH", "")]
    )
    environment["SCENTHAUS_BUILD_TRAINING"] = "1"
    environment.setdefault(
        "HF_HOME", str(Path(tempfile.gettempdir()) / "scenthaus-hf-cache")
    )
    subprocess.run(
        [str(python), "-m", "app.vercel_init"],
        check=True,
        cwd=BACKEND,
        env=environment,
    )


if __name__ == "__main__":
    main()
