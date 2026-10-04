#!/bin/bash
set -e
alembic upgrade head
if [ "${BOOTSTRAP_DEMO:-false}" = "true" ]; then
 python -m app.seed
 if [ ! -f "${ARTIFACT_DIR:-artifacts}/current.json" ]; then python -m app.ml.train; fi
fi
if [ "${START_SCHEDULER:-false}" = "true" ]; then
 python -m app.worker &
 worker_pid=$!
 trap 'kill "$worker_pid" 2>/dev/null || true' EXIT
 uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" &
 api_pid=$!
 trap 'kill "$worker_pid" "$api_pid" 2>/dev/null || true' EXIT TERM INT
 wait -n "$api_pid" "$worker_pid"
else
 exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
fi
