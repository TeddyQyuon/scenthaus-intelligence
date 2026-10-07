"""Server-priced Checkout and minimal, signature-verified payment event handling."""
import hashlib
import hmac
import json
import re
from datetime import timedelta
from decimal import Decimal
from typing import Literal

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from . import stripe_service
from .config import settings
from .database import get_db
from .models import (CartItem, Event, Order, OrderItem, OrderNumberCounter, Product,
                     StripeWebhookEvent, User, Variant, now)
from .security import user_required

router = APIRouter()


class Delivery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    phone: str = Field(default="", max_length=24, pattern=r"^[+0-9 ()-]*$")
    line1: str = Field(min_length=3, max_length=200)
    line2: str = Field(default="", max_length=200)
    postal_code: str = Field(pattern=r"^\d{6}$")
    city: str = Field(default="Singapore", min_length=2, max_length=100)
    country: Literal["SG"] = "SG"

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value.lower()


class CheckoutItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: StrictInt = Field(gt=0)
    variant_id: StrictInt = Field(gt=0)
    size_ml: StrictInt = Field(gt=0)
    quantity: StrictInt = Field(ge=1, le=10)


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    delivery: Delivery
    items: list[CheckoutItem] = Field(min_length=1, max_length=50)
    quote_token: str = Field(min_length=64, max_length=64)
    idempotency_key: str = Field(min_length=16, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")


def configured():
    key = settings.stripe_secret_key.get_secret_value()
    return key.startswith(("sk_test_", "sk_live_")) and bool(settings.stripe_webhook_secret.get_secret_value())


def mode():
    return "live" if settings.stripe_secret_key.get_secret_value().startswith("sk_live_") else "test"


def cents(price):
    amount = Decimal(price) * 100
    if amount != amount.to_integral_value() or amount <= 0:
        raise HTTPException(409, "A price needs review. Please contact the store.")
    return int(amount)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def quote_token(items):
    return hmac.new(settings.secret_key.encode(), fingerprint(items).encode(), hashlib.sha256).hexdigest()


def bag_quote(user, db):
    rows = db.execute(select(CartItem, Variant, Product)
                      .join(Variant, CartItem.variant_id == Variant.id)
                      .join(Product, Variant.product_id == Product.id)
                      .where(CartItem.user_id == user.id).order_by(Variant.id)).all()
    if not rows:
        raise HTTPException(409, "Your bag is empty. Choose a scent before checking out.")
    if len(rows) > 50:
        raise HTTPException(409, "Please reduce your bag to 50 sizes or fewer.")
    items = []
    for cart, variant, product in rows:
        if product.hidden or not 1 <= cart.quantity <= 10 or variant.stock < cart.quantity:
            raise HTTPException(409, "Availability changed. Review the sizes and quantities in your bag.")
        unit = cents(variant.price)
        items.append({"product_id": product.id, "variant_id": variant.id,
                      "size_ml": variant.size_ml, "quantity": cart.quantity,
                      "unit_price_minor": unit, "item_total_minor": unit * cart.quantity,
                      "name": product.name, "brand": product.brand,
                      "slug": product.slug, "image": product.image_path})
    subtotal = sum(item["item_total_minor"] for item in items)
    # Initial delivery policy: Singapore only, free standard delivery, no coupons
    # or additional tax. All four components remain explicit and server-owned.
    return {"items": items, "subtotal_minor": subtotal, "shipping_minor": 0,
            "discount_minor": 0, "tax_minor": 0, "total_minor": subtotal,
            "currency": "SGD", "quote_token": quote_token(items),
            "payment_mode": mode(), "payments_available": configured()}


@router.get("/checkout/quote")
def quote(user=Depends(user_required), db=Depends(get_db)):
    active = db.scalar(select(Order).where(Order.user_id == user.id, Order.stock_reserved.is_(True),
                                         Order.payment_status.in_(["pending", "failed"])))
    if active and active.expires_at < now():
        reconcile_order(active, db)
        active = db.get(Order, active.id)
        if not active.stock_reserved:
            active = None
    if active:
        saved = public_order(active, db)
        return {**saved, "quote_token": quote_token(saved["items"]),
                "payments_available": configured(), "pending_order": {
                    **payment_response(active), "delivery": {
                        **active.delivery_address, "full_name": active.customer_name,
                        "email": active.customer_email, "phone": active.customer_phone or ""}}}
    return bag_quote(user, db)


def order_items(order, db):
    return db.scalars(select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.variant_id)).all()


