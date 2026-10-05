# Phase 0 — recovered native scaffold

Users, orders and events are **SIMULATED**. No training or domain seed in this phase.

| Check | Command / evidence | Result |
|---|---|---|
| PostgreSQL protocol + Alembic | `node tools/pg-run.mjs .venv/bin/python scripts/verify.py --phase 0` | Initial migration passed on PGlite |
| API readiness | FastAPI TestClient `/health`, real SQL SELECT 1 | HTTP 200 |
| Python checks | Same command: scaffold pytest + root ruff | 2 passed; lint clean |
| React bundle | `npm --prefix frontend run build` | Passed |
| Served frontend | Vite preview + HTTP request to localhost:5173 | HTTP 200, React mount present |

User override: native development and Vercel preparation; removed Docker files. Reused the published React/Vite JavaScript and FastAPI/SQLAlchemy base after workspace maintenance removed unpushed work. New local development dependency: PGlite and pglite-socket in `tools/` for this runtime only. Python checks use Python 3.12.14, Node 24.19.0. PGlite is a WASM PostgreSQL protocol fixture, not proof of native concurrency or Neon TLS. The inherited Ruff policy checks fatal syntax/undefined-name errors; later ML tests add behavioural coverage. No model weights or data dumps are tracked.
