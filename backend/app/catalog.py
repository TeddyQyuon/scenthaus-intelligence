import re
from datetime import date
from .models import Product, Variant

ACCORDS = ["citrus", "fresh", "aquatic", "floral", "woody", "amber", "spicy", "sweet"]
ROWS = [
    ("Citrus Theory", "Atelier 08", "Fresh", 108),
    ("After Hours", "Maison Oblique", "Amber", 158),
    ("Soft Geometry", "Studio Sillage", "Floral", 128),
    ("Santal Study", "Atelier 08", "Woody", 148),
    ("Salt & Air", "Coastline", "Fresh", 98),
    ("Rose Unscripted", "Maison Oblique", "Floral", 138),
    ("Amber Archive", "Nocturne", "Amber", 168),
    ("Green Interval", "Botanique", "Fresh", 118),
    ("Cedar Notes", "Studio Sillage", "Woody", 128),
    ("Moon Garden", "Botanique", "Floral", 148),
    ("Velvet Smoke", "Nocturne", "Amber", 178),
    ("Morning Ritual", "Coastline", "Fresh", 88),
    ("Paper Woods", "Atelier 08", "Woody", 138),
    ("Peony Room", "Studio Sillage", "Floral", 118),
    ("Golden Hour", "Maison Oblique", "Amber", 148),
    ("Rain on Stone", "Coastline", "Fresh", 108),
    ("Moss Memory", "Botanique", "Woody", 128),
    ("Iris Index", "Atelier 08", "Floral", 158),
    ("Tonka Letters", "Nocturne", "Amber", 158),
    ("Bergamot Society", "Studio Sillage", "Fresh", 118),
    ("Hinoki Quiet", "Botanique", "Woody", 168),
    ("Jasmine Cinema", "Maison Oblique", "Floral", 148),
    ("Spice District", "Nocturne", "Amber", 138),
    ("Ocean Dialect", "Coastline", "Fresh", 98),
    ("Vetiver Form", "Atelier 08", "Woody", 148),
    ("Neroli Days", "Botanique", "Floral", 128),
    ("Oud Perspective", "Maison Oblique", "Amber", 198),
    ("Tea at Three", "Studio Sillage", "Fresh", 108),
    ("Figue Studio", "Coastline", "Woody", 128),
    ("Petal Theory", "Botanique", "Floral", 138),
    ("Dusk Edition", "Nocturne", "Amber", 158),
    ("Mineral Skin", "Coastline", "Fresh", 118),
    ("Saffron Signal", "Maison Oblique", "Amber", 188),
    ("Forest Frequency", "Botanique", "Woody", 148),
    ("Bloom Sequence", "Studio Sillage", "Floral", 138),
    ("Daylight 02", "Atelier 08", "Fresh", 108),
]
FAMILIES = {
    "Fresh": (
        ["citrus", "fresh", "aquatic"],
        ["bergamot", "mandarin", "neroli"],
        ["green tea", "lavender", "sea salt"],
        ["white musk", "cedar", "vetiver"],
    ),
    "Woody": (
        ["woody", "spicy", "fresh"],
        ["cardamom", "grapefruit", "juniper"],
        ["cedar", "iris", "sage"],
        ["sandalwood", "vetiver", "oakmoss"],
    ),
    "Floral": (
        ["floral", "fresh", "sweet"],
        ["pear", "pink pepper", "mandarin"],
        ["jasmine", "rose", "peony"],
        ["white musk", "cashmere wood", "vanilla"],
    ),
    "Amber": (
        ["amber", "sweet", "spicy"],
        ["saffron", "cinnamon", "orange"],
        ["benzoin", "rose", "tonka"],
        ["amber", "vanilla", "oud"],
    ),
}


def seed_catalog(db):
    for i, (name, brand, family, price) in enumerate(ROWS, 1):
        accords, *pyramid = FAMILIES[family]
        shift = (i // 4) % 3
        notes = {
            k: [values[shift], values[(shift + 1) % 3]]
            for k, values in zip(["top", "heart", "base"], pyramid)
        }
        notes["heart"].append(
            [
                "fig leaf",
                "black tea",
                "ambrette",
                "pink pepper",
                "iso e super",
                "lemon zest",
            ][i % 6]
        )
        db.add(
            Product(
                id=i,
                slug=re.sub("[^a-z0-9]+", "-", name.lower()).strip("-"),
                name=name,
                brand=brand,
                category=family,
                concentration="Parfum"
                if i in [2, 7, 11, 18, 21, 27, 33]
                else "EDT"
                if i in [5, 12, 17, 24, 26, 36]
                else "EDP",
                gender="Unisex"
                if i % 5
                else "Feminine"
                if family == "Floral"
                else "Masculine",
                description=f"{name} unfolds through {notes['top'][0]}, {notes['heart'][0]} and {notes['base'][0]}. A {family.lower()} composition for your own rhythm.",
                notes=notes,
                accords=accords,
                seasons=["Summer", "Spring"]
                if family in ["Fresh", "Floral"]
                else ["Autumn", "Winter"],
                occasions=["Office", "Everyday"]
                if family in ["Fresh", "Woody"]
                else ["Evening", "Gift"],
                longevity=5 + i % 6,
                sillage="Soft" if i % 3 == 0 else "Moderate" if i % 3 == 1 else "Bold",
                launch_date=date(2026, 9, 21) if i > 32 else date(2024, 9, 30),
            )
        )
        db.flush()
        for j, (size, factor) in enumerate([(30, 0.62), (50, 1), (100, 1.55)]):
            db.add(
                Variant(
                    id=(i - 1) * 3 + j + 1,
                    product_id=i,
                    sku=f"SH-{i:03}-{size}",
                    size_ml=size,
                    price=round(price * factor, 2),
                    stock=0
                    if i in [7, 27] or (i + j) % 17 == 0
                    else (i * 7 + j * 23) % 120 + 8,
                    lead_time_weeks=2 + i % 2,
                )
            )
