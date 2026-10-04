# Hosting evidence

Verified on 4 October 2026. Historical sales/users are simulated; demo checkout collects no payment.

- Live application: https://scenthaus-intelligence.vercel.app/
- Source: https://github.com/TeddyQyuon/scenthaus-intelligence
- Portfolio case study: https://teddy-qyuon-portfolio.vercel.app/projects/scenthaus-intelligence
- Application revision verified in production: `2cced1a436251a9b42c012315a17766c1ede6903`; Vercel deployment `dpl_4wgqRid4dTWrQE6ytk9eRcVNHu9e` was READY. Later documentation/calendar commits do not change the shopping flow.
- React/Vite and Python FastAPI share one Vercel Services project and HTTPS origin. Python functions run in Singapore (`sin1`). Docker is not used for hosting.
- Dedicated `scenthaus-postgres` Neon database: Free plan, Singapore, Neon Auth disabled, connected to this project's production environment only. The user approved Marketplace terms before creation. Preview deployments have no production database credentials.
- Runtime secrets are encrypted project variables; database connection variables are sensitive. They are absent from source control. Initialization uses a direct connection for its session advisory lock and a pooled connection for application requests.
- First initialization loaded 36 products, 108 SKUs, 2,000 fictional customers, 12,139 simulated orders and 90,495 events. Bulk insertion retained the original data fingerprint. A subsequent build logged `Catalogue exists; seed is idempotent.` and preserved persisted shopping state.
- The bundled model is checksum verified. `/api/health` returned `status=ok`, `models_ready=true`, `demo_mode=true`.
- Production cloud-browser checks passed: homepage and bottle images, catalogue/product detail, wishlist after reload, quiz matches, selected-size bag after reload, a saved demo order with inventory update, consent on/off persistence, and guest admin gate.
- [Production API smoke evidence](production-api-smoke.json): 17 checks passed, covering session/CSRF admin sign-in, SKU and aggregate forecasts, inventory, segments, evaluation, model versions, forecast tracking, monitoring, CSV export and logout. Missing session, guest role and unauthenticated maintenance returned their expected 401/403 responses.
- Vercel runtime log inspection found no 5xx entries in the verification window. This is a smoke check, not a capacity, uptime or production-latency guarantee.
- [GitHub CI run 37198738709](https://github.com/TeddyQyuon/scenthaus-intelligence/actions/runs/37198738709) passed native PostgreSQL 16 training/tests and browser journeys for the verified application revision.

Daily authenticated Vercel maintenance is configured at 04:00 Singapore. No completed scheduled-cron invocation is claimed at delivery time. Weekly model training is supplied in `retrain.yml`, but remains **disabled**: automatic approval review blocked storing the production database URL as `SCENTHAUS_DATABASE_URL` in this repository's encrypted Actions secrets because it expands credential access to workflows and collaborators. Enabling it requires the owner's explicit approval of that destination and scope. No production database credential was saved to GitHub.
