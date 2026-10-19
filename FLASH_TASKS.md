# Gemini 3.8 Flash — Ready-to-Run Task Prompts (F1–F11)

Use these self-contained prompts with **Gemini 3.8 Flash** (or a lower-cost model) to complete the pattern-following tasks while preserving your high-tier usage. Each task points to the exact files and the reference implementation in `backend/app/domains/catalog/`.

---

## Task F1 — Gate Demo/"Simulated" UI Copy on Storefront Config (`is_demo`)
**Prompt to copy:**
> Read `AGENTS.md`, `frontend/src/App.jsx`, and `frontend/src/Checkout.jsx`.
> Fetch `/storefront/config` in `frontend/src/context.jsx` on boot and expose `storeConfig` (`{ name, currency, is_demo, theme, hero_title, hero_subtitle }`) in the context.
> Wrap all portfolio/demo disclaimer banners and `"simulated"` badges in `frontend/src/App.jsx` (around lines 249, 1469, 1483, 1543, 1578, 1610–1618) and `frontend/src/Checkout.jsx` (around line 148) so they ONLY render when `storeConfig?.is_demo === true`.
> Replace hardcoded `"SCENTHAUS"` header/hero text with `storeConfig?.name || "SCENTHAUS"`. Run `npm --prefix frontend test` and `npm --prefix frontend run build` to verify.

---

## Task F2 — Split Monolithic `frontend/src/App.jsx` and `frontend/src/Admin.jsx` into Page Modules
**Prompt to copy:**
> Read `frontend/src/App.jsx` and `frontend/src/Admin.jsx`.
> Without changing any behavior, CSS classes, or test selectors, extract the page components from `frontend/src/App.jsx` into `frontend/src/pages/` (`HomePage.jsx`, `ShopPage.jsx`, `ProductDetailPage.jsx`, `QuizPage.jsx`, `WishlistPage.jsx`, `CartPage.jsx`, `OrderPage.jsx`, `PrivacyPage.jsx`, `IntelligencePage.jsx`) and re-export/route them in `App.jsx`.
> Run `npm --prefix frontend test` and `npm --prefix frontend run build` to verify zero regressions.

---

## Task F3 — Create Production `Dockerfile` and `docker-compose.yml` (API + Worker + Postgres + Redis)
**Prompt to copy:**
> Create a multi-stage `backend/Dockerfile` (Python 3.12-slim) that installs `backend/requirements.txt` (without PyTorch in the runtime API image) and supports two entrypoints:
> 1. API server: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
> 2. Background worker: `python -m app.worker`
> Create a root `docker-compose.yml` with `postgres:16`, `redis:7-alpine`, `api`, and `worker` services. Update `render.yaml` and `railway.toml` to point to `backend/Dockerfile`.

---

## Task F4 — Clone `domains/catalog/` Pattern for Tenant Customers & Coupon Codes
**Prompt to copy:**
> Read `AGENTS.md` and inspect the reference module in `backend/app/domains/catalog/` (`schemas.py`, `service.py`, `router.py`).
> Create `backend/app/domains/customers/` following the exact same 3-file pattern:
> - `GET /tenant/customers`: List non-simulated customers (`User.tenant_id == tenant.id`, `User.email.is_not(None)`) with order count and total spend.
> - `GET /tenant/customers/{user_id}`: Customer detail + order history for that tenant.
> Register the router in `backend/app/main.py` and add tests in `backend/tests/test_multi_tenant_saas.py`.

---

## Task F5 — Merchant Admin UI for Product CRUD, Variants & Order Fulfilment
**Prompt to copy:**
> Read `backend/app/domains/catalog/router.py`, `backend/app/orders/state_machine.py`, and `frontend/src/Admin.jsx`.
> Add two new tabs in `frontend/src/Admin.jsx`:
> 1. **Catalog Manager**: Create/edit products (`POST /tenant/catalog/products`, `PUT /tenant/catalog/products/{id}`) and add/edit SKU variants (`POST /tenant/catalog/products/{id}/variants`).
> 2. **Orders & Fulfilment**: Table of orders from `GET /tenant/orders` with buttons to transition status (`fulfilling`, `shipped` with carrier + tracking number modal, `delivered`, `refunded` with restock checkbox) calling `POST /tenant/orders/{order_id}/transition`.
> Run `npm --prefix frontend run build` to verify.

---

## Task F6 — Bulk CSV Product & Variant Import/Export for Merchants
**Prompt to copy:**
> Read `backend/app/domains/catalog/service.py` and `backend/app/domains/catalog/router.py`.
> Add `GET /tenant/catalog/export.csv` and `POST /tenant/catalog/import.csv` to `backend/app/domains/catalog/router.py`.
> Escape CSV formula-injection characters (`=`, `+`, `-`, `@`) on export, validate rows with `ProductCreate`/`VariantCreate` on import, and log an `AuditLog` entry (`catalog.csv_imported`). Add a unit test in `backend/tests/test_multi_tenant_saas.py`.

---

## Task F7 — Transactional Email Templates & Job Handlers
**Prompt to copy:**
> Read `backend/app/jobs/queue.py`.
> Create `backend/app/notifications/emails.py` registering `@register_task("email.order_confirmed")`, `@register_task("email.order_shipped")`, `@register_task("email.order_refunded")`, and `@register_task("email.password_reset")`.
> Provide clean HTML + plain-text templates parameterized by `tenant.name` and `tenant.settings_json`, sending via Resend/SMTP when `RESEND_API_KEY` or `SMTP_HOST` is set in `config.py`, and logging in development/test.

---

## Task F8 — Dynamic Tenant CSS Variables (`styles.css`)
**Prompt to copy:**
> Read `frontend/src/styles.css` and `backend/app/tenancy/router.py` (`GET /storefront/config`).
> Extract hardcoded brand colors and font families in `frontend/src/styles.css` into root CSS variables (`--brand-bg`, `--brand-surface`, `--brand-text`, `--brand-accent`, `--font-display`, `--font-sans`) with the current SCENTHAUS palette as defaults.
> Apply overrides from `storeConfig.theme` onto `document.documentElement.style` when `/storefront/config` loads.
