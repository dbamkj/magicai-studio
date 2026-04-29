"""Creative Plan Engine — POST /api/creative-plan

Generates a structured creative plan JSON from a free-form idea (or a marketplace
template id). The plan is the single source of truth that downstream stages use
to keep visuals + voice + BGM in sync:

  {
    "creative_plan_id": "cp_xxx",
    "hook":            "<one-sentence opener>",
    "script":          ["scene1 voiceover", "scene2 voiceover", ...],
    "scene_keywords":  ["krishna flute", "vrindavan garden", ...],
    "voice_style":     "devotional warm slow",
    "bgm_style":       "indian classical flute",
    "mood":            "spiritual"
  }

Pipeline integration:
  • Pixabay search uses `scene_keywords` (one query per scene).
  • TTS engine uses `voice_style` for emotional delivery.
  • BGM picker uses `bgm_style` to choose the closest local track.
  • Final reel duration matches the script length.

LLM: GPT-4o-mini via emergentintegrations + EMERGENT_LLM_KEY.
Cache: Mongo collection `creative_plans` keyed by `creative_plan_id`.
"""
from __future__ import annotations
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

from core.config import DB_NAME

load_dotenv()

log = logging.getLogger("creative_plan")
router = APIRouter(prefix="/api", tags=["creative-plan"])

MONGO_URL = os.environ["MONGO_URL"]
_client = AsyncIOMotorClient(MONGO_URL)
db = _client[DB_NAME]


# --------------------------- Schemas ---------------------------
class CreativePlanRequest(BaseModel):
    idea: Optional[str] = Field(None, min_length=3, max_length=600)
    template_id: Optional[str] = Field(None, max_length=80)
    language: Optional[str] = Field("english", max_length=24)  # english | hindi | hinglish | ...
    duration: Optional[int] = Field(30, ge=5, le=60)            # target reel length in seconds (multi-scene)
    scene_count: Optional[int] = Field(4, ge=2, le=6)           # 2-6 scenes for Multi-Scene Story Engine


class CreativePlan(BaseModel):
    creative_plan_id: str
    hook: str
    script: list[str]
    scene_keywords: list[str]
    voice_style: str
    bgm_style: str
    mood: str
    language: str = "english"
    duration: int = 10
    source: str = "llm"   # 'llm' | 'cache' | 'fallback'
    created_at: str = ""
    idea: Optional[str] = None
    template_id: Optional[str] = None


# --------------------------- LLM ---------------------------
SYSTEM_PROMPT = """You are MagiCAi Studio's senior creative director. Given a user idea,
output ONE creative plan as STRICT JSON (no prose, no markdown). The plan must align
visuals + narration + music so the reel feels cohesive.

JSON schema (all keys required):
{
  "hook":            "<one-sentence opener that earns the first 2s of attention>",
  "script":          ["<scene 1 voiceover, 1-2 short sentences>", "<scene 2>", ... up to scene_count entries],
  "scene_keywords":  ["<2-3 keyword search query for scene 1, vivid and concrete>", ...],
  "voice_style":     "<descriptive voice style — e.g. 'devotional warm slow', 'energetic confident', 'cinematic deep'>",
  "bgm_style":       "<background music style — e.g. 'indian classical flute', 'cinematic orchestral build', 'lofi chillhop'>",
  "mood":            "<one word — spiritual | emotional | energetic | nostalgic | romantic | inspiring | playful | dramatic>"
}

Rules:
 • EXACTLY scene_count items in script[] and scene_keywords[] (matched 1:1).
 • script entries must read aloud in ~2-3 seconds each so total ~= duration seconds.
 • script MUST match the requested language (english | hindi | hinglish).
   - For hindi: write in Devanagari script.
   - For hinglish: write Hindi words in Roman/English letters mixed with English words.
 • scene_keywords MUST ALWAYS BE IN ENGLISH (concrete English nouns/queries),
   regardless of the script language. They are sent to Pixabay stock-video search
   which only indexes English. NEVER write scene_keywords in Devanagari, Hindi,
   Tamil, or any non-Latin script.
 • Each scene_keywords entry MUST be a Pixabay-friendly search query
   (concrete English nouns: e.g. "krishna idol temple", "indian flute musician",
   "diya lamp prayer"). NO abstract feelings, NO Hindi words.
 • voice_style and bgm_style MUST also be in English (downstream code maps them
   to preset ids).
 • NO copyrighted song/movie/celebrity names.
 • Output ONLY valid JSON. NEVER wrap in code fences."""


