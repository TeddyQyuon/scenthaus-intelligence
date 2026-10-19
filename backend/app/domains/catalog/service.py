import csv
import io
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DatabaseSession

from ...catalog import slugify
from ...models import AuditLog, Product, Tenant, Variant
from .schemas import ProductCreate, ProductUpdate, VariantCreate, VariantUpdate


def serialize_product(product: Product, variants: list[Variant]) -> dict:
    return {
        "id": product.id,
        "tenant_id": product.tenant_id,
        "slug": product.slug,
        "name": product.name,
        "brand": product.brand,
        "concentration": product.concentration,
        "category": product.category,
        "gender": product.gender,
        "description": product.description,
        "notes": product.notes,
        "accords": product.accords,
        "seasons": product.seasons,
        "occasions": product.occasions,
        "longevity": product.longevity,
        "sillage": product.sillage,
        "launch_date": product.launch_date.isoformat() if product.launch_date else None,
        "pinned": product.pinned,
        "hidden": product.hidden,
        "image": product.image_path or "/images/product.png",
        "variants": [
            {
                "id": v.id,
                "sku": v.sku,
                "size_ml": v.size_ml,
                "price": float(v.price),
                "stock": v.stock,
                "lead_time_weeks": v.lead_time_weeks,
            }
            for v in variants
        ],
        "price_from": min((float(v.price) for v in variants), default=0.0),
        "in_stock": any(v.stock > 0 for v in variants),
    }


def list_tenant_products(
    db: DatabaseSession,
    tenant: Tenant,
    *,
    include_hidden: bool = False,
) -> list[dict]:
    stmt = select(Product).where(Product.tenant_id == tenant.id)
    if not include_hidden:
        stmt = stmt.where(Product.hidden.is_(False))
    products = db.scalars(stmt.order_by(Product.pinned.desc(), Product.id)).all()
    if not products:
        return []
    product_ids = [p.id for p in products]
    variants = db.scalars(
        select(Variant)
        .where(
            Variant.tenant_id == tenant.id,
            Variant.product_id.in_(product_ids),
        )
        .order_by(Variant.size_ml)
    ).all()
    by_product: dict[int, list[Variant]] = {pid: [] for pid in product_ids}
    for v in variants:
        by_product.setdefault(v.product_id, []).append(v)
    return [serialize_product(p, by_product.get(p.id, [])) for p in products]


def create_tenant_product(
    db: DatabaseSession,
    tenant: Tenant,
    actor_id: str,
    data: ProductCreate,
) -> dict:
    slug = data.slug or slugify(data.name, data.brand)
    if db.scalar(
        select(Product).where(
            Product.tenant_id == tenant.id,
            Product.slug == slug,
        )
    ):
        raise HTTPException(409, f"Product slug '{slug}' already exists in this store")

    seen_sizes: set[int] = set()
    for v in data.variants:
        if v.size_ml in seen_sizes:
            raise HTTPException(422, f"Duplicate variant size {v.size_ml}ml")
        seen_sizes.add(v.size_ml)

    product = Product(
        tenant_id=tenant.id,
        slug=slug,
        name=data.name,
        brand=data.brand,
        concentration=data.concentration,
        category=data.category,
        gender=data.gender,
        description=data.description,
        notes=data.notes.model_dump(),
        accords=data.accords,
        seasons=data.seasons,
        occasions=data.occasions,
        longevity=data.longevity,
        sillage=data.sillage,
        launch_date=data.launch_date,
        pinned=data.pinned,
        hidden=data.hidden,
        image_path=data.image_path,
        source_metadata={"created_by": actor_id},
    )
    db.add(product)
    try:
        db.flush()
        created_variants: list[Variant] = []
        for v in data.variants:
            variant = Variant(
                tenant_id=tenant.id,
                product_id=product.id,
                sku=v.sku,
                size_ml=v.size_ml,
                price=v.price,
                stock=v.stock,
                lead_time_weeks=v.lead_time_weeks,
            )
            db.add(variant)
            created_variants.append(variant)
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        err_msg = str(getattr(exc, "orig", exc)).lower()
        if "pkey" in err_msg or ("duplicate key" in err_msg and "id" in err_msg):
            from ...database import sync_postgres_sequences

            sync_postgres_sequences(db)
            db.add(product)
            db.flush()
            created_variants = []
            for v in data.variants:
                variant = Variant(
                    tenant_id=tenant.id,
                    product_id=product.id,
                    sku=v.sku,
                    size_ml=v.size_ml,
                    price=v.price,
                    stock=v.stock,
                    lead_time_weeks=v.lead_time_weeks,
                )
                db.add(variant)
                created_variants.append(variant)
            db.flush()
        else:
            raise HTTPException(409, "SKU or product slug conflicts with an existing item") from exc

    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor=actor_id,
            action="catalog.product_created",
            detail={"product_id": product.id, "slug": product.slug},
        )
    )
    db.commit()
    return serialize_product(product, created_variants)


