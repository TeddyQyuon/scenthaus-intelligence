# Deployment status

**Checked 2026-10-05. The current real-catalogue source is not live.** The public Vercel domain still answers with the older invented-catalogue application.

## Observed state

| Surface | Observation |
| --- | --- |
| Public domain | `https://scenthaus-intelligence.vercel.app/` responds. Its API returned older generated catalogue entries such as “Citrus Theory” from “Atelier 08”, not the current 150-product reference catalogue. |
| Latest ready Production deployment | Vercel lists `dpl_6oaHexM8rZ4V1mRdbc3QBewgrkLR`, source commit `22c3c35` on `main`; that source belongs to the older release. |
| Latest project deployment state | The Vercel project API reports the latest deployment as `ERROR` and `live: false`; the domain still has the earlier production response. |
| Preview environment variables | The configured database integration and app secrets inspected for this project are scoped to `Production`; no Preview-scoped `DATABASE_URL` is configured. A branch Preview cannot initialize against a missing database URL. |
| New source release | Local commit `f3ec1dc` contains the real-catalogue Vercel build and storefront changes. It has not been pushed, so no CI run or Vercel deployment exists for this commit. The new release requires a separate clean database. Its release guard fails before writing catalogue rows when the database contains a different catalogue. |

The request to `/api/products?in_stock=false` was read-only and showed the legacy catalogue. Environment variable names and target scopes were inspected without decrypting values. No secret was read or changed, and no database rows were modified.

## Repository publish access

The local `git push` could not prompt for GitHub credentials. The connected GitHub integration returned `403 Resource not accessible by integration` when asked to create a tree; the workspace has no GitHub CLI session. No remote ref was changed. The phase 7-9 work remains committed locally and needs a write-enabled GitHub connection or a normal authenticated push before CI or Vercel can run it.

## Required owner setup

Create one empty managed PostgreSQL database for Preview and another for Production. Add the required `DATABASE_URL`, `DATABASE_URL_UNPOOLED`, `ENVIRONMENT`, `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `CRON_SECRET` and `ALLOWED_ORIGINS` values to the corresponding Vercel environments. Do not reuse the old catalogue database. After the source branch is pushed, deploy Preview first and complete the smoke checks in [`docs/deployment.md`](../docs/deployment.md); only then promote the verified release.

The GitHub retraining workflow is an artifact-producing simulated-data job. It does not connect to Production or push a serving release. No production database credential was added to GitHub Actions.
