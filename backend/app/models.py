from datetime import datetime
from uuid import uuid4
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Date,
    JSON,
    Numeric,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from .database import Base


def now():
    return datetime.now(__import__("datetime").timezone.utc).replace(tzinfo=None)


def uid():
    return str(uuid4())


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    slug = Column(String(100), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    brand = Column(String(100), nullable=False, index=True)
    concentration = Column(String(12), nullable=False)
    category = Column(String(30), nullable=False)
    gender = Column(String(20), default="Unisex", nullable=False)
    description = Column(String(1000), nullable=False)
    notes = Column(JSON, nullable=False)
    accords = Column(JSON, nullable=False)
    seasons = Column(JSON, nullable=False)
    occasions = Column(JSON, nullable=False)
    longevity = Column(Float, nullable=False)
    sillage = Column(String(30), nullable=False)
    launch_date = Column(Date, nullable=False)
    pinned = Column(Boolean, default=False, nullable=False)
    hidden = Column(Boolean, default=False, nullable=False)
    image_path = Column(String(500))
    source_metadata = Column(JSON)
    __table_args__ = (
        CheckConstraint(
            "concentration IN ('EDT','EDP','Parfum','Cologne','Unverified')"
        ),
    )


class Variant(Base):
    __tablename__ = "variants"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    sku = Column(String(40), unique=True, nullable=False)
    size_ml = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    stock = Column(Integer, nullable=False)
    lead_time_weeks = Column(Integer, default=2, nullable=False)
    __table_args__ = (
        UniqueConstraint("product_id", "size_ml"),
        CheckConstraint("price > 0"),
        CheckConstraint("stock >= 0"),
    )


class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=uid)
    email = Column(String(254), unique=True)
    password_hash = Column(String(255))
    role = Column(String(20), default="customer", nullable=False)
    consent = Column(Boolean, default=False, nullable=False)
    simulated = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=now, nullable=False)
    quiz_profile = Column(JSON)
    totp_secret = Column(String(512))
    totp_last_counter = Column(Integer)
    recovery_code_hashes = Column(JSON, default=list, nullable=False)
    pending_totp_secret = Column(String(512))
    pending_totp_expires_at = Column(DateTime)
    pending_totp_session = Column(String(64))


class StockWeek(Base):
    __tablename__ = "stock_weeks"
    variant_id = Column(Integer, ForeignKey("variants.id"), primary_key=True)
    week = Column(Date, primary_key=True)
    in_stock = Column(Boolean, nullable=False)


class Session(Base):
    __tablename__ = "sessions"
    token_hash = Column(String(64), primary_key=True)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at = Column(DateTime, nullable=False)
    public_id = Column(String(36), default=uid, nullable=False)
    created_at = Column(DateTime)
    last_seen_at = Column(DateTime)
    ip_address = Column(String(45))
    user_agent = Column(String(512))
    location = Column(String(200))
    __table_args__ = (UniqueConstraint("public_id", name="uq_sessions_public_id"),)


class SecurityEvent(Base):
    __tablename__ = "security_events"
    id = Column(String(36), primary_key=True, default=uid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    account_hash = Column(String(64), index=True)
    kind = Column(String(40), nullable=False)
    success = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=now, nullable=False, index=True)
    ip_address = Column(String(45), index=True)
    user_agent = Column(String(512))
    location = Column(String(200))


class Wishlist(Base):
    __tablename__ = "wishlists"
    id = Column(Integer, primary_key=True)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    created_at = Column(DateTime, default=now, nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "product_id"),)