def public_order(order, db):
    return {"id": order.id, "order_number": order.order_number,
            "customer_name": order.customer_name, "customer_email": order.customer_email,
            "delivery_address": order.delivery_address,
            "items": [{**(item.product_snapshot or {}), "variant_id": item.variant_id,
                       "quantity": item.quantity, "unit_price_minor": cents(item.unit_price),
                       "item_total_minor": cents(item.unit_price) * item.quantity}
                      for item in order_items(order, db)],
            "subtotal_minor": order.subtotal_minor, "shipping_minor": order.shipping_minor,
            "discount_minor": order.discount_minor, "tax_minor": order.tax_minor,
            "total_minor": order.total_minor, "currency": order.currency,
            "payment_status": order.payment_status, "status": order.status,
            "payment_mode": order.payment_mode, "created_at": str(order.created_at),
            "updated_at": str(order.updated_at), "refunded_minor": order.refunded_minor}


def owned_order(order_id, user, db):
    order = db.scalar(select(Order).where(Order.id == order_id, Order.user_id == user.id,
                                        Order.order_number.is_not(None)))
    if not order:
        raise HTTPException(404, "Order not found.")
    return order


def next_number(db):
    year = now().year
    if not db.get(OrderNumberCounter, year):
        try:
            with db.begin_nested():
                db.add(OrderNumberCounter(year=year, value=0))
                db.flush()
        except IntegrityError:
            pass
    value = db.scalar(update(OrderNumberCounter).where(OrderNumberCounter.year == year)
                      .values(value=OrderNumberCounter.value + 1).returning(OrderNumberCounter.value))
    return f"SCENT-{year}-{value:06d}"


def payment_response(order):
    return {"order_id": order.id, "order_number": order.order_number,
            "payment_status": order.payment_status, "checkout_url": order.stripe_checkout_url,
            "total_minor": order.total_minor, "currency": order.currency}


def stripe_params(order, db):
    root = settings.checkout_public_url.rstrip("/")
    address = order.delivery_address
    shipping = {"name": order.customer_name, "address": address}
    if order.customer_phone:
        shipping["phone"] = order.customer_phone
    return {"mode": "payment", "client_reference_id": order.id,
            "customer_email": order.customer_email,
            "metadata": {"order_id": order.id, "order_number": order.order_number},
            "payment_intent_data": {"metadata": {"order_id": order.id}, "shipping": shipping,
                                    "receipt_email": order.customer_email},
            "line_items": [{"quantity": item.quantity, "price_data": {
                "currency": "sgd", "unit_amount": cents(item.unit_price),
                "product_data": {"name": f"{item.product_snapshot['brand']} · {item.product_snapshot['name']} · {item.product_snapshot['size_ml']}ml"}}}
                for item in order_items(order, db)],
            "success_url": root + "/checkout/success?order_id=" + order.id,
            "cancel_url": root + "/checkout/cancelled?order_id=" + order.id,
            "expires_at": int(order.expires_at.replace(tzinfo=__import__('datetime').timezone.utc).timestamp()),
            "locale": "en"}


