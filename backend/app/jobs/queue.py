"""Database-backed background job queue with tenant RLS isolation and dead-letter handling."""

from collections.abc import Callable
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession

from ..models import BackgroundJob, now
from ..tenancy.constants import DEFAULT_TENANT_ID
from ..tenancy.deps import set_db_tenant_context

TaskHandler = Callable[[DatabaseSession, str, dict[str, Any]], None]
_REGISTRY: dict[str, TaskHandler] = {}


def register_task(name: str):
    """Decorator to register a background job handler."""

    def _decorator(fn: TaskHandler) -> TaskHandler:
        _REGISTRY[name] = fn
        return fn

    return _decorator


def enqueue_job(
    db: DatabaseSession,
    task_name: str,
    payload: dict[str, Any] | None = None,
    *,
    tenant_id: str = DEFAULT_TENANT_ID,
    max_attempts: int = 3,
) -> BackgroundJob:
    """Enqueue an asynchronous job inside the caller's database transaction."""
    job = BackgroundJob(
        tenant_id=tenant_id,
        task_name=task_name,
        payload=payload or {},
        status="pending",
        attempts=0,
        max_attempts=max_attempts,
        scheduled_at=now(),
    )
    db.add(job)
    db.flush()
    return job


def process_pending_jobs(db: DatabaseSession, *, limit: int = 25) -> dict[str, int]:
    """Process up to `limit` pending background jobs with tenant context isolation."""
    jobs = db.scalars(
        select(BackgroundJob)
        .where(
            BackgroundJob.status.in_(["pending", "failed"]),
            BackgroundJob.scheduled_at <= now(),
        )
        .order_by(BackgroundJob.scheduled_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()

    completed = 0
    failed = 0
    dead_lettered = 0

    for job in jobs:
        handler = _REGISTRY.get(job.task_name)
        job.attempts += 1
        job.status = "running"
        set_db_tenant_context(db, job.tenant_id)
        try:
            if handler is None:
                raise RuntimeError(f"Unregistered task handler: {job.task_name}")
            handler(db, job.tenant_id, job.payload or {})
            job.status = "completed"
            job.completed_at = now()
            job.last_error = None
            completed += 1
        except Exception as exc:  # noqa: BLE001
            job.last_error = str(exc)[:1000]
            if job.attempts >= job.max_attempts:
                job.status = "dead_letter"
                dead_lettered += 1
            else:
                job.status = "failed"
                failed += 1
        db.commit()

    return {
        "completed": completed,
        "failed": failed,
        "dead_letter": dead_lettered,
    }
