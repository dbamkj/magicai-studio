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
from motor.motor_asyncio import AsyncIOMotorClient

from core.auth import get_current_user
from core.db import db
from core.config import MONGO_URL, DB_NAME as AUTH_DB_NAME
from core.constants import MH_CREDIT_COSTS, MH_QUALITY_TIERS
from core.pricing import (
    MH_PER_SEC, MH_MIN_BILLED_SECONDS,
    PLANS, plan_by_id, utc_month_str, utc_today_str,
)

# DSAR/audit must hit the SAME database where auth stores users
# (magicai_beta), not the legacy core.db default (videoai_database).
_auth_db = AsyncIOMotorClient(MONGO_URL)[AUTH_DB_NAME]

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
    uid = user.get("user_id") or user.get("id") or user.get("email")

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
# GET /api/me/limits — current tier feature gates + month-to-date usage
# ══════════════════════════════════════════════════════════════════════
@router.get("/me/limits")
async def me_limits(request: Request):
    """Return the calling user's tier gates + this-month usage + upsell hints.

    Frontend uses this to render progress bars on the Credits screen and to
    pre-disable buttons / show lock badges on Pro-only / Creator-only features
    BEFORE the user hits them (saving a wasted 402 round-trip).
    """
    user = await get_current_user(request)
    uid = user.get("user_id") or user.get("id") or user.get("email")

    # Re-hydrate from DB so we get the latest monthly_usage counters
    u = await db.users.find_one({"id": uid}) or user
    tier_id = (u.get("subscription_tier") or "free").lower()
    plan = plan_by_id(tier_id)

    month = utc_month_str()
    today = utc_today_str()
    mu = u.get("monthly_usage") or {}
    if u.get("monthly_usage_month") != month:
        mu = {"reels": 0, "lipsync": 0, "ai_videos": 0, "images": 0}

    daily_images = int(u.get("daily_image_usage", 0) or 0) if u.get("daily_usage_date") == today else 0

    def _bar(used, cap):
        used = int(used or 0)
        cap = int(cap or 0)
        if cap >= 9999 or cap == 0:
            return {"used": used, "cap": cap, "unlimited": cap >= 9999, "pct": 0.0, "exhausted": False}
        pct = round(100 * used / cap, 1) if cap > 0 else 0
        return {"used": used, "cap": cap, "unlimited": False, "pct": pct, "exhausted": used >= cap}

    return {
        "tier": {
            "id": plan["id"],
            "label": plan["label"],
            "price_inr": plan["price_inr"],
            "max_resolution": plan.get("max_resolution", "480p"),
            "watermark": plan.get("watermark", False),
        },
        "credits": {
            "balance": int(u.get("credits_balance", 0) or 0),
            "monthly_grant": int(plan.get("credits", 0)),
        },
        "usage_this_month": {
            "month": month,
            "reels":     _bar(mu.get("reels"),     plan.get("monthly_reels_limit", 0)),
            "lipsync":   _bar(mu.get("lipsync"),   plan.get("monthly_lipsync_limit", 0)),
            "ai_videos": _bar(mu.get("ai_videos"), plan.get("monthly_ai_videos_limit", 0)),
            "images":    _bar(mu.get("images"),    plan.get("max_images", 9999)),
        },
        "usage_today": {
            "date": today,
            "images": _bar(daily_images, plan.get("daily_image_limit", 9999)),
        },
        "feature_gates": {
            "face_swap":        plan.get("allow_face_swap", False),
            "lip_sync":         plan.get("allow_lip_sync", False),
            "head_swap":        plan.get("allow_head_swap", False),
            "body_swap":        plan.get("allow_body_swap", False),
            "video_to_video":   plan.get("allow_video_to_video", False),
            "divine":           plan.get("allow_divine", False),
            "ai_bg_lipsync":    plan.get("allow_ai_bg_lipsync", False),
            "multishot":        plan.get("allow_multishot", False),
            "ai_video":         plan.get("allow_ai_video", False),
            "video_studio":     plan.get("allow_video_studio", False),
            "video_cinematic":  plan.get("allow_video_cinematic", False),
            "image_cinematic":  plan.get("allow_image_cinematic", False),
        },
        "upgrade_hints": _upgrade_hints(tier_id, plan, mu, daily_images),
    }


def _upgrade_hints(tier_id: str, plan: dict, mu: dict, daily_images: int) -> list[dict]:
    """Return a list of friendly upsell suggestions based on current usage."""
    hints: list[dict] = []
    # Free: daily image cap hit
    cap_img = int(plan.get("daily_image_limit", 9999) or 9999)
    if cap_img < 9999 and daily_images >= cap_img - 1:
        hints.append({
            "icon": "image",
            "text": f"You're about to hit the {cap_img}-image/day Free cap. Upgrade to Starter for unlimited images.",
            "cta": "Upgrade to Starter",
            "target_tier": "starter",
        })
    # Starter/Creator: nearing reel cap
    for bucket, label, next_tier in [
        ("reels", "reels", "pro"),
        ("lipsync", "lip syncs", "pro"),
        ("ai_videos", "AI videos", "pro"),
    ]:
        cap = int(plan.get(f"monthly_{bucket}_limit", 0) or 0)
        if cap and cap < 9999:
            used = int((mu or {}).get(bucket, 0) or 0)
            if used >= cap - 1:
                hints.append({
                    "icon": bucket,
                    "text": f"You've used {used}/{cap} {label} this month. Upgrade to Pro for more.",
                    "cta": "Upgrade to Pro",
                    "target_tier": next_tier,
                })
    # Kling 3.0 / Veo gate (Pro-only)
    if tier_id != "pro" and not plan.get("allow_video_cinematic", False):
        hints.append({
            "icon": "sparkles",
            "text": "Unlock Kling 3.0 Pro / Veo cinematic quality on Pro.",
            "cta": "See Pro features",
            "target_tier": "pro",
        })
    return hints


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



