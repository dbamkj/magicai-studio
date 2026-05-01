"""V2.0 ChatGPT-style Prompt Selection — POST /api/generate-prompts

Phase C+ / C++ — adds:
  • style_boost ('default' | 'emotional' | 'cinematic') — biases the LLM
    output to match the user's chosen vibe toggle.
  • Per-user rate limit (20 calls/hour) tracked in `db.prompt_generations`,
    returns HTTP 429 with reset_at + retry_after when exceeded.
  • POST /api/generate-prompts/preview-audio  — 2-second Sarvam TTS preview
    of a hook line. Used by the "Preview" button on each prompt card.

Pipeline integration:
    User idea  →  /api/generate-prompts  →  3 PromptOption cards
      →  user picks one  →  /api/creative-plan  (uses the picked title+hook+mood)
      →  Pixabay + Sarvam TTS + BGM  →  rendered MP4

LLM: GPT-4o-mini via emergentintegrations + EMERGENT_LLM_KEY.
Cache: In-memory LRU (512 keys, 30-min TTL) — idempotent for repeated
       typing/debouncing. Telemetry rows also written to
       `db.prompt_generations` for offline analysis + rate-limit accounting.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import subprocess
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core.db import db

load_dotenv()
logger = logging.getLogger("prompts")
router = APIRouter(prefix="/api", tags=["prompts"])


# ────────────────────────────── Config ─────────────────────────────────────

# Per-user rate limit window
RATE_LIMIT_WINDOW_S = 60 * 60       # 1 hour
RATE_LIMIT_MAX_CALLS = 20           # 20 calls/hour/user
RATE_LIMIT_FREE_TIER = 8            # tighter cap for free tier (upgrade nudge)

SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "").strip().strip('"').strip("'")
PREVIEW_AUDIO_DIR = Path("/app/backend/uploads/preview_audio")
PREVIEW_AUDIO_DIR.mkdir(parents=True, exist_ok=True)


# ────────────────────────────── Schemas ────────────────────────────────────

StyleBoost = Literal["default", "emotional", "cinematic"]


class GeneratePromptsRequest(BaseModel):
    idea: str = Field(..., min_length=3, max_length=400)
    language: Optional[str] = Field(
        default="english",
        description="english | hindi | hinglish | tamil | ...",
    )
    aspect: Optional[str] = Field(default="9:16", description="9:16 | 1:1 | 16:9")
    category_hint: Optional[str] = Field(default=None, max_length=60)
    force_refresh: Optional[bool] = Field(
        default=False,
        description="If true, skip cache and ask the LLM for fresh variants.",
    )
    style_boost: Optional[StyleBoost] = Field(
        default="default",
        description="Bias the prompt vibe — 'emotional' or 'cinematic'.",
    )


class DetectedContext(BaseModel):
    category: str
    mood: str
    suggested_voice: str
    scene_keywords: List[str]


class PromptOption(BaseModel):
    id: str
    title: str
    hook: str
    voice_type: str
    music_type: str
    duration: int
    mood: str
    style_tag: str
    hashtags: List[str] = Field(default_factory=list)
    cta: Optional[str] = None
    score: Optional[float] = None  # populated for "Recommended" badge


class GeneratePromptsResponse(BaseModel):
    detected: DetectedContext
    prompts: List[PromptOption]
    cached: bool = False
    tokens_used: int = 0
    source: str = "llm"             # llm | cache | fallback
    style_boost: str = "default"
    rate_limit: Dict[str, Any] = Field(
        default_factory=dict,
        description="{ used: n, limit: 20, reset_at: iso, remaining: n }",
    )


class PreviewAudioRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=200)
    voice_type: Optional[str] = Field(default="warm_storyteller_female")
    language: Optional[str] = Field(default="english")
    max_seconds: Optional[float] = Field(default=2.5, ge=0.5, le=4.0)


# ────────────────────────────── LRU cache ──────────────────────────────────

class _LRU:
    """Tiny OrderedDict LRU with TTL — avoids hammering GPT on debounced typing."""

    def __init__(self, *, max_size: int = 512, ttl_s: int = 30 * 60) -> None:
        self._data: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()
        self._max = max_size
        self._ttl = ttl_s

    def get(self, key: str) -> Optional[Any]:
        item = self._data.get(key)
        if item is None:
            return None
        stored_at, value = item
        if time.time() - stored_at > self._ttl:
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        self._data[key] = (time.time(), value)
        self._data.move_to_end(key)
        while len(self._data) > self._max:
            self._data.popitem(last=False)


_cache = _LRU(max_size=512, ttl_s=30 * 60)
_audio_cache = _LRU(max_size=256, ttl_s=24 * 60 * 60)  # audio cache 24h


def _cache_key(idea: str, language: str, aspect: str, category_hint: Optional[str], style_boost: str) -> str:
    raw = (
        f"{idea.strip().lower()}|{(language or '').strip().lower()}"
        f"|{aspect or ''}|{(category_hint or '').strip().lower()}|{style_boost or 'default'}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ────────────────────────────── User resolution ────────────────────────────

async def _resolve_user(request: Request) -> dict:
    """Best-effort current-user resolve. Falls back to anonymous user keyed by IP.

    Returns a dict like { user_id, tier, anonymous: bool }. Never raises.
    """
    try:
        from core.auth import decode_token
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            data = decode_token(token)
            if data and data.get("sub"):
                u = await db.users.find_one({"id": data["sub"]}, {"_id": 0, "password_hash": 0})
                if u:
                    return {
                        "user_id": u.get("id") or u.get("user_id") or data["sub"],
                        "tier": (u.get("subscription_tier") or "free").lower(),
                        "anonymous": False,
                    }
    except Exception:
        pass
    # Anonymous — bucket by IP so a single browser still gets fair-use limits
    ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "anon")
    )
    return {"user_id": f"anon:{ip}", "tier": "free", "anonymous": True}


# ────────────────────────────── Rate limit ─────────────────────────────────

async def _rate_limit_status(user_id: str, tier: str) -> Dict[str, Any]:
    """Returns { used, limit, remaining, reset_at, blocked, retry_after_s }."""
    cap = RATE_LIMIT_FREE_TIER if tier == "free" else RATE_LIMIT_MAX_CALLS
    window_start = datetime.now(timezone.utc) - timedelta(seconds=RATE_LIMIT_WINDOW_S)
    try:
        used = await db.prompt_generations.count_documents({
            "user_id": user_id,
            "created_at": {"$gte": window_start.isoformat()},
        })
    except Exception as e:
        logger.warning("rate_limit count failed: %s", e)
        used = 0
    remaining = max(0, cap - used)
    blocked = used >= cap
    # When blocked, resetAt = oldest in-window record + window
    reset_iso = (datetime.now(timezone.utc) + timedelta(seconds=RATE_LIMIT_WINDOW_S)).isoformat()
    retry_after = 0
    if blocked:
        try:
            oldest = await db.prompt_generations.find_one(
                {"user_id": user_id, "created_at": {"$gte": window_start.isoformat()}},
                sort=[("created_at", 1)],
            )
            if oldest:
                # reset = oldest.created_at + window
                created_at = oldest.get("created_at")
                if isinstance(created_at, str):
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                else:
                    dt = created_at
                reset_dt = dt + timedelta(seconds=RATE_LIMIT_WINDOW_S)
                reset_iso = reset_dt.isoformat()
                retry_after = max(1, int((reset_dt - datetime.now(timezone.utc)).total_seconds()))
        except Exception as e:
            logger.debug("rate_limit reset calc failed: %s", e)
    return {
        "used": used,
        "limit": cap,
        "remaining": remaining,
        "reset_at": reset_iso,
        "blocked": blocked,
        "retry_after_s": retry_after,
        "tier": tier,
    }


# ────────────────────────────── System prompt ──────────────────────────────

BASE_SYSTEM_PROMPT = """You are MagiCAi Studio's senior creative producer.
Given a user's raw idea, infer the context AND propose 3 distinct,
production-ready short-form video concepts.

