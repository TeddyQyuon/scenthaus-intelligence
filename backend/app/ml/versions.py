"""Checksum-verified immutable local model releases and atomic activation."""

from pathlib import Path
import hashlib
import json
import os
import re
import uuid

VERSION = re.compile(r"[0-9]{8}T[0-9]{6}-[a-f0-9]{8}(?:-[a-f0-9]{8})?")


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root: Path, version: str) -> dict:
    if not VERSION.fullmatch(version):
        raise ValueError("Invalid model version")
    folder = root / version
    manifest = json.loads((folder / "manifest.json").read_text())
    if manifest.get("version") != version or not manifest.get("files"):
        raise ValueError("Invalid model manifest")
    for name, expected in manifest["files"].items():
        target = folder / name
        if target.is_symlink() or not target.resolve().is_relative_to(folder.resolve()):
            raise ValueError("Invalid model file path")
        if checksum(target) != expected:
            raise ValueError(f"Model checksum mismatch: {name}")
    return manifest


def activate(root: Path, version: str) -> None:
    verify(root, version)
    pointer = {
        "version": version,
        "manifest_sha256": checksum(root / version / "manifest.json"),
    }
    temp = root / f"current-{uuid.uuid4().hex}.tmp"
    with temp.open("w") as handle:
        json.dump(pointer, handle)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, root / "current.json")


def resolve_current(root: Path) -> tuple[Path, dict]:
    pointer = json.loads((root / "current.json").read_text())
    version = pointer["version"]
    if not VERSION.fullmatch(version):
        raise ValueError("Invalid model version")
    folder = root / version
    if checksum(folder / "manifest.json") != pointer["manifest_sha256"]:
        raise ValueError("Model manifest checksum mismatch")
    return folder, verify(root, version)
