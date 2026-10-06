# SCENTHAUS project guidance

SCENTHAUS is a fragrance discovery portfolio project. Stack: React + Vite (`frontend/`), FastAPI + SQLAlchemy + PostgreSQL (`backend/`), PyTorch for offline training and NumPy/ONNX Runtime for serving (`ml/`). Production target: Vercel Services. Docker is not part of the requested workflow. The older Next.js application and legacy catalogue are not the source of truth.

## Workflow

- Work through phases in order. By default, finish one phase, run its Done-when checks, update `PLAN.md`, commit as `phase N: <name>`, and wait for the user. An explicit user instruction to continue across phases overrides the pause.
- Inspect before editing. Keep the diff scoped to the active phase or user request.
- If something is ambiguous, choose the simplest safe option and record it under Assumptions in `PLAN.md`.

## Rules

- Users, orders, prices, stock and events are **SIMULATED**. Say so in the README, UI and every model card. Product references may be real; do not imply their authenticity or current availability has been verified.
- Compare every deep-learning model to a baseline on the same time split. Report results honestly, including when a baseline wins.
- Use time-based splits for events/orders. Fix random seeds and keep hyperparameters in `ml/configs/*.yaml`.
- Python 3.12, type hints, Ruff and pytest. Add meaningful tests with code changes.
- Schema changes only through Alembic migrations.
- Never commit secrets, generated datasets or model weights.
- Do not point a new catalogue release at an existing database unless its release guard accepts the exact catalogue.

## Done means

Tests and lint pass, the README is current, and model results are written to `ml/reports/*.md` as tables. A deployment phase also requires a verified deployment; code/configuration readiness alone is not a live-release claim.

## Local commands

Run from the repository root. Use a native PostgreSQL database and set a unique admin password before seeding. These commands install training dependencies only in the local environment; Vercel creates its own temporary build environment.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install torch==2.9.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r backend/requirements-training.txt
npm --prefix frontend ci

export DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5432/scenthaus'
export ADMIN_PASSWORD='choose-a-unique-password-at-least-12-chars'
(cd backend && PYTHONPATH=..:. ../.venv/bin/alembic upgrade head)
PYTHONPATH=backend:. .venv/bin/python -m app.seed
PYTHONPATH=backend:. .venv/bin/python -m ml.train_all
PYTHONPATH=backend:. .venv/bin/uvicorn app.main:app --port 8000
npm --prefix frontend run dev

PYTHONPATH=backend:. .venv/bin/pytest
.venv/bin/ruff check .
npm --prefix frontend test
npm --prefix frontend run build
```

For Vercel variables and first-release requirements, see [`docs/deployment.md`](docs/deployment.md). GitHub Actions uses native PostgreSQL and exercises the API/browser flows.
