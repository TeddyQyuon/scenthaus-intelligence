# SCENTHAUS Multi-Tenant SaaS — Agent & Developer Conventions

SCENTHAUS is a multi-tenant fragrance commerce and ML intelligence SaaS platform.
Stack: React + Vite (`frontend/`), FastAPI + SQLAlchemy 2 + PostgreSQL with Row-Level Security (`backend/`), PyTorch for offline training and NumPy/ONNX Runtime for serving (`ml/`).

## Core Architecture Rules (MUST FOLLOW)

1. **Multi-Tenancy & Data Isolation**:
   - Every tenant-owned table (`products`, `variants`, `users`, `wishlists`, `cart_items`, `events`, `recommendation_requests`, `orders`, `model_runs`, `forecast_snapshots`, `audit_logs`, `background_jobs`) has a `tenant_id` column and a PostgreSQL Row-Level Security (`tenant_isolation_policy`) policy.
   - Public storefront routes MUST depend on `tenant: Tenant = Depends(resolve_tenant)` from `app.tenancy.deps`.
   - Merchant admin routes MUST depend on `ctx: tuple[Tenant, User] = Depends(require_tenant_role("owner", "admin", ...))` from `app.tenancy.deps`.
   - Always filter queries explicitly by `Model.tenant_id == tenant.id` in addition to RLS (`set_db_tenant_context(db, tenant.id)`).

2. **Standard Backend Domain Module Layout**:
   Copy the reference module in `backend/app/domains/catalog/` when adding or refactoring domain features:
   - `schemas.py` — Pydantic v2 models with `model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)`
   - `service.py` — Pure database/business logic functions taking `(db, tenant, ...)` and writing an `AuditLog` on state changes
   - `router.py` — FastAPI `APIRouter` wiring HTTP endpoints to `service.py`

3. **Cryptographic Key Separation (`backend/app/core/keys.py`)**:
   - Never use `settings.secret_key` directly for new tokens or encryption.
   - Use `derive_subkey(purpose)` / `derive_hex_key(purpose)` or `totp_fernet()` from `app.core.keys`.

4. **Order Lifecycle & Side Effects**:
   - All order state changes MUST go through `transition_order()` in `backend/app/orders/state_machine.py`.
   - Asynchronous side effects (emails, analytics, retraining) MUST be enqueued via `enqueue_job()` in `backend/app/jobs/queue.py`.

5. **Schema Changes**:
   - Only through defensive Alembic migrations in `backend/alembic/versions/`.
   - Never hardcode demo catalogue checks (`verify_catalog`) outside `settings.demo_mode`.
