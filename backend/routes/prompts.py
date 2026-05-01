"""V2.0 ChatGPT-style Prompt Selection — POST /api/generate-prompts

Takes a free-form user idea and returns:
  1. `detected` context — auto-classified category / mood / suggested voice /
     evocative scene keywords (used for the feedback pill row in the UI).
  2. `prompts` — exactly 3 distinct, ready-to-shoot prompt options the user
     can preview & pick from. Each one is a full creative brief.

Pipeline integration:
    User idea  →  /api/generate-prompts  →  3 PromptOption cards
      →  user picks one  →  /api/creative-plan  (uses the picked title+hook+mood)
      →  Pixabay + Sarvam TTS + BGM  →  rendered MP4

LLM: GPT-4o-mini via emergentintegrations + EMERGENT_LLM_KEY.
Cache: In-memory LRU (512 keys, 30-min TTL) — idempotent for repeated
       typing/debouncing. Telemetry rows also written to
       `db.prompt_generations` for offline analysis.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from core.db import db

load_dotenv()
logger = logging.getLogger("prompts")
router = APIRouter(prefix="/api", tags=["prompts"])


# ────────────────────────────── Schemas ────────────────────────────────────

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
    # Extras kept so the frontend can show richer previews
    hashtags: List[str] = Field(default_factory=list)
    cta: Optional[str] = None


class GeneratePromptsResponse(BaseModel):
    detected: DetectedContext
    prompts: List[PromptOption]
    cached: bool = False
    tokens_used: int = 0
    source: str = "llm"  # llm | cache | fallback


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


def _cache_key(idea: str, language: str, aspect: str, category_hint: Optional[str]) -> str:
    raw = f"{idea.strip().lower()}|{(language or '').strip().lower()}|{aspect or ''}|{(category_hint or '').strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ────────────────────────────── System prompt ──────────────────────────────

SYSTEM_PROMPT = """You are MagiCAi Studio's senior creative producer.
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


# ────────────────────────────── Helpers ────────────────────────────────────

def _strip_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        # ```json\n{...}\n``` or ``` {...} ```
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
    # Ensure we always return exactly 3 cards. Pad by duplicating if the LLM
    # short-changed us; truncate if it over-produced.
    while len(prompts) < 3:
        prompts.append(dict(prompts[-1], id=f"p{len(prompts)+1}"))
    data["prompts"] = prompts[:3]
    # Normalise fields + fill sensible defaults
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


async def _call_llm(idea: str, language: str, aspect: str, category_hint: Optional[str]) -> tuple[dict, str, int]:
    """Returns (payload_dict, source, tokens_estimate)."""
    api_key = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("generate-prompts: no EMERGENT_LLM_KEY, using fallback")
        return _fallback(idea, language), "fallback", 0
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=api_key,
            session_id=f"gp_{hashlib.sha256(idea.encode()).hexdigest()[:16]}",
            system_message=SYSTEM_PROMPT,
        ).with_model("openai", "gpt-4o-mini")
        user_text = (
            f"User idea: {idea!r}\n"
            f"language: {language or 'english'}\n"
            f"aspect: {aspect or '9:16'}\n"
            f"category_hint: {category_hint or '(auto)'}\n"
            "Return the JSON now."
        )
        resp = await chat.send_message(UserMessage(text=user_text))
        data = _parse_json(resp)
        _validate_payload(data)
        # Cheap token estimate (4 chars/token avg) — only used for telemetry.
        tokens = max(1, (len(SYSTEM_PROMPT) + len(user_text) + len(resp)) // 4)
        return data, "llm", tokens
    except Exception as e:
        logger.exception("generate-prompts: LLM error: %s", e)
        return _fallback(idea, language), "fallback", 0


# ────────────────────────────── Route ──────────────────────────────────────

@router.post("/generate-prompts", response_model=GeneratePromptsResponse)
async def generate_prompts(body: GeneratePromptsRequest, request: Request) -> GeneratePromptsResponse:
    """V2.0 ChatGPT-style prompt generator.

    Takes a free-form user idea and returns 3 distinct ready-to-produce
    prompt options + auto-detected context. Cached (LRU 30-min) so
    repeated/debounced calls from the wizard UI are cheap.
    """
    idea = body.idea.strip()
    language = (body.language or "english").strip().lower()
    aspect = (body.aspect or "9:16").strip()
    category_hint = (body.category_hint or "").strip() or None

    key = _cache_key(idea, language, aspect, category_hint)

    # Cache hit (unless force_refresh)
    if not body.force_refresh:
        hit = _cache.get(key)
        if hit is not None:
            return GeneratePromptsResponse(
                **hit, cached=True, source="cache", tokens_used=0,
            )

    payload, source, tokens = await _call_llm(idea, language, aspect, category_hint)

    # Write telemetry (best-effort, never fail the request)
    try:
        await db.prompt_generations.insert_one(
            {
                "id": f"pg_{uuid.uuid4().hex[:12]}",
                "cache_key": key,
                "idea": idea,
                "language": language,
                "aspect": aspect,
                "category_hint": category_hint,
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

    return GeneratePromptsResponse(
        **response_dict,
        cached=False,
        tokens_used=tokens,
        source=source,
    )


@router.get("/generate-prompts/health")
async def health() -> Dict[str, Any]:
    """Lightweight sanity endpoint — confirms the module loaded cleanly."""
    return {
        "ok": True,
        "llm_key_configured": bool(
            os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("OPENAI_API_KEY")
        ),
        "cache_size": len(_cache._data),  # noqa: SLF001 — internal peek is fine here
    }


__all__ = [
    "router",
    "GeneratePromptsRequest",
    "GeneratePromptsResponse",
    "DetectedContext",
    "PromptOption",
]
