# Vercel deployment

SCENTHAUS hosts its React/Vite frontend and FastAPI backend together on Vercel Services. The project root is the repository root. Use the current `services` configuration rather than the older `experimentalServices` syntax; services preserve original request paths, so `backend/main.py` mounts the API at `/api`. Frontend SPA rewrites belong to the storefront service and cannot swallow API responses.

## Database and initial build

Create a dedicated managed PostgreSQL database. Neon or Supabase can supply the URL; prefer a pooled URL and require TLS. Store DATABASE_URL, ENVIRONMENT=production, SECRET_KEY, ADMIN_EMAIL, ADMIN_PASSWORD, CRON_SECRET and ALLOWED_ORIGINS in the Vercel project. Database passwords and runtime secrets never go in source control.

The API build runs `python -m app.vercel_init`. It takes a PostgreSQL advisory lock, applies Alembic migrations, runs the idempotent generator if the catalogue is empty, and registers the committed model version and forecasts. It preserves an existing catalogue and orders. Seeds are reproducible fictional data, with 2,000 users and 104 weeks of history. A missing cloud connection fails the build with a clear message; it does not publish a storefront backed by a placeholder API.

The bootstrap's model-registry entry points to the bundled offline training version. Its MLflow run ID is unset because the original tracking database is not hosted. Offline metrics and the version checksum are delivered with the model. Subsequent CI training logs its own MLflow run and uploads tracking evidence as a workflow artifact.

## Serving and schedules

Vercel's filesystem is read-only except for temporary files. Requests load the checksum-verified pickle from the committed artifact folder and read/write customer state in PostgreSQL. No request trains or activates models. Python runtime dependencies live in pyproject.toml; the larger training environment uses requirements.txt.

An authenticated daily Vercel Cron calls `/api/internal/maintenance` at 20:00 UTC (04:00 Singapore). It deletes expired sessions/retention-limited events and reconciles forecast snapshots only after full weeks finish. CRON_SECRET must be set for Vercel to send its bearer header; missing or wrong credentials return 401.

Weekly training is the separate GitHub Actions workflow `retrain.yml`. Configure its three SCENTHAUS secrets and opt-in variable before enabling the Sunday 03:00 Singapore schedule. The job trains with temporal evaluation and validation gates, saves MLflow evidence, and pushes immutable model files to main. Vercel's Git integration then builds/deploys the new version. The secret connection must belong to this project's database. Calendar support currently ends in 2026; verify and add future-year holiday dates before future-horizon training.

## Verification before production promotion

Verify `/api/health`, catalogue access, consent and session cookies, persistence across reload, quiz results, demo checkout and guest admin rejection. Sign in with the configured admin account to verify forecasting, inventory, exports and model health. Check build/function logs for errors and only then update the portfolio live-demo link.

## Current evidence

See `reports/deployment.md` for actual account setup, commit and deployment outcomes. Repository code and deployment configuration do not imply that production is live.

## Official references

- https://vercel.com/docs/services
- https://vercel.com/docs/services/routing
- https://vercel.com/docs/services/config-reference
- https://vercel.com/docs/frameworks/backend/fastapi
- https://vercel.com/docs/functions/runtimes/python
- https://vercel.com/docs/cron-jobs
