"""Session 38 — Persistent Job Queue (Sprint 4).

Goal: replace fire-and-forget BackgroundTasks with a durable, retry-capable
queue that survives restarts and exposes status to the client.

ARCHITECTURE
------------
We expose a backend-agnostic `enqueue(job_name, payload, *, priority=0)` API.
Behind it sits one of two adapters:

  • **MongoQueue** (default — works everywhere):
      Jobs persist in `db.job_queue` with status pending → running → done|failed.
      A worker loop polls every QUEUE_POLL_SECONDS, claims jobs atomically via
      findAndUpdate, dispatches to a registered handler, applies retry logic.

  • **ArqQueue** (opt-in via REDIS_URL env):
      Persistent Arq queue on Redis. Plugs in once infra is provisioned.
      Same `enqueue`/`get_status` signatures — drop-in replacement.

Schema:
    {
      job_id, name, payload, status, priority, retries, max_retries,
      error, result, created_at, started_at, finished_at,
    }

Public API:
    from core.queue import enqueue, get_job_status, register_handler

    @register_handler("video.render")
    async def render_video(payload: dict) -> dict:
        ...
        return {"output_url": "..."}

    job_id = await enqueue("video.render", {"prompt": "..."}, priority=5)
    status = await get_job_status(job_id)
    # → {"status": "running", "retries": 0, "result": None, ...}
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Awaitable, Optional

from motor.motor_asyncio import AsyncIOMotorClient

from core.config import MONGO_URL, DB_NAME

log = logging.getLogger("queue")
_client = AsyncIOMotorClient(MONGO_URL)
_db = _client[DB_NAME]

QUEUE_POLL_SECONDS = float(os.environ.get("QUEUE_POLL_SECONDS", "2.0"))

# ═══════════════════════════════════════════════════════════════════
# Backend selection — Mongo (default) or Arq/Redis (opt-in via REDIS_URL).
# When REDIS_URL is set in env and the `arq` package + adapter import OK,
# enqueue/get_job_status/queue_stats route through core.queue_arq_adapter.
# Otherwise the Mongo-backed implementation below stays active.
# This makes the Redis swap a one-line ops change with zero caller-code edits.
# ═══════════════════════════════════════════════════════════════════
_USE_REDIS = bool(os.environ.get("REDIS_URL"))


def _arq():
    """Lazy import the Arq adapter (only when REDIS_URL is set)."""
    if not _USE_REDIS:
        return None
    try:
        from core import queue_arq_adapter  # type: ignore
        return queue_arq_adapter
    except Exception as e:
        log.warning("queue: REDIS_URL set but arq adapter unavailable (%s) — "
                    "falling back to mongo backend", e)
        return None
QUEUE_MAX_RETRIES = int(os.environ.get("QUEUE_MAX_RETRIES", "3"))
QUEUE_STUCK_THRESHOLD_SEC = int(os.environ.get("QUEUE_STUCK_THRESHOLD_SEC", "600"))  # 10 min

_HANDLERS: dict[str, Callable[[dict], Awaitable[Any]]] = {}
_worker_task: Optional[asyncio.Task] = None
_stuck_recovery_task: Optional[asyncio.Task] = None


# ════════════════════════════════════════════════════════════
# Handler registration
# ════════════════════════════════════════════════════════════
def register_handler(name: str):
    """Decorator to register an async handler for a queue job.

    Usage:
        @register_handler("video.render")
        async def render_video(payload: dict) -> dict:
            ...
    """
    def wrap(fn: Callable[[dict], Awaitable[Any]]):
        _HANDLERS[name] = fn
        log.info("queue: registered handler %s", name)
        return fn
    return wrap


def registered_handlers() -> list[str]:
    return sorted(_HANDLERS.keys())


# ════════════════════════════════════════════════════════════
# Enqueue + status
# ════════════════════════════════════════════════════════════
async def enqueue(
    name: str,
    payload: dict,
    *,
    priority: int = 0,
    max_retries: int = QUEUE_MAX_RETRIES,
    user_id: Optional[str] = None,
) -> str:
    """Insert a pending job and return its job_id.

    Routes to Arq when REDIS_URL is set, otherwise uses Mongo backend.
    """
    adapter = _arq()
    if adapter is not None:
        return await adapter.enqueue(name, payload,
                                     priority=priority,
                                     max_retries=max_retries,
                                     user_id=user_id)
    job_id = f"job_{uuid.uuid4().hex[:16]}"
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "job_id": job_id,
        "name": name,
        "payload": payload,
        "user_id": user_id,
        "status": "pending",
        "priority": int(priority),
        "retries": 0,
        "max_retries": int(max_retries),
        "error": None,
        "result": None,
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "finished_at": None,
    }
    await _db.job_queue.insert_one(doc)
    log.info("queue: enqueued %s job_id=%s priority=%d", name, job_id, priority)
    return job_id


async def get_job_status(job_id: str) -> Optional[dict]:
    adapter = _arq()
    if adapter is not None:
        return await adapter.get_job_status(job_id)
    return await _db.job_queue.find_one({"job_id": job_id}, {"_id": 0})


async def queue_stats() -> dict:
    """Aggregate counters for admin dashboard."""
    adapter = _arq()
    if adapter is not None and hasattr(adapter, "queue_stats"):
        return await adapter.queue_stats()
    pipeline = [
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1},
        }},
    ]
    rows = await _db.job_queue.aggregate(pipeline).to_list(length=20)
    stats = {r["_id"]: r["count"] for r in rows}
    total = sum(stats.values())
    return {
        "total": total,
        "pending": stats.get("pending", 0),
        "running": stats.get("running", 0),
        "done": stats.get("done", 0),
        "failed": stats.get("failed", 0),
        "dead": stats.get("dead", 0),
        "handlers": registered_handlers(),
        "poll_seconds": QUEUE_POLL_SECONDS,
        "backend": "mongo",
    }


# ════════════════════════════════════════════════════════════
# Worker loop
# ════════════════════════════════════════════════════════════
async def _claim_next_job() -> Optional[dict]:
    """Atomically claim the highest-priority pending job."""
    now = datetime.now(timezone.utc).isoformat()
    return await _db.job_queue.find_one_and_update(
        {"status": "pending"},
        {"$set": {"status": "running", "started_at": now, "updated_at": now}},
        sort=[("priority", -1), ("created_at", 1)],
        return_document=True,
    )


async def _execute_job(job: dict) -> None:
    """Run the handler for a single claimed job, with retry semantics."""
    name = job.get("name")
    job_id = job.get("job_id")
    retries = int(job.get("retries", 0))
    max_retries = int(job.get("max_retries", QUEUE_MAX_RETRIES))
    handler = _HANDLERS.get(name)

    if not handler:
        log.error("queue: no handler for %s job_id=%s — marking dead", name, job_id)
        await _db.job_queue.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "dead",
                "error": f"No handler registered for '{name}'",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        return

    try:
        result = await handler(job.get("payload") or {})
        now = datetime.now(timezone.utc).isoformat()
        await _db.job_queue.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "done",
                "result": result if isinstance(result, (dict, list, str, int, float, bool, type(None))) else str(result),
                "finished_at": now,
                "updated_at": now,
            }},
        )
        log.info("queue: done %s job_id=%s", name, job_id)
    except Exception as e:
        now = datetime.now(timezone.utc).isoformat()
        if retries + 1 < max_retries:
            # Retry — put back to pending with incremented counter
            await _db.job_queue.update_one(
                {"job_id": job_id},
                {"$set": {
                    "status": "pending",
                    "error": str(e)[:500],
                    "retries": retries + 1,
                    "updated_at": now,
                }},
            )
            log.warning("queue: retry %d/%d for %s job_id=%s err=%s",
                        retries + 1, max_retries, name, job_id, e)
        else:
            await _db.job_queue.update_one(
                {"job_id": job_id},
                {"$set": {
                    "status": "failed",
                    "error": str(e)[:500],
                    "finished_at": now,
                    "updated_at": now,
                }},
            )
            log.error("queue: failed %s job_id=%s after %d retries: %s",
                      name, job_id, max_retries, e)


async def _worker_loop():
    """Forever-loop polling for pending jobs."""
    log.info("queue: worker loop started (poll=%.1fs)", QUEUE_POLL_SECONDS)
    while True:
        try:
            job = await _claim_next_job()
            if job:
                # Don't block the polling loop — fan out concurrent jobs.
                asyncio.create_task(_execute_job(job))
            else:
                await asyncio.sleep(QUEUE_POLL_SECONDS)
        except asyncio.CancelledError:
            log.info("queue: worker loop cancelled (graceful shutdown)")
            raise
        except Exception as e:
            log.error("queue: worker loop error: %s", e)
            await asyncio.sleep(QUEUE_POLL_SECONDS)


async def _stuck_recovery_loop():
    """Recover jobs stuck in 'running' for too long (e.g. server crashed)."""
    while True:
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(seconds=QUEUE_STUCK_THRESHOLD_SEC)).isoformat()
            r = await _db.job_queue.update_many(
                {"status": "running", "started_at": {"$lt": cutoff}},
                {"$set": {"status": "pending", "error": "recovered from stuck", "updated_at": datetime.now(timezone.utc).isoformat()}},
            )
            if r.modified_count:
                log.warning("queue: recovered %d stuck jobs", r.modified_count)
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error("queue: stuck recovery error: %s", e)
            await asyncio.sleep(60)


def start_worker() -> None:
    """Spawn the background worker. Safe to call multiple times.

    No-op when REDIS_URL is set — Arq runs its own external worker process
    (`python -m arq core.queue_arq_adapter.WorkerSettings`), so the in-process
    Mongo worker is not started.
    """
    if _arq() is not None:
        log.info("queue: REDIS_URL set — skipping in-process worker (Arq has its own)")
        return
    global _worker_task, _stuck_recovery_task
    loop = asyncio.get_event_loop()
    if _worker_task is None or _worker_task.done():
        _worker_task = loop.create_task(_worker_loop(), name="queue_worker")
    if _stuck_recovery_task is None or _stuck_recovery_task.done():
        _stuck_recovery_task = loop.create_task(_stuck_recovery_loop(), name="queue_stuck_recovery")


def stop_worker() -> None:
    global _worker_task, _stuck_recovery_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
    if _stuck_recovery_task and not _stuck_recovery_task.done():
        _stuck_recovery_task.cancel()


# ════════════════════════════════════════════════════════════
# Default handlers (sanity test + demonstration)
# ════════════════════════════════════════════════════════════
@register_handler("system.ping")
async def _ping_handler(payload: dict) -> dict:
    """Sanity-check handler — echoes payload back. Used by health endpoints."""
    return {"pong": True, "echo": payload, "ts": datetime.now(timezone.utc).isoformat()}


@register_handler("system.sleep")
async def _sleep_handler(payload: dict) -> dict:
    """Sleeps for `seconds` (max 30s). Used to test long-running jobs."""
    seconds = min(30, int(payload.get("seconds") or 1))
    await asyncio.sleep(seconds)
    return {"slept": seconds}