def update_tenant_product(
    db: DatabaseSession,
    tenant: Tenant,
    actor_id: str,
    product_id: int,
    data: ProductUpdate,
) -> dict:
    product = db.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.tenant_id == tenant.id,
        )
    )
    if product is None:
        raise HTTPException(404, "Product not found")

    updates = data.model_dump(exclude_unset=True)
    if "notes" in updates and data.notes is not None:
        updates["notes"] = data.notes.model_dump()
    for field, value in updates.items():
        setattr(product, field, value)

    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor=actor_id,
            action="catalog.product_updated",
            detail={"product_id": product.id, "fields": list(updates.keys())},
        )
    )
    db.commit()
    variants = db.scalars(
        select(Variant)
        .where(Variant.product_id == product.id, Variant.tenant_id == tenant.id)
        .order_by(Variant.size_ml)
    ).all()
    return serialize_product(product, variants)


def add_or_update_variant(
    db: DatabaseSession,
    tenant: Tenant,
    actor_id: str,
    product_id: int,
    variant_id: int | None,
    data: VariantCreate | VariantUpdate,
) -> dict:
    product = db.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.tenant_id == tenant.id,
        )
    )
    if product is None:
        raise HTTPException(404, "Product not found")

    if variant_id is None:
        assert isinstance(data, VariantCreate)
        variant = Variant(
            tenant_id=tenant.id,
            product_id=product.id,
            sku=data.sku,
            size_ml=data.size_ml,
            price=data.price,
            stock=data.stock,
            lead_time_weeks=data.lead_time_weeks,
        )
        db.add(variant)
        action = "catalog.variant_created"
    else:
        variant = db.scalar(
            select(Variant).where(
                Variant.id == variant_id,
                Variant.product_id == product.id,
                Variant.tenant_id == tenant.id,
            )
        )
        if variant is None:
            raise HTTPException(404, "Variant not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(variant, field, value)
        action = "catalog.variant_updated"

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Variant SKU or size conflicts with an existing SKU") from exc

    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor=actor_id,
            action=action,
            detail={"product_id": product.id, "variant_id": variant.id, "sku": variant.sku},
        )
    )
    db.commit()
    variants = db.scalars(
        select(Variant)
        .where(Variant.product_id == product.id, Variant.tenant_id == tenant.id)
        .order_by(Variant.size_ml)
    ).all()
    return serialize_product(product, variants)


def escape_csv_cell(val: Any) -> Any:
    """Escape any string cell starting with =, +, -, or @ by prefixing a single quote."""
    if isinstance(val, str) and len(val) > 0 and val[0] in ("=", "+", "-", "@"):
        return f"'{val}"
    return val


def unescape_csv_cell(val: str) -> str:
    """Strip leading single quote if escaping formula injection."""
    val = val.strip()
    if val.startswith("'") and len(val) > 1 and val[1] in ("=", "+", "-", "@"):
        return val[1:]
    return val


def export_tenant_catalog_csv(
    db: DatabaseSession,
    tenant: Tenant,
) -> str:
    """Export tenant products and variants as CSV formatted string."""
    products = db.scalars(
        select(Product)
        .where(Product.tenant_id == tenant.id)
        .order_by(Product.id)
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "slug",
            "name",
            "brand",
            "concentration",
            "category",
            "gender",
            "sku",
            "size_ml",
            "price",
            "stock",
        ]
    )
    if not products:
        return output.getvalue()

    product_ids = [p.id for p in products]
    variants = db.scalars(
        select(Variant)
        .where(
            Variant.tenant_id == tenant.id,
            Variant.product_id.in_(product_ids),
        )
        .order_by(Variant.product_id, Variant.size_ml)
    ).all()

    by_product: dict[int, list[Variant]] = {pid: [] for pid in product_ids}
    for v in variants:
        by_product.setdefault(v.product_id, []).append(v)

    for p in products:
        p_variants = by_product.get(p.id, [])
        for v in p_variants:
            writer.writerow(
                [
                    escape_csv_cell(p.slug),
                    escape_csv_cell(p.name),
                    escape_csv_cell(p.brand),
                    escape_csv_cell(p.concentration),
                    escape_csv_cell(p.category),
                    escape_csv_cell(p.gender),
                    escape_csv_cell(v.sku),
                    v.size_ml,
                    f"{float(v.price):.2f}",
                    v.stock,
                ]
            )
        if not p_variants:
            writer.writerow(
                [
                    escape_csv_cell(p.slug),
                    escape_csv_cell(p.name),
                    escape_csv_cell(p.brand),
                    escape_csv_cell(p.concentration),
                    escape_csv_cell(p.category),
                    escape_csv_cell(p.gender),
                    "",
                    "",
                    "",
                    "",
                ]
            )

    return output.getvalue()


