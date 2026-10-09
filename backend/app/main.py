import csv, io, re, time
import secrets
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import timedelta, date
from uuid import uuid4
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, delete, update, text, func, or_
from sqlalchemy.exc import IntegrityError
from .config import settings
from .database import get_db
from .models import *
from .schemas import *
from .security import (
    user_required,
    admin_required,
    session_user,
    issue,
    identity,
    csrf,
    digest,
    hasher,
)
from .ml.serving import store
from .catalog import ACCORDS
from .account_security import router as security_router, check_rate_limit, record_event, verify_factor
from .checkout import router as checkout_router, public_order


@asynccontextmanager
async def lifespan(app):
    # The mounted Vercel entrypoint imports this hook. Models load on demand
    # through ModelStore and the serving modules' existing process caches.
    yield


app = FastAPI(
    lifespan=lifespan,
    title="SCENTHAUS Intelligence",
    version="1.0.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)
app.include_router(security_router)
app.include_router(checkout_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)
latencies = deque(maxlen=5000)
requests = defaultdict(deque)


@app.middleware("http")
async def safeguards(request, call_next):
    start = time.perf_counter()
    key = (
        request.client.host if request.client else "unknown",
        request.url.path.startswith("/auth/")
        and request.method in {"POST", "PUT", "DELETE"},
    )
    if len(requests) > 10000:
        requests.clear()
    bucket = requests[key]
    while bucket and bucket[0] < start - 60:
        bucket.popleft()
    limit = 30 if key[1] else 500
    if len(bucket) >= limit:
        return JSONResponse({"detail": "Too many requests"}, status_code=429)
    bucket.append(start)
    if request.method in ["POST", "PUT"]:
        if (
            int(request.headers.get("content-length", "0")) > 65536
            or len(await request.body()) > 65536
        ):
            return JSONResponse({"detail": "Request too large"}, status_code=413)
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    latencies.append((request.url.path, elapsed, response.status_code))
    response.headers.update(
        {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "same-origin",
            "Cache-Control": "no-store",
            "Server-Timing": f"app;dur={elapsed:.1f}",
        }
    )
    if settings.environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response


@app.exception_handler(ValueError)
async def bad_input(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=422)


def product_json(p, db, variants=None):
    if variants is None:
        variants = db.scalars(
            select(Variant).where(Variant.product_id == p.id).order_by(Variant.size_ml)
        ).all()
    return {
        key: getattr(p, key)
        for key in [
            "id",
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
            "pinned",
            "hidden",
        ]
    } | {
        "image": p.image_path or "/images/product.png",
        "source": p.source_metadata,
        "simulated_commerce": settings.demo_mode,
        "variants": [
            {
                "id": v.id,
                "sku": v.sku,
                "size_ml": v.size_ml,
                "price": float(v.price),
                "stock": v.stock,
            }
            for v in variants
        ],
        "price_from": min(float(v.price) for v in variants),
        "in_stock": any(v.stock > 0 for v in variants),
    }


def available(
    db,
    budget=None,
    size=None,
    gender=None,
    season=None,
    in_stock=True,
    category=None,
    brand=None,
    q=None,
):
    products = db.scalars(
        select(Product)
        .where(Product.hidden == False, Product.launch_date <= date.today())
        .order_by(Product.id)
    ).all()
    variants_by_product = defaultdict(list)
    for variant in db.scalars(select(Variant).order_by(Variant.size_ml)):
        variants_by_product[variant.product_id].append(variant)
    out = []
    for p in products:
        if (
            gender
            and p.gender != gender
            or season
            and season not in p.seasons
            or category
            and p.category != category
            or brand
            and p.brand != brand
        ):
            continue
        if (
            q
            and q.lower()
            not in " ".join(
                [p.name, p.brand, p.category, *p.accords, *sum(p.notes.values(), [])]
            ).lower()
        ):
            continue
        row = product_json(p, db, variants_by_product[p.id])
        if any(
            (budget is None or v["price"] <= budget)
            and (size is None or v["size_ml"] == size)
            and (not in_stock or v["stock"] > 0)
            for v in row["variants"]
        ):
            out.append(row)
    return out


def functional_event(db, user, pid, kind):
    if not user.consent:
        return
    click = (
        db.scalar(
            select(Event)
            .where(
                Event.user_id == user.id,
                Event.product_id == pid,
                Event.event_type == "click",
                Event.created_at >= now() - timedelta(days=7),
            )
            .order_by(Event.created_at.desc())
            .limit(1)
        )
        if kind in ["add_to_cart", "purchase"]
        else None
    )
    db.add(
        Event(
            user_id=user.id,
            product_id=pid,
            event_type=kind,
            slot=click.slot if click else None,
            recommendation_id=click.recommendation_id if click else None,
            model_version=click.model_version if click else None,
        )
    )


def bundle():
    b = store.get()
    if not b:
        raise HTTPException(503, "Models are not trained. Run python -m app.ml.train")
    return b


def history(db, user):
    values = defaultdict(float)
    wishes = set()
    if not user.consent:
        return values, wishes, None
    for r in db.scalars(select(Wishlist).where(Wishlist.user_id == user.id)):
        values[r.product_id] += 2
        wishes.add(r.product_id)
    for c, v in db.execute(
        select(CartItem, Variant)
        .join(Variant, CartItem.variant_id == Variant.id)
        .where(CartItem.user_id == user.id)
    ):
        values[v.product_id] += c.quantity
    for item, v in db.execute(
        select(OrderItem, Variant)
        .join(Variant, OrderItem.variant_id == Variant.id)
        .join(Order, OrderItem.order_id == Order.id)
        .where(Order.user_id == user.id, or_(Order.payment_status.is_(None), Order.payment_status == "paid"))
    ):
        values[v.product_id] += item.quantity * 3
    for e in db.scalars(
        select(Event)
        .where(Event.user_id == user.id)
        .order_by(Event.created_at.desc())
        .limit(50)
    ):
        if e.product_id:
            values[e.product_id] += {
                "view": 0.15,
                "click": 0.3,
                "add_to_cart": 0.7,
            }.get(e.event_type, 0)
    profile = db.get(QuizProfile, user.id)
    return values, wishes, profile.weights if profile else None


def results(
    db, user, kind="user", product_id=None, k=8, quiz=None, experiment=None, **filters
):
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity
    from .ml.recommender import scores, mmr, scale

    b = bundle()
    model = b["recommender"]
    eligible = available(db, **filters)
    rows = {p["id"]: p for p in eligible}
    signal, wishes, profile = history(db, user)
    why = {}
    rule_details = {}
    if kind in ["similar", "also-bought", "substitutes"]:
        if product_id not in model["index"]:
            raise HTTPException(404, "Product not found")
        relevance = store.static(b["version"], kind, product_id)
        rows.pop(product_id, None)
        signal = {product_id: 1}
    elif kind == "cart":
        cartpids = {
            v.product_id
            for c, v in db.execute(
                select(CartItem, Variant)
                .join(Variant, CartItem.variant_id == Variant.id)
                .where(CartItem.user_id == user.id)
            )
        }
        relevance = np.zeros(len(model["ids"]))
        for rule in model["rules"]:
            if set(rule["antecedents"]) <= cartpids:
                for pid in rule["consequents"]:
                    i = model["index"][pid]
                    score = rule["confidence"] * np.log1p(rule["lift"])
                    if score > relevance[i]:
                        relevance[i] = score
                        rule_details[pid] = rule
        for pid in cartpids:
            rows.pop(pid, None)
        if not relevance.max():
            relevance = scores(model, {pid: 1 for pid in cartpids})[2]
    else:
        relevance = scores(model, signal, quiz=quiz or profile)[2]
        if experiment and experiment != "two_tower":
            raise HTTPException(422, "Supported experiment: two_tower")
        if (experiment == "two_tower" and user.consent) or quiz:
            from ml.rec_serving import score as tower_score

            relevance = scale(
                tower_score(
                    user.id if user.consent else "",
                    signal,
                    quiz or profile,
                    b["torch_recommender"],
                    recent_ids=list(
                        reversed(
                            db.scalars(
                                select(Event.product_id)
                                .where(
                                    Event.user_id == user.id,
                                    Event.product_id.is_not(None),
                                )
                                .order_by(Event.created_at.desc())
                                .limit(10)
                            ).all()
                        )
                    )
                    if user.consent
                    else [],
                )
                + 1
            )
    candidates = [model["index"][pid] for pid in rows if pid in model["index"]]
    brands = [
        next((p["brand"] for p in eligible if p["id"] == pid), "")
        for pid in model["ids"]
    ]
    pinned = [
        model["index"][p["id"]] for p in eligible if p["pinned"] and p["id"] in rows
    ]
    rank = mmr(model, relevance, candidates, brands, k, pinned)
    output = []
    for i in rank:
        pid = model["ids"][i]
        p = rows[pid]
        reason_tags = []
        reason = (
            "Popular with the community"
            if not signal and not quiz and not profile
            else "Aligned with your scent profile"
        )
        if signal:
            known = [old for old in signal if old != pid and old in model["index"]]
            if known:
                best = max(
                    known, key=lambda old: model["content"][i, model["index"][old]]
                )
                source = db.get(Product, best)
                shared = set(sum(source.notes.values(), [])) & set(
                    sum(p["notes"].values(), [])
                )
                reason = (
                    f"Because you {'wishlisted' if best in wishes else 'explored'} {source.name}"
                    + (": shared " + ", ".join(sorted(shared)[:3]) if shared else "")
                )
                reason_tags = [f"Shared note: {note}" for note in sorted(shared)[:3]]
                shared_accords = set(source.accords or []) & set(p.get("accords", []))
                reason_tags.extend(
                    f"Shared accord: {accord}" for accord in sorted(shared_accords)[:2]
                )
        if pid in rule_details:
            reason = "Often in the same basket: " + ", ".join(
                db.get(Product, int(a)).name for a in rule_details[pid]["antecedents"]
            )
            reason_tags = ["Often bought together"]
        elif quiz or profile:
            preferences = quiz or profile or {}
            ranked_accords = sorted(
                p.get("accords", []),
                key=lambda accord: preferences.get(accord, 0),
                reverse=True,
            )
            reason_tags = [
                f"{accord.title()} accord"
                for accord in ranked_accords
                if preferences.get(accord, 0) > 0
            ][:3]
            if not reason_tags:
                reason_tags = ["Profile match"]
        elif not signal:
            reason_tags = ["Community pick"]
        elif not reason_tags:
            reason_tags = ["Similar scent profile"]
        match = None
        if quiz or profile:
            q = np.array([(quiz or profile).get(a, 0) for a in ACCORDS])
            match = round(
                float(cosine_similarity([q], [model["accords"][i]])[0, 0]) * 100
            )
        output.append(
            p
            | {
                "why": reason,
                "reason_tags": reason_tags,
                "match": match,
                "rule": rule_details.get(pid),
            }
        )
    recid = None
    if user.consent and output:
        req = RecommendationRequest(
            user_id=user.id,
            product_ids=[p["id"] for p in output],
            slot=kind,
            model_version=b["version"],
        )
        db.add(req)
        db.commit()
        recid = req.id
    return {
        "products": output,
        "recommendation_id": recid,
        "model_version": b["version"],
        "ranking_model": "two_tower"
        if (experiment == "two_tower" and user.consent) or quiz
        else "hybrid",
        "slot": kind,
        "match_note": "Cosine alignment with stated accords, not a probability of liking a scent.",
    }


@app.get("/health")
def health(db=Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "models_ready": store.get() is not None,
        "demo_mode": settings.demo_mode,
    }


@app.get("/auth/session")
def auth_session(request: Request, response: Response, db=Depends(get_db)):
    user = session_user(request, db)
    if not user:
        user = User()
        db.add(user)
        db.commit()
        token = issue(user, response, db, request)
    else:
        token = csrf(request.cookies["scenthaus_session"])
    return identity(user, token)


@app.post("/auth/register")
def register(
    body: Credentials,
    request: Request,
    response: Response,
    user=Depends(user_required),
    db=Depends(get_db),
):
    if user.email:
        raise HTTPException(409, "Already signed in")
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(409, "Email already registered")
    user.email = body.email
    user.password_hash = hasher.hash(body.password)
    record_event(db, request, "account_created", True, user)
    db.delete(db.get(Session, digest(request.cookies["scenthaus_session"])))
    db.commit()
    return identity(user, issue(user, response, db, request))


@app.post("/auth/login")
def login(
    body: Credentials,
    request: Request,
    response: Response,
    user=Depends(user_required),
    db=Depends(get_db),
):
    check_rate_limit(db, request, body.email)
    account = db.scalar(select(User).where(User.email == body.email).with_for_update()
                        .execution_options(populate_existing=True))
    try:
        valid = account and hasher.verify(account.password_hash, body.password)
    except Exception:
        valid = False
    if not valid:
        record_event(db, request, "login", False, account, body.email)
        db.commit()
        raise HTTPException(401, "Incorrect email or password")
    if account.totp_secret:
        if not body.otp_code:
            return {"mfa_required": True}
        if not verify_factor(account, body.otp_code):
            record_event(db, request, "login", False, account, body.email)
            db.commit()
            raise HTTPException(401, "Invalid verification code. Use a fresh authenticator code or an unused recovery code.")
    if not user.email and user.id != account.id:
        for old in db.scalars(
            select(CartItem).where(CartItem.user_id == user.id)
        ).all():
            dest = db.scalar(
                select(CartItem).where(
                    CartItem.user_id == account.id,
                    CartItem.variant_id == old.variant_id,
                )
            )
            if dest:
                dest.quantity = min(10, dest.quantity + old.quantity)
                db.delete(old)
            else:
                old.user_id = account.id
        for old in db.scalars(
            select(Wishlist).where(Wishlist.user_id == user.id)
        ).all():
            dest = db.scalar(
                select(Wishlist).where(
                    Wishlist.user_id == account.id,
                    Wishlist.product_id == old.product_id,
                )
            )
            if dest:
                db.delete(old)
            else:
                old.user_id = account.id
    db.delete(db.get(Session, digest(request.cookies["scenthaus_session"])))
    record_event(db, request, "login", True, account)
    db.commit()
    return identity(account, issue(account, response, db, request))


@app.post("/auth/logout")
def logout(
    request: Request,
    response: Response,
    user=Depends(user_required),
    db=Depends(get_db),
):
    db.delete(db.get(Session, digest(request.cookies["scenthaus_session"])))
    if user.email:
        record_event(db, request, "logout", True, user)
    guest = User()
    db.add(guest)
    db.commit()
    return identity(guest, issue(guest, response, db, request))


@app.put("/privacy/consent")
def consent(body: Consent, user=Depends(user_required), db=Depends(get_db)):
    user.consent = body.consent
    if not body.consent:
        for model in [Event, RecommendationRequest, QuizProfile]:
            db.execute(delete(model).where(model.user_id == user.id))
    db.commit()
    return {
        "consent": user.consent,
        "note": "Withdrawal removes your personal tracking/profile and excludes future training. Existing aggregate model contributions clear with retraining.",
    }


@app.get("/privacy/export")
def personal_export(user=Depends(user_required), db=Depends(get_db)):
    profile = db.get(QuizProfile, user.id)
    return {
        "user": {"id": user.id, "email": user.email, "consent": user.consent},
        "wishlist": [
            w.product_id
            for w in db.scalars(select(Wishlist).where(Wishlist.user_id == user.id))
        ],
        "quiz": profile.answers if profile else None,
        "orders": order_list(user, db),
        "checkout_orders": [public_order(order, db) for order in db.scalars(
            select(Order).where(Order.user_id == user.id, Order.order_number.is_not(None)))],
        "security_history": [
            {"kind": event.kind, "success": event.success,
             "created_at": event.created_at.isoformat() + "Z",
             "ip_address": event.ip_address, "location": event.location,
             "user_agent": event.user_agent}
            for event in db.scalars(select(SecurityEvent).where(
                SecurityEvent.user_id == user.id,
                SecurityEvent.created_at >= now() - timedelta(days=90)))
        ],
        "events": [
            {
                "product_id": e.product_id,
                "type": e.event_type,
                "created_at": str(e.created_at),
            }
            for e in db.scalars(select(Event).where(Event.user_id == user.id))
        ],
    }


@app.get("/products")
def products(
    q: str | None = None,
    category: str | None = None,
    brand: str | None = None,
    budget: float | None = None,
    size: int | None = None,
    gender: str | None = None,
    season: str | None = None,
    in_stock: bool = False,
    sort: str = "featured",
    db=Depends(get_db),
):
    rows = available(
        db,
        q=q,
        category=category,
        brand=brand,
        budget=budget,
        size=size,
        gender=gender,
        season=season,
        in_stock=in_stock,
    )
    rows.sort(
        key=(lambda p: p["price_from"])
        if sort == "price-low"
        else (lambda p: -p["price_from"])
        if sort == "price-high"
        else (lambda p: (not p["pinned"], p["id"]))
    )
    return {
        "products": rows,
        "brands": list(db.scalars(
            select(Product.brand).where(
                Product.hidden == False, Product.launch_date <= date.today(),
                Product.id.in_(select(Variant.product_id)),
            ).distinct().order_by(Product.brand)
        )),
    }


@app.get("/products/{slug}")
def product(slug: str, db=Depends(get_db)):
    p = db.scalar(
        select(Product).where(
            Product.slug == slug,
            Product.hidden == False,
            Product.launch_date <= date.today(),
        )
    )
    if not p:
        raise HTTPException(404, "Scent not found")
    return product_json(p, db)


@app.get("/wishlist")
def wishlist(user=Depends(user_required), db=Depends(get_db)):
    rows = db.scalars(
        select(Product)
        .join(Wishlist, Wishlist.product_id == Product.id)
        .where(Wishlist.user_id == user.id, Product.hidden == False)
    ).all()
    return {"products": [product_json(p, db) for p in rows]}


@app.put("/wishlist/{pid}")
def add_wishlist(pid: int, user=Depends(user_required), db=Depends(get_db)):
    p = db.get(Product, pid)
    if not p or p.hidden:
        raise HTTPException(404, "Product not found")
    if not db.scalar(
        select(Wishlist).where(Wishlist.user_id == user.id, Wishlist.product_id == pid)
    ):
        db.add(Wishlist(user_id=user.id, product_id=pid))
        functional_event(db, user, pid, "wishlist_add")
        db.commit()
    return {"ok": True}


@app.delete("/wishlist/{pid}")
def remove_wishlist(pid: int, user=Depends(user_required), db=Depends(get_db)):
    db.execute(
        delete(Wishlist).where(Wishlist.user_id == user.id, Wishlist.product_id == pid)
    )
    functional_event(db, user, pid, "wishlist_remove")
    db.commit()
    return {"ok": True}


@app.get("/cart")
def cart(user=Depends(user_required), db=Depends(get_db)):
    rows = db.execute(
        select(CartItem, Variant, Product)
        .join(Variant, CartItem.variant_id == Variant.id)
        .join(Product, Variant.product_id == Product.id)
        .where(CartItem.user_id == user.id)
    ).all()
    items = [
        {
            "variant_id": v.id,
            "quantity": c.quantity,
            "size_ml": v.size_ml,
            "price": float(v.price),
            "stock": v.stock,
            "product": product_json(p, db),
        }
        for c, v, p in rows
    ]
    return {
        "items": items,
        "total": round(sum(r["quantity"] * r["price"] for r in items), 2),
    }


@app.put("/cart")
def update_cart(body: CartUpdate, user=Depends(user_required), db=Depends(get_db)):
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    v = db.get(Variant, body.variant_id)
    if not v or db.get(Product, v.product_id).hidden:
        raise HTTPException(404, "Product not found")
    if v.stock < body.quantity:
        raise HTTPException(409, "Insufficient stock")
    row = db.scalar(
        select(CartItem).where(CartItem.user_id == user.id, CartItem.variant_id == v.id)
    )
    if row:
        row.quantity = body.quantity
    else:
        db.add(CartItem(user_id=user.id, variant_id=v.id, quantity=body.quantity))
    functional_event(db, user, v.product_id, "add_to_cart")
    db.commit()
    return cart(user, db)


@app.post("/cart/add")
def quick_add_cart(body: CartUpdate, user=Depends(user_required), db=Depends(get_db)):
    # Serialize additive and replacement bag writes for this user across devices.
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    existing = db.scalar(select(CartItem).where(
        CartItem.user_id == user.id, CartItem.variant_id == body.variant_id))
    quantity = body.quantity + (existing.quantity if existing else 0)
    if quantity > 10:
        raise HTTPException(409, "You can add up to 10 bottles of a size to your bag.")
    return update_cart(CartUpdate(variant_id=body.variant_id, quantity=quantity), user, db)


@app.delete("/cart/{vid}")
def remove_cart(vid: int, user=Depends(user_required), db=Depends(get_db)):
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    db.execute(
        delete(CartItem).where(CartItem.user_id == user.id, CartItem.variant_id == vid)
    )
    db.commit()
    return cart(user, db)


@app.post("/checkout")
def checkout(user=Depends(user_required)):
    raise HTTPException(410, "Continue to secure checkout to complete your purchase.")


def order_list(user, db):
    return [
        {
            "id": o.id,
            "total": float(o.total),
            "created_at": str(o.created_at),
            "status": o.status,
            "order_number": o.order_number,
            "payment_status": o.payment_status,
            "payment_mode": o.payment_mode,
        }
        for o in db.scalars(
            select(Order)
            .where(Order.user_id == user.id)
            .order_by(Order.created_at.desc())
            .limit(50)
        )
    ]


@app.get("/orders")
def orders(user=Depends(user_required), db=Depends(get_db)):
    return order_list(user, db)


@app.post("/events")
def event(body: TrackedEvent, user=Depends(user_required), db=Depends(get_db)):
    if not user.consent:
        return {"accepted": False, "reason": "Personalization is off"}
    p = db.get(Product, body.product_id)
    if not p or p.hidden:
        raise HTTPException(404, "Product not found")
    req = None
    if body.recommendation_id:
        req = db.get(RecommendationRequest, body.recommendation_id)
        if (
            not req
            or req.user_id != user.id
            or body.product_id not in req.product_ids
            or req.created_at < now() - timedelta(days=7)
        ):
            raise HTTPException(422, "Invalid recommendation attribution")
        duplicate = db.scalar(
            select(Event).where(
                Event.user_id == user.id,
                Event.recommendation_id == req.id,
                Event.product_id == body.product_id,
                Event.event_type == body.event_type,
            )
        )
        if duplicate:
            return {"accepted": True, "duplicate": True}
    elif body.event_type != "view":
        raise HTTPException(422, "Recommendation reference required")
    db.add(
        Event(
            user_id=user.id,
            product_id=body.product_id,
            event_type=body.event_type,
            recommendation_id=req.id if req else None,
            slot=req.slot if req else None,
            model_version=req.model_version if req else None,
        )
    )
    db.commit()
    return {"accepted": True}


@app.get("/recommend/user")
def recommend_user(
    budget: float | None = None,
    size: int | None = None,
    gender: str | None = None,
    season: str | None = None,
    in_stock: bool = True,
    k: int = Query(8, ge=1, le=24),
    experiment: str | None = None,
    user=Depends(user_required),
    db=Depends(get_db),
):
    return results(
        db,
        user,
        budget=budget,
        size=size,
        gender=gender,
        season=season,
        in_stock=in_stock,
        k=k,
        experiment=experiment,
    )


@app.get("/recommend/similar")
def similar(
    product_id: int,
    budget: float | None = None,
    size: int | None = None,
    gender: str | None = None,
    season: str | None = None,
    in_stock: bool = True,
    user=Depends(user_required),
    db=Depends(get_db),
):
    return results(
        db,
        user,
        "similar",
        product_id,
        budget=budget,
        size=size,
        gender=gender,
        season=season,
        in_stock=in_stock,
    )


@app.get("/recommend/also-bought")
def also_bought(product_id: int, user=Depends(user_required), db=Depends(get_db)):
    return results(db, user, "also-bought", product_id)


@app.get("/recommend/substitutes")
def substitutes(product_id: int, user=Depends(user_required), db=Depends(get_db)):
    return results(db, user, "substitutes", product_id)


@app.get("/recommend/cart")
def cart_recs(user=Depends(user_required), db=Depends(get_db)):
    return results(db, user, "cart")


@app.post("/recommend/quiz")
def quiz(body: Quiz, user=Depends(user_required), db=Depends(get_db)):
    from .ml.recommender import quiz_weights

    answers = body.model_dump()
    weights = quiz_weights(answers)
    if user.consent:
        profile = db.get(QuizProfile, user.id)
        if profile:
            profile.answers = answers
            profile.weights = weights
            profile.created_at = now()
        else:
            db.add(QuizProfile(user_id=user.id, answers=answers, weights=weights))
        functional_event(db, user, None, "quiz_submit")
    db.commit()
    return results(
        db, user, "quiz", quiz=weights, budget=body.budget, size=body.size, k=12
    )


@app.get("/search")
def natural_search(
    q: str = Query(min_length=2, max_length=200),
    method: str = "hybrid",
    db=Depends(get_db),
):
    from ml.search import parse_query, eligible_ids, load_index, rank
    from ml.core import ARTIFACTS

    b = bundle()
    parsed = parse_query(q)
    index = load_index(b.get("search_path", str(ARTIFACTS / "search")))
    ranked = rank(index, parsed["text"], eligible_ids(db, parsed), method)[:12]
    products = {
        p.id: p for p in db.scalars(select(Product).where(Product.id.in_(ranked)))
    }
    return {
        "products": [product_json(products[pid], db) for pid in ranked],
        "parsed": parsed,
        "method": method,
        "model_version": b["version"],
        "simulated_data": True,
        "manual_review_required": True,
    }


@app.get("/intelligence")
def intelligence():
    return bundle()["metrics"]


@app.get("/forecast/sku")
def sku_forecast(
    sku: str,
    horizon: int = Query(8, ge=4, le=12),
    model: str = "lightgbm",
    user=Depends(admin_required),
):
    b = bundle()
    available = b["forecast"].get("models", {})
    if model not in available:
        raise HTTPException(422, "Choose seasonal_naive, lightgbm, lstm or nbeats")
    series = next(
        (s for s in available[model] if s["sku"] == sku or str(s["id"]) == sku), None
    )
    if not series:
        raise HTTPException(404, "SKU not found")
    return series | {
        "forecast": series["forecast"][:horizon],
        "model_version": b["version"],
        "simulated_data": True,
        "as_of": b["forecast"]["as_of"],
        "interval_note": b["forecast"]["metrics"]["interval_note"],
    }


@app.get("/forecast/sku/{id}")
def sku_forecast_by_id(
    id: str,
    horizon: int = Query(8, ge=4, le=12),
    model: str = "lightgbm",
    user=Depends(admin_required),
):
    return sku_forecast(id, horizon, model, user)


@app.get("/forecast/summary")
def forecast_summary(
    group: str = "all",
    key: str | None = None,
    horizon: int = Query(8, ge=4, le=12),
    model: str = "lightgbm",
    user=Depends(admin_required),
):
    b = bundle()
    if model not in b["forecast"].get("models", {}):
        raise HTTPException(422, "Choose seasonal_naive, lightgbm, lstm or nbeats")
    if group not in ["all", "brand", "category"]:
        raise HTTPException(422, "Choose all, brand or category")
    series = b["forecast"]["models"][model]
    if group == "category":
        series = b["forecast"]["category_models"][model]
    chosen = (
        series
        if group == "all"
        else [s for s in series if group in ["brand", "category"] and s[group] == key]
    )
    if not chosen:
        raise HTTPException(404, "Group not found")
    hist = defaultdict(lambda: defaultdict(float))
    future = defaultdict(lambda: defaultdict(float))
    for s in chosen:
        for r in s["history"]:
            for f in ["actual", "revenue"]:
                hist[r["week"]][f] += r[f]
        for r in s["forecast"][:horizon]:
            for f in [
                "prediction",
                "lower80",
                "upper80",
                "lower95",
                "upper95",
                "revenue",
            ]:
                future[r["week"]][f] += r[f]
    return {
        "model": model,
        "model_version": b["version"],
        "simulated_data": True,
        "as_of": b["forecast"]["as_of"],
        "aggregation": "direct category model"
        if group == "category"
        else "sum of SKU forecasts",
        "history": [{"week": w, **r} for w, r in sorted(hist.items())],
        "forecast": [{"week": w, **r} for w, r in sorted(future.items())],
        "skus": len(chosen),
        "interval_note": bundle()["forecast"]["metrics"]["interval_note"],
        "revenue_note": "Forecast revenue uses current catalogue prices; historical series here is valued at current prices.",
    }


@app.get("/admin/overview")
def admin_overview(
    start: str | None = None,
    end: str | None = None,
    user=Depends(admin_required),
    db=Depends(get_db),
):
    from .analytics import overview

    return overview(db, start, end)


def inventory_rows(db):
    rows = []
    for saved in bundle()["forecast"]["inventory"]:
        v = db.get(Variant, saved["variant_id"])
        stock = v.stock
        risk = (
            "stockout"
            if stock == 0
            else "reorder"
            if stock < saved["reorder_point"]
            else "overstock"
            if stock > max(saved["weekly_demand"] * 12, saved["safety_stock"] + 12)
            else "healthy"
        )
        rows.append(
            saved
            | {
                "stock": stock,
                "risk": risk,
                "suggested_reorder": max(0, saved["target_stock"] - stock)
                if risk in ["reorder", "stockout"]
                else 0,
            }
        )
    return rows


@app.get("/admin/inventory")
def admin_inventory(user=Depends(admin_required), db=Depends(get_db)):
    return inventory_rows(db)


@app.get("/admin/segments")
def admin_segments(user=Depends(admin_required), db=Depends(get_db)):
    from .analytics import segments

    return segments(db)


@app.get("/admin/evaluation")
def admin_evaluation(user=Depends(admin_required)):
    return bundle()["metrics"]


@app.get("/admin/tracking")
def admin_tracking(
    sku: str | None = None, user=Depends(admin_required), db=Depends(get_db)
):
    holdout = [
        r for r in bundle()["forecast"]["tracking"] if not sku or r["sku"] == sku
    ]
    saved = db.scalars(
        select(ForecastSnapshot).where(ForecastSnapshot.sku == sku)
        if sku
        else select(ForecastSnapshot)
    ).all()
    return {
        "holdout": holdout,
        "live": [
            {
                "version": r.version,
                "sku": r.sku,
                "week": str(r.target_week),
                "prediction": r.prediction,
                "actual": r.actual,
                "lower80": r.lower80,
                "upper80": r.upper80,
                "lower95": r.lower95,
                "upper95": r.upper95,
            }
            for r in saved
        ],
    }


@app.get("/admin/products")
def admin_products(user=Depends(admin_required), db=Depends(get_db)):
    return [
        product_json(p, db) for p in db.scalars(select(Product).order_by(Product.id))
    ]


@app.put("/admin/products/{pid}")
def override(
    pid: int, body: Override, user=Depends(admin_required), db=Depends(get_db)
):
    if body.pinned and body.hidden:
        raise HTTPException(422, "A hidden product cannot be pinned")
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(404, "Product not found")
    p.pinned = body.pinned
    p.hidden = body.hidden
    db.add(
        AuditLog(
            actor=user.id,
            action="recommendation_override",
            detail={"product_id": pid, **body.model_dump()},
        )
    )
    db.commit()
    return {"ok": True}


@app.put("/admin/stock/{vid}")
def stock_update(
    vid: int, body: Stock, user=Depends(admin_required), db=Depends(get_db)
):
    v = db.get(Variant, vid)
    if not v:
        raise HTTPException(404, "SKU not found")
    v.stock = body.stock
    db.add(
        AuditLog(
            actor=user.id,
            action="stock_update",
            detail={"variant_id": vid, "stock": body.stock},
        )
    )
    db.commit()
    return {"ok": True}


@app.get("/admin/models")
def models(user=Depends(admin_required), db=Depends(get_db)):
    return [
        {
            "version": r.version,
            "created_at": str(r.created_at),
            "data_hash": r.data_hash,
            "mlflow_run_id": r.mlflow_run_id,
        }
        for r in db.scalars(select(ModelRun).order_by(ModelRun.created_at.desc()))
    ]


@app.get("/admin/monitor")
def monitor(user=Depends(admin_required), db=Depends(get_db)):
    import numpy as np
    from .ml.metrics import metrics as forecast_metrics

    b = bundle()
    data = np.array([l[1] for l in latencies])
    views = db.execute(
        select(Event.product_id, func.count())
        .where(
            Event.event_type == "view", Event.created_at >= now() - timedelta(days=28)
        )
        .group_by(Event.product_id)
    ).all()
    count = dict(views)
    observed = np.array([count.get(pid, 0) for pid in b["recommender"]["ids"]], float)
    base = b["recommender"]["popularity"]
    base = (base + 0.01) / (base + 0.01).sum()
    observed = (observed + 0.01) / (observed + 0.01).sum()
    psi = float(sum((observed - base) * np.log(observed / base)))
    completed = db.scalars(
        select(ForecastSnapshot).where(
            ForecastSnapshot.version == b["version"],
            ForecastSnapshot.actual.is_not(None),
        )
    ).all()
    live_error = {"observations": len(completed), "wape": None, "smape": None}
    if completed:
        values = forecast_metrics(
            [r.actual for r in completed], [r.prediction for r in completed], [0, 1]
        )
        live_error.update({key: values[key] for key in ["wape", "smape"]})
    return {
        "latency": {
            "samples": len(data),
            "p50_ms": float(np.percentile(data, 50)) if len(data) else None,
            "p95_ms": float(np.percentile(data, 95)) if len(data) else None,
            "error_rate": sum(l[2] >= 500 for l in latencies) / len(latencies)
            if latencies
            else 0,
            "scope": "This API process only",
        },
        "drift": {
            "psi": psi,
            "events": sum(count.values()),
            "alert": psi > 0.25 and sum(count.values()) >= 200,
            "note": "Recent view distribution versus training purchase popularity. Different signals can produce drift without model failure.",
        },
        "forecast_error": b["metrics"]["forecast"],
        "live_forecast_error": live_error,
        "model_version": b["version"],
    }


@app.post("/admin/ab-simulate")
def experiment(body: Experiment, user=Depends(admin_required)):
    from .ml.experiments import ab_simulate

    return ab_simulate(**body.model_dump())


@app.get("/admin/export")
def export(
    kind: str = "sales",
    start: str | None = None,
    end: str | None = None,
    user=Depends(admin_required),
    db=Depends(get_db),
):
    from .analytics import date_range

    if kind == "inventory":
        rows = inventory_rows(db)
    elif kind == "products":
        rows = [
            {
                "id": p.id,
                "name": p.name,
                "brand": p.brand,
                "pinned": p.pinned,
                "hidden": p.hidden,
            }
            for p in db.scalars(select(Product))
        ]
    elif kind == "tracking":
        tracked = admin_tracking(None, user, db)
        rows = [r | {"version": bundle()["version"]} for r in tracked["holdout"]]
        rows.extend(r | {"kind": "live_snapshot"} for r in tracked["live"])
    elif kind == "sales":
        lo, hi = date_range(start, end)
        rows = [
            {
                "id": o.id,
                "date": str(o.created_at),
                "total": float(o.total),
                "status": o.status,
                "simulated": o.simulated,
            }
            for o in db.scalars(
                select(Order).where(Order.created_at >= lo, Order.created_at < hi, or_(Order.payment_status.is_(None), Order.payment_status == "paid"))
            )
        ]
    else:
        raise HTTPException(422, "Choose sales, inventory, products or tracking")
    stream = io.StringIO()
    writer = csv.DictWriter(
        stream,
        fieldnames=list(dict.fromkeys(key for row in rows for key in row))
        if rows
        else ["no_data"],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                k: (
                    "'" + v
                    if isinstance(v, str) and v.startswith(("=", "+", "-", "@"))
                    else v
                )
                for k, v in row.items()
            }
        )
    return Response(
        stream.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="scenthaus-{kind}.csv"'},
    )


@app.get("/internal/maintenance", include_in_schema=False)
def daily_maintenance(request: Request):
    expected = settings.cron_secret
    if not expected or not secrets.compare_digest(
        request.headers.get("authorization", ""), "Bearer " + expected
    ):
        raise HTTPException(401, "Cron authorization required")
    from .maintenance import maintain

    maintain()
    return {"ok": True, "task": "retention_and_forecast_reconciliation"}
