# Deployment status

**Checked 2026-10-06. The published real-catalogue source is not live.** The public Vercel domain still uses the older invented-catalogue application.

## Observed state

| Surface | Observation |
| --- | --- |
| Public domain | `https://scenthaus-intelligence.vercel.app/` responds. Its API returned older generated catalogue entries such as “Citrus Theory” from “Atelier 08”, not the current 150-product reference catalogue. |
| Latest ready Production deployment | Vercel lists `dpl_6oaHexM8rZ4V1mRdbc3QBewgrkLR`, source commit `22c3c35` on `main`; that source belongs to the older release. |
| Published-source Preview | [Deployment `8CoKSSaSCSR3m61HcsET7md7aeFS`](https://vercel.com/qyuon1/scenthaus-intelligence/8CoKSSaSCSR3m61HcsET7md7aeFS), source `2120a66`, failed with `RuntimeError: Set DATABASE_URL before building the SCENTHAUS API`. The storefront production build passed; API initialization did not begin. |
| Preview environment variables | The configured database integration and app secrets inspected for this project are scoped to `Production`; no Preview-scoped `DATABASE_URL` is configured. A branch Preview cannot initialize against a missing database URL. |
| New source release | Published on `complete-phases-real-catalog`. Initial tree `00b39de` exactly matches prepared source `560f2a4`; corrected runtime source `bebe4a5` passes all three browser journeys and the storefront build against the native-tested backend/model bundle. The new release requires a separate clean database. Its release guard fails before writing catalogue rows when the database contains a different catalogue. |

The request to `/api/products?in_stock=false` was read-only and showed the legacy catalogue. Environment variable names and target scopes were inspected without decrypting values. No secret was read or changed, and no database rows were modified.

## Repository publication

The cloud browser uploaded a checksum-verified source bundle to the recovery branch. The signed-in GitHub editor saved the two feature-branch workflows. The existing publisher checked the exact remote branch head, unchanged workflow contents and prepared source tree before publishing a normal descendant commit. No force push, new credential or permission expansion was used. The original phase commits remain in the bundle. Publication is complete; automated code verification is recorded in [`verification.md`](verification.md).

## Required owner setup

Create one empty managed PostgreSQL database for Preview and another for Production. Add the required `DATABASE_URL`, `DATABASE_URL_UNPOOLED`, `ENVIRONMENT`, `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `CRON_SECRET` and `ALLOWED_ORIGINS` values to the corresponding Vercel environments. Do not reuse the old catalogue database. Redeploy the published feature branch to Preview first and complete the smoke checks in [`docs/deployment.md`](../docs/deployment.md). Then build and verify the same source revision for Production using its dedicated Production database before changing the public alias.

The GitHub retraining workflow is an artifact-producing simulated-data job. It does not connect to Production or push a serving release. No production database credential was added to GitHub Actions.