def import_tenant_catalog_csv(
    db: DatabaseSession,
    tenant: Tenant,
    actor_id: str,
    csv_text: str,
) -> dict:
    """Import products and variants from CSV text for tenant, recording an AuditLog."""
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    products_by_slug: dict[str, Product] = {}
    products_created = 0
    imported_rows = 0

    for row in reader:
        if not row or not any(row.values()):
            continue
        imported_rows += 1

        clean_row = {
            k.strip(): unescape_csv_cell(str(v)) if v is not None else ""
            for k, v in row.items()
            if k is not None
        }

        name = clean_row.get("name", "").strip()
        brand = clean_row.get("brand", "").strip()
        slug = clean_row.get("slug", "").strip()
        if not slug and (name or brand):
            slug = slugify(name, brand)

        concentration = clean_row.get("concentration", "").strip() or "EDP"
        if concentration not in {"EDT", "EDP", "Parfum", "Cologne", "Unverified"}:
            concentration = "EDP"
        category = clean_row.get("category", "").strip() or "Woody"
        gender = clean_row.get("gender", "").strip() or "Unisex"
        description = (
            clean_row.get("description", "").strip()
            or f"{name or 'Fragrance'} by {brand or 'House'}."
        )

        sku = clean_row.get("sku", "").strip()
        try:
            size_ml = int(clean_row.get("size_ml", 50))
        except (ValueError, TypeError):
            size_ml = 50
        try:
            price = Decimal(str(clean_row.get("price", "100.00")))
        except Exception:
            price = Decimal("100.00")
        try:
            stock = int(clean_row.get("stock", 0))
        except (ValueError, TypeError):
            stock = 0

        # Find or create product
        product = products_by_slug.get(slug)
        if product is None and slug:
            product = db.scalar(
                select(Product).where(
                    Product.tenant_id == tenant.id,
                    Product.slug == slug,
                )
            )

        if product is None:
            product = Product(
                tenant_id=tenant.id,
                slug=slug or f"prod-{uuid4().hex[:8]}",
                name=name or "Unnamed Product",
                brand=brand or "House",
                concentration=concentration,
                category=category,
                gender=gender,
                description=description,
                notes={"top": [], "heart": [], "base": []},
                accords={},
                seasons=["Autumn", "Winter"],
                occasions=["Everyday"],
                longevity=6.0,
                sillage="Moderate",
                launch_date=date.today(),
                pinned=False,
                hidden=False,
                source_metadata={"imported_by": actor_id},
            )
            db.add(product)
            try:
                db.flush()
            except IntegrityError as exc:
                err_msg = str(getattr(exc, "orig", exc)).lower()
                if "pkey" in err_msg or ("duplicate key" in err_msg and "id" in err_msg):
                    db.rollback()
                    from ...database import sync_postgres_sequences

                    sync_postgres_sequences(db)
                    db.add(product)
                    db.flush()
                else:
                    raise
            products_by_slug[product.slug] = product
            products_created += 1
        else:
            if name:
                product.name = name
            if brand:
                product.brand = brand
            if concentration:
                product.concentration = concentration
            if category:
                product.category = category
            if gender:
                product.gender = gender
            if clean_row.get("description"):
                product.description = description
            products_by_slug[product.slug] = product

        # Find or create variant
        if sku:
            variant = db.scalar(
                select(Variant).where(
                    Variant.tenant_id == tenant.id,
                    Variant.sku == sku,
                )
            )
            if variant is None:
                variant = db.scalar(
                    select(Variant).where(
                        Variant.tenant_id == tenant.id,
                        Variant.product_id == product.id,
                        Variant.size_ml == size_ml,
                    )
                )

            if variant is None:
                variant = Variant(
                    tenant_id=tenant.id,
                    product_id=product.id,
                    sku=sku,
                    size_ml=size_ml,
                    price=price,
                    stock=stock,
                    lead_time_weeks=2,
                )
                db.add(variant)
            else:
                variant.product_id = product.id
                variant.sku = sku
                variant.size_ml = size_ml
                variant.price = price
                variant.stock = stock

            try:
                db.flush()
            except IntegrityError as exc:
                err_msg = str(getattr(exc, "orig", exc)).lower()
                if "pkey" in err_msg or ("duplicate key" in err_msg and "id" in err_msg):
                    db.rollback()
                    from ...database import sync_postgres_sequences

                    sync_postgres_sequences(db)
                    if variant not in db:
                        db.add(variant)
                    db.flush()
                else:
                    raise

    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor=actor_id,
            action="catalog.csv_imported",
            detail={"imported_rows": imported_rows},
        )
    )
    db.commit()

    return {
        "imported_rows": imported_rows,
        "products_created": products_created,
    }

