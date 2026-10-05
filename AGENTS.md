# AGENTS.md
SCENTHAUS: fragrance shop with an ML layer (portfolio project).
Stack: React + Vite (frontend/), FastAPI + SQLAlchemy +
Postgres (backend/), PyTorch (ml/), Docker Compose.
Plan: PLAN.md. An old Next.js app, if present, is in /legacy
and is read-only.

## Workflow
- Work on one phase at a time, in order.
- Inspect before editing. Keep the diff inside the phase scope.
- At the end of a phase: run its Done-when checks, tick it in
  PLAN.md, commit ("phase N: <name>"), then reply with changed
  files, commands + results, assumptions and remaining risks.
- Then STOP and wait for me to say "continue".
- If something is ambiguous, pick the simplest option, log it
  under Assumptions in PLAN.md, and keep going.

## Rules
- Users, orders and events are SIMULATED. Say so in the
  README, the UI and every model card.
- Every DL model is compared to a baseline on the same split.
  Report results honestly, even when the baseline wins.
- Time-based splits only. No random splits on events/orders.
- Fixed seeds. Hyperparameters live in ml/configs/*.yaml.
- Python 3.11+, type hints, ruff, pytest. Add tests with code.
- Schema changes only through Alembic migrations.
- Prefer the libraries a phase names. List any other new
  dependency in the phase summary.
- Never commit secrets, data dumps or model weights.

## Done means
Tests pass, ruff is clean, README is updated, and results are
written to ml/reports/*.md as tables.

## Commands
Run from the repository root. User overrides: no Docker; complete all phases without pausing.

```bash
python3 -m venv .venv
uv pip install --python .venv/bin/python -r backend/requirements-training.txt
npm --prefix frontend ci
# Export DATABASE_URL for PostgreSQL/Neon and ADMIN_PASSWORD (12+ characters).
(cd backend && ../.venv/bin/alembic upgrade head)
PYTHONPATH=backend .venv/bin/python -m app.seed
PYTHONPATH=backend .venv/bin/python -m ml.train_all
PYTHONPATH=backend .venv/bin/uvicorn app.main:app --port 8000
npm --prefix frontend run dev
.venv/bin/pytest
.venv/bin/ruff check .
npm --prefix frontend test
npm --prefix frontend run build
# Restricted runtime fallback for local tests (PGlite, not native Postgres):
npm --prefix tools ci
node tools/pg-run.mjs .venv/bin/python scripts/verify.py --phase 0
```
