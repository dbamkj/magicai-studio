"""Account / usage / credits info endpoints (Phase-B extraction).

These three endpoints used to live in server.py:
  GET /api/usage          — per-user project counts grouped by type
  GET /api/credits-info   — lifetime credit spend + cost-table preview
  GET /api/mh-models      — MH quality tiers + per-feature pricing/picker data

Moving them here:
  * trims ~200 lines off the 3.5k-LOC server.py
  * uses the shared `db` instance (core.db) instead of re-creating a client —
    same fix we applied to routes/avatar.py in r4.
  * imports constants DIRECTLY from core.constants / core.pricing instead of
    back-reaching into server.py (which was a circular dependency).

server.py imports this module's `router` at startup and calls
`app.include_router(router)`; no other changes needed.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Request

from core.auth import get_current_user
from core.db import db
from core.constants import MH_CREDIT_COSTS, MH_QUALITY_TIERS
from core.pricing import MH_PER_SEC, MH_MIN_BILLED_SECONDS

log = logging.getLogger("routes.account")
router = APIRouter(prefix="/api", tags=["account"])


# ══════════════════════════════════════════════════════════════════════
# GET /api/usage — per-user project counts grouped by type
# ══════════════════════════════════════════════════════════════════════
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


# ══════════════════════════════════════════════════════════════════════
# GET /api/credits-info — lifetime MH credit spend + per-action cost table
# ══════════════════════════════════════════════════════════════════════
@router.get("/credits-info")
async def credits_info(request: Request = None):
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


# ══════════════════════════════════════════════════════════════════════
# GET /api/mh-models — per-feature MH models + duration/resolution pickers
# ══════════════════════════════════════════════════════════════════════
# Duration + resolution options are gated to what MH actually accepts.
# * text_to_video / image_to_video / video_to_video: 5 / 10 / 15 s
#   (MH min-billed = 5s; backend locally trims shorter requests before
#    returning, but we only expose these ≥5s values in the UI because
#    shorter values bill the user the same as 5s.)
# * lip_sync / talking_avatar / redub: duration comes from audio/script
#   (no picker required — we return None).
# * face_swap_photo: no duration concept.
# * face_swap_video: matches source video duration (no picker).
_MH_VIDEO_DURATIONS = [5, 10, 15]
_MH_RES = {
    "480p":  {"id": "480p",  "label": "480p",            "enabled": True,  "note": "Fast, low data · same MH cost"},
    "720p":  {"id": "720p",  "label": "720p (HD)",       "enabled": True,  "note": "Default, HD · same MH cost"},
    "1080p": {"id": "1080p", "label": "1080p (Full HD)", "enabled": False, "note": "Coming soon"},
}
_STD_RES = [_MH_RES["480p"], _MH_RES["720p"], _MH_RES["1080p"]]


@router.get("/mh-models")
async def get_mh_models():
    """Returns MH quality tiers + REAL credit pricing (matches MH 2026 billing).

    Also returns per-feature ``duration_options`` and ``resolution_options`` so
    the frontend only exposes picker values that Magic Hour actually supports
    for the currently selected tool + model combination.

    These numbers are what MH actually charges on our account, so the cost
    shown in-app mirrors what the user will be debited. MH enforces a
    5-second minimum billed duration — any video shorter is still billed
    for 5s (backend locally trims with FFmpeg if the user picked <5s).
    """
    return {
        "quality_tiers":       MH_QUALITY_TIERS,
        "min_billed_seconds":  5,
        "resolutions":         _STD_RES,  # legacy global list (kept for back-compat)
        "features": {
            "text_to_video": {
                "models": [
                    {"id": "quick",     "label": "Kling Lite",       "enabled": True, "credits_per_sec": 60,  "min_cost": 300, "default": True, "desc": "Fast · cheapest"},
                    {"id": "studio",    "label": "Kling 2.5",        "enabled": True, "credits_per_sec": 80,  "min_cost": 400,                  "desc": "Balanced quality"},
                    {"id": "cinematic", "label": "Kling 3.0 / Veo",  "enabled": True, "credits_per_sec": 120, "min_cost": 600,                  "desc": "Top quality · premium"},
                ],
                "duration_options":   _MH_VIDEO_DURATIONS,
                "resolution_options": _STD_RES,
            },
            "image_to_video": {
                "models": [
                    {"id": "quick",     "label": "Kling Lite",       "enabled": True, "credits_per_sec": 60,  "min_cost": 300, "default": True, "desc": "Animate images fast"},
                    {"id": "studio",    "label": "Kling 2.5",        "enabled": True, "credits_per_sec": 80,  "min_cost": 400,                  "desc": "Balanced animation"},
                    {"id": "cinematic", "label": "Kling 3.0 / Veo",  "enabled": True, "credits_per_sec": 120, "min_cost": 600,                  "desc": "Premium animation"},
                ],
                "duration_options":   _MH_VIDEO_DURATIONS,
                "resolution_options": _STD_RES,
            },
            "video_to_video": {
                "models": [
                    {"id": "quick",  "label": "Fast Style",   "enabled": True, "credits_per_sec": 50, "min_cost": 250, "default": True, "desc": "Fast style transfer"},
                    {"id": "studio", "label": "Studio Style", "enabled": True, "credits_per_sec": 70, "min_cost": 350,                  "desc": "Better quality"},
                ],
                "duration_options":   _MH_VIDEO_DURATIONS,
                "resolution_options": _STD_RES,
            },
            "ai_image_generator": {
                "models": [
                    {"id": "quick",     "label": "FLUX Schnell", "enabled": True, "credits_per_image": 4,  "default": True, "desc": "Fastest (~2s)"},
                    {"id": "studio",    "label": "FLUX Dev",     "enabled": True, "credits_per_image": 6,                   "desc": "Balanced default"},
                    {"id": "cinematic", "label": "FLUX Pro",     "enabled": True, "credits_per_image": 10,                  "desc": "Top quality"},
                ],
                "duration_options":   None,  # N/A for still images
                "resolution_options": _STD_RES,
            },
            "face_swap_photo": {
                "flat_cost": 60, "desc": "Photo face-swap (per image)",
                "duration_options":   None,
                "resolution_options": _STD_RES,
            },
            "face_swap_video": {
                "credits_per_sec": 80, "min_cost": 400, "desc": "Video face-swap",
                "duration_options":   None,  # derived from source video
                "resolution_options": _STD_RES,
            },
            "lip_sync": {
                "credits_per_sec": 40, "min_cost": 200, "desc": "Lip sync to audio",
                "duration_options":   None,  # driven by audio length
                "resolution_options": _STD_RES,
            },
            "talking_avatar": {
                "credits_per_sec": 60, "min_cost": 300, "desc": "AI Talking Photo",
                "duration_options":   None,  # driven by script/audio length
                "resolution_options": _STD_RES,
            },
        },
        "notice": "MH enforces 5-second minimum billing. Videos under 5s are still charged for 5s.",
    }