@router.post("/checkout/session")
def create_checkout(body: CheckoutRequest, user=Depends(user_required), db=Depends(get_db)):
    if not configured():
        raise HTTPException(503, "Secure payments are temporarily unavailable. Your bag is saved.")
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    existing = db.scalar(select(Order).where(Order.user_id == user.id,
                                            Order.idempotency_key == body.idempotency_key))
    active = db.scalar(select(Order).where(Order.user_id == user.id, Order.stock_reserved.is_(True),
                                         Order.payment_status.in_(["pending", "failed"])))
    order = existing or active
    if order:
        # One active checkout per user, including across tabs and fresh request keys.
        if order.payment_status == "paid":
            return payment_response(order)
        if not order.stock_reserved:
            raise HTTPException(409, "This checkout ended. Return to checkout to start again.")
        claimed = sorted([item.model_dump() for item in body.items], key=lambda item: item["variant_id"])
        if fingerprint({"items": claimed, "delivery": body.delivery.model_dump()}) != order.checkout_fingerprint:
            raise HTTPException(409, "A checkout is already open. Resume it or cancel it before changing your order.")
        if order.stripe_session_id:
            return payment_response(order)
    else:
        recent = db.scalar(select(func.count()).select_from(Order).where(
            Order.user_id == user.id, Order.order_number.is_not(None),
            Order.created_at > now() - timedelta(minutes=10)))
        if recent >= 10:
            raise HTTPException(429, "Please wait a few minutes before starting another checkout.")
        authoritative = bag_quote(user, db)
        claimed = sorted([item.model_dump() for item in body.items], key=lambda item: item["variant_id"])
        actual = [{key: item[key] for key in ("product_id", "variant_id", "size_ml", "quantity")}
                  for item in authoritative["items"]]
        if claimed != actual or not hmac.compare_digest(body.quote_token, authoritative["quote_token"]):
            raise HTTPException(409, "Your bag or prices changed. Review the updated order before paying.")
        address = body.delivery.model_dump(exclude={"full_name", "email", "phone"})
        order = Order(user_id=user.id, order_number=next_number(db),
                      customer_name=body.delivery.full_name, customer_email=body.delivery.email,
                      customer_phone=body.delivery.phone, delivery_address=address,
                      idempotency_key=body.idempotency_key, status="pending", payment_status="pending",
                      payment_mode=mode(), simulated=mode() == "test", currency="SGD", total=Decimal(authoritative["total_minor"]) / 100,
                      stock_reserved=True, expires_at=now() + timedelta(minutes=35),
                      checkout_fingerprint=fingerprint({"items": actual, "delivery": body.delivery.model_dump()}),
                      **{key: authoritative[key] for key in ("subtotal_minor", "shipping_minor", "discount_minor", "tax_minor", "total_minor")})
        db.add(order)
        db.flush()
        for item in authoritative["items"]:
            changed = db.execute(update(Variant).where(Variant.id == item["variant_id"], Variant.stock >= item["quantity"])
                                 .values(stock=Variant.stock - item["quantity"]))
            if changed.rowcount != 1:
                db.rollback()
                raise HTTPException(409, "Availability changed. Please review your bag.")
            db.add(OrderItem(order_id=order.id, variant_id=item["variant_id"], quantity=item["quantity"],
                             unit_price=Decimal(item["unit_price_minor"]) / 100, product_snapshot=item))
        db.commit()
    params = stripe_params(order, db)
    db.commit()  # No database locks are held during Stripe's network request.
    try:
        session = stripe_service.create_session(params, "scenthaus-order-" + order.id)
    except stripe.InvalidRequestError:
        db.scalar(select(User).where(User.id == user.id).with_for_update())
        order = db.scalar(select(Order).where(Order.id == order.id).with_for_update())
        # A definitive rejected request did not create a charge or session.
        if not order.stripe_session_id:
            release_inventory(order, db)
            db.commit()
        raise HTTPException(503, "Secure payment could not open. Return to checkout and review your selection.") from None
    except stripe.StripeError:
        # A timeout may conceal a successful Stripe creation. Keep the same order
        # and reservation: retrying reuses the exact Stripe idempotency key.
        raise HTTPException(503, "We could not connect to secure payment. Your bag is saved; please retry.") from None
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    order = db.scalar(select(Order).where(Order.id == order.id).with_for_update())
    if order.stripe_session_id and order.stripe_session_id != session.id:
        raise HTTPException(409, "Your checkout is already open. Please return to it.")
    order.stripe_session_id = session.id
    order.stripe_checkout_url = session.url
    order.updated_at = now()
    db.commit()
    return payment_response(order)


