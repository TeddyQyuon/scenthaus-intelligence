# Verification evidence

Verification was performed against the restored project and the bundled trained model version. Historical sales/users are simulated.

| Check | Outcome / scope |
| --- | --- |
| Python syntax and undefined-name checks | Passed. |
| Data migration and generator | Ran successfully: 36 products, 108 variants, 2,000 users, 12,139 simulated orders and 104 weeks. |
| Full model training | Ran successfully. All validation gates passed; five forecast methods fit with no recorded fallback failures. MLflow metrics and the trusted model bundle were logged. |
| API / ML tests | Local: **29 passed, 1 skipped**. Native PostgreSQL 16 CI: **30 passed**, including concurrent checkout. Consent, session rotation, role/ownership boundaries, attribution, rollback, filters, temporal cutoff, forecast bands, reconciliation and CSV export are covered. See pytest.txt for the local run. |
| Browser journeys | **3 passed**: collection → wishlist persistence → quiz → product → bag persistence → demo order → consent → intelligence; protected admin sign-in and every panel; 390px mobile routes/menu and overflow checks. |
| Visual review | Desktop/mobile storefront and admin overview/forecast screenshots reviewed. Charts render without initial animation; headline layout, KPI width and mobile contrast corrected. |
| Frontend production build | Passed. The admin chart bundle is loaded separately from the storefront. See build.txt. |
| Local latency | Warm TestClient with local PostgreSQL-WASM: 40 measured requests per endpoint after five warmups. See latency.json. Under-200ms target met here; no production/internet/concurrency claim. |
| Native PostgreSQL concurrency | Passed in GitHub CI; not executed against the local WASM database. |
| Docker Compose execution | Configuration supplied and inspected. Docker daemon unavailable here, so no container-run claim. |
| GitHub Actions | [Run 37198738709](https://github.com/TeddyQyuon/scenthaus-intelligence/actions/runs/37198738709) succeeded: native PostgreSQL 16 migration, generation/training, 30 Python tests, frontend build and three Playwright journeys. |
| Public deployment | Vercel + dedicated Neon Postgres verified. Homepage, quiz, wishlist/cart reloads, demo checkout, consent withdrawal and guest admin gate passed in the cloud browser. |
| Production API smoke checks | **17 passed**: health, expected authorization failures, admin login/logout, forecasts, inventory, evaluation, models, segments, tracking, monitoring and CSV. See production-api-smoke.json. |
| Batched cloud initialization | Fresh local database reproduced the same 12,139 orders, 90,495 events, 15,983 lines and fingerprint `5016c2be634523bc6e553b19387783c9243d416e3557354b1ff23413ec4e7076`; a repeat seed preserved counts. Cloud first seed and later idempotent build completed. |
| Future calendar | MOM's 2027 dates verified; a 12-week forecast feature window crossing the year boundary and the three 2027 holiday anchors passed. Unknown years retain a validation error. |

The local integration database used PGlite, PostgreSQL compiled to WASM with a PostgreSQL protocol socket adapter. It verifies SQL/schema/API mechanics but does not establish native PostgreSQL concurrency behaviour. The CI service and Compose configuration use native PostgreSQL 16. A specific same-user concurrent checkout test is skipped unless NATIVE_POSTGRES_TESTS=1.

The regular Chrome/agent-browser helper could not launch because this execution environment disallows its Unix singleton socket. Direct Playwright tests succeeded using official Chrome Headless Shell; no security-policy escalation was used. Browser screenshots and browser-tests.json/txt are evidence from that actual browser run.

The browser found a React effect returning the new browser scroll result during navigation and a controlled consent-toggle timing issue. Effects now return only cleanup functions/undefined; the toggle updates optimistically, disables while saving, and rolls back on failure. All journey tests passed after those fixes. An API catalogue read was batched to avoid per-product variant queries during recommendation eligibility.

The benchmark reports in-process request latency with no network-region delay and one client. Static similarities are precomputed and cached; personalized state and stock remain live. Full monitoring is process-local and requires a metrics sink for multi-instance production.

The Vercel revision also verifies `/api` mounting, CSRF origins, PostgreSQL URL normalization and unauthenticated cron rejection. Serving does not import the training forecast stack. The homepage needs an explicit service destination path to `/index.html`; nested storefront routes and API routes remain independently served. Production verification used revision `2cced1a`; deployment.md records the account and hosting evidence. CI run 37198738709 passed at that revision. The weekly hosted retraining workflow remains disabled pending approval to share the project's database credential with GitHub Actions.

The production API smoke runner observed roughly 6.8–10.6 seconds per external request through its remote network path. Those measurements include connection/proxy/network overhead; they do not prove a server latency under 200 ms. The earlier warm in-process benchmark is a separate measurement. A production load test and a multi-instance metrics sink remain operational follow-up work.
