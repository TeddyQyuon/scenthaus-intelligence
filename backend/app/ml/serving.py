import json, pickle, threading
from .versions import resolve_current
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
                folder, _ = resolve_current(settings.artifact_dir)
                payload = (folder / "bundle.pkl").read_bytes()
                # Only trusted, locally trained artifacts. Never accept uploaded pickle files.
                self.bundle = pickle.loads(payload)
                for key in ["torch_recommender", "search_path"]:
                    relative = self.bundle[key]
                    target = folder / relative
                    if not target.resolve().is_relative_to(folder.resolve()):
                        raise ValueError("Invalid model asset path")
                    self.bundle[key] = str(target)
                self.static.cache_clear()
            return self.bundle

    @lru_cache(maxsize=128)
    def static(self, version, kind, pid):
        model = self.get()["recommender"]
        i = model["index"][pid]
        return model["cf" if kind == "also-bought" else "content"][i].copy()


store = ModelStore()