@router.get("/orders/{order_id}")
def order_detail(order_id: str, user=Depends(user_required), db=Depends(get_db)):
    return public_order(owned_order(order_id, user, db), db)


def release_inventory(order, db):
    if not order.stock_reserved or order.payment_status in {"paid", "refunded"}:
        return
    for item in order_items(order, db):
        db.execute(update(Variant).where(Variant.id == item.variant_id)
                   .values(stock=Variant.stock + item.quantity))
    order.stock_reserved = False
    order.payment_status = "failed"
    order.status = "cancelled"
    order.updated_at = now()


def reconcile_order(order, db):
    identifier, owner_id = order.id, order.user_id
    db.commit()
    try:
        if order.stripe_session_id:
            session, complete = stripe_service.retrieve_session(order.stripe_session_id), True
        else:
            session, complete = stripe_service.find_session(order)
    except stripe.StripeError:
        return  # Uncertain payment state never releases stock or confirms payment.
    db.scalar(select(User).where(User.id == owner_id).with_for_update())
    order = db.scalar(select(Order).where(Order.id == identifier).with_for_update())
    if session:
        order.stripe_session_id = session.id
        if session.url:
            order.stripe_checkout_url = session.url
        if session.status == "expired" and session.payment_status == "unpaid":
            release_inventory(order, db)
        # A paid Stripe retrieval still does not substitute for the signed webhook.
    elif complete and order.expires_at < now() - timedelta(minutes=5):
        release_inventory(order, db)
    db.commit()


def reconcile_expired(db):
    if configured():
        orders = db.scalars(select(Order).where(Order.stock_reserved.is_(True),
                           Order.expires_at < now()).order_by(Order.expires_at).limit(3)).all()
        for order in orders:
            reconcile_order(order, db)


@router.post("/checkout/{order_id}/cancel")
def cancel_checkout(order_id: str, user=Depends(user_required), db=Depends(get_db)):
    order = owned_order(order_id, user, db)
    if order.payment_status in {"paid", "refunded"} or not order.stock_reserved:
        return public_order(order, db)
    if not order.stripe_session_id:
        raise HTTPException(409, "Payment connection is still being checked. Retry checkout before cancelling.")
    session_id = order.stripe_session_id
    db.commit()
    try:
        session = stripe_service.retrieve_session(session_id)
        if session.status == "open":
            try:
                session = stripe_service.expire_session(session_id)
            except stripe.InvalidRequestError:
                # A concurrent cancellation/completion may have won the race.
                session = stripe_service.retrieve_session(session_id)
    except stripe.StripeError:
        raise HTTPException(503, "We could not confirm cancellation. Please try again shortly.") from None
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    # Cancellation never marks paid; success still requires a verified webhook.
    if session.status == "expired" and session.payment_status == "unpaid":
        release_inventory(order, db)
    db.commit()
    return public_order(order, db)