Output STRICT JSON (no prose, no code fences). Schema:

{
  "detected": {
    "category":         "<one of: devotional | motivational | funny | festival | storytelling | romantic | educational | promotional | lifestyle>",
    "mood":             "<one lowercase word: spiritual | emotional | energetic | nostalgic | romantic | inspiring | playful | dramatic>",
    "suggested_voice":  "<short English descriptor e.g. 'warm_storyteller_male', 'energetic_confident_female'>",
    "scene_keywords":   ["<3 English Pixabay-friendly nouns>"]
  },
  "prompts": [
    {
      "id":         "p1",
      "title":      "<6-8 word hook-worthy title>",
      "hook":       "<one-sentence scroll-stopper for the first 2 seconds>",
      "voice_type": "<short voice descriptor, different across the 3 options>",
      "music_type": "<BGM style, short English descriptor>",
      "duration":   <integer 15 | 20 | 30>,
      "mood":       "<one word mood>",
      "style_tag":  "<one of: cinematic | handheld | aesthetic | documentary | meme>",
      "hashtags":   ["<#tag1>", "<#tag2>", "<#tag3>"],
      "cta":        "<short call-to-action phrase>"
    },
    { "id": "p2", ... },
    { "id": "p3", ... }
  ]
}

Rules:
 • EXACTLY 3 items in prompts[] (ids p1, p2, p3).
 • The 3 prompts MUST be meaningfully DIFFERENT — vary the angle, mood,
   duration, or style_tag across them so the user has a real choice.
 • detected.scene_keywords MUST be 3 concrete English nouns suitable for
   Pixabay search (e.g. "temple flute dawn", "rain window tea").
 • voice_type and music_type MUST be short English descriptors.
 • Titles must feel premium & creator-grade (no clickbait, no ALL-CAPS).
 • NO copyrighted song titles, movie names, or celebrity impersonations.
 • Language preference: if hindi/hinglish/tamil, write hook/title/cta in
   that language; keep all technical fields (scene_keywords, voice_type,
   music_type, style_tag, mood, category) in English.
 • Output ONLY valid JSON. NEVER wrap in code fences or add explanations."""

STYLE_BOOST_HINTS: Dict[str, str] = {
    "default": "",
    "emotional": (
        "\n\n*** STYLE BOOST: EMOTIONAL ***\n"
        "Bias all 3 prompts toward heartfelt, tear-jerking, intimate vibes.\n"
        " • At least 2 of the 3 prompts MUST have mood ∈ {emotional, nostalgic, romantic}.\n"
        " • Hooks should be vulnerable, first-person, soul-stirring.\n"
        " • Prefer music_type like 'emotional_piano', 'soft_strings', 'melodic_acoustic'.\n"
        " • style_tag preference: aesthetic, documentary."
    ),
    "cinematic": (
        "\n\n*** STYLE BOOST: CINEMATIC ***\n"
        "Bias all 3 prompts toward big-screen, dramatic, visually epic vibes.\n"
        " • At least 2 of the 3 prompts MUST have style_tag = 'cinematic' or 'documentary'.\n"
        " • Hooks should be bold, voice-of-god, trailer-grade.\n"
        " • Prefer music_type like 'cinematic_orchestral_build', 'epic_trailer', 'tense_strings'.\n"
        " • mood preference: dramatic, inspiring, energetic."
    ),
}


# ────────────────────────────── Helpers ────────────────────────────────────

def _strip_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1] if "```" in t[3:] else t[3:]
        if t.startswith("json"):
            t = t[4:].lstrip()
    return t.strip()


def _parse_json(text: str) -> dict:
    t = _strip_fences(text)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        start = t.find("{")
        end = t.rfind("}")
        if start >= 0 and end > start:
            return json.loads(t[start : end + 1])
        raise


def _validate_payload(data: dict) -> None:
    if "detected" not in data or "prompts" not in data:
        raise ValueError("missing 'detected' or 'prompts'")
    det = data["detected"]
    for k in ("category", "mood", "suggested_voice", "scene_keywords"):
        if k not in det:
            raise ValueError(f"detected.{k} missing")
    if not isinstance(det["scene_keywords"], list) or len(det["scene_keywords"]) < 1:
        raise ValueError("scene_keywords must be a non-empty list")
    prompts = data["prompts"]
    if not isinstance(prompts, list) or len(prompts) < 1:
        raise ValueError("prompts must be a non-empty list")
    while len(prompts) < 3:
        prompts.append(dict(prompts[-1], id=f"p{len(prompts)+1}"))
    data["prompts"] = prompts[:3]
    for i, p in enumerate(data["prompts"]):
        p.setdefault("id", f"p{i+1}")
        p.setdefault("hook", "")
        p.setdefault("title", "")
        p.setdefault("voice_type", "neutral")
        p.setdefault("music_type", "uplifting")
        p.setdefault("duration", 20)
        p.setdefault("mood", det.get("mood", "inspiring"))
        p.setdefault("style_tag", "cinematic")
        p.setdefault("hashtags", [])
        p.setdefault("cta", "")
        try:
            p["duration"] = int(p["duration"])
        except Exception:
            p["duration"] = 20


def _score_prompts(prompts: List[dict], style_boost: str, idea: str) -> None:
    """Mutates prompts with a `score` (0..1) so the UI can mark a 'Recommended' card.

    Heuristic — favours: matching style_boost, idea-keyword overlap in title/hook,
    a balanced (20-25s) duration, and richer content (CTA + hashtags filled).
    """
    idea_words = {w.lower() for w in idea.split() if len(w) >= 4}
    for p in prompts:
        s = 0.5
        st = (p.get("style_tag") or "").lower()
        m = (p.get("mood") or "").lower()
        if style_boost == "cinematic":
            if st in ("cinematic", "documentary"): s += 0.18
            if m in ("dramatic", "inspiring", "energetic"): s += 0.06
        elif style_boost == "emotional":
            if m in ("emotional", "nostalgic", "romantic"): s += 0.18
            if st in ("aesthetic", "documentary"): s += 0.06
        # idea overlap
        title_l = (p.get("title", "") + " " + p.get("hook", "")).lower()
        overlap = sum(1 for w in idea_words if w in title_l)
        s += min(0.12, overlap * 0.04)
        # duration preference (20-25s sweet spot)
        d = int(p.get("duration") or 20)
        if 18 <= d <= 25: s += 0.06
        # richer cards
        if p.get("cta"): s += 0.03
        if p.get("hashtags"): s += 0.03
        p["score"] = round(min(1.0, max(0.0, s)), 3)


def _fallback(idea: str, language: str) -> dict:
    """Deterministic fallback when the LLM is unreachable. Keeps UX alive."""
    base = (idea or "your idea").strip()
    return {
        "detected": {
            "category": "storytelling",
            "mood": "inspiring",
            "suggested_voice": "warm_storyteller_male",
            "scene_keywords": [base, "sunrise over landscape", "close up portrait"],
        },
        "prompts": [
            {
                "id": "p1",
                "title": f"A Cinematic Take on {base[:40]}",
                "hook": f"What if the story of {base} had never been told?",
                "voice_type": "warm_storyteller_male",
                "music_type": "cinematic_orchestral_build",
                "duration": 20,
                "mood": "inspiring",
                "style_tag": "cinematic",
                "hashtags": ["#storytime", "#cinematic", "#shortfilm"],
                "cta": "Follow for part 2",
            },
            {
                "id": "p2",
                "title": f"POV: You Discover {base[:40]}",
                "hook": f"Nobody told me {base} would change everything.",
                "voice_type": "conversational_female",
                "music_type": "aesthetic_lofi",
                "duration": 15,
                "mood": "nostalgic",
                "style_tag": "aesthetic",
                "hashtags": ["#pov", "#aesthetic", "#reels"],
                "cta": "Save this for later",
            },
            {
                "id": "p3",
                "title": f"The Truth Behind {base[:40]}",
                "hook": f"Everyone talks about {base}. Nobody explains WHY.",
                "voice_type": "energetic_confident",
                "music_type": "upbeat_electronic",
                "duration": 30,
                "mood": "energetic",
                "style_tag": "documentary",
                "hashtags": ["#explained", "#trending", "#learn"],
                "cta": "Share with someone who needs this",
            },
        ],
    }


async def _call_llm(
    idea: str, language: str, aspect: str, category_hint: Optional[str], style_boost: str,
) -> tuple[dict, str, int]:
    """Returns (payload_dict, source, tokens_estimate)."""
    api_key = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("generate-prompts: no EMERGENT_LLM_KEY, using fallback")
        return _fallback(idea, language), "fallback", 0
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        sys_prompt = BASE_SYSTEM_PROMPT + STYLE_BOOST_HINTS.get(style_boost, "")
        chat = LlmChat(
            api_key=api_key,
            session_id=f"gp_{hashlib.sha256((idea+style_boost).encode()).hexdigest()[:16]}",
            system_message=sys_prompt,
        ).with_model("openai", "gpt-4o-mini")
        user_text = (
            f"User idea: {idea!r}\n"
            f"language: {language or 'english'}\n"
            f"aspect: {aspect or '9:16'}\n"
            f"category_hint: {category_hint or '(auto)'}\n"
            f"style_boost: {style_boost or 'default'}\n"
            "Return the JSON now."
        )
        resp = await chat.send_message(UserMessage(text=user_text))
        data = _parse_json(resp)
        _validate_payload(data)
        tokens = max(1, (len(sys_prompt) + len(user_text) + len(resp)) // 4)
        return data, "llm", tokens
    except Exception as e:
        logger.exception("generate-prompts: LLM error: %s", e)
        return _fallback(idea, language), "fallback", 0


# ────────────────────────────── Voice mapping (TTS preview) ────────────────

# Map LLM voice_type descriptors → Sarvam speaker.
# Sarvam supports: anushka, manisha, vidya, arya (F), abhilash, karun, hitesh (M).
def _voice_to_sarvam(voice_type: str) -> tuple[str, str]:
    """Returns (speaker, target_language_code)."""
    v = (voice_type or "").lower()
    is_female = any(t in v for t in ("female", "anushka", "manisha", "vidya", "jenny", "aria"))
    is_male = any(t in v for t in ("male", "guy", "abhilash", "karun", "arvind"))
    if not is_female and not is_male:
        is_female = True   # default
    is_calm = any(t in v for t in ("warm", "calm", "storyteller", "gentle", "soft"))
    is_energetic = any(t in v for t in ("energetic", "confident", "bold", "punchy"))
    if is_female:
        if is_calm:      speaker = "manisha"
        elif is_energetic: speaker = "anushka"
        else:            speaker = "vidya"
    else:
        if is_calm:      speaker = "abhilash"
        elif is_energetic: speaker = "karun"
        else:            speaker = "hitesh"
    return speaker, "hi-IN"


async def _sarvam_tts(text: str, speaker: str, language: str = "hi-IN") -> Optional[bytes]:
    """Calls Sarvam bulbul-v2 for a short TTS clip. Returns raw mp3 bytes."""
    if not SARVAM_API_KEY:
        logger.warning("preview-audio: SARVAM_API_KEY missing")
        return None
    try:
        payload = {
            "inputs": [text[:200]],
            "target_language_code": language,
            "speaker": speaker,
            "pitch": 0,
            "pace": 1.0,
            "loudness": 1.1,
            "speech_sample_rate": 22050,
            "enable_preprocessing": True,
            "model": "bulbul:v2",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as c:
            r = await c.post(
                "https://api.sarvam.ai/text-to-speech",
                json=payload,
                headers={
                    "api-subscription-key": SARVAM_API_KEY,
                    "Content-Type": "application/json",
                },
            )
        if r.status_code != 200:
            logger.warning("preview-audio: Sarvam %s — %s", r.status_code, r.text[:200])
            return None
        data = r.json()
        audios = data.get("audios", [])
        if not audios:
            return None
        # WAV bytes (base64). We re-encode to mp3 via ffmpeg for smaller payloads.
        wav_bytes = base64.b64decode(audios[0])
        tmp_in = PREVIEW_AUDIO_DIR / f".tmp_{uuid.uuid4().hex}.wav"
        tmp_out = PREVIEW_AUDIO_DIR / f".tmp_{uuid.uuid4().hex}.mp3"
        try:
            tmp_in.write_bytes(wav_bytes)
            res = subprocess.run(
                ["/usr/bin/ffmpeg", "-y", "-i", str(tmp_in),
                 "-codec:a", "libmp3lame", "-b:a", "96k", str(tmp_out)],
                capture_output=True, timeout=15,
            )
            if res.returncode == 0 and tmp_out.exists() and tmp_out.stat().st_size > 200:
                return tmp_out.read_bytes()
        finally:
            try:
                if tmp_in.exists():  tmp_in.unlink()
                if tmp_out.exists(): tmp_out.unlink()
            except Exception:
                pass
        return wav_bytes  # fallback raw wav
    except Exception as e:
        logger.exception("preview-audio: sarvam error: %s", e)
        return None


# ────────────────────────────── Routes ─────────────────────────────────────

@router.post("/generate-prompts", response_model=GeneratePromptsResponse)
async def generate_prompts(body: GeneratePromptsRequest, request: Request) -> GeneratePromptsResponse:
    """V2.0 ChatGPT-style prompt generator with style_boost + per-user rate limit."""
    idea = body.idea.strip()
    language = (body.language or "english").strip().lower()
    aspect = (body.aspect or "9:16").strip()
    category_hint = (body.category_hint or "").strip() or None
    style_boost = (body.style_boost or "default").strip().lower()
    if style_boost not in ("default", "emotional", "cinematic"):
        style_boost = "default"

    # Resolve user + check rate limit
    user = await _resolve_user(request)
    rl = await _rate_limit_status(user["user_id"], user["tier"])
    if rl["blocked"]:
        # 429 with a structured detail payload the FE can render as a chat bubble.
        raise HTTPException(
            status_code=429,
            detail={
                "code": "rate_limited",
                "message": (
                    f"You've used {rl['used']}/{rl['limit']} idea generations this hour. "
                    f"They reset shortly — or upgrade for unlimited."
                ),
                "rate_limit": rl,
                "tier": user["tier"],
                "anonymous": user["anonymous"],
            },
        )

    key = _cache_key(idea, language, aspect, category_hint, style_boost)

    # Cache hit (unless force_refresh)
    if not body.force_refresh:
        hit = _cache.get(key)
        if hit is not None:
            return GeneratePromptsResponse(
                **hit, cached=True, source="cache", tokens_used=0,
                style_boost=style_boost, rate_limit=rl,
            )

    payload, source, tokens = await _call_llm(idea, language, aspect, category_hint, style_boost)
    _score_prompts(payload["prompts"], style_boost, idea)

    # Telemetry write — also powers the rate-limit window count.
    try:
        await db.prompt_generations.insert_one(
            {
                "id": f"pg_{uuid.uuid4().hex[:12]}",
                "cache_key": key,
                "user_id": user["user_id"],
                "tier": user["tier"],
                "anonymous": user["anonymous"],
                "idea": idea,
                "language": language,
                "aspect": aspect,
                "category_hint": category_hint,
                "style_boost": style_boost,
                "source": source,
                "tokens_est": tokens,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as e:
        logger.debug("generate-prompts: telemetry write skipped: %s", e)

    response_dict = {
        "detected": payload["detected"],
        "prompts": payload["prompts"],
    }
    _cache.set(key, response_dict)

    # Refresh remaining count after this insert
    rl_after = dict(rl)
    rl_after["used"] = rl["used"] + 1
    rl_after["remaining"] = max(0, rl["limit"] - rl_after["used"])

    return GeneratePromptsResponse(
        **response_dict,
        cached=False,
        tokens_used=tokens,
        source=source,
        style_boost=style_boost,
        rate_limit=rl_after,
    )


@router.post("/generate-prompts/preview-audio")
async def preview_audio(body: PreviewAudioRequest):
    """Generate a tiny TTS clip of a hook line for the Preview button.

    Caches the rendered mp3 by sha256(text+voice) so repeated previews are free.
    Returns audio/mpeg (or audio/wav as fallback) inline.
    """
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    voice_type = body.voice_type or "warm_storyteller_female"
    language = (body.language or "english").strip().lower()
    target_lang = "hi-IN" if language in ("hindi", "hinglish", "marathi") else "hi-IN"
    speaker, _ = _voice_to_sarvam(voice_type)
    cache_id = hashlib.sha256(f"{text}|{speaker}|{target_lang}".encode()).hexdigest()[:32]
    out_path = PREVIEW_AUDIO_DIR / f"{cache_id}.mp3"
    if not out_path.exists() or out_path.stat().st_size < 200:
        # Memcache shortcut
        cached = _audio_cache.get(cache_id)
        if cached and isinstance(cached, (bytes, bytearray)):
            out_path.write_bytes(cached)
        else:
            audio = await _sarvam_tts(text, speaker, target_lang)
            if not audio:
                raise HTTPException(status_code=503, detail={
                    "code": "tts_unavailable",
                    "message": "Voice preview is temporarily unavailable.",
                })
            out_path.write_bytes(audio)
            _audio_cache.set(cache_id, bytes(audio))
    media_type = "audio/mpeg" if out_path.suffix == ".mp3" else "audio/wav"
    return FileResponse(str(out_path), media_type=media_type, filename=out_path.name)


@router.get("/generate-prompts/health")
async def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "llm_key_configured": bool(
            os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("OPENAI_API_KEY")
        ),
        "sarvam_configured": bool(SARVAM_API_KEY),
        "cache_size": len(_cache._data),  # noqa: SLF001
        "rate_limit_window_s": RATE_LIMIT_WINDOW_S,
        "rate_limit_max": RATE_LIMIT_MAX_CALLS,
    }


@router.get("/generate-prompts/usage")
async def usage(request: Request) -> Dict[str, Any]:
    """Lightweight endpoint the frontend polls to display 'X / 20 left this hour'."""
    user = await _resolve_user(request)
    rl = await _rate_limit_status(user["user_id"], user["tier"])
    return {"user_id": user["user_id"], "tier": user["tier"], "anonymous": user["anonymous"], **rl}


__all__ = [
    "router",
    "GeneratePromptsRequest",
    "GeneratePromptsResponse",
    "DetectedContext",
    "PromptOption",
]
