"""Real catalog references with explicitly simulated commercial annotations."""

from datetime import date
import json
from pathlib import Path
import re
import unicodedata

from sqlalchemy.orm import Session

from .models import Product, Variant

ACCORDS = ["citrus", "fresh", "aquatic", "floral", "woody", "amber", "spicy", "sweet"]
FAMILIES = {
    "Fresh": ["citrus", "fresh", "aquatic"],
    "Woody": ["woody", "spicy", "fresh"],
    "Floral": ["floral", "fresh", "sweet"],
    "Amber": ["amber", "sweet", "spicy"],
}
CATALOG_PATH = Path(__file__).with_name("real_catalog.json")


def catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text())


def slugify(name: str, brand: str) -> str:
    value = (
        unicodedata.normalize("NFKD", brand + " " + name)
        .encode("ascii", "ignore")
        .decode()
    )
    return re.sub("[^a-z0-9]+", "-", value.lower()).strip("-")[:100]


def seed_catalog(db: Session) -> None:
    variant_id = 1
    luxury = {
        "Creed",
        "Tom Ford",
        "Maison Francis Kurkdjian",
        "Le Labo",
        "Byredo",
        "Parfums de Marly",
        "Initio Parfums Privés",
    }
    for row in catalog()["products"]:
        pid = row["id"]
        family = row["category"]
        db.add(
            Product(
                id=pid,
                slug=slugify(row["name"], row["brand"]),
                name=row["name"],
                brand=row["brand"],
                concentration=row["concentration"],
                category=family,
                gender=row["gender"],
                description=f"Explore {row['name']} by {row['brand']}. "
                "Product photograph and key notes are sourced; SGD prices, availability and style tags are demo annotations.",
                # Preserve key notes without inventing a top/heart/base pyramid.
                notes={"top": [], "heart": row["key_notes"], "base": []},
                accords=FAMILIES[family],
                seasons=["Summer", "Spring"]
                if family in {"Fresh", "Floral"}
                else ["Autumn", "Winter"],
                occasions=["Office", "Everyday"]
                if family in {"Fresh", "Woody"}
                else ["Evening", "Gift"],
                longevity=0,
                sillage="Not rated",
                # Simulated availability, never a manufacturer release-date claim.
                launch_date=date(2026, 9, 21) if pid > 146 else date(2025, 3, 31),
                image_path=row["image_path"],
                source_metadata=row,
            )
        )
        db.flush()
        base_price = (280 if row["brand"] in luxury else 115) + pid % 7 * 8
        for size in row["sizes_ml"]:
            db.add(
                Variant(
                    id=variant_id,
                    product_id=pid,
                    sku=f"SH-{pid:03}-{size}",
                    size_ml=size,
                    price=round(base_price * (size / 50) ** 0.65, 2),
                    stock=0
                    if pid in {7, 27} or (pid + size) % 19 == 0
                    else (pid * 7 + size) % 120 + 8,
                    lead_time_weeks=2 + pid % 2,
                )
            )
            variant_id += 1
