"""Initialize a clean SCENTHAUS demo database during a Vercel build."""

from contextlib import contextmanager
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Iterator

from alembic import command
from alembic.config import Config
from huggingface_hub import hf_hub_download
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine

from .catalog import FAMILIES, catalog, slugify
from .config import settings
from .database import SessionLocal, engine
from .ml.serving import store
from .models import ForecastSnapshot, ModelRun, Product, Variant
from .seed import seed


def verify_catalog(db):
    rows = catalog()["products"]
    product_fields = [
        "slug",
        "name",
        "brand",
        "concentration",
        "category",
        "gender",
        "description",
        "notes",
        "accords",
        "seasons",
        "occasions",
        "longevity",
        "sillage",
        "launch_date",
        "image_path",
        "source_metadata",
    ]
    expected_products = {}
    expected_variants = {}
    variant_id = 1
    for row in rows:
        family = row["category"]
        expected_products[row["id"]] = {
            "slug": slugify(row["name"], row["brand"]),
            "name": row["name"],
            "brand": row["brand"],
            "concentration": row["concentration"],
            "category": family,
            "gender": row["gender"],
            "description": (
                f"Explore {row['name']} by {row['brand']}. "
                "Product photograph and key notes are sourced; SGD prices, availability and style tags are demo annotations."
            ),
            "notes": {"top": [], "heart": row["key_notes"], "base": []},
            "accords": FAMILIES[family],
            "seasons": ["Summer", "Spring"]
            if family in {"Fresh", "Floral"}
            else ["Autumn", "Winter"],
            "occasions": ["Office", "Everyday"]
            if family in {"Fresh", "Woody"}
            else ["Evening", "Gift"],
            "longevity": 0,
            "sillage": "Not rated",
            "launch_date": date(2026, 9, 21)
            if row["id"] > 146
            else date(2025, 3, 31),
            "image_path": row["image_path"],
            "source_metadata": row,
        }
        for size in row["sizes_ml"]:
            expected_variants[variant_id] = (
                row["id"],
                f"SH-{row['id']:03}-{size}",
                size,
            )
            variant_id += 1

    products = {row.id: row for row in db.scalars(select(Product))}
    variants = {row.id: row for row in db.scalars(select(Variant))}
    product_mismatches = {
        product_id
        for product_id in set(products) | set(expected_products)
        if product_id not in products
        or product_id not in expected_products
        or any(
            getattr(products[product_id], field) != expected_products[product_id][field]
            for field in product_fields
        )
    }
    variant_mismatches = {
        variant_id
        for variant_id in set(variants) | set(expected_variants)
        if variant_id not in variants
        or variant_id not in expected_variants
        or (
            variants[variant_id].product_id,
            variants[variant_id].sku,
            variants[variant_id].size_ml,
        )
        != expected_variants[variant_id]
    }
    if product_mismatches or variant_mismatches:
        raise RuntimeError(
            f"The configured database has {len(products)} catalogue products and "
            f"{len(variants)} SKU sizes; this release requires the {len(expected_products)} "
            f"real-product catalogue and {len(expected_variants)} stable SKU sizes. "
            f"Mismatched product IDs: {sorted(product_mismatches)[:5]}; "
            f"mismatched SKU IDs: {sorted(variant_mismatches)[:5]}. "
            "No catalogue rows were overwritten. Configure a new, empty, "
            "dedicated PostgreSQL database before promoting this release."
        )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_search_encoder():
    from ml.core import config as ml_config

    cfg = ml_config("search")
    folder = settings.artifact_dir / "encoder"
    folder.mkdir(parents=True, exist_ok=True)
    files = {
        Path(cfg["vercel_encoder_file"]).name: cfg["vercel_encoder_file"],
        "tokenizer.json": "tokenizer.json",
    }
    hashes = {}
    for target_name, upstream_name in files.items():
        source = Path(
            hf_hub_download(
                repo_id=cfg["vercel_encoder_repo"],
                filename=upstream_name,
                revision=cfg["vercel_encoder_revision"],
            )
        )
        target = folder / target_name
        if not target.exists() or sha256(target) != sha256(source):
            shutil.copy2(source, target)
        hashes[target_name] = sha256(target)
    model_name = Path(cfg["vercel_encoder_file"]).name
    if hashes[model_name] != cfg["vercel_encoder_sha256"]:
        raise RuntimeError("Downloaded Vercel ONNX model failed its pinned checksum")
    (folder / "encoder.json").write_text(
        json.dumps(
            {
                "repo": cfg["vercel_encoder_repo"],
                "revision": cfg["vercel_encoder_revision"],
                "license": "Apache-2.0",
                "files": hashes,
            },
            indent=2,
        )
    )