def apply_event(event, db):
    kind = event.get("type")
    if kind not in {"checkout.session.completed", "checkout.session.async_payment_succeeded",
                    "checkout.session.async_payment_failed", "checkout.session.expired",
                    "payment_intent.payment_failed", "charge.refunded"}:
        return
    obj = event["data"]["object"]
    order_id = obj.get("metadata", {}).get("order_id")
    if kind == "charge.refunded":
        order = db.scalar(select(Order).where(Order.stripe_payment_intent_id == obj.get("payment_intent")))
    else:
        order = db.get(Order, order_id) if order_id else None
    if not order or not order.order_number:
        return  # Other Stripe applications' events are not SCENTHAUS orders.
    if bool(event.get("livemode")) != (order.payment_mode == "live"):
        raise HTTPException(400, "Payment event mode does not match the order.")
    db.scalar(select(User).where(User.id == order.user_id).with_for_update())
    order = db.scalar(select(Order).where(Order.id == order.id).with_for_update())
    if db.get(StripeWebhookEvent, event["id"]):
        return
    if kind.startswith("checkout.session."):
        if (obj.get("client_reference_id") != order.id or obj.get("currency", "").upper() != order.currency
                or obj.get("amount_total") != order.total_minor or obj.get("mode") != "payment"
                or (order.stripe_session_id and order.stripe_session_id != obj["id"])):
            raise HTTPException(400, "Payment event does not match the order.")
        order.stripe_session_id = obj["id"]
        if obj.get("payment_intent"):
            order.stripe_payment_intent_id = obj["payment_intent"]
        if kind in {"checkout.session.completed", "checkout.session.async_payment_succeeded"} and obj.get("payment_status") == "paid":
            if order.payment_status not in {"paid", "refunded"}:
                if not order.stock_reserved:
                    # Never silently fulfil an order whose reservation was released.
                    raise HTTPException(409, "Payment requires inventory reconciliation.")
                order.payment_status = "paid"
                order.status = "confirmed"
                order.paid_at = now()
                order.stock_reserved = False
                customer = db.get(User, order.user_id)
                for item in order_items(order, db):
                    cart = db.scalar(select(CartItem).where(CartItem.user_id == order.user_id, CartItem.variant_id == item.variant_id))
                    if cart:
                        remaining = cart.quantity - item.quantity
                        if remaining > 0:
                            cart.quantity = remaining
                        else:
                            db.delete(cart)
                    if customer.consent:
                        db.add(Event(user_id=customer.id, product_id=item.product_snapshot["product_id"], event_type="purchase"))
        elif kind == "checkout.session.expired" and obj.get("status") == "expired" and obj.get("payment_status") == "unpaid":
            release_inventory(order, db)
        elif kind == "checkout.session.async_payment_failed":
            release_inventory(order, db)
    elif kind == "payment_intent.payment_failed":
        if obj.get("currency", "").upper() != order.currency or obj.get("amount") != order.total_minor:
            raise HTTPException(400, "Payment event does not match the order.")
        if order.stripe_payment_intent_id and order.stripe_payment_intent_id != obj["id"]:
            raise HTTPException(400, "Payment event does not match the order.")
        order.stripe_payment_intent_id = obj["id"]
        if order.payment_status not in {"paid", "refunded"}:
            order.payment_status = "failed"  # Card declines remain retryable in the same Checkout Session.
    elif kind == "charge.refunded":
        if obj.get("currency", "").upper() != order.currency or obj.get("amount") != order.total_minor:
            raise HTTPException(400, "Refund event does not match the order.")
        order.refunded_minor = max(order.refunded_minor, obj.get("amount_refunded", 0))
        if order.refunded_minor == order.total_minor and order.payment_status in {"paid", "refunded"}:
            order.payment_status = "refunded"
            order.status = "cancelled"
    else:
        return
    order.updated_at = now()
    db.add(StripeWebhookEvent(id=event["id"], event_type=kind, order_id=order.id))
    db.commit()


@router.post("/stripe/webhook")
async def webhook(request: Request, db=Depends(get_db)):
    if not settings.stripe_webhook_secret.get_secret_value():
        raise HTTPException(503, "Payment notifications are unavailable.")
    try:
        event = stripe_service.verify_event(await request.body(), request.headers.get("stripe-signature", ""))
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(400, "Invalid payment notification signature.") from None
    apply_event(event, db)
    return {"received": True}
