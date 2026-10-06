# Verification record

## Storefront merchandising follow-up — 2026-10-06

The requested beauty-retail refresh exposes all 35 catalogue houses through searchable brand navigation, applies brand links to the collection filter, and adds visible quick bag actions. Local `npm run build`, JavaScript syntax and `git diff --check` pass. A consistency check confirms the 35 unique storefront house names match `backend/app/real_catalog.json` exactly.

A fourth Playwright journey now checks the mobile directory, brand search, encoded brand links and filtered results. The existing mobile journey uses the updated navigation label. These new journeys have not yet run locally: the Playwright browser download returned an invalid archive, and the cloud browser cannot open this workspace's loopback server. The earlier native/browser results below verify the earlier runtime revision; they do not verify this follow-up. Its Vercel release remains dependent on the separate clean databases described in `deployment.md`.

## Earlier verified runtime

**Checked 2026-10-06. Published runtime source: `bebe4a53604c0eaca58d791615ef677cb1903cc4`.** The backend, training code and dependencies are unchanged from native-tested source `2e19249ec2030c4b19a1c73336899e1413b78695`. Its three changed files are the two frontend views and their browser journeys.

| Check | Result | Scope |
| --- | --- | --- |
| Actual ML training | Passed in native CI | Baselines, two-tower variants, search, LSTM and N-BEATS. Four MLflow receipts identify source `2e19249` and the same dataset hash. |
| Python unit/integration tests | 65 passed, 0 skipped, 0 errors or failures | Native PostgreSQL after complete model training in [run `37411420198`](https://github.com/TeddyQyuon/scenthaus-intelligence/actions/runs/37411420198). No local full-suite pass is claimed. |
| Ruff | Passed in native CI and locally with pinned Ruff 0.14.14 | Includes the Vercel catalogue guard's corrected `date` import. |
| Browser journeys | 3 passed, 0 skipped, 0 failures or flaky tests | [Exact-source run `37413048770`](https://github.com/TeddyQyuon/scenthaus-intelligence/actions/runs/37413048770) used a fresh native PostgreSQL fixture and the immutable trained bundle. |
| Frontend production build | Passed locally and in exact-source CI | Run `37413048770` built the same published frontend after all three browser journeys passed. |
| README stack launcher | Passed: API, Vite and MLflow ready | `python scripts/dev.py` passed all three health checks in run `37413048770` from a fresh checkout. Installation, migration, seed and training commands were also exercised by native CI. |
| Model registration and integrity | Passed in native CI | `app.vercel_init.initialize()` verifies the exact catalogue, model checksums and matching fresh-seed data hash before registering model metadata and forecast snapshots. No training is performed in the browser verification job. |
| Syntax/config/whitespace | Passed | Python compile, Vercel JSON parse, browser-test JavaScript syntax and `git diff --check`. These are local structural checks. |
| Vercel Preview | Blocked before API initialization | Published-source Preview built the frontend, then failed because Preview `DATABASE_URL` is missing. |
| Vercel Production | Current source is not live | Latest ready Production is legacy source `22c3c35`. Required owner setup is recorded in [`deployment.md`](deployment.md). |

## Training and report provenance

The accepted training artifact is `11389448639` from run `37411420198`, with SHA-256 `7f594447df186782c2dbeea15a1e0a5757de2519a9ac342e7cff1ce16e92451c`. The downloaded ZIP matches that digest. Its JUnit receipt records 65 tests with no skips, failures or errors. The four generated evaluation reports in `ml/reports/`, README metrics and model cards use this artifact's measurements.

Serving version: `20261006T040911-15589597-827c10a1`. Simulated dataset hash: `15589597379a864309b5db3ce8e995894c7fa02af58b23848297989141c8faca`. Generated weights, datasets and database files stay outside Git.

The full native workflow's browser stage passed the storefront and mobile journeys, then exposed a real React crash: old K=5 metric keys were read from the current K=10 report. The frontend now reads the current metrics and exclusive time cutoffs, displays actual two-tower ablations, and uses reported LightGBM MASE/80% coverage. It no longer reads absent legacy loss curves, elasticity or 95% coverage. Earlier sign-in timing, ambiguous links/chart locators and cold-search timing were also corrected. That full run is not an aggregate CI success; the final frontend is verified separately against its unchanged backend and verified model artifact.

The focused workflow is stored on `restore-workspace`. It pins the tested runtime commit, requires exactly the three expected frontend changes from the native-tested source, restores the artifact by immutable ID, checks the Python receipt, registers models against a matching fresh seed, starts the documented stack, runs all three journeys and builds the frontend. It has read-only repository and Actions permissions. It never connects to Production or publishes a serving release.

The successful focused run's artifact is `11390605167`, SHA-256 `81dfa6b88eabfade11183766ba9612a5a3eda7e2c7b6701f42a38f46099c7501`. Its downloaded ZIP matches that digest. The provenance receipt identifies runtime source `bebe4a5`, training source `2e19249`, training artifact `11389448639`, the model version and matching dataset hash. Its browser JSON records three expected passes, zero skips, zero unexpected results and zero flaky tests. The journeys cover catalogue counts/images, search, default-off consent and export/withdrawal, wishlist/bag persistence, quiz, demo checkout, protected forecasts, every admin panel, the A/B simulator, correct K=10 metrics on the public model page, and mobile layout.

## Source publication

Initial prepared source `560f2a4` was published as `00b39de` with exact tree `41cf0e958705465c4332c3ba9ba72b95e362d24b`. The corrected frontend was reviewed as `5b9aa56` and published as `bebe4a5` with exact tree `f04f0b82abd5c01b1c25c1ad37545d40d66a9eab`. The guarded publisher validates the bundle digest, expected remote head, unchanged workflows and exact source tree before making a normal descendant commit. No force push or token-permission expansion was used.

Original phase 6–9 history is retained in `prepared-phase-6-9.bundle` on the recovery branch, SHA-256 `20f939c9f0883d17956a89f1705e8e62b0ee24176a26a1b091305c7bf2828d8e`. Recovery files are archival and are not the product deployment branch. Earlier invented-catalogue logs are clearly separated under [`historical/`](historical/); they do not verify this release.

The Phase 9 publication after that runtime commit changed documentation and historical-report locations only. Its runtime files were identical to the verified source above. The newer storefront follow-up is recorded separately at the top of this report.