class CartItem(Base):
    __tablename__ = "cart_items"
    id = Column(Integer, primary_key=True)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    variant_id = Column(Integer, ForeignKey("variants.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    __table_args__ = (
        UniqueConstraint("user_id", "variant_id"),
        CheckConstraint("quantity BETWEEN 1 AND 10"),
    )


class QuizProfile(Base):
    __tablename__ = "quiz_profiles"
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    answers = Column(JSON, nullable=False)
    weights = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=now, nullable=False)


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id = Column(Integer, ForeignKey("products.id"))
    event_type = Column(String(30), nullable=False)
    slot = Column(String(50))
    recommendation_id = Column(String(36))
    model_version = Column(String(80))
    created_at = Column(DateTime, default=now, nullable=False, index=True)
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('view','add_to_cart','wishlist_add','wishlist_remove','purchase','quiz_submit','impression','click')"
        ),
        Index("ix_event_user_time", "user_id", "created_at"),
    )


class RecommendationRequest(Base):
    __tablename__ = "recommendation_requests"
    id = Column(String(36), primary_key=True, default=uid)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_ids = Column(JSON, nullable=False)
    slot = Column(String(50), nullable=False)
    model_version = Column(String(80), nullable=False)
    created_at = Column(DateTime, default=now, nullable=False)


class Order(Base):
    __tablename__ = "orders"
    id = Column(String(36), primary_key=True, default=uid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=now, nullable=False, index=True)
    total = Column(Numeric(12, 2), nullable=False)
    status = Column(String(30), default="demo_completed", nullable=False)
    simulated = Column(Boolean, default=False, nullable=False)
    idempotency_key = Column(String(100))
    order_number = Column(String(32), unique=True)
    customer_name = Column(String(120))
    customer_email = Column(String(254))
    customer_phone = Column(String(24))
    delivery_address = Column(JSON)
    subtotal_minor = Column(Integer)
    shipping_minor = Column(Integer)
    discount_minor = Column(Integer)
    tax_minor = Column(Integer)
    total_minor = Column(Integer)
    currency = Column(String(3))
    payment_status = Column(String(20))
    stripe_session_id = Column(String(255), unique=True)
    stripe_payment_intent_id = Column(String(255), unique=True)
    stripe_checkout_url = Column(String(2048))
    checkout_fingerprint = Column(String(64))
    payment_mode = Column(String(4))
    stock_reserved = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime)
    paid_at = Column(DateTime)
    updated_at = Column(DateTime, default=now, nullable=False)
    refunded_minor = Column(Integer, default=0, nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key"),)


class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    variant_id = Column(Integer, ForeignKey("variants.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    product_snapshot = Column(JSON)
    __table_args__ = (
        CheckConstraint("quantity > 0"),
        CheckConstraint("unit_price > 0"),
        UniqueConstraint("order_id", "variant_id"),
    )


class OrderNumberCounter(Base):
    __tablename__ = "order_number_counters"
    year = Column(Integer, primary_key=True)
    value = Column(Integer, nullable=False, default=0)


class StripeWebhookEvent(Base):
    __tablename__ = "stripe_webhook_events"
    id = Column(String(255), primary_key=True)
    event_type = Column(String(100), nullable=False)
    order_id = Column(String(36), ForeignKey("orders.id"), nullable=False)
    created_at = Column(DateTime, default=now, nullable=False)


class ModelRun(Base):
    __tablename__ = "model_runs"
    version = Column(String(80), primary_key=True)
    created_at = Column(DateTime, default=now, nullable=False)
    metrics = Column(JSON, nullable=False)
    data_hash = Column(String(64), nullable=False)
    mlflow_run_id = Column(String(80))


class ForecastSnapshot(Base):
    __tablename__ = "forecast_snapshots"
    id = Column(Integer, primary_key=True)
    version = Column(String(80), nullable=False)
    sku = Column(String(40), nullable=False)
    origin = Column(Date, nullable=False)
    target_week = Column(Date, nullable=False)
    prediction = Column(Float, nullable=False)
    lower80 = Column(Float, nullable=False)
    upper80 = Column(Float, nullable=False)
    lower95 = Column(Float, nullable=False)
    upper95 = Column(Float, nullable=False)
    actual = Column(Float)
    __table_args__ = (UniqueConstraint("version", "sku", "target_week"),)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    actor = Column(String(36), nullable=False)
    action = Column(String(100), nullable=False)
    detail = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=now, nullable=False)
