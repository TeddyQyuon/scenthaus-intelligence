# Verification evidence

Verification was performed against the restored project and the bundled trained model version. Historical sales/users are simulated.

| Check | Outcome / scope |
| --- | --- |
| Python syntax and undefined-name checks | Passed. |
| Data migration and generator | Ran successfully: 36 products, 108 variants, 2,000 users, 12,139 simulated orders and 104 weeks. |
| Full model training | Ran successfully. All validation gates passed; five forecast methods fit with no recorded fallback failures. MLflow metrics and the trusted model bundle were logged. |
| API / ML tests | **29 passed, 1 skipped**. Consent, session rotation, role/ownership boundaries, attribution, idempotent checkout, rollback, budget/stock filters, temporal cutoff, forecast bands, saved-forecast reconciliation and CSV export are covered. See pytest.txt. |
| Browser journeys | **3 passed**: collection → wishlist persistence → quiz → product → bag persistence → demo order → consent → intelligence; protected admin sign-in and every panel; 390px mobile routes/menu and overflow checks. |
| Visual review | Desktop/mobile storefront and admin overview/forecast screenshots reviewed. Charts render without initial animation; headline layout, KPI width and mobile contrast corrected. |
| Frontend production build | Passed. The admin chart bundle is loaded separately from the storefront. See build.txt. |
| Local latency | Warm TestClient with local PostgreSQL-WASM: 40 measured requests per endpoint after five warmups. See latency.json. Under-200ms target met here; no production/internet/concurrency claim. |
| Native PostgreSQL concurrency | Test supplied and enabled in CI, not executed locally. |
| Docker Compose execution | Configuration supplied and inspected. Docker daemon unavailable here, so no container-run claim. |
| GitHub Actions | Native PostgreSQL workflow supplied; no remote workflow-run claim. |
| Public deployment | Vercel project linked. Cloud frontend build passed; Python initialization is waiting for a dedicated PostgreSQL DATABASE_URL. No working public app is claimed. |

The local integration database used PGlite, PostgreSQL compiled to WASM with a PostgreSQL protocol socket adapter. It verifies SQL/schema/API mechanics but does not establish native PostgreSQL concurrency behaviour. The CI service and Compose configuration use native PostgreSQL 16. A specific same-user concurrent checkout test is skipped unless NATIVE_POSTGRES_TESTS=1.

The regular Chrome/agent-browser helper could not launch because this execution environment disallows its Unix singleton socket. Direct Playwright tests succeeded using official Chrome Headless Shell; no security-policy escalation was used. Browser screenshots and browser-tests.json/txt are evidence from that actual browser run.

The browser found a React effect returning the new browser scroll result during navigation and a controlled consent-toggle timing issue. Effects now return only cleanup functions/undefined; the toggle updates optimistically, disables while saving, and rolls back on failure. All journey tests passed after those fixes. An API catalogue read was batched to avoid per-product variant queries during recommendation eligibility.

The benchmark reports in-process request latency with no network-region delay and one client. Static similarities are precomputed and cached; personalized state and stock remain live. Full monitoring is process-local and requires a metrics sink for multi-instance production.

The Vercel deployment revision also verifies `/api` mounting, production/preview CSRF origins, PostgreSQL URL normalization and unauthenticated cron rejection. Serving no longer imports the training forecast stack. Hosted database provisioning is paused at Neon's terms-acceptance step; deployment.md records that state. The first GitHub Actions run stopped during container initialization before any tests, due to health-command quoting. The command was corrected to double quotes and a new run started; consult the repository Actions page for the current result. A green CI run is not yet claimed in this report.
