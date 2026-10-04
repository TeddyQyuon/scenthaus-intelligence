import hashlib
import pandas as pd
from sqlalchemy import select
from app.models import Product, Variant, Order, OrderItem, User, Wishlist, Event


def frame(db, query):
    result = db.execute(query)
    return pd.DataFrame(result.fetchall(), columns=result.keys())


def load(db):
    products = frame(db, select(Product.__table__))
    variants = frame(db, select(Variant.__table__))
    orders = frame(
        db,
        select(
            Order.id.label("order_id"),
            Order.user_id,
            Order.created_at,
            OrderItem.variant_id,
            OrderItem.quantity,
            OrderItem.unit_price,
        )
        .join(OrderItem, Order.id == OrderItem.order_id)
        .join(User, Order.user_id == User.id)
        .where(User.consent == True),
    )
    orders = orders.merge(
        variants[["id", "product_id", "sku", "size_ml"]],
        left_on="variant_id",
        right_on="id",
    ).drop(columns="id")
    orders["revenue"] = orders.quantity * orders.unit_price.astype(float)
    wishes = frame(
        db,
        select(Wishlist.user_id, Wishlist.product_id, Wishlist.created_at)
        .join(User, Wishlist.user_id == User.id)
        .where(User.consent == True),
    )
    events = frame(
        db,
        select(Event.user_id, Event.product_id, Event.event_type, Event.created_at)
        .join(User, Event.user_id == User.id)
        .where(User.consent == True),
    )
    return products, variants, orders, wishes, events


def validate(products, variants, orders):
    errors = []
    warnings = []
    for name, df, cols in [
        (
            "products",
            products,
            ["id", "name", "brand", "notes", "accords", "launch_date"],
        ),
        ("variants", variants, ["id", "sku", "price", "stock"]),
        (
            "orders",
            orders,
            ["order_id", "user_id", "variant_id", "quantity", "created_at"],
        ),
    ]:
        if df.empty:
            errors.append(name + " is empty")
        elif df[cols].isnull().any().any():
            errors.append(name + " contains nulls")
    if (
        products.id.duplicated().any()
        or variants.sku.duplicated().any()
        or orders.duplicated(["order_id", "variant_id"]).any()
    ):
        errors.append("Duplicate identifiers or order lines")
    if (
        not variants.price.astype(float).between(0.01, 2000).all()
        or (variants.stock < 0).any()
    ):
        errors.append("Invalid catalogue price or stock")
    if (orders.quantity <= 0).any() or (orders.unit_price.astype(float) <= 0).any():
        errors.append("Invalid order quantities or prices")
    if not set(orders.variant_id) <= set(variants.id) or not set(
        variants.product_id
    ) <= set(products.id):
        errors.append("Broken foreign keys")
    joined = orders.merge(
        products[["id", "launch_date"]], left_on="product_id", right_on="id"
    )
    if (pd.to_datetime(joined.created_at) < pd.to_datetime(joined.launch_date)).any():
        errors.append("Orders precede product launch")
    for size, group in variants.groupby("size_ml"):
        prices = group.price.astype(float)
        median = prices.median()
        mad = (prices - median).abs().median()
        if mad and ((prices - median).abs() > 6 * mad).any():
            warnings.append(f"Price outlier at {size}ml; reviewed, not deleted")
    if errors:
        raise ValueError("; ".join(errors))
    fingerprint = hashlib.sha256(
        pd.util.hash_pandas_object(
            orders.sort_values(["order_id", "variant_id"]).astype(str), index=False
        ).values.tobytes()
    ).hexdigest()
    return {
        "passed": True,
        "warnings": warnings,
        "data_hash": fingerprint,
        "order_lines": len(orders),
    }