def _hash_key(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.startswith("json"):
            t = t[4:].lstrip()
    return t.strip()


def _validate_plan(data: dict, scene_count: int) -> None:
    required = ["hook", "script", "scene_keywords", "voice_style", "bgm_style", "mood"]
    for k in required:
        if k not in data:
            raise ValueError(f"missing key: {k}")
    if not isinstance(data["script"], list) or not data["script"]:
        raise ValueError("script must be a non-empty list")
    if not isinstance(data["scene_keywords"], list) or not data["scene_keywords"]:
        raise ValueError("scene_keywords must be a non-empty list")
    # Pad / truncate to scene_count for safety
    while len(data["script"]) < scene_count:
        data["script"].append(data["script"][-1])
    while len(data["scene_keywords"]) < scene_count:
        data["scene_keywords"].append(data["scene_keywords"][-1])
    data["script"] = data["script"][:scene_count]
    data["scene_keywords"] = data["scene_keywords"][:scene_count]


def _fallback_plan(idea: str, scene_count: int, duration: int, language: str) -> dict:
    """Deterministic fallback when the LLM is unavailable."""
    base = (idea or "creative reel").strip()
    return {
        "hook": f"Watch till the end — {base}.",
        "script": [
            f"{base}. A story unfolds.",
            "Every moment matters.",
            "Tag someone who needs to see this.",
        ][:scene_count],
        "scene_keywords": [base, base + " emotion", base + " sunset"][:scene_count],
        "voice_style": "warm cinematic",
        "bgm_style": "cinematic orchestral",
        "mood": "inspiring",
    }


async def _generate_with_llm(idea: str, language: str, duration: int, scene_count: int) -> tuple[dict, str]:
    """Returns (plan_dict, source). source is 'llm' or 'fallback'."""
    api_key = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        log.warning("creative-plan: no EMERGENT_LLM_KEY — using fallback")
        return _fallback_plan(idea, scene_count, duration, language), "fallback"
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=api_key,
            session_id=f"cp_{_hash_key(idea, language, str(duration), str(scene_count))}",
            system_message=SYSTEM_PROMPT,
        ).with_model("openai", "gpt-4o-mini")
        user_text = (
            f"User idea: {idea!r}\n"
            f"language: {language}\n"
            f"duration_seconds: {duration}\n"
            f"scene_count: {scene_count}\n"
            f"Return the JSON now."
        )
        resp = await chat.send_message(UserMessage(text=user_text))
        text = _strip_fences(resp)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to recover by locating the first { ... } block
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                data = json.loads(text[start : end + 1])
            else:
                raise
        _validate_plan(data, scene_count)
        return data, "llm"
    except Exception as e:
        log.exception("creative-plan: LLM error: %s", e)
        return _fallback_plan(idea, scene_count, duration, language), "fallback"


# --------------------------- Routes ---------------------------
@router.post("/creative-plan")
async def post_creative_plan(req: CreativePlanRequest):
    """Generate (or return cached) Creative Plan JSON for the given idea/template."""
    if not req.idea and not req.template_id:
        raise HTTPException(status_code=400, detail="Provide either 'idea' or 'template_id'.")

    # Resolve template_id → idea if needed
    idea = (req.idea or "").strip()
    template_doc: Optional[dict] = None
    if req.template_id:
        template_doc = await db.marketplace_templates.find_one({"id": req.template_id})
        if not template_doc:
            raise HTTPException(status_code=404, detail="Template not found")
        # Build a richer idea string from the template fields
        idea = idea or " ".join([
            template_doc.get("title") or "",
            template_doc.get("wizard_idea") or "",
            template_doc.get("wizard_script") or "",
        ]).strip()

    if not idea:
        raise HTTPException(status_code=400, detail="Could not derive idea from inputs.")

    # Cache by content hash (24h TTL via $expireAt index would be nicer; for now just key)
    cache_key = _hash_key(idea, req.language or "english", str(req.duration or 10), str(req.scene_count or 3))
    cached = await db.creative_plans.find_one({"cache_key": cache_key})
    if cached:
        cached.pop("_id", None)
        cached["source"] = "cache"
        return cached

    plan_dict, source = await _generate_with_llm(
        idea=idea,
        language=req.language or "english",
        duration=req.duration or 10,
        scene_count=req.scene_count or 3,
    )

    plan_id = f"cp_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    plan: dict[str, Any] = {
        "creative_plan_id": plan_id,
        "cache_key": cache_key,
        "idea": idea,
        "template_id": req.template_id,
        "language": req.language or "english",
        "duration": req.duration or 10,
        "scene_count": req.scene_count or 3,
        "source": source,
        "created_at": now,
        **plan_dict,
    }
    try:
        await db.creative_plans.insert_one(dict(plan))
    except Exception as e:
        log.warning("creative-plan: cache insert failed: %s", e)

    plan.pop("_id", None)
    return plan


@router.get("/creative-plan/{plan_id}")
async def get_creative_plan(plan_id: str):
    p = await db.creative_plans.find_one({"creative_plan_id": plan_id})
    if not p:
        raise HTTPException(status_code=404, detail="Creative plan not found")
    p.pop("_id", None)
    return p
