"""Sprint 6 Phase 1 + 2 — Content Intelligence: Templates system.

Provides:
- AI Bhajan Creator (LLM-generated devotional lyrics)
- Viral Hook Generator (LLM-generated short-form hooks)
- Template CRUD (create, list, get, use-to-prefill)
- Preview Generator (5-sec ffmpeg motion preview with watermark — zero MH credit cost)

Designed to be wired into server.py via `router` import.
"""
import os
import json
import uuid
import subprocess
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

from core.models import (
    Template,
    GenerateBhajanRequest,
    GenerateHookRequest,
    CreateTemplateRequest,
)
from core.constants import motion_preset_by_id, voice_style_by_id, sfx_by_id

load_dotenv()
ROOT_DIR = Path(__file__).parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# Use the same db instance as server.py (respects ENV-based routing)
from core.config import MONGO_URL as _mongo_url, DB_NAME as _db_name
_mongo_client = AsyncIOMotorClient(_mongo_url)
db = _mongo_client[_db_name]

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
logger = logging.getLogger("magicai.templates")

router = APIRouter(prefix="/api/templates", tags=["templates"])


# ========== LLM helpers ==========
async def _call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 800) -> str:
    """Invoke Gemini via emergent LLM key. Returns raw text response."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"tmpl_{uuid.uuid4().hex[:8]}",
            system_message=system_prompt,
        ).with_model("gemini", "gemini-2.0-flash")
        resp = await chat.send_message(UserMessage(text=user_prompt))
        return (resp or "").strip()
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {str(e)[:200]}")


# ========== Content Generators ==========
BHAJAN_SYSTEM_PROMPT = """You are a devotional lyricist who writes short, emotional, singable bhajans.
Your lyrics:
- Are 4-8 lines (unless asked otherwise)
- Feel reverent, musical, and singable
- Use simple, emotional language
- For 'traditional' style: use Sanskrit + classical devotional vocabulary (Om Namah Shivaya, Govinda, Hari, etc.)
- For 'modern' style: use everyday Hindi with devotional emotion
- NEVER include stage directions, markdown, or explanations — ONLY the lyrics.

Respond with ONLY the lyrics, one line per line, no numbering, no commentary.
If [pause:1.5] markers would add emotional weight (e.g. after an invocation), include them naturally."""

HOOK_SYSTEM_PROMPT = """You are a viral short-form content expert (Reels/Shorts/TikTok).
You generate SHORT, scroll-stopping hooks (10-18 words each) designed to make viewers stop and watch.
Each hook must:
- Be punchy, curiosity-driven, or emotionally charged
- Work as opening 3 seconds of a vertical video
- Be in Hindi or Hinglish unless English is requested
- Avoid clickbait lies — hooks must deliver on the promise
- NEVER include numbering, markdown, quotes, or explanations — ONLY the hooks, one per line.

