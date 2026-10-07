# Vercel release evidence

Current release: Stripe runtime source `2398d7504b3a014105aca83f22655153ca8c02a8` is Ready and promoted. Full native CI passed 119 Python tests, 15 frontend tests and 12 browser journeys. Actual hosted test payment, signed confirmation, decline, cancellation and event retries passed. Portfolio source `9b0001c4` is Ready and publicly verified. See [complete Stripe release evidence](stripe-verification.md). The earlier catalogue and maintenance releases below are historical.

| Item | Evidence |
| --- | --- |
| Source | `complete-phases-real-catalog`, source `7694dcda`; exact prepared tree `1070274919b3f84d57d13d37a9fc01dc82dd8c3f`. The publication is a normal descendant of the checked remote head; no force push. |
| Storefront | Searchable directory of all 35 houses, direct brand filters and quick bag actions. Catalogue: 150 product references, 297 size variants. Prices, stock and commerce are simulated. |
| Full storefront CI | [Run `37458566982`](https://github.com/TeddyQyuon/scenthaus-intelligence/actions/runs/37458566982) passed actual training, 65 Python tests, Ruff, four browser journeys and the frontend build for storefront source `2137b64`. |
| Exact-source CI | [Run `37466416865`](https://github.com/TeddyQyuon/scenthaus-intelligence/actions/runs/37466416865) pins `7694dcda`: seven native PostgreSQL tests, Ruff, four browser journeys, frontend build and isolated runtime-only API verification passed. |
| Preview database | Neon `scenthaus-reference-preview`, store `store_gUcEwpPttoWcy6gS`, connected only to Preview. The clean seed completed with 150 products and 35 brands. |
| Production database | Neon `scenthaus-reference-production`, store `store_oWze3kXlNpqn52Un`, connected only to Production. |
| Legacy preservation | The old `scenthaus-postgres` database, store `store_Leo9nCxNV99KSvAk`, remains connected under `LEGACY_*` variables. No catalogue rows were overwritten or database deleted. |
| Corrected Preview | [Deployment `ETd1JVrzTfR55k2KsTgihq1faYcz`](https://vercel.com/qyuon1/scenthaus-intelligence/ETd1JVrzTfR55k2KsTgihq1faYcz), source `7694dcda`, Ready; hosted catalogue, search, consent-off quiz, wishlist/bag and demo checkout verified. Model `20261006T130203-15589597-36ae7611`. |
| Staged Production | [Deployment `ACQSAZuUg8E3VsDPu8neugu7F2K9`](https://vercel.com/qyuon1/scenthaus-intelligence/ACQSAZuUg8E3VsDPu8neugu7F2K9), source `7694dcda`, Ready and promoted after hosted checks. Uses the dedicated Production database; model `20261006T131850-15589597-03587659`. |
| Release settings | Production branch is `complete-phases-real-catalog`. Automatic domain assignment is disabled; promote the verified Production deployment manually. Do not promote a Preview backed by the Preview database. |

The first clean Preview (`3gQRkupm1RSNbWKJr8N1amgFABFs`, source `2137b64`) completed model training, catalogue validation, model registration and runtime packaging. It then failed while releasing the session advisory lock because the idle direct connection had been shut down. The transaction-scoped advisory lock subsequently needed a transaction-local idle-timeout override. Source `7694dcda` includes both corrections and the missing PyJWT runtime dependency. Its context releases the lock on commit or rollback. Native regressions check concurrent exclusion, release on both success and failure, and restoration of the session timeout. The packaged API is separately exercised without training dependencies. This build failure was not treated as a successful deployment.

The databases use the existing Neon Marketplace installation and Free plan. The application keeps its own authentication; Neon Auth is disabled. Production app credentials remain as configured, while Preview has its own app secrets. No credentials are recorded in this report or source control.

Hosted source `7694dcda` verified health, 150 products / 35 brands / 297 variants, model-versioned semantic search with an inferred $150 budget, guest admin and maintenance rejection, persistent bags and no-payment demo checkout. Preview also verified all-house navigation, encoded Hermès filtering, wishlist, quiz and public K=10 model metrics. Privileged admin/forecast flows were verified in isolated native CI; no hosted admin login is claimed. The portfolio release `cd1f59d2` is Ready and live with a new storefront cover, working Live demo link and current counts. The old pending-database notice is removed.

Running the daily maintenance from Vercel exposed a 504 after the 60-second function limit. It used one sales aggregate query for each forecast snapshot. Source `618a1d1a170cc4183ab9ff59751dbde523f5a421` reconciles completed weeks in one bulk update following the three retention deletes. Tests check inclusive/exclusive week boundaries, preservation of existing actuals, zero-sales snapshots, future snapshots and a bounded query count. Release checks are documented in [`docs/deployment.md`](../docs/deployment.md).

## Final maintenance release — 2026-10-07

Source `618a1d1a170cc4183ab9ff59751dbde523f5a421`, exact tree `d9dc756058e939dc0f991fa2ae59b8f1a23115a2`, passed [focused run `37558473333`](https://github.com/TeddyQyuon/scenthaus-intelligence/actions/runs/37558473333): nine native PostgreSQL tests, Ruff, four browser journeys, frontend build and the isolated runtime API including authenticated maintenance. Artifact `11455219018` SHA-256 `057c8839a54c8ffe90a6d2d8f2848301f9c60b6c7b731945cc02dc109bc5bb60` matches the downloaded ZIP.

Production deployment `dpl_CK5urixvbqqjkdZMBZmgeowbebwG` was Ready and checked before manual promotion. The live alias now serves model `20261006T134630-d486f55f-651788c8`; health is 200 with models ready and semantic search is 200 with an inferred $150 budget. Its dedicated database retains 150 products, 35 brands and 297 variants. The new build has a different data hash after the earlier simulated checkout, so its model version is recorded separately from the pristine CI seed.

The authorized Vercel Cron request at `2026-10-07T01:47:19.176Z` returned **200**, used `vercel-cron/1.0`, and completed its function in **1.83 seconds** (2.1-second total response). The log identifies this exact Production deployment and source branch. Unauthenticated requests returned 401. The daily schedule remains `0 20 * * *` UTC, subject to Hobby's one-hour scheduling window.

Sanitized receipts and screenshots are in [`release-2026-10-06/`](release-2026-10-06/). The final documentation publication changes no runtime files; retain the verified deployment rather than retraining for documentation alone.