def package_runtime_ml(service_root: Path, source_root: Path) -> Path:
    """Copy the importable ML runtime into the API service bundle."""
    source = source_root / "ml"
    destination = service_root / "ml"
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for name in [
        "__init__.py",
        "core.py",
        "embeddings.py",
        "rec_serving.py",
        "search.py",
        "tracking.py",
    ]:
        shutil.copy2(source / name, destination / name)
    shutil.copytree(source / "configs", destination / "configs")
    return destination


@contextmanager
def build_lock(lock_engine: Engine) -> Iterator[None]:
    # Neon keeps an idle transaction active during CPU-only model training.
    # The direct connection holds the lock until commit or rollback on exit.
    # Scope the idle timeout override to this build transaction only.
    with lock_engine.begin() as lock:
        lock.execute(text("SET LOCAL idle_in_transaction_session_timeout = '0'"))
        lock.execute(text("SELECT pg_advisory_xact_lock(736284105)"))
        yield


def initialize():
    if os.environ.get("VERCEL") and not os.environ.get("DATABASE_URL"):
        raise RuntimeError(
            "Set DATABASE_URL for a dedicated PostgreSQL database before deploying SCENTHAUS"
        )
    direct_url = os.environ.get("DATABASE_URL_UNPOOLED", "").strip()
    if os.environ.get("VERCEL") and not direct_url:
        raise RuntimeError(
            "Set DATABASE_URL_UNPOOLED to the direct PostgreSQL connection for the Vercel build lock"
        )
    if direct_url.startswith(("postgres://", "postgresql://")):
        direct_url = "postgresql+psycopg://" + direct_url.split("://", 1)[1]
    lock_engine = create_engine(direct_url) if direct_url else engine
    root = Path(__file__).resolve().parents[1]
    with build_lock(lock_engine):
        print("Migrating dedicated PostgreSQL schema", flush=True)
        alembic = Config(str(root / "alembic.ini"))
        alembic.set_main_option("script_location", str(root / "alembic"))
        command.upgrade(alembic, "head")
        seed()
        with SessionLocal() as db:
            verify_catalog(db)

        model = store.get()
        if model is not None:
            from ml.core import snapshot

            if (
                snapshot()["data_hash"]
                != model["metrics"]["validation"]["data_hash"]
            ):
                print("Serving bundle is stale for this consented dataset", flush=True)
                model = None
        if model is None:
            if not os.environ.get("SCENTHAUS_BUILD_TRAINING"):
                raise RuntimeError(
                    "No verified serving bundle is available; run the Vercel build entrypoint"
                )
            print("Training the versioned serving bundle from simulated data", flush=True)
            from ml.train_all import main as train_models

            train_models()
            model = store.get()
        if model is None:
            raise RuntimeError("Model training did not publish a serving bundle")

        if os.environ.get("VERCEL"):
            prepare_search_encoder()

        with SessionLocal() as db:
            version = model["version"]
            if not db.get(ModelRun, version):
                db.add(
                    ModelRun(
                        version=version,
                        metrics=model["metrics"],
                        data_hash=model["metrics"]["validation"]["data_hash"],
                    )
                )
                for series in model["forecast"]["series"]:
                    origin = datetime.fromisoformat(
                        series["history"][-1]["week"]
                    ).date()
                    for row in series["forecast"]:
                        db.add(
                            ForecastSnapshot(
                                version=version,
                                sku=series["sku"],
                                origin=origin,
                                target_week=datetime.fromisoformat(
                                    row["week"]
                                ).date(),
                                **{
                                    key: row[key]
                                    for key in [
                                        "prediction",
                                        "lower80",
                                        "upper80",
                                        "lower95",
                                        "upper95",
                                    ]
                                },
                            )
                        )
                db.commit()
        if os.environ.get("VERCEL"):
            package_runtime_ml(root, root.parent)
        print(
            "Database initialized; serving artifacts verified. Historical orders are simulated.",
            flush=True,
        )


if __name__ == "__main__":
    initialize()