Respond with EXACTLY the number of hooks requested, one per line."""


@router.post("/generate-bhajan")
async def generate_bhajan(req: GenerateBhajanRequest):
    """AI Bhajan Creator — generate devotional lyrics via Gemini."""
    style_hint = "traditional (Sanskrit + classical devotional style)" if req.style == "traditional" else "modern (everyday Hindi, emotional)"
    lang_hint = {"sanskrit": "primarily in Sanskrit", "hindi": "primarily in Hindi", "mixed": "mixing Sanskrit + Hindi naturally"}.get(req.language, "in Hindi")
    lines = req.lines or 4
    prompt = (
        f"Write a {style_hint} bhajan about {req.theme}, {lang_hint}. "
        f"Exactly {lines} lines. Make it emotional and singable."
    )
    lyrics = await _call_llm(BHAJAN_SYSTEM_PROMPT, prompt, max_tokens=600)
    return {"lyrics": lyrics, "theme": req.theme, "style": req.style, "language": req.language}


@router.post("/generate-hooks")
async def generate_hooks(req: GenerateHookRequest):
    """Viral Hook Generator — generate N short-form hooks via Gemini."""
    count = max(1, min(10, req.count or 3))
    topic = f" about {req.topic}" if req.topic else ""
    prompt = f"Generate {count} viral Reels/Shorts hooks{topic} for the '{req.category}' category. One per line."
    raw = await _call_llm(HOOK_SYSTEM_PROMPT, prompt, max_tokens=400)
    hooks = [ln.strip() for ln in raw.split("\n") if ln.strip() and not ln.strip().startswith("#")]
    hooks = hooks[:count]
    return {"hooks": hooks, "category": req.category, "topic": req.topic}


# ========== Template CRUD ==========
@router.get("")
async def list_templates(
    category: Optional[str] = None,
    tier: Optional[str] = None,
    is_trending: Optional[bool] = None,
    festival_pack: Optional[str] = None,
    limit: int = 50,
):
    """List templates with optional filtering."""
    q: dict = {"is_active": True}
    if category:
        q["category"] = category
    if tier:
        q["tier"] = tier
    if is_trending is not None:
        q["is_trending"] = is_trending
    if festival_pack:
        q["festival_pack"] = festival_pack
    cursor = db.templates.find(q, {"_id": 0}).sort("score", -1).limit(limit)
    items = await cursor.to_list(length=limit)
    return {"templates": items, "count": len(items)}


@router.get("/festivals/summary")
async def festival_summary():
    """Summary of festival packs with counts + featured template per festival."""
    packs = ["janmashtami", "mahashivratri", "navratri"]
    out = []
    for fp in packs:
        items = await db.templates.find({"is_active": True, "festival_pack": fp}, {"_id": 0}).sort("score", -1).to_list(length=6)
        if items:
            out.append({"festival_pack": fp, "count": len(items), "templates": items})
    return {"festivals": out}


@router.get("/{template_id}")
async def get_template(template_id: str):
    t = await db.templates.find_one({"id": template_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    # Phase 3: increment view_count on every GET (fire-and-forget — ignore errors)
    try:
        await db.templates.update_one(
            {"id": template_id},
            {"$inc": {"view_count": 1}},
        )
    except Exception:
        pass
    return t


# ========== Phase 3 — Trending score admin trigger ==========
@router.post("/_internal/recompute-trending")
async def admin_recompute_trending(request: Request):
    """Admin-only. Force an immediate trending recompute (normally runs nightly at 02:00 UTC)."""
    from core.auth import get_current_user
    u = await get_current_user(request, strict=True)
    if not u.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    from core.trending import recompute_all
    result = await recompute_all(db)
    return {"ok": True, "result": result}


# ========== Phase 4 — Tier gating helper ==========
_TIER_RANK = {"free": 0, "starter": 1, "pro": 2, "premium": 2}


def _user_tier_rank(user_tier: str) -> int:
    return _TIER_RANK.get((user_tier or "free").lower(), 0)


def _template_tier_rank(tpl_tier: str) -> int:
    return _TIER_RANK.get((tpl_tier or "free").lower(), 0)


@router.post("")
async def create_template(req: CreateTemplateRequest):
    """Create a new template (admin/curator use)."""
    t = Template(
        title=req.title,
        category=req.category,  # type: ignore
        subcategory=req.subcategory,
        hook_text=req.hook_text,
        lyrics=req.lyrics,
        voice_id=req.voice_id or "hi-IN-SwaraNeural",
        voice_style=req.voice_style,
        motion=req.motion,
        sound_effect=req.sound_effect,
        aspect_ratio=req.aspect_ratio or "9:16",
        duration=req.duration or 5,
        thumbnail_url=req.thumbnail_url,
        tier=req.tier or "free",  # type: ignore
        source=req.source or "ai_generated",  # type: ignore
    )
    await db.templates.insert_one(t.dict())
    return {"template_id": t.id, "template": t.dict()}


@router.delete("/{template_id}")
async def delete_template(template_id: str):
    res = await db.templates.update_one({"id": template_id}, {"$set": {"is_active": False}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"ok": True}


# ========== Phase 2 — Preview Generator ==========
def _generate_preview_video(template_id: str, thumbnail_path: Path, motion_id: Optional[str], text_overlay: Optional[str], duration: float = 5.0) -> Optional[Path]:
    """Generate a 5s preview video with 'PREVIEW' watermark using ffmpeg zoompan.
    Zero MH credits — pure ffmpeg.
    """
    if not thumbnail_path.exists():
        logger.warning(f"preview: thumbnail not found {thumbnail_path}")
        return None
    preset = motion_preset_by_id(motion_id) if motion_id else None
    # Target 480p portrait for previews (small file, quick to render)
    w, h = 480, 854
    fps = 25
    total_frames = int(round(duration * fps))
    out_path = UPLOAD_DIR / f"preview_{template_id}_{uuid.uuid4().hex[:8]}.mp4"
    # Build zoompan filter (default to zoom_in if no motion specified)
    if preset and preset.get("zoompan_expr"):
        expr = preset["zoompan_expr"]
        z = expr["z"]
        x = expr["x"].replace("{D}", str(total_frames))
        y = expr["y"].replace("{D}", str(total_frames))
    else:
        z = "min(zoom+0.0012,1.25)"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    scale_w, scale_h = int(w * 1.5), int(h * 1.5)
    # Build filter chain: motion + watermark + optional hook text
    filters = [
        f"scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase",
        f"crop={scale_w}:{scale_h}",
        f"zoompan=z='{z}':x='{x}':y='{y}':d={total_frames}:s={w}x{h}:fps={fps}",
        "format=yuv420p",
    ]
    # Watermark: "PREVIEW" diagonal semi-transparent, lower-right
    # Use drawtext (requires fontfile; fallback to default)
    watermark = "drawtext=text='PREVIEW':fontcolor=white@0.6:fontsize=28:box=1:boxcolor=black@0.35:boxborderw=6:x=w-tw-20:y=h-th-20"
    filters.append(watermark)
    # Optional text overlay (hook / title) — top center
    if text_overlay:
        safe_text = text_overlay.replace("'", "").replace(":", "")[:60]
        filters.append(
            f"drawtext=text='{safe_text}':fontcolor=white:fontsize=26:box=1:boxcolor=black@0.5:boxborderw=10:x=(w-tw)/2:y=40"
        )
    vf = ",".join(filters)
    cmd = [
        "/usr/bin/ffmpeg", "-y",
        "-loop", "1", "-i", str(thumbnail_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-frames:v", str(total_frames),
        str(out_path),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, timeout=60)
        if res.returncode == 0 and out_path.exists() and out_path.stat().st_size > 1000:
            logger.info(f"preview: OK {template_id} -> {out_path.name} ({out_path.stat().st_size}b)")
            return out_path
        logger.warning(f"preview: ffmpeg fail {template_id}: {res.stderr[-300:].decode('utf-8', errors='ignore') if res.stderr else ''}")
    except Exception as e:
        logger.warning(f"preview: exception {template_id}: {e}")
    return None


@router.post("/{template_id}/generate-preview")
async def generate_template_preview(template_id: str, background_tasks: BackgroundTasks):
    """Generate a 5-second preview video for a template using its thumbnail + motion preset.
    Runs async in background — client should poll GET /api/templates/{id} for preview_url.
    """
    t = await db.templates.find_one({"id": template_id})
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    if not t.get("thumbnail_url"):
        raise HTTPException(status_code=400, detail="Template has no thumbnail_url")
    # Resolve thumbnail to local path
    raw = t["thumbnail_url"].replace("/api/serve-file/", "").replace("/uploads/", "")
    thumb = UPLOAD_DIR / raw.lstrip("/")
    if not thumb.exists():
        raise HTTPException(status_code=400, detail=f"Thumbnail file not found: {t['thumbnail_url']}")

    async def _bg():
        try:
            text_for_overlay = t.get("hook_text") or (t.get("title") if t.get("category") != "devotional" else None)
            out = _generate_preview_video(
                template_id=template_id,
                thumbnail_path=thumb,
                motion_id=t.get("motion"),
                text_overlay=text_for_overlay,
                duration=float(t.get("duration") or 5),
            )
            if out and out.exists():
                url = f"/api/serve-file/{out.name}"
                await db.templates.update_one(
                    {"id": template_id},
                    {"$set": {"preview_url": url, "updated_at": datetime.now(timezone.utc).isoformat()}},
                )
            else:
                logger.warning(f"preview: generation returned None for {template_id}")
        except Exception as e:
            logger.error(f"preview bg failed {template_id}: {e}")

    background_tasks.add_task(_bg)
    return {"ok": True, "status": "generating", "message": "Poll GET /api/templates/{id} for preview_url"}


@router.post("/{template_id}/use")
async def use_template(template_id: str, request: Request):
    """Mark a template as used (increments usage_count). Returns the full template so the
    client can pre-fill the appropriate creation screen.

    Phase 4: Enforces `tier` gating. Free users cannot use premium/starter/pro templates.
    """
    t = await db.templates.find_one({"id": template_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")

    # Phase 4: Tier gating. Pull user from JWT (best-effort; guest allowed on free templates in DEV).
    from core.auth import get_current_user
    user = await get_current_user(request, strict=False)
    user_tier = (user or {}).get("subscription_tier", "free")
    tpl_tier = t.get("tier") or "free"
    if _user_tier_rank(user_tier) < _template_tier_rank(tpl_tier):
        label_map = {"starter": "Starter", "pro": "Pro", "premium": "Pro"}
        needed = label_map.get(tpl_tier, tpl_tier.capitalize())
        raise HTTPException(
            status_code=402,
            detail=f"This template requires {needed} plan. Upgrade to unlock.",
        )

    await db.templates.update_one(
        {"id": template_id},
        {"$inc": {"usage_count": 1}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    # Recommend which screen to open based on available fields
    if t.get("lyrics"):
        recommended_screen = "/videogen"  # T2V with lyrics
    elif t.get("hook_text") and t.get("thumbnail_url"):
        recommended_screen = "/avatar"    # talking avatar pattern
    else:
        recommended_screen = "/videogen"
    return {"template": t, "recommended_screen": recommended_screen}


@router.post("/{template_id}/rate")
async def rate_template(template_id: str, request: Request):
    body = await request.json()
    stars = float(body.get("stars", 0))
    if stars < 1 or stars > 5:
        raise HTTPException(status_code=400, detail="Stars must be 1-5")
    t = await db.templates.find_one({"id": template_id})
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.templates.update_one(
        {"id": template_id},
        {"$inc": {"rating_sum": stars, "rating_count": 1}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True}
