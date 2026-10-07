# Vercel deployment

This repository targets Vercel Services for the React/Vite storefront and FastAPI API. It does not use Docker or Render. Vercel's project root must be the repository root so it can read `vercel.json`; the config assigns `frontend/` and `backend/` to their services and routes `/api/*` to FastAPI.

## Before deploying

Create two separate managed PostgreSQL databases: one for Preview and one for Production. Each database must be new and empty for the first build of this release. Do not point this release at the older production database: the bootstrap validates the exact 150-product reference catalogue and fails without modifying an older or mixed catalogue.

Add the variables below to the matching Vercel environment. Do not copy Production database values into branch previews.

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | PostgreSQL URL for API requests. Use a TLS URL and a provider's pooled endpoint where supported. |
| `DATABASE_URL_UNPOOLED` | Direct PostgreSQL URL for the build's transaction-scoped advisory lock. |
| `ENVIRONMENT` | `production` |
| `SECRET_KEY` | Unique random value of at least 32 characters. |
| `ADMIN_EMAIL` | Initial admin email for the empty-database seed. |
| `ADMIN_PASSWORD` | Unique initial admin password, at least 12 characters. |
| `CRON_SECRET` | Unique bearer secret for the daily maintenance cron. |
| `ALLOWED_ORIGINS` | Exact public HTTPS storefront origin. Vercel's current and production project URLs are also added at runtime. |

The frontend uses same-origin `/api` requests. No `VITE_API_URL` is needed. Local values and examples are in [`frontend/.env.example`](../frontend/.env.example) and [`backend/.env.example`](../backend/.env.example).

## Build and initialization

The API service build command is `python -m app.vercel_build`. It checks the required database variables, creates a temporary build-only Python environment, installs CPU PyTorch and training dependencies, then runs `app.vercel_init`. The initializer takes a transaction-scoped PostgreSQL advisory lock on the direct connection, applies Alembic migrations, seeds only an empty database with the 150 real-product references and simulated records, validates the catalogue, trains a versioned bundle when one is not current, and downloads the pinned ONNX query encoder.

The API build then copies only the inference modules and YAML configs into the API service root. The function includes those files and `backend/artifacts/`; its request path uses NumPy and ONNX Runtime and never trains or writes model files. Generated weights and simulated training records are not committed.

The first build trains from the synthetic history and may take substantially longer than a frontend build. If it fails because the database lacks the 150-product catalogue or the build environment lacks the required variables, it fails closed. Create a separate clean database or correct the environment settings, then retry; it does not rewrite a legacy catalogue.

## Release verification

After setting environment values and deploying, verify:

1. The API build completed its migrations, clean seed, catalogue check, model registration and ONNX checksum check.
2. `/api/health` succeeds and `/api/products?in_stock=false` returns 150 products from 35 brands.
3. Search, product pages, quiz, wishlist, cart and demo checkout work; checkout takes no payment.
4. Consent-off quiz answers are not retained; opt-in tracking, export and withdrawal behave as documented.
5. Guest access to `/admin/forecast` is rejected, and an admin can inspect model versions, forecast comparisons and inventory signals.
6. Vercel logs show no API errors and the scheduled `/api/internal/maintenance` request is authorized with `CRON_SECRET`.

Do not change the public demo alias until the new release passes these checks. Current account and deployment observations are in [`reports/deployment.md`](../reports/deployment.md); automated code checks are tracked in [`reports/verification.md`](../reports/verification.md).

## Current release status

Separate Neon databases are connected: `scenthaus-reference-preview` is Preview-only and `scenthaus-reference-production` is Production-only. The older catalogue database remains connected under the `LEGACY` variable prefix and has not been overwritten. App secrets are stored in the matching Vercel environments and are not committed.

The production source branch is `complete-phases-real-catalog`. Automatic production-domain assignment is disabled while builds are staged; manually promote only a verified Production deployment. A Preview must never be promoted directly because it uses the Preview database.

The first clean Preview completed seed/training but exposed an idle-lock connection shutdown at cleanup. Source `7694dcda` holds its direct build connection in a transaction with `pg_advisory_xact_lock` and uses `SET LOCAL idle_in_transaction_session_timeout = '0'`. The override lasts only for this transaction; the connection keeps Neon active during CPU-only training and releases the lock on either successful or failed builds. The runtime dependency list also explicitly includes PyJWT; the isolated packaged-API check verifies startup and JWT auth without the training libraries. Preview and Production source `7694dcda` passed hosted model startup, catalogue, search and guest shopping checks and the public alias was promoted. Source `618a1d1` additionally replaces per-snapshot maintenance queries with a bounded bulk reconciliation. Its nine native tests, four browser journeys and runtime-only API checks passed; the promoted Production Cron returned 200 in 1.83 seconds. The updated portfolio includes its live link and storefront cover. See [`reports/deployment.md`](../reports/deployment.md).

## References

- [Vercel Services](https://vercel.com/docs/services)
- [Vercel Services routing](https://vercel.com/docs/services/routing)
- [Vercel project configuration](https://vercel.com/docs/project-configuration/vercel-json)
- [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi)
- [Python runtime file inclusion](https://vercel.com/docs/functions/runtimes/python)
- [Vercel Cron Jobs](https://vercel.com/docs/cron-jobs)

## Stripe payment deployment

The existing Vercel Services architecture also serves the secure Checkout API and raw-body webhook endpoint. Configure Production variables and register the exact mode-specific webhook as described in [Stripe checkout](stripe-checkout.md). Keep branch previews on separate databases and test credentials. The checkout release does not migrate to Docker or reset the catalogue.
