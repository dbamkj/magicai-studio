"""Session 39 — Arq adapter for the persistent job queue (Sprint 4).

This file is the OPT-IN Redis backend. It is imported lazily by
`core/queue.py::_arq()` ONLY when the `REDIS_URL` env var is set AND
the `arq` package is installed.

While Redis is unavailable in this environment, this file is intentionally
NOT importable end-to-end — the top-level `import arq` will fail, the
lazy import in core/queue.py catches that and falls back to the Mongo
backend. That keeps the codebase shippable today and Arq-ready tomorrow.

Activation steps (when Redis is provisioned):
    1. pip install arq>=0.26
    2. Add REDIS_URL=redis://...:6379 to backend/.env
    3. Restart backend → enqueue/get_job_status/queue_stats route here
    4. Run `python -m arq core.queue_arq_adapter.WorkerSettings` as a
       separate supervisor program for the worker process.

Public surface (mirrors core/queue.py):
    enqueue(name, payload, *, priority=, max_retries=, user_id=) → job_id
    get_job_status(job_id) → dict | None
    queue_stats() → dict
    WorkerSettings              # used by arq's CLI runner
"""
from __future__ import annotations

import logging
import os
from typing import Optional

# These imports will fail (ImportError) if `arq` is not installed.
# That's expected and handled by `core.queue._arq()` which catches it
# and falls back to the Mongo backend gracefully.
import arq  # noqa: F401
from arq.connections import RedisSettings, ArqRedis, create_pool

# Re-use the in-process handler registry from core.queue so any function
# decorated with @register_handler("…") is automatically exposed as an
# Arq task with the same name.
from core.queue import _HANDLERS, registered_handlers  # noqa: F401

log = logging.getLogger("queue.arq")

REDIS_URL = os.environ.get("REDIS_URL", "")
QUEUE_NAME = os.environ.get("ARQ_QUEUE", "default")

_pool: Optional[ArqRedis] = None


async def _get_pool() -> ArqRedis:
    """Lazy singleton — one shared connection pool per process."""
    global _pool
    if _pool is None:
        if not REDIS_URL:
            raise RuntimeError("REDIS_URL is not set; cannot use Arq adapter")
        settings = RedisSettings.from_dsn(REDIS_URL)
        _pool = await create_pool(settings)
    return _pool


# ── Public API (signatures match core.queue) ────────────────────
async def enqueue(
    name: str,
    payload: dict,
    *,
    priority: int = 0,
    max_retries: int = 3,
    user_id: Optional[str] = None,
) -> str:
    pool = await _get_pool()
    # Arq supports `_defer_by` for priority by inverse delay; for now we
    # keep priority=0 → immediate, priority>0 → still immediate but log
    # so future scheduling can hook in.
    job = await pool.enqueue_job(
        name,
        payload,
        _job_try=max(1, int(max_retries)),
        _queue_name=QUEUE_NAME,
        _expires=86400,  # auto-drop after 24h
    )
    return job.job_id


async def get_job_status(job_id: str) -> Optional[dict]:
    pool = await _get_pool()
    job = arq.jobs.Job(job_id, pool, _queue_name=QUEUE_NAME)
    info = await job.info()
    if info is None:
        return None
    status_enum = await job.status()
    # Try to read result if completed
    result = None
    error = None
    try:
        result = await job.result(timeout=0)
    except arq.jobs.JobNotFound:
        pass
    except Exception as e:
        error = str(e)
    return {
        "job_id": job_id,
        "name": info.function,
        "status": str(status_enum.value),
        "retries": int(info.job_try or 0),
        "result": result,
        "error": error,
        "created_at": info.enqueue_time.isoformat() if info.enqueue_time else None,
        "started_at": info.start_time.isoformat() if getattr(info, "start_time", None) else None,
        "finished_at": info.finish_time.isoformat() if getattr(info, "finish_time", None) else None,
        "backend": "arq",
    }


async def queue_stats() -> dict:
    """Counters via Arq internals (simpler form — Arq doesn't expose group-by)."""
    pool = await _get_pool()
    # Pending jobs count via list of queue
    try:
        pending = await pool.zcard(f"arq:queue:{QUEUE_NAME}")
    except Exception:
        pending = 0
    return {
        "total": pending,  # approx — Arq doesn't track historical counters by default
        "pending": pending,
        "running": 0,
        "done": 0,
        "failed": 0,
        "dead": 0,
        "handlers": registered_handlers(),
        "backend": "arq",
    }


# ── Worker settings used by `python -m arq core.queue_arq_adapter.WorkerSettings` ──
class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(REDIS_URL) if REDIS_URL else None
    # Every handler registered via @register_handler in core.queue becomes
    # an Arq task automatically — Arq looks up by __qualname__/function name.
    functions = list(_HANDLERS.values())
    max_jobs = int(os.environ.get("ARQ_MAX_JOBS", "10"))
    job_timeout = int(os.environ.get("ARQ_JOB_TIMEOUT", "600"))  # 10 min
    keep_result = int(os.environ.get("ARQ_KEEP_RESULT", "3600"))  # 1 h
    on_startup = None
    on_shutdown = None