# ══════════════════════════════════════════════════════════════════════
# Session 36 — DPDPA Sprint 2 — DSAR (Data Subject Access Request)
# ══════════════════════════════════════════════════════════════════════
#
# DPDPA Article 11 / GDPR Art. 15 + 17: users have a right to obtain
# a copy of all personal data we hold about them, and to request its
# deletion. We implement both as self-service endpoints.
#

@router.get("/account/export-data")
async def dsar_export_data(request: Request):
    """Return a JSON dump of all personal data we hold about the user.

    Includes: user profile, video projects, audit log entries,
    waitlist signups, notifications. Excludes: hashed password
    (security), marketplace_templates (not user-owned).

    DPDPA Article 11: must be provided within 30 days. We do it inline.
    """
    user = await get_current_user(request, strict=True)
    uid = user.get("id") or user.get("user_id") or user.get("email")
    email = (user.get("email") or "").lower()

    # User profile (drop sensitive fields)
    profile = await _auth_db.users.find_one({"id": uid}, {"_id": 0, "password_hash": 0}) or {}

    # All video projects (any kind) — these live in legacy `db`
    projects = await db.video_projects.find(
        {"$or": [{"user_id": uid}, {"user_email": email}]},
        {"_id": 0},
    ).sort("created_at", -1).to_list(length=5000)

    # Audit-log entries for this user (audit collection in auth DB)
    audit = await _auth_db.audit_logs.find(
        {"user_id": uid}, {"_id": 0}
    ).sort("timestamp", -1).to_list(length=10000)

    # Waitlist signups (if any)
    waitlist = await _auth_db.waitlist.find(
        {"email": email}, {"_id": 0}
    ).to_list(length=10)

    # Notifications (legacy db)
    notifs = await db.notifications.find(
        {"user_id": uid}, {"_id": 0}
    ).sort("created_at", -1).to_list(length=1000)

    # Audit the export itself (DPDPA Article 7(f))
    try:
        from core.audit import log_audit
        await log_audit("dsar.export", user_id=uid,
                        meta={"projects": len(projects), "audit_rows": len(audit)},
                        request=request)
    except Exception:
        pass

    from datetime import datetime, timezone
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user_id": uid,
        "regulation": "DPDPA 2023 / GDPR Article 15",
        "data": {
            "profile": profile,
            "video_projects": projects,
            "audit_logs": audit,
            "waitlist_entries": waitlist,
            "notifications": notifs,
        },
        "counts": {
            "projects": len(projects),
            "audit_logs": len(audit),
            "waitlist_entries": len(waitlist),
            "notifications": len(notifs),
        },
    }


@router.post("/account/delete-account")
async def dsar_delete_account(request: Request):
    """Soft-delete the user account and scrub PII.

    Strategy: we do NOT hard-delete because:
      - We need to retain audit logs for compliance (DPDPA Art. 7(f)).
      - Outstanding subscriptions / refund obligations need user_id traceability.
    Instead, we:
      - Anonymize email → `deleted-<uuid>@deleted.local`
      - Wipe name, picture, password_hash, push_tokens
      - Set deleted_at + is_deleted=true
      - Subscription tier → 'free'
      - Mark all video_projects with redacted=true
      - Append final audit log entry

    DPDPA Article 12: right to erasure. Must be completed within 30 days.
    This endpoint completes synchronously.
    """
    import uuid
    from datetime import datetime, timezone

    user = await get_current_user(request, strict=True)
    uid = user.get("id") or user.get("user_id")
    email = (user.get("email") or "").lower()

    if not uid:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="User id missing")

    redaction_email = f"deleted-{uuid.uuid4().hex[:12]}@deleted.local"
    now = datetime.now(timezone.utc).isoformat()

    await _auth_db.users.update_one(
        {"id": uid},
        {"$set": {
            "email": redaction_email,
            "name": "[deleted]",
            "picture": "",
            "password_hash": "",
            "push_tokens": [],
            "google_email": "",
            "is_deleted": True,
            "deleted_at": now,
            "subscription_tier": "free",
            "credits_balance": 0,
            "requires_upgrade": False,
        }},
    )

    # Optionally redact project metadata that could re-identify the user
    await db.video_projects.update_many(
        {"$or": [{"user_id": uid}, {"user_email": email}]},
        {"$set": {"user_email": redaction_email, "redacted": True, "redacted_at": now}},
    )

    try:
        from core.audit import log_audit
        await log_audit("dsar.deletion_completed", user_id=uid,
                        meta={"redaction_email": redaction_email}, request=request)
    except Exception:
        pass

    return {
        "ok": True,
        "deleted_at": now,
        "redaction_email": redaction_email,
        "message": "Account has been deleted. You will be logged out.",
    }
