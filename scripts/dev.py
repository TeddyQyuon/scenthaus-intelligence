"""Start API, React and MLflow as native processes; Ctrl-C stops all three."""

from pathlib import Path
import os
import signal
import subprocess
import sys
import time
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "backend/.env")
os.environ["PYTHONPATH"] = str(ROOT / "backend") + os.pathsep + str(ROOT)


def main() -> None:
    processes = []
    commands = [
        (
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            ROOT / "backend",
        ),
        (["npm", "run", "dev", "--", "--host", "127.0.0.1"], ROOT / "frontend"),
        (
            [
                sys.executable,
                "-m",
                "mlflow",
                "server",
                "--host",
                "127.0.0.1",
                "--port",
                "5000",
                "--backend-store-uri",
                os.environ.get(
                    "MLFLOW_TRACKING_URI",
                    "sqlite:///" + str(ROOT / "backend/mlflow.db"),
                ),
            ],
            ROOT / "backend",
        ),
    ]

    def stop(signum=None, frame=None):
        for process in processes:
            process.terminate()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        for command, cwd in commands:
            processes.append(subprocess.Popen(command, cwd=cwd, env=os.environ))
        print(
            "Storefront http://localhost:5173 · API http://localhost:8000 · MLflow http://localhost:5000",
            flush=True,
        )
        while all(p.poll() is None for p in processes):
            time.sleep(0.5)
    finally:
        stop()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
