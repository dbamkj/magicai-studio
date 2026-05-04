"""Account / usage / credits info endpoints (Phase-B extraction).

Before this file existed these three endpoints lived in server.py:
  GET /api/usage          — per-user project counts grouped by type
  GET /api/credits-info   — lifetime credit spend + cost-table preview

Both are read-only aggregations over the `video_projects` collection
plus a handful of constants. Moving them here:
  * trims ~80 lines off the 3.5kLOC server.py
  * uses the shared `db` instance (core.db) instead of re-creating
    a client — same fix we applied to routes/avatar.py in r4.

server.py imports this module's `router` at startup; no other changes
needed. The /mh-models endpoint (much larger, tied to MH_*_TIERS /
MH_RES constants inside server.py) is NOT extracted here — that's a
future pass.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Request

from core.auth import get_current_user
from core.db import db

log = logging.getLogger("routes.account")
router = APIRouter(prefix="/api", tags=["account"])


@router.get("/usage")
async def get_usage(request: Request):
    """Return per-type project counts for the calling user.

    Response shape:
        {"lipsync": {"total": 3, "completed": 2}, ...,
         "total_projects": 12, "total_completed": 9}
    """
    user = await get_current_user(request)
    uid = user["user_id"]

    pipeline = [
        {"$match": {"user_id": uid}},
        {"$group": {"_id": "$type", "count": {"$sum": 1}}},
    ]
    counts: dict = {}
    async for doc in db.video_projects.aggregate(pipeline):
        counts[doc["_id"]] = doc["count"]

    completed_pipeline = [
        {"$match": {"user_id": uid, "status": "completed"}},
        {"$group": {"_id": "$type", "count": {"$sum": 1}}},
    ]
    completed: dict = {}
    async for doc in db.video_projects.aggregate(completed_pipeline):
        completed[doc["_id"]] = doc["count"]

    return {
        "lipsync":  {"total": counts.get("lipsync",  0), "completed": completed.get("lipsync",  0)},
        "faceswap": {"total": counts.get("faceswap", 0), "completed": completed.get("faceswap", 0)},
        "headswap": {"total": counts.get("headswap", 0), "completed": completed.get("headswap", 0)},
        "bodyswap": {"total": counts.get("bodyswap", 0), "completed": completed.get("bodyswap", 0)},
        "total_projects":  sum(counts.values()),
        "total_completed": sum(completed.values()),
    }


@router.get("/credits-info")
async def credits_info(request: Optional[Request] = None):
    """Return Magic Hour credit usage + per-action cost estimates.

    MagicHour does not expose a public balance endpoint — we sum the
    `credits_charged` captured on each completed project instead.
    Anonymous callers get a zero-usage card so the Credits screen
    still renders without forcing a login.
    """
    user_id = "anonymous"
    if request is not None:
        try:
            user = await get_current_user(request)
            user_id = user.get("id") or user.get("email") or "anonymous"
        except Exception:
            user_id = "anonymous"

    total_used, total_count = 0, 0
    try:
        pipeline = [
            {"$match": {"user_id": user_id, "status": "completed"}},
            {"$group": {"_id": None, "total": {"$sum": "$credits_charged"},
                        "count": {"$sum": 1}}},
        ]
        agg = await db.video_projects.aggregate(pipeline).to_list(length=1)
        if agg:
            total_used = int(agg[0].get("total") or 0)
            total_count = int(agg[0].get("count") or 0)
    except Exception as e:
        log.warning("credits-info agg failed: %s", e)

    # Local imports — server.py still owns the canonical cost tables.
    from core.pricing import MH_PER_SEC, MH_MIN_BILLED_SECONDS
    try:
        from server import MH_CREDIT_COSTS, MH_QUALITY_TIERS  # type: ignore
    except Exception:
        MH_CREDIT_COSTS, MH_QUALITY_TIERS = {}, []

    return {
        "credits_used_total": total_used,
        "completed_jobs":     total_count,
        "cost_table":         MH_CREDIT_COSTS,
        "pricing": {
            "min_billed_seconds":  MH_MIN_BILLED_SECONDS,
            "per_sec":             MH_PER_SEC,
            "video_5s_quick":      MH_PER_SEC['quick']      * MH_MIN_BILLED_SECONDS,
            "video_5s_studio":     MH_PER_SEC['studio']     * MH_MIN_BILLED_SECONDS,
            "video_5s_cinematic":  MH_PER_SEC['cinematic']  * MH_MIN_BILLED_SECONDS,
            "image_flux_schnell":  4,
            "image_flux_dev":      6,
            "face_swap_photo":     60,
            "lip_sync_per_sec":    40,
            "talking_avatar_per_sec": 60,
        },
        "quality_tiers":       MH_QUALITY_TIERS,
        "resolutions":         ["480p", "720p", "1080p"],
        "resolutions_enabled": ["480p", "720p"],
        "note": "MH enforces 5-second minimum billing. Shorter videos are still billed for 5s.",
    }
