"""Phase-2 Marketplace API — read-only template marketplace.

Endpoints:
  GET  /api/marketplace/categories            → category metadata
  GET  /api/marketplace/templates             → list templates (filter+sort)
  GET  /api/marketplace/templates/{id}        → single template (increments view_count)
  POST /api/marketplace/templates/{id}/use    → increments usage_count, returns wizard prefill payload
  POST /api/marketplace/_internal/seed        → idempotent seed (idempotent on every call)

Ranking:
  trending = (usage_count * 3) + (view_count * 0.5) + recency_decay + featured_bonus
"""
from __future__ import annotations
import logging
import math
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient

from core.config import DB_NAME
from core.marketplace_seed import (
    SEED_TEMPLATES,
    CATEGORY_META,
    ensure_seeded,
    enrich_thumbnails,
)

log = logging.getLogger("marketplace")
router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])

MONGO_URL = os.environ["MONGO_URL"]
_client = AsyncIOMotorClient(MONGO_URL)
db = _client[DB_NAME]


def _serialize(t: dict) -> dict:
    """Drop ObjectId & convert datetimes to ISO."""
    out = {k: v for k, v in t.items() if k != "_id"}
    for k, v in out.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
    return out


def _trending_score(t: dict) -> float:
    usage = float(t.get("usage_count", 0))
    views = float(t.get("view_count", 0))
    base = usage * 3.0 + views * 0.5
    if t.get("is_featured"):
        base += 8.0
    if t.get("is_trending"):
        base += 5.0
    # recency boost (newer = higher), capped to 5
    created = t.get("created_at")
    if isinstance(created, datetime):
        days_old = max(0.0, (datetime.now(timezone.utc) - created.replace(tzinfo=created.tzinfo or timezone.utc)).total_seconds() / 86400.0)
        base += max(0.0, 5.0 - math.log(1 + days_old))
    return round(base, 2)


# ---------------- categories ----------------
@router.get("/categories")
async def list_categories():
    return {"categories": CATEGORY_META, "count": len(CATEGORY_META)}


# ---------------- templates ----------------
@router.get("/templates")
async def list_templates(
    category: Optional[str] = None,
    sort: str = "trending",  # trending | new | featured
    limit: int = 24,
):
    q: dict = {"is_active": True}
    if category and category != "all":
        q["category"] = category

    cursor = db.marketplace_templates.find(q, {"_id": 0})
    items = await cursor.to_list(length=200)

    # Apply ranking + sort
    for it in items:
        it["_score"] = _trending_score(it)

    if sort == "new":
        items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    elif sort == "featured":
        items = [x for x in items if x.get("is_featured")] + [x for x in items if not x.get("is_featured")]
    else:  # trending (default)
        items.sort(key=lambda x: x["_score"], reverse=True)

    items = [_serialize(x) for x in items[:limit]]
    return {
        "templates": items,
        "count": len(items),
        "category": category or "all",
        "sort": sort,
    }


@router.get("/templates/{template_id}")
async def get_template(template_id: str):
    t = await db.marketplace_templates.find_one({"id": template_id})
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    # fire-and-forget view increment
    try:
        await db.marketplace_templates.update_one(
            {"id": template_id}, {"$inc": {"view_count": 1}}
        )
    except Exception:
        pass
    return _serialize(t)


@router.post("/templates/{template_id}/use")
async def use_template(template_id: str):
    """User tapped 'Use Template'. Increments usage_count and returns the payload
    the wizard needs to pre-fill its steps."""
    t = await db.marketplace_templates.find_one({"id": template_id})
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    try:
        await db.marketplace_templates.update_one(
            {"id": template_id},
            {"$inc": {"usage_count": 1}, "$set": {"last_used_at": datetime.now(timezone.utc)}},
        )
    except Exception:
        pass

    # Build a rich prefill prompt: combine the wizard idea + script + image
    # query into a single descriptive prompt the wizard can drop straight
    # into the textarea. Falls back to first prompts[] entry, then tagline.
    prompts_arr: list[str] = list(t.get("prompts") or [])
    rich_prompt = ""
    if prompts_arr:
        rich_prompt = prompts_arr[0]
    else:
        idea = (t.get("wizard_idea") or "").strip()
        script = (t.get("wizard_script") or "").strip()
        iq = (t.get("wizard_image_query") or "").strip()
        mood = (t.get("music_mood") or "").replace("_", " ")
        rich_prompt = (
            f"{idea}. {script} Visual: {iq}, cinematic 9:16 vertical, {mood} mood."
            if idea else (t.get("tagline") or t.get("title") or "")
        )

    return {
        "id": t["id"],
        "title": t.get("title"),
        "category": t.get("category"),
        "tagline": t.get("tagline"),
        "plan_tier": t.get("plan_tier", "free"),
        "prompts": prompts_arr,
        "wizard_payload": {
            "idea": t.get("wizard_idea") or t.get("title"),
            "title": t.get("title"),
            "script": t.get("wizard_script") or "",
            "image_query": t.get("wizard_image_query") or t.get("title", ""),
            "video_query": t.get("wizard_image_query") or t.get("title", ""),
            "mode": t.get("wizard_mode") or "video",
            "voice_id": t.get("voice_id") or "en-US-JennyNeural",
            "voice_style": t.get("voice_style") or "story",
            "music_mood": t.get("music_mood") or "cinematic_epic",
            "motion": t.get("motion") or "auto",
            "aspect_ratio": t.get("aspect_ratio") or "9:16",
            "total_duration": float(t.get("duration") or 10),
            # Sprint 30f: language drives downstream Sarvam tier-routing.
            # Bhajan/devotional templates default to 'hinglish' so the wizard's
            # voice_layer routes Premium users to Sarvam Bulbul-v2 (Vidya/Karun)
            # even though the wizard_script is written in Roman Hindi.
            "lang": t.get("language") or _default_lang_for_category(t.get("category")),
            "language": t.get("language") or _default_lang_for_category(t.get("category")),
            # Rich prompt for direct prefill into the wizard textarea
            "prompt": rich_prompt,
            "prompts": prompts_arr,
            "plan_tier": t.get("plan_tier", "free"),
        },
    }


# Bhajan / devotional templates ship with Roman-Hindi (Hinglish) scripts so
# Premium users get auto-routed to Sarvam Bulbul-v2 voices. Other categories
# default to English unless they have an explicit `language` field set.
_HINGLISH_CATEGORIES = {
    'bhajan', 'devotional', 'mantra', 'shloka', 'aarti',
    'patriotic', 'shaayri', 'shayari', 'ghazal',
}


def _default_lang_for_category(category: Optional[str]) -> str:
    if not category:
        return 'english'
    return 'hinglish' if category.lower() in _HINGLISH_CATEGORIES else 'english'


# ---------------- internal: seed ----------------
@router.post("/_internal/seed")
async def seed_marketplace(request: Request, force: bool = False):
    """Idempotent. Call once at startup or manually. Returns counts.

    When `?force=true` is passed, existing seed-id rows are wiped and re-inserted
    (used to push the new plan_tier + prompts schema into the DB)."""
    res = await ensure_seeded(db, force=force)
    log.info("marketplace seed: %s", res)
    return res


@router.post("/_internal/enrich-thumbnails")
async def enrich_marketplace_thumbnails(force: bool = False):
    """Pull a Pixabay vertical image for each template. Run once after seeding."""
    res = await enrich_thumbnails(db, force=force)
    return res
