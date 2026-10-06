# Verification record

**Checked 2026-10-05 against the current real-catalogue source tree.** Results below distinguish local checks, discovered browser tests and checks that still require CI or configured accounts.

| Check | Result | Scope |
| --- | --- | --- |
| Python compile | Passed: `python3 -m compileall -q backend/app backend/tests ml` | Syntax only; does not import runtime dependencies or exercise database code. |
| Vercel config parse | Passed: `vercel.json` parses as JSON | Structural JSON check only; not a Vercel deployment validation. |
| Frontend production build | Passed: `npm run build` | Vite built the storefront and separately loaded admin chunk. |
| Browser journey inventory | 3 Playwright journeys discovered with `npm test -- --list` | Discovery only; browser journeys were not run in this local workspace. |
| Python unit/integration tests | Not run locally | The workspace Python lacks SQLAlchemy and the local PostgreSQL/browser test stack is unavailable. GitHub CI is configured to install dependencies, run native PostgreSQL, pytest, Ruff and Playwright. |
| Diff whitespace | Passed: `git diff --check` | No whitespace errors in the current diff. |
| Current public API | Responded with the prior generated “Citrus Theory” / “Atelier 08” catalogue | Confirms the current domain is the legacy release; it does not test the un-deployed real-catalogue source. |
| Vercel Production release | Not verified for the current source | Latest ready Production deployment is the earlier `22c3c35` release. Current project status and missing Preview database configuration are recorded in [`deployment.md`](deployment.md). |
| Source publication | Not completed | Commit `f3ec1dc` is local only. Git push lacks CLI credentials and the connected GitHub integration denied tree creation with 403; therefore no CI run or Vercel build was triggered for this source. |

The browser journeys cover catalogue counts and images, discovery/search, consent and export/withdrawal, wishlist persistence, quiz results, demo checkout, protected forecast administration, model information, and mobile layout. Their source is [`frontend/e2e/journeys.spec.js`](../frontend/e2e/journeys.spec.js); a passing test run is not claimed here.

## CI procedure

`.github/workflows/ci.yml` installs CPU PyTorch and training dependencies, starts native PostgreSQL 16, migrates and seeds the synthetic dataset, trains the reported models, runs pytest and Ruff, starts the API, runs Playwright journeys, and builds the frontend. A CI run on the remote revision is required before claiming the full suite passed.
