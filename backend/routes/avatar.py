"""Phase-4A — Cartoon Avatar Generator.

Uses Gemini Nano Banana (gemini-3.1-flash-image-preview) to convert either
a user-uploaded photo OR a text prompt into a stylised cartoon avatar.

Endpoints:
  GET  /api/avatar/styles                 → list available styles + descriptions
  POST /api/avatar/cartoonize             → generate a cartoon avatar (FREE: watermark, PAID: clean)
  GET  /api/avatar/jobs/{job_id}          → poll a generation job (always returns {status, image_url?, error?})

Body for POST /cartoonize:
  {
    style: 'pixar' | 'anime' | 'disney' | 'caricature' | 'comic',
    emotion?: 'happy' | 'angry' | 'sad' | 'surprised' | 'neutral',
    prompt?: str           # optional text prompt — used standalone OR as guidance with image
    image_b64?: str        # base64 (data URL OK) of the user's photo (selfie)
    image_url?: str        # alternative — URL of the input photo
  }

Free tier behavior:
  • output gets a small "MagiCAi" watermark in the corner (FFmpeg drawtext)
  • paid tiers (starter/creator/pro) get the clean image
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

from core.config import DB_NAME

log = logging.getLogger("avatar")
router = APIRouter(prefix="/api/avatar", tags=["avatar"])

MONGO_URL = os.environ["MONGO_URL"]
_db_client = AsyncIOMotorClient(MONGO_URL)
db = _db_client[DB_NAME]

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR") or "/app/backend/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
AVATAR_DIR = UPLOAD_DIR        # serve-file endpoint only looks in UPLOAD_DIR root


# =====================================================================
#  STYLE DEFINITIONS  (the prompt-engineering core)
# =====================================================================
STYLES: dict[str, dict] = {
    "pixar": {
        "label": "Pixar",
        "icon": "🎬",
        "tagline": "3D rendered like Pixar films",
        "premium": False,
        "prompt_modifier": (
            "as a Pixar-style 3D animated character, big expressive eyes, soft skin, "
            "warm subsurface scattering, cinematic studio lighting, high-detail rendered, "
            "professional 3D animation style"
        ),
    },
    "anime": {
        "label": "Anime",
        "icon": "🌸",
        "tagline": "Japanese anime / manga look",
        "premium": False,
        "prompt_modifier": (
            "as an anime character, large detailed eyes, sharp clean line art, "
            "vibrant cell-shading, soft pastel palette, manga / Studio Ghibli aesthetic, "
            "Japanese animation style"
        ),
    },
    "disney": {
        "label": "Disney",
        "icon": "✨",
        "tagline": "Classic Disney-princess illustration",
        "premium": True,
        "prompt_modifier": (
            "as a classic Disney 2D animated character, smooth flowing line art, "
            "warm cinematic lighting, soft watercolor textures, cheerful expression, "
            "fairytale storybook illustration style"
        ),
    },
    "caricature": {
        "label": "Caricature",
        "icon": "🎨",
        "tagline": "Exaggerated playful caricature",
        "premium": False,
        "prompt_modifier": (
            "as a hand-drawn caricature, exaggerated facial features, oversized smile, "
            "playful exaggerated proportions, bright bold colors, comic newspaper style, "
            "humorous illustration"
        ),
    },
    "comic": {
        "label": "Comic Book",
        "icon": "💥",
        "tagline": "Western comic-book superhero",
        "premium": True,
        "prompt_modifier": (
            "as a western comic-book character, bold inked outlines, halftone shading dots, "
            "high-contrast vibrant colors, dramatic action pose, Marvel/DC art style, "
            "superhero illustration"
        ),
    },
}

EMOTIONS: dict[str, str] = {
    "happy":      "with a wide joyful smile, eyes sparkling with happiness, cheerful expression",
    "angry":      "with a furious frowning expression, knitted eyebrows, intense sharp eyes",
    "sad":        "with a melancholy downturned expression, soulful glistening eyes",
    "surprised":  "with a wide-eyed shocked expression, mouth open in surprise",
    "neutral":    "with a calm composed neutral expression",
    # ---- Phase 4D: Expression Engine ----
    "excited":    "with an exhilarated grin, eyes wide with thrill, energetic and enthusiastic expression",
    "mysterious": "with a subtle knowing smirk, half-closed eyes, secretive and intriguing expression",
    "peaceful":   "with a serene gentle smile, softly closed eyes, deeply tranquil and content expression",
    "confident":  "with a self-assured smirk, raised chin, focused intense gaze, charismatic and bold",
    "devotional": "with a humble reverent expression, hands prayer-folded subtly, soft glowing aura, devotional and divine",
    "playful":    "with a cheeky tongue-out grin, winking one eye, playful mischievous expression",
    "fierce":     "with a fierce warrior's gaze, jaw set firmly, eyes burning with power and determination",
}


# =====================================================================
#  PYDANTIC MODELS
# =====================================================================
class CartoonizeRequest(BaseModel):
    style: str = Field(..., description="One of: pixar, anime, disney, caricature, comic")
    emotion: Optional[str] = "happy"
    prompt: Optional[str] = None
    image_b64: Optional[str] = None     # data URL or raw base64
    image_url: Optional[str] = None


# =====================================================================
#  AUTH (lightweight — accepts guest, but reads tier from JWT if present)
# =====================================================================
async def _resolve_user(request: Request) -> dict:
    auth = (request.headers.get("authorization") or "").strip()
    if not auth.lower().startswith("bearer "):
        return {"id": None, "subscription_tier": "free"}
    token = auth.split(" ", 1)[1].strip()
    try:
        try:
            from core.auth import decode_token  # type: ignore
            payload = decode_token(token)
        except Exception:
            import jwt
            secret = os.environ.get("JWT_SECRET") or os.environ.get("SECRET_KEY") or "secret"
            payload = jwt.decode(token, secret, algorithms=["HS256"])
        uid = payload.get("user_id") or payload.get("sub") or payload.get("id")
        if not uid:
            return {"id": None, "subscription_tier": "free"}
        u = await db.users.find_one({"id": uid}) or await db.users.find_one({"_id": uid})
        return u or {"id": uid, "subscription_tier": "free"}
    except Exception:
        return {"id": None, "subscription_tier": "free"}


# =====================================================================
#  PUBLIC ENDPOINTS
# =====================================================================
@router.get("/styles")
async def list_styles():
    out = [
        {
            "id": k,
            "label": v["label"],
            "icon": v["icon"],
            "tagline": v["tagline"],
            "premium": v["premium"],
        }
        for k, v in STYLES.items()
    ]
    return {"styles": out, "emotions": list(EMOTIONS.keys()), "count": len(out)}


@router.post("/cartoonize")
async def cartoonize(req: CartoonizeRequest, background: BackgroundTasks, request: Request):
    """Generate a cartoon avatar. Returns a job_id; poll /avatar/jobs/{id}.
    For very fast generations (<10s) this could be sync, but Nano Banana avg 6-15s
    so we run it in the background to avoid client timeouts."""
    if req.style not in STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown style. Use: {', '.join(STYLES.keys())}")
    style_def = STYLES[req.style]

    # Phase-4 safety — moderate any text input
    from core.moderation import moderate_text, raise_if_blocked
    if req.prompt:
        raise_if_blocked(await moderate_text(req.prompt, source="avatar.prompt"))

    user = await _resolve_user(request)
    user_tier = (user.get("subscription_tier") or "free").lower()
    is_paid = user_tier in ("starter", "creator", "pro")

    # Premium-style gate: pixar/anime/caricature → free, disney/comic → paid only
    if style_def["premium"] and not is_paid:
        raise HTTPException(
            status_code=403,
            detail={
                "premium_required": True,
                "style": req.style,
                "reason": f"The {style_def['label']} style is part of MagiCAi Premium. Upgrade or pick a free style.",
            },
        )

    # Need at least one source
    if not (req.image_b64 or req.image_url or req.prompt):
        raise HTTPException(status_code=400, detail="Provide either image_b64, image_url, or prompt.")

    job_id = f"av_{uuid.uuid4().hex[:12]}"
    job_doc = {
        "id": job_id,
        "user_id": user.get("id"),
        "user_tier": user_tier,
        "style": req.style,
        "emotion": req.emotion or "neutral",
        "status": "queued",
        "created_at": datetime.now(timezone.utc),
        "watermarked": not is_paid,
    }
    await db.avatar_jobs.insert_one(job_doc)

    # Run in background — never block the client
    background.add_task(
        _process_avatar_job,
        job_id=job_id,
        style=req.style,
        emotion=req.emotion or "happy",
        prompt=req.prompt,
        image_b64=req.image_b64,
        image_url=req.image_url,
        watermark=not is_paid,
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "style": req.style,
        "tier": user_tier,
        "watermark": not is_paid,
    }


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = await db.avatar_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Avatar job not found")
    for k, v in list(job.items()):
        if isinstance(v, datetime):
            job[k] = v.isoformat()
    return job


# =====================================================================
#  WORKER
# =====================================================================
async def _set_job(job_id: str, **fields):
    fields["updated_at"] = datetime.now(timezone.utc)
    try:
        await db.avatar_jobs.update_one({"id": job_id}, {"$set": fields})
    except Exception:
        pass


async def _process_avatar_job(*, job_id: str, style: str, emotion: str,
                              prompt: Optional[str], image_b64: Optional[str],
                              image_url: Optional[str], watermark: bool):
    try:
        await _set_job(job_id, status="processing", stage="prepare")

        # Decode/fetch the source image (optional)
        source_bytes: Optional[bytes] = None
        if image_b64:
            data = image_b64
            if data.startswith("data:"):
                data = data.split(",", 1)[-1]
            try:
                source_bytes = base64.b64decode(data)
            except Exception:
                source_bytes = None
        elif image_url:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), follow_redirects=True) as c:
                    r = await c.get(image_url)
                    if r.status_code == 200 and len(r.content) > 800:
                        source_bytes = r.content
            except Exception as e:
                log.warning("avatar: image_url fetch failed: %s", e)

        # Build the Nano Banana prompt
        style_def = STYLES[style]
        emo_text = EMOTIONS.get(emotion, EMOTIONS["happy"])
        user_prompt = (prompt or "a portrait of a friendly person").strip()
        full_prompt = (
            f"{user_prompt}, {style_def['prompt_modifier']}, {emo_text}, "
            "9:16 vertical portrait composition, centered framing, no text overlay"
        )
        await _set_job(job_id, stage="generate", prompt_used=full_prompt[:600])

        # Call Nano Banana
        out_bytes = await _nano_banana_image(full_prompt, source_bytes, job_id)
        if not out_bytes:
            await _set_job(job_id, status="failed", error="Image generation returned no result.")
            return

        # Persist clean version
        clean_path = AVATAR_DIR / f"{job_id}.png"
        clean_path.write_bytes(out_bytes)
        clean_url = f"/api/serve-file/{clean_path.name}"

        # Watermark for free tier
        final_url = clean_url
        if watermark:
            await _set_job(job_id, stage="watermark")
            wm_path = AVATAR_DIR / f"{job_id}_wm.png"
            ok = await _apply_watermark(clean_path, wm_path)
            if ok:
                final_url = f"/api/serve-file/{wm_path.name}"

        await _set_job(
            job_id,
            status="completed",
            stage="done",
            image_url=final_url,
            clean_url=clean_url if not watermark else None,
            completed_at=datetime.now(timezone.utc),
        )
        log.info("avatar: job %s completed (style=%s, watermark=%s)", job_id, style, watermark)
    except Exception as e:
        log.exception("avatar: job %s failed: %s", job_id, e)
        await _set_job(job_id, status="failed", error=str(e)[:300])


async def _nano_banana_image(prompt: str, source_bytes: Optional[bytes], job_id: str) -> Optional[bytes]:
    """Call Gemini Nano Banana via emergentintegrations. If source_bytes is provided,
    pass it as a multimodal input (image-to-image stylise). Otherwise pure text-to-image."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
        api_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
        if not api_key:
            log.warning("avatar: EMERGENT_LLM_KEY missing")
            return None

        chat = LlmChat(
            api_key=api_key,
            session_id=f"avatar_{job_id}",
            system_message="You are an AI image generator specialised in stylised cartoon avatars (9:16 vertical).",
        )
        chat = chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])

        if source_bytes:
            try:
                ic = ImageContent(image_base64=base64.b64encode(source_bytes).decode())
                msg = UserMessage(text=prompt, image_contents=[ic])
            except Exception:
                msg = UserMessage(text=prompt)
        else:
            msg = UserMessage(text=prompt)

        text, images = await chat.send_message_multimodal_response(msg)
        if not images:
            log.warning("avatar: nano banana returned 0 images")
            return None
        raw = base64.b64decode(images[0].get("data") or "")
        return raw if raw and len(raw) > 500 else None
    except Exception as e:
        log.exception("avatar nano banana error: %s", e)
        return None


async def _apply_watermark(src: Path, dst: Path) -> bool:
    """Add a small 'MagiCAi' watermark at bottom-right (Free tier)."""
    cmd = [
        "/usr/bin/ffmpeg", "-y",
        "-i", str(src),
        "-vf",
        ("drawtext=text='MagiCAi':fontcolor=white@0.85:fontsize=h/22:"
         "borderw=2:bordercolor=black@0.6:x=w-text_w-18:y=h-text_h-18"),
        "-q:v", "3",
        str(dst),
    ]
    try:
        r = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, timeout=30)
        return r.returncode == 0 and dst.exists() and dst.stat().st_size > 500
    except Exception as e:
        log.warning("watermark failed: %s", e)
        return False
