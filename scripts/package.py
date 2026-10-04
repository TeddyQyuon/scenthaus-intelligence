from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
target = root.parent / "SCENTHAUS-Intelligence.zip"
excluded = {
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".git",
    "mlruns",
    "dist",
    "test-results",
}
with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
    for p in sorted(root.rglob("*")):
        if (
            p.is_file()
            and not any(n in excluded for n in p.parts)
            and p.name not in [".env", "mlflow.db"]
            and not p.name.endswith(("-wal", "-shm", ".pyc"))
        ):
            archive.write(p, p.relative_to(root.parent))
print(target)
