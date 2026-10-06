# Verification record

**Checked 2026-10-06 against published source commit `00b39de951e185c74a3a60594e5649e52df6c9e7`.** Results below distinguish local checks, discovered browser tests and checks that still require CI or configured accounts.

| Check | Result | Scope |
| --- | --- | --- |
| Python compile | Passed: `python3 -m compileall -q backend/app backend/tests ml` | Syntax only; does not import runtime dependencies or exercise database code. |
| Ruff | Passed with pinned Ruff 0.14.14 | Includes the corrected `date` import used by the read-only Vercel catalogue guard. |
| Vercel config parse | Passed: `vercel.json` parses as JSON | Structural JSON check only; not a Vercel deployment validation. |
| Frontend production build | Passed: `npm run build` | Vite built the storefront and separately loaded admin chunk. |
| Browser journey inventory | 3 Playwright journeys discovered with `npm test -- --list` | Discovery only; browser journeys were not run in this local workspace. |
| Python unit/integration tests | Not run locally | The workspace Python lacks SQLAlchemy and the local PostgreSQL/browser test stack is unavailable. GitHub CI is configured to install dependencies, run native PostgreSQL, pytest, Ruff and Playwright. |
| Diff whitespace | Passed: `git diff --check` | No whitespace errors in the current diff. |
| Current public API | Responded with the prior generated “Citrus Theory” / “Atelier 08” catalogue | Confirms the current domain is the legacy release; it does not test the un-deployed real-catalogue source. |
| Vercel Production release | Not verified for the current source | Latest ready Production deployment is the earlier `22c3c35` release. Current project status and missing Preview database configuration are recorded in [`deployment.md`](deployment.md). |
| Source publication | Passed | Published as `00b39de` on `complete-phases-real-catalog`. Tree `41cf0e958705465c4332c3ba9ba72b95e362d24b` exactly matches prepared commit `560f2a4`. Original phase commits remain in the checksum-verified bundle on `restore-workspace`. |

The browser journeys cover catalogue counts and images, discovery/search, consent and export/withdrawal, wishlist persistence, quiz results, demo checkout, protected forecast administration, model information, and mobile layout. Their source is [`frontend/e2e/journeys.spec.js`](../frontend/e2e/journeys.spec.js); a passing test run is not claimed here.

## CI procedure

`.github/workflows/ci.yml` installs CPU PyTorch and training dependencies, starts native PostgreSQL 16, migrates and seeds the synthetic dataset, trains the reported models, runs pytest and Ruff, starts the API, runs Playwright journeys, and builds the frontend. A CI run on the remote revision is required before claiming the full suite passed.

The signed-in GitHub editor published the two workflow files. The existing publisher verified the bundle digest, the exact feature branch head, unchanged workflows and the prepared tree before creating a normal descendant commit. It did not force-push or expand token permissions. This record update triggers CI against the published release.
