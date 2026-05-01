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

    # ---- Phase D1: Indian cartoon-inspired buckets ------------------------
    # NOTE: these deliberately describe visual characteristics ONLY — no
    # brand / IP names (Motu Patlu, Chhota Bheem, Doraemon, Mowgli). That
    # keeps us safe on Play/App-Store review + DMCA, while users still get
    # that familiar "desi cartoon" or "jungle kid" vibe from the portrait.
    "desi_toon": {
        "label": "Desi Toon",
        "icon": "🇮🇳",
        "tagline": "Indian TV cartoon — flat 2D, vibrant pop colors",
        "premium": False,
        "prompt_modifier": (
            "as a flat 2D Indian television animated character in the style of "
            "a modern Indian kids' cartoon, large round head, simple big eyes with "
            "small pupils, thick black outlines, vibrant saturated pop colors, "
            "bright yellow/red/blue palette, minimal shading, friendly expressive face, "
            "clean children's animation aesthetic"
        ),
    },
    "jungle_hero": {
        "label": "Jungle Hero",
        "icon": "🌳",
        "tagline": "Adventurous jungle-child painterly look",
        "premium": True,
        "prompt_modifier": (
            "as a semi-realistic painterly jungle-adventure animated character, "
            "tousled hair, sun-kissed warm skin tone, lush tropical leaves and "
            "dappled jungle light in background, storybook watercolor shading, "
            "curious hopeful expression, classic jungle-adventure film aesthetic, "
            "wholesome family-animation look"
        ),
    },
    "robo_pal": {
        "label": "Robo Pal",
        "icon": "🤖",
        "tagline": "Round cartoon robot friend — classic anime",
        "premium": True,
        "prompt_modifier": (
            "as a chibi round-bodied cartoon robot-pal character, oversized friendly "
            "head with large round black eyes, small smiling mouth, smooth pastel "
            "blue-and-white color scheme, soft cell shading, retro classic Japanese "
            "cartoon aesthetic, innocent cheerful expression, simple flat background"
        ),
    },
    "mythological": {
        "label": "Mythological",
        "icon": "🕉️",
        "tagline": "Divine Indian-mythology illustration",
        "premium": True,
        "prompt_modifier": (
            "as a richly illustrated Indian mythology divine character, "
            "ornate gold jewelry and silk garments, soft divine glow and halo, "
            "traditional Indian classical art influence, intricate decorative borders, "
            "serene reverent expression, painterly temple-mural texture, "
            "devotional calendar art aesthetic"
        ),
    },
    "bollywood_poster": {
        "label": "Bollywood Poster",
        "icon": "🎭",
        "tagline": "Retro Bollywood hand-painted poster vibe",
        "premium": False,
        "prompt_modifier": (
            "as a retro 70s Indian hand-painted Bollywood movie poster caricature, "
            "exaggerated bold facial features, dramatic heroic expression, "
            "saturated primary colors with grainy brush-stroke texture, "
            "painted poster style, vintage cinema advertisement aesthetic, "
            "bold stylized linework"
        ),
    },
    "cricket_champion": {
        "label": "Cricket Champion",
        "icon": "🏏",
        "tagline": "Indian sports-hero action cartoon",
        "premium": False,
        "prompt_modifier": (
            "as a dynamic Indian sports cartoon hero character, confident victorious "
            "pose, stylized speed-lines and action bursts in background, blue India "
            "cricket-jersey colors, bold clean linework, energetic cheerful expression, "
            "sports-comic magazine aesthetic"
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
#  PERSONALITY ENGINE — maps style → category + voice/tone/mood/bgm
# =====================================================================
# Powers the AI Avatar Studio wizard:
#   • category drives the Step-1 tab chips (Indian / Funny / Spiritual / Influencer)
#   • personality drives the Step-4 auto-mapped voice + Step-6 BGM mood
#   • the same mapping is echoed by GET /api/avatar/styles so the frontend
#     never has to re-derive it.
STYLE_CATEGORY: dict[str, str] = {
    # Indian-cartoon bucket
    "desi_toon":         "indian",
    "jungle_hero":       "indian",
    "bollywood_poster":  "indian",
    "cricket_champion":  "indian",
    # Spiritual
    "mythological":      "spiritual",
    # Funny / playful
    "caricature":        "funny",
    "comic":             "funny",
    "robo_pal":          "funny",
    # Influencer / aspirational
    "pixar":             "influencer",
    "anime":             "influencer",
    "disney":            "influencer",
}

DEFAULT_PERSONALITY = {
    "voice_id":    "en-US-JennyNeural",
    "voice_style": "story",
    "mood":        "inspiring",
    "bgm_style":   "cinematic orchestral",
    "tone":        "warm and friendly",
}

STYLE_PERSONALITY: dict[str, dict] = {
    "pixar": {
        "voice_id": "en-US-JennyNeural", "voice_style": "story",
        "mood": "playful",  "bgm_style": "cinematic orchestral",
        "tone": "warm, cinematic, imaginative",
    },
    "anime": {
        "voice_id": "en-US-AriaNeural", "voice_style": "story",
        "mood": "playful",  "bgm_style": "anime upbeat synth",
        "tone": "expressive, youthful, bright",
    },
    "disney": {
        "voice_id": "en-US-JennyNeural", "voice_style": "story",
        "mood": "romantic", "bgm_style": "fairytale orchestral",
        "tone": "whimsical, dreamy, heartfelt",
    },
    "caricature": {
        "voice_id": "en-US-GuyNeural", "voice_style": "funny",
        "mood": "playful",  "bgm_style": "upbeat funny cartoon",
        "tone": "exaggerated, theatrical, fun",
    },
    "comic": {
        "voice_id": "en-US-GuyNeural", "voice_style": "motivation",
        "mood": "dramatic", "bgm_style": "cinematic epic trailer",
        "tone": "bold, heroic, punchy",
    },
    "desi_toon": {
        "voice_id": "hi-IN-SwaraNeural", "voice_style": "funny",
        "mood": "playful",  "bgm_style": "upbeat funny indian cartoon",
        "tone": "cheerful, desi-playful, warm",
    },
    "jungle_hero": {
        "voice_id": "hi-IN-MadhurNeural", "voice_style": "story",
        "mood": "inspiring", "bgm_style": "adventure tribal drums",
        "tone": "curious, adventurous, hopeful",
    },
    "robo_pal": {
        "voice_id": "en-US-GuyNeural", "voice_style": "funny",
        "mood": "playful",  "bgm_style": "retro synth chiptune",
        "tone": "quirky, robotic, friendly",
    },
    "mythological": {
        "voice_id": "hi-IN-MadhurNeural", "voice_style": "devotional",
        "mood": "spiritual", "bgm_style": "indian classical flute",
        "tone": "reverent, calm, divine",
    },
    "bollywood_poster": {
        "voice_id": "hi-IN-MadhurNeural", "voice_style": "motivation",
        "mood": "dramatic", "bgm_style": "bollywood retro brass",
        "tone": "theatrical, bold, vintage-drama",
    },
    "cricket_champion": {
        "voice_id": "hi-IN-MadhurNeural", "voice_style": "motivation",
        "mood": "energetic", "bgm_style": "sports stadium anthem",
        "tone": "confident, victorious, energetic",
    },
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
            "category": STYLE_CATEGORY.get(k, "funny"),
            "personality": STYLE_PERSONALITY.get(k, DEFAULT_PERSONALITY),
        }
        for k, v in STYLES.items()
    ]
    # Also return a category index so the frontend can render tabs directly.
    categories = [
        {"id": "indian",     "label": "Indian",     "icon": "🇮🇳"},
        {"id": "funny",      "label": "Funny",      "icon": "😂"},
        {"id": "spiritual",  "label": "Spiritual",  "icon": "🕉️"},
        {"id": "influencer", "label": "Influencer", "icon": "✨"},
    ]
    return {
        "styles": out,
        "emotions": list(EMOTIONS.keys()),
        "categories": categories,
        "count": len(out),
    }


# =====================================================================
#  AI AVATAR STUDIO — POST /api/avatar/dialogues
# =====================================================================
# Generates 3 short avatar-appropriate one-liners (8–15 words each)
# tuned to the picked style's personality. Used by Step 3 of the
# AI Avatar Studio wizard.  GPT-4o-mini via Emergent LLM Key.
# Cached in-memory by sha256(style|idea|language|count) for 30 min.

import hashlib as _hashlib_av
import json as _json_av
import time as _time_av
from collections import OrderedDict as _OrderedDict_av


class _DialogueLRU:
    def __init__(self, max_size=256, ttl_s=30 * 60):
        self._d: _OrderedDict = _OrderedDict_av()
        self._max = max_size
        self._ttl = ttl_s

    def get(self, key):
        item = self._d.get(key)
        if not item:
            return None
        t, v = item
        if _time_av.time() - t > self._ttl:
            self._d.pop(key, None)
            return None
        self._d.move_to_end(key)
        return v

    def set(self, key, v):
        self._d[key] = (_time_av.time(), v)
        self._d.move_to_end(key)
        while len(self._d) > self._max:
            self._d.popitem(last=False)


_dialogue_cache = _DialogueLRU()


class AvatarDialoguesRequest(BaseModel):
    style_id: str = Field(..., description="One of the STYLES ids (e.g. 'mythological').")
    idea: str = Field(..., min_length=3, max_length=280)
    language: Optional[str] = Field("english", description="english | hindi | hinglish")
    count: Optional[int] = Field(3, ge=1, le=5)


DIALOGUE_SYSTEM_PROMPT = """You are MagiCAi Studio's avatar scriptwriter.
Given an avatar's personality + a user idea, produce short punchy ONE-LINERS
that the avatar would say. These are spoken aloud by a cartoon/portrait
avatar, so they MUST:
 • Be 8–15 words per line (spoken in ~2.5–4 seconds).
 • Be first-person, natural, creator-grade (NOT clickbait, NOT hashtag spam).
 • Match the avatar's personality, tone, and cultural setting precisely.
 • Avoid copyrighted names, songs, movies, or celebrity impersonations.

Output STRICT JSON (no prose, no code fences). Schema:
{
  "dialogues": [
    { "id": "d1", "text": "<one-liner>", "tone": "<one short descriptor>" },
    { "id": "d2", "text": "...", "tone": "..." },
    { "id": "d3", "text": "...", "tone": "..." }
  ]
}

Language rules:
 • english → write in English.
 • hindi   → write in Devanagari.
 • hinglish→ write Hindi words in Roman letters, mixed with English.
 • 'tone' field is ALWAYS in English (short label: warm, playful, bold, ...).

Make the 3 dialogues MEANINGFULLY different in angle (e.g. a warm opener,
a bold hook, a playful tease) so the user has a real choice."""


def _dialogue_fallback(style_id: str, idea: str, count: int, language: str) -> dict:
    """Deterministic fallback when the LLM is unreachable — keeps UX alive."""
    style = STYLES.get(style_id) or {}
    label = style.get("label", "Avatar")
    base = (idea or "your idea").strip()
    if (language or "").lower() == "hindi":
        items = [
            {"id": "d1", "text": f"{base} — ये कहानी आज मैं सुनाता हूँ।", "tone": "warm"},
            {"id": "d2", "text": f"रुकिए! {base} के बारे में एक राज़ है।",   "tone": "bold"},
            {"id": "d3", "text": f"चलो मिलकर {base} का जादू महसूस करते हैं।", "tone": "playful"},
        ]
    else:
        items = [
            {"id": "d1", "text": f"Today I want to share a story about {base}.", "tone": "warm"},
            {"id": "d2", "text": f"Wait — {base} is not what you think. Listen in.",        "tone": "bold"},
            {"id": "d3", "text": f"Ever wondered what {label} would say about {base}?",    "tone": "playful"},
        ]
    return {"dialogues": items[:count]}


@router.post("/dialogues")
async def post_avatar_dialogues(req: AvatarDialoguesRequest):
    """Generate 3 avatar-appropriate one-liners based on picked style + idea."""
    if req.style_id not in STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown style. Use: {', '.join(STYLES.keys())}")
    # Moderation — block abusive / unsafe ideas before any LLM spend.
    from core.moderation import moderate_text, raise_if_blocked
    raise_if_blocked(await moderate_text(req.idea, source="avatar.dialogues.idea"))

    style = STYLES[req.style_id]
    persona = STYLE_PERSONALITY.get(req.style_id, DEFAULT_PERSONALITY)
    lang = (req.language or "english").strip().lower()
    count = max(1, min(5, req.count or 3))

    cache_key = _hashlib_av.sha256(
        f"{req.style_id}|{req.idea.strip().lower()}|{lang}|{count}".encode()
    ).hexdigest()[:24]
    hit = _dialogue_cache.get(cache_key)
    if hit:
        return {**hit, "cached": True, "source": "cache"}

    api_key = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        log.warning("avatar/dialogues: no EMERGENT_LLM_KEY — using fallback")
        out = _dialogue_fallback(req.style_id, req.idea, count, lang)
        _dialogue_cache.set(cache_key, out)
        return {**out, "cached": False, "source": "fallback", "personality": persona}

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=api_key,
            session_id=f"avd_{cache_key}",
            system_message=DIALOGUE_SYSTEM_PROMPT,
        ).with_model("openai", "gpt-4o-mini")
        user_text = (
            f"Avatar: {style['label']} ({style.get('tagline', '')})\n"
            f"Personality tone: {persona.get('tone')}\n"
            f"Voice style: {persona.get('voice_style')}, mood: {persona.get('mood')}\n"
            f"User idea: {req.idea!r}\n"
            f"language: {lang}\n"
            f"count: {count}\n"
            f"Return the JSON now."
        )
        resp = await chat.send_message(UserMessage(text=user_text))
        text = (resp or "").strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:].lstrip()
            text = text.strip()
        try:
            data = _json_av.loads(text)
        except _json_av.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                data = _json_av.loads(text[start : end + 1])
            else:
                raise
        dlg = data.get("dialogues") or []
        if not isinstance(dlg, list) or not dlg:
            raise ValueError("missing dialogues[]")
        # Pad/trim to requested count, guarantee `id` on every item.
        while len(dlg) < count:
            dlg.append({**dlg[-1], "id": f"d{len(dlg)+1}"})
        dlg = dlg[:count]
        for i, d in enumerate(dlg):
            d.setdefault("id", f"d{i+1}")
            d.setdefault("tone", persona.get("tone", "neutral"))
            d["text"] = str(d.get("text", "")).strip()
        out = {"dialogues": dlg, "personality": persona, "style_id": req.style_id, "language": lang}
        _dialogue_cache.set(cache_key, out)
        return {**out, "cached": False, "source": "llm"}
    except Exception as e:
        log.exception("avatar/dialogues: LLM error — falling back: %s", e)
        out = _dialogue_fallback(req.style_id, req.idea, count, lang)
        out["personality"] = persona
        _dialogue_cache.set(cache_key, out)
        return {**out, "cached": False, "source": "fallback"}




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
