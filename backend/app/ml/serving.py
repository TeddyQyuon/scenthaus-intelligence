import hashlib, json, pickle, re, threading
from functools import lru_cache
from app.config import settings


class ModelStore:
    def __init__(self):
        self.lock = threading.RLock()
        self.bundle = None

    def get(self):
        manifest_path = settings.artifact_dir / "current.json"
        if not manifest_path.exists():
            return None
        manifest = json.loads(manifest_path.read_text())
        version = manifest["version"]
        with self.lock:
            if self.bundle is None or self.bundle["version"] != version:
                if not re.fullmatch(r"[0-9]{8}T[0-9]{6}-[a-f0-9]{8}", version):
                    raise ValueError("Invalid model path")
                payload = (settings.artifact_dir / version / "bundle.pkl").read_bytes()
                if hashlib.sha256(payload).hexdigest() != manifest["sha256"]:
                    raise ValueError("Model checksum mismatch")
                # Only trusted, locally trained artifacts. Never accept uploaded pickle files.
                self.bundle = pickle.loads(payload)
                self.static.cache_clear()
            return self.bundle

    @lru_cache(maxsize=128)
    def static(self, version, kind, pid):
        model = self.get()["recommender"]
        i = model["index"][pid]
        return model["cf" if kind == "also-bought" else "content"][i].copy()


store = ModelStore()
