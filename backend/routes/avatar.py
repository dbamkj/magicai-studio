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
import re
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
        "voice_id": "hi-IN-PrabhatNeural", "voice_style": "story",
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
        "voice_id": "hi-IN-AaravNeural", "voice_style": "motivation",
        "mood": "dramatic", "bgm_style": "bollywood retro brass",
        "tone": "theatrical, bold, vintage-drama",
    },
    "cricket_champion": {
        "voice_id": "hi-IN-KunalNeural", "voice_style": "motivation",
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
    emotion: Optional[str] = Field("happy", description="One of EMOTIONS keys (happy/excited/playful/...).")
    # Session 25 — Cartoon Avatar mode toggle on the dialogue step.
    # 'solo'  → single-speaker 4-line monologue (no A/B prefixes)
    # 'dual'  → two-speaker 4-5 line A:/B: scene (legacy default)
    mode: Optional[str] = Field("dual", description="solo | dual — controls one-speaker vs two-speaker dialogues.")
    # Session 25 round 4 — let the "Regenerate options" button actually
    # produce DIFFERENT dialogues each click. Frontend sends a fresh
    # nonce per regenerate; backend mixes it into the cache key so the
    # cache miss → LLM re-runs.
    nonce: Optional[str] = Field(None, description="Optional cache-busting token; pass a fresh value to force a new LLM call.")


DIALOGUE_SYSTEM_PROMPT = """You are MagiCAi Studio's avatar scriptwriter.
Given an avatar's personality + a user idea + an emotion cue, produce
short SCENES that the avatar(s) would perform on screen. Each scene is
EXACTLY ONE option the user can pick.

Each scene MUST contain 4–5 lines of dialogue formatted as a TWO-PERSON
conversation between two characters (A and B), so the user gets a real
performable mini-skit. Add expressive cues:
 • [pause:1.0] markers between sentences for natural breathing rhythm
 • Stage actions in *asterisks* (e.g. *smiles warmly*, *raises eyebrow*)
 • The emotion cue must come through clearly in tone choices

Hard rules:
 • Each line is one speaker only, prefixed with "A:" or "B:"
 • Each LINE is 6–14 words spoken (excluding pause/action markers)
 • Total scene = 4–5 lines, ~25–45 spoken seconds
 • Match avatar personality, tone, and cultural setting precisely
 • Avoid copyrighted names, songs, movies, or celebrity impersonations
 • The first line MUST hook the viewer in the first 3 seconds

Output STRICT JSON (no prose, no code fences). Schema:
{
  "dialogues": [
    {
      "id": "d1",
      "tone": "<one short label>",
      "title": "<3-5 word vibe e.g. 'Festival Reunion'>",
      "text": "A: *smiles warmly* Bhai, kahan gum ho gaye the?\\n[pause:1.0]\\nB: Yaar, kaam ki bheed mein khud ko bhool gaya.\\n[pause:0.8]\\nA: *hands over a sweet box* Diwali aaya, ab to mil hi lo!\\n[pause:1.0]\\nB: *eyes glisten* Yeh roshni — sirf diye ki nahi, dosti ki bhi hai."
    },
    { "id": "d2", "tone": "...", "title": "...", "text": "A: ...\\nB: ..." },
    { "id": "d3", "tone": "...", "title": "...", "text": "A: ...\\nB: ..." }
  ]
}

Language rules:
 • english  → write everything in English (incl. action cues).
 • hindi    → dialogue lines in Devanagari; action cues in English asterisks.
 • hinglish → write Hindi words in Roman letters mixed with English; action
              cues in English asterisks.
 • The 'tone' and 'title' fields are ALWAYS in English.

Make the 3 scenes MEANINGFULLY different in angle (e.g. heartfelt
reunion / playful rivalry / dramatic reveal) so the user has a real
choice."""


def _dialogue_fallback(style_id: str, idea: str, count: int, language: str, emotion: str = "happy") -> dict:
    """Deterministic fallback when the LLM is unreachable — keeps UX alive.
    Two-person mini-skits with pause + action cues; matches the new schema."""
    style = STYLES.get(style_id) or {}
    label = style.get("label", "Avatar")
    base = (idea or "your idea").strip()
    if (language or "").lower() == "hindi":
        items = [
            {"id": "d1", "tone": "warm", "title": "गर्मजोशी से मुलाक़ात",
             "text": (f"A: *मुस्कुराते हुए* अरे, {base} — ये बात आज याद आ गई।\n[pause:1.0]\n"
                      f"B: सच कहूँ तो दिल में बस यही चल रहा था।\n[pause:0.8]\n"
                      f"A: *हाथ बढ़ाते हुए* तो चलो, इस पल को साथ जीते हैं।\n[pause:1.0]\n"
                      f"B: *आँखें भर आईं* दोस्ती की रोशनी सबसे चमकदार होती है।")},
            {"id": "d2", "tone": "bold", "title": "नाटकीय खुलासा",
             "text": (f"A: *भौं उठाते हुए* रुको — {base} वैसा नहीं जैसा तुम सोचते हो।\n[pause:1.0]\n"
                      f"B: मतलब? पूरी बात बताओ।\n[pause:0.8]\n"
                      f"A: *धीमी आवाज़ में* एक राज़ है, जो हर किसी को नहीं पता।\n[pause:1.0]\n"
                      f"B: *चौंकते हुए* तो आज ही सुना दो, अब और इंतज़ार नहीं!")},
            {"id": "d3", "tone": "playful", "title": "मज़ाकिया झड़प",
             "text": (f"A: *हँसते हुए* {base} पर तुम्हें मेरी राय चाहिए?\n[pause:1.0]\n"
                      f"B: हाँ, पर सच्ची वाली, मीठी नहीं।\n[pause:0.8]\n"
                      f"A: *आँख मारते हुए* ठीक है, तैयार रहो।\n[pause:1.0]\n"
                      f"B: *हँसकर* चलो, सुनते हैं तुम्हारा फ़लसफ़ा।")},
        ]
    else:
        items = [
            {"id": "d1", "tone": "warm", "title": "Heartfelt Reunion",
             "text": (f"A: *smiles warmly* Hey — {base} just hit me hard.\n[pause:1.0]\n"
                      f"B: Honestly, I was thinking the same thing today.\n[pause:0.8]\n"
                      f"A: *reaches out a hand* Then let's live this moment together.\n[pause:1.0]\n"
                      f"B: *eyes glisten* Friendship makes the brightest light.")},
            {"id": "d2", "tone": "bold", "title": "Dramatic Reveal",
             "text": (f"A: *raises eyebrow* Wait — {base} isn't what you think.\n[pause:1.0]\n"
                      f"B: Hold on, what do you mean by that?\n[pause:0.8]\n"
                      f"A: *lowers voice* There's a secret nobody saw coming.\n[pause:1.0]\n"
                      f"B: *startled* Then tell me right now — no more waiting!")},
            {"id": "d3", "tone": "playful", "title": f"{label} Banter",
             "text": (f"A: *grins* You really want my take on {base}?\n[pause:1.0]\n"
                      f"B: Yes — but the real version, not sugar-coated.\n[pause:0.8]\n"
                      f"A: *winks* Alright, brace yourself for the truth.\n[pause:1.0]\n"
                      f"B: *laughs* Go on then, sage of the streets.")},
        ]
    return {"dialogues": items[:count]}


# =====================================================================
#  AI AVATAR STUDIO — POST /api/avatar/suggestions
# =====================================================================
# Dynamic "quick start" idea chips for Step 2 of the wizard. Each tuple of
# (style, emotion, language) gets 4 creator-grade one-phrase prompts that
# the user can tap to fill the idea textarea. GPT-4o-mini, 30-min LRU.


class AvatarSuggestionsRequest(BaseModel):
    style_id: str
    emotion: Optional[str] = "happy"
    language: Optional[str] = "english"


SUGGESTIONS_SYSTEM_PROMPT = """You are MagiCAi Studio's idea-starter generator.
Given an avatar's style + emotion cue + output language, produce exactly
4 short CREATIVE IDEA PROMPTS a user could tap to fill a "what should your
avatar say" textarea. Rules:
 • Each idea is 3-7 words.
 • First-person framing from the USER's point of view ("Greet my viewers
   on Diwali", "Tell a funny Monday story") — NOT scene descriptions.
 • Must match the avatar's cultural/personality vibe (e.g. an Indian
   spiritual avatar → devotional themes; an influencer → growth/hacks).
 • Emotion cue should subtly colour every idea.
 • Avoid hashtags, emojis, quotation marks, copyrighted references.
 • Each idea unique — different angles (festival / funny / educational /
   personal).

Language rule:
 • english → write in English.
 • hindi   → write in Devanagari.
 • hinglish→ write Hindi in Roman, mixed with English.

Output STRICT JSON only:
{ "suggestions": ["...", "...", "...", "..."] }"""


def _suggestions_fallback(style_id: str, emotion: str, language: str) -> list[str]:
    style = STYLES.get(style_id, {})
    label = style.get("label", "Avatar")
    if (language or "").lower() == "hindi":
        return [
            f"{label} पर दीवाली शुभकामना",
            f"एक दिल छूने वाली बात",
            f"सुबह का प्रेरणादायक विचार",
            f"मज़ेदार रोज़ाना पल",
        ]
    return [
        f"Greet my viewers on Diwali",
        f"Share a heartfelt moment today",
        f"A motivational morning thought",
        f"My funniest everyday story",
    ]


@router.post("/suggestions")
async def post_avatar_suggestions(req: AvatarSuggestionsRequest):
    """Dynamic 4-idea starter chips based on (style, emotion, language)."""
    if req.style_id not in STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown style. Use: {', '.join(STYLES.keys())}")
    style = STYLES[req.style_id]
    persona = STYLE_PERSONALITY.get(req.style_id, DEFAULT_PERSONALITY)
    lang = (req.language or "english").strip().lower()
    emotion = (req.emotion or "happy").strip().lower()

    cache_key = _hashlib_av.sha256(f"sug|{req.style_id}|{emotion}|{lang}".encode()).hexdigest()[:20]
    hit = _dialogue_cache.get(cache_key)
    if hit:
        return {**hit, "cached": True, "source": "cache"}

    api_key = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        out = {"suggestions": _suggestions_fallback(req.style_id, emotion, lang), "style_id": req.style_id, "emotion": emotion, "language": lang}
        _dialogue_cache.set(cache_key, out)
        return {**out, "cached": False, "source": "fallback"}

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=api_key,
            session_id=f"sug_{cache_key}",
            system_message=SUGGESTIONS_SYSTEM_PROMPT,
        ).with_model("openai", "gpt-4o-mini")
        user_text = (
            f"Avatar: {style['label']} — {style.get('tagline', '')}\n"
            f"Personality: {persona.get('tone')}, mood: {persona.get('mood')}\n"
            f"Emotion cue: {emotion}\n"
            f"Language: {lang}\n"
            f"Return JSON now."
        )
        resp = await chat.send_message(UserMessage(text=user_text))
        text = (resp or "").strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:].lstrip()
            text = text.strip()
        start = text.find("{")
        end = text.rfind("}")
        data = _json_av.loads(text[start:end + 1] if start >= 0 and end > start else text)
        sug = data.get("suggestions") or []
        if not isinstance(sug, list) or not sug:
            raise ValueError("empty suggestions[]")
        sug = [str(x).strip().strip('"').strip("'") for x in sug][:4]
        while len(sug) < 4:
            sug.extend(_suggestions_fallback(req.style_id, emotion, lang))
        sug = sug[:4]
        out = {"suggestions": sug, "style_id": req.style_id, "emotion": emotion, "language": lang}
        _dialogue_cache.set(cache_key, out)
        return {**out, "cached": False, "source": "llm"}
    except Exception as e:
        log.exception("avatar/suggestions: LLM error — %s", e)
        out = {"suggestions": _suggestions_fallback(req.style_id, emotion, lang), "style_id": req.style_id, "emotion": emotion, "language": lang}
        _dialogue_cache.set(cache_key, out)
        return {**out, "cached": False, "source": "fallback"}




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
    emotion = (req.emotion or "happy").strip().lower()
    if emotion not in EMOTIONS:
        emotion = "happy"
    dlg_mode = (req.mode or "dual").strip().lower()
    if dlg_mode not in ("solo", "dual"):
        dlg_mode = "dual"

    cache_key = _hashlib_av.sha256(
        f"{req.style_id}|{req.idea.strip().lower()}|{lang}|{count}|{emotion}|{dlg_mode}|{req.nonce or ''}".encode()
    ).hexdigest()[:24]
    hit = _dialogue_cache.get(cache_key)
    if hit:
        return {**hit, "cached": True, "source": "cache"}

    api_key = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        log.warning("avatar/dialogues: no EMERGENT_LLM_KEY — using fallback")
        out = _dialogue_fallback(req.style_id, req.idea, count, lang, emotion)
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
            f"Emotion cue: {emotion}\n"
            f"User idea: {req.idea!r}\n"
            f"language: {lang}\n"
            f"count: {count}\n"
            f"mode: {dlg_mode}\n"
            + (
                "Return the JSON now. Each dialogue MUST be a SINGLE-SPEAKER "
                "4-line monologue (NO 'A:' / 'B:' prefixes). Each line is one "
                "punchy sentence. Add [pause:X.X] markers between lines and "
                "*action cues* in asterisks where natural."
                if dlg_mode == "solo" else
                "Return the JSON now. Each dialogue MUST be a 4–5 line two-person scene "
                "with [pause:X.X] markers between sentences and *action cues* in asterisks. "
                "Lines MUST alternate between 'A:' and 'B:'."
            )
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
            # GPT-4o-mini occasionally emits literal newlines INSIDE the
            # multi-line dialogue strings (instead of \\n). That breaks
            # strict JSON. Fix: walk the string and escape any newline
            # that occurs while we're inside a JSON string literal.
            try:
                fixed_chars = []
                in_str = False
                escape = False
                src = text[text.find("{") : text.rfind("}") + 1] or text
                for ch in src:
                    if escape:
                        fixed_chars.append(ch); escape = False; continue
                    if ch == "\\":
                        fixed_chars.append(ch); escape = True; continue
                    if ch == '"':
                        fixed_chars.append(ch); in_str = not in_str; continue
                    if in_str and ch == "\n":
                        fixed_chars.append("\\n"); continue
                    if in_str and ch == "\r":
                        continue
                    fixed_chars.append(ch)
                data = _json_av.loads("".join(fixed_chars))
            except Exception:
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
        out = {"dialogues": dlg, "personality": persona, "style_id": req.style_id, "language": lang, "emotion": emotion}
        _dialogue_cache.set(cache_key, out)
        return {**out, "cached": False, "source": "llm"}
    except Exception as e:
        log.exception("avatar/dialogues: LLM error — falling back: %s", e)
        out = _dialogue_fallback(req.style_id, req.idea, count, lang, emotion)
        out["personality"] = persona
        out["emotion"] = emotion
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
#  AI AVATAR STUDIO — Phase 2a/2b: Dual-speaker endpoints
# =====================================================================
#  (1) POST /api/avatar/infer-genders
#        Fast GPT-4o-mini call that reads an A:/B: two-person script and
#        returns the inferred gender per speaker (male/female/neutral).
#  (2) POST /api/avatar/generate-character
#        Fabricates a fictional A or B character portrait in the chosen
#        cartoon style + gender via Gemini Nano Banana. Returns a
#        job_id compatible with the existing /avatar/jobs/{id} poll.
#  (3) POST /api/avatar/dual-lipsync
#        Full split-screen dual-speaker pipeline: parse A:/B:, synth TTS
#        per segment with voice A or voice B, concat with [pause] gaps,
#        hstack A+B images into a split-screen PNG, MH lipsync on the
#        combined frame. Returns project_id (compatible with /api/project/{id}).


class InferGendersRequest(BaseModel):
    dialogue_text: str = Field(..., min_length=4, max_length=4000)


@router.post("/infer-genders")
async def post_infer_genders(req: InferGendersRequest):
    """Cheap LLM call that guesses the gender of Person A and Person B
    from a two-person dialogue. Used by Avatar Studio dual mode (b3)."""
    cache_key = _hashlib_av.sha256(f"gen|{req.dialogue_text.strip()[:400]}".encode()).hexdigest()[:20]
    hit = _dialogue_cache.get(cache_key)
    if hit:
        return {**hit, "cached": True}

    api_key = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        out = {"A": "neutral", "B": "neutral", "confidence": 0.0, "source": "fallback"}
        _dialogue_cache.set(cache_key, out)
        return {**out, "cached": False}

    sys = ("You analyse a two-speaker dialogue (prefixed A: and B:) and infer "
           "each speaker's likely gender from linguistic cues (names, honorifics, "
           "verb inflections, relationship context). Output STRICT JSON only:\n"
           "{ \"A\": \"male|female|neutral\", \"B\": \"male|female|neutral\", \"confidence\": 0.0-1.0 }\n"
           "Use 'neutral' if you genuinely cannot tell — don't guess.")
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=api_key, session_id=f"gen_{cache_key}", system_message=sys).with_model("openai", "gpt-4o-mini")
        resp = await chat.send_message(UserMessage(text=req.dialogue_text[:3500]))
        text = (resp or "").strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:].lstrip()
            text = text.strip()
        s = text.find("{"); e = text.rfind("}")
        data = _json_av.loads(text[s:e + 1] if s >= 0 and e > s else text)
        out = {
            "A": str(data.get("A", "neutral")).lower() if data.get("A") in ("male", "female", "neutral") or str(data.get("A", "")).lower() in ("male", "female", "neutral") else "neutral",
            "B": str(data.get("B", "neutral")).lower() if data.get("B") in ("male", "female", "neutral") or str(data.get("B", "")).lower() in ("male", "female", "neutral") else "neutral",
            "confidence": float(data.get("confidence", 0.5) or 0.5),
            "source": "llm",
        }
        _dialogue_cache.set(cache_key, out)
        return {**out, "cached": False}
    except Exception as e:
        log.exception("avatar/infer-genders failed: %s", e)
        out = {"A": "neutral", "B": "neutral", "confidence": 0.0, "source": "fallback"}
        _dialogue_cache.set(cache_key, out)
        return {**out, "cached": False}


class GenerateCharacterRequest(BaseModel):
    style_id: str
    gender: str = Field("neutral", description="male | female | neutral")
    role: str = Field("A", description="A | B — used as a seed modifier")
    seed: Optional[int] = None


@router.post("/generate-character")
async def post_generate_character(req: GenerateCharacterRequest, background: BackgroundTasks, request: Request):
    """Generate a fictional cartoon character portrait matching the picked
    style + gender. Returns a job_id that polls on /avatar/jobs/{id} (same
    shape as /avatar/cartoonize results)."""
    if req.style_id not in STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown style. Use: {', '.join(STYLES.keys())}")
    style = STYLES[req.style_id]
    user = await _resolve_user(request)
    user_tier = (user.get("subscription_tier") or "free").lower()
    is_paid = user_tier in ("starter", "creator", "pro")

    gender = (req.gender or "neutral").lower()
    if gender not in ("male", "female", "neutral"):
        gender = "neutral"
    gender_txt = {
        "male": "a male character",
        "female": "a female character",
        "neutral": "a character",
    }[gender]

    # Build a prompt tailored to style + gender + role — keeps A and B
    # visually distinct even when gender is the same.
    role_seed = "warm welcoming eyes" if req.role == "A" else "bold confident expression"
    prompt = (
        f"{style['tagline']} Create {gender_txt} with {role_seed}, "
        f"friendly and expressive, front-facing portrait, upper body, clean background, "
        f"consistent with the {style['label']} cartoon style."
    )

    job_id = f"av_{uuid.uuid4().hex[:12]}"
    await db.avatar_jobs.insert_one({
        "id": job_id,
        "user_id": user.get("id"),
        "user_tier": user_tier,
        "style": req.style_id,
        "emotion": "happy",
        "status": "queued",
        "created_at": datetime.now(timezone.utc),
        "watermarked": not is_paid,
        "kind": "character",  # marker for analytics
    })

    background.add_task(
        _process_avatar_job,
        job_id=job_id,
        style=req.style_id,
        emotion="happy",
        prompt=prompt,
        image_b64=None,
        image_url=None,
        watermark=not is_paid,
    )
    return {"job_id": job_id, "status": "queued", "style": req.style_id, "gender": gender, "role": req.role}


class DualLipsyncRequest(BaseModel):
    image_a_path: str = Field(..., description="Uploads path for Person A image.")
    image_b_path: str = Field(..., description="Uploads path for Person B image.")
    script: str = Field(..., min_length=6, description="Multi-line script with A:/B: prefixes and optional [pause:X] markers.")
    voice_a_id: str = "en-US-JennyNeural"
    voice_b_id: str = "en-US-GuyNeural"
    voice_a_style: Optional[str] = None
    voice_b_style: Optional[str] = None
    motion: Optional[str] = "ken_burns"
    aspect_ratio: Optional[str] = "16:9"   # hstack composites are wider
    resolution: Optional[str] = "720p"
    style_hint: Optional[str] = None


@router.post("/dual-lipsync")
async def post_dual_lipsync(req: DualLipsyncRequest, background: BackgroundTasks, request: Request):
    """Phase 2a — split-screen two-person avatar lipsync. V1: single MH
    lipsync pass over a hstacked image + combined audio (A/B voices
    interleaved). V2 (next session) will do dual independent lipsync."""
    # Lazy-import heavy helpers from server.py (same pattern as routes/talking.py)
    from server import (
        MAGIC_HOUR_API_KEY, MagicHourClient, UPLOAD_DIR,
        _link_as_version, _resolve_upload_path,
        apply_resolution_to_project, generate_tts_audio,
        upload_to_magic_hour, mh_create_lipsync_with_retry, mh_poll_video,
    )
    from core.billing import preflight_and_reserve, settle_credits
    from core.models import VideoProject

    img_a = _resolve_upload_path(req.image_a_path)
    img_b = _resolve_upload_path(req.image_b_path)
    if not img_a.exists():
        raise HTTPException(status_code=400, detail=f"Image A not found: {req.image_a_path}")
    if not img_b.exists():
        raise HTTPException(status_code=400, detail=f"Image B not found: {req.image_b_path}")
    if not (req.script or "").strip():
        raise HTTPException(status_code=400, detail="Script is required")

    user, cost = await preflight_and_reserve(request, job_type='lipsync', feature='lip_sync_dual')

    p = VideoProject(
        name=f"DualAvatar_{datetime.now(timezone.utc).strftime('%H%M%S')}",
        type="dual_talking_avatar",
        user_id=user["user_id"],
        input_payload=req.dict(),
        endpoint="/api/avatar/dual-lipsync",
    )
    await db.video_projects.insert_one(p.dict())

    async def _bg():
        import subprocess
        try:
            await db.video_projects.update_one({"id": p.id}, {"$set": {"status": "processing", "progress": 8}})

            # 1) Parse script into (speaker, text, pause_after_s) segments.
            segments: list[tuple[str, str, float]] = []
            pending_pause = 0.0
            for raw in (req.script or "").splitlines():
                line = raw.strip()
                if not line: continue
                m_pause = re.match(r"\[pause:([0-9.]+)\]", line, re.I)
                if m_pause:
                    pending_pause += float(m_pause.group(1))
                    continue
                m = re.match(r"^([AB])[:：]\s*(.+)$", line)
                if not m: continue
                speaker = m.group(1).upper()
                text = m.group(2).strip()
                # Strip *action* cues so TTS doesn't speak them.
                text = re.sub(r"\*[^*\n]+\*", "", text).strip()
                if not text: continue
                segments.append((speaker, text, pending_pause))
                pending_pause = 0.0
            if not segments:
                raise Exception("Could not parse any A:/B: lines from script")

            await db.video_projects.update_one({"id": p.id}, {"$set": {"progress": 18}})

            # 2) Generate TTS per segment with the right voice.
            seg_paths: list[Path] = []
            for i, (spk, txt, pre_pause) in enumerate(segments):
                vid    = req.voice_a_id if spk == "A" else req.voice_b_id
                vstyle = req.voice_a_style if spk == "A" else req.voice_b_style
                out_mp3 = UPLOAD_DIR / f"dual_{p.id[:8]}_{i}_{spk}.mp3"
                await generate_tts_audio(txt, vid, out_mp3, min_duration=1.2, voice_style=vstyle)
                if not out_mp3.exists() or out_mp3.stat().st_size < 300:
                    raise Exception(f"TTS failed for segment {i} ({spk})")
                # Pre-pend the pre-pause as silence if needed.
                if pre_pause > 0.05:
                    silence = UPLOAD_DIR / f"dual_{p.id[:8]}_{i}_pad.mp3"
                    subprocess.run([
                        "/usr/bin/ffmpeg", "-y", "-f", "lavfi", "-i",
                        f"anullsrc=r=44100:cl=stereo", "-t", str(pre_pause),
                        "-q:a", "9", str(silence),
                    ], capture_output=True, timeout=20)
                    if silence.exists(): seg_paths.append(silence)
                seg_paths.append(out_mp3)

            # 3) Concatenate all TTS segments into one combined audio file.
            await db.video_projects.update_one({"id": p.id}, {"$set": {"progress": 40}})
            combined = UPLOAD_DIR / f"dual_{p.id[:8]}_combined.mp3"
            list_txt = UPLOAD_DIR / f"dual_{p.id[:8]}_list.txt"
            with open(list_txt, "w") as lf:
                for sp in seg_paths:
                    lf.write(f"file '{sp.resolve()}'\n")
            subprocess.run([
                "/usr/bin/ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_txt), "-c", "copy", str(combined),
            ], capture_output=True, timeout=60)
            if not combined.exists() or combined.stat().st_size < 500:
                raise Exception("Audio concatenation failed")

            # Probe duration (need 2.5s min for MH).
            dur_r = subprocess.run([
                "/usr/bin/ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(combined),
            ], capture_output=True, timeout=15)
            audio_dur = float((dur_r.stdout.decode() or "3.0").strip() or "3.0")
            if audio_dur < 2.5:
                padded = UPLOAD_DIR / f"dual_{p.id[:8]}_padded.mp3"
                subprocess.run([
                    "/usr/bin/ffmpeg", "-y", "-i", str(combined),
                    "-af", "apad=pad_dur=2.5", "-t", "3.0", str(padded),
                ], capture_output=True, timeout=20)
                if padded.exists(): combined = padded; audio_dur = 3.0

            # 4) Build the split-screen A|B PNG and loop it for duration.
            await db.video_projects.update_one({"id": p.id}, {"$set": {"progress": 55}})
            split_img = UPLOAD_DIR / f"dual_{p.id[:8]}_split.png"
            # Each half = 540x960 portrait → side by side = 1080x960 (16:9 range).
            subprocess.run([
                "/usr/bin/ffmpeg", "-y",
                "-i", str(img_a), "-i", str(img_b),
                "-filter_complex",
                "[0:v]scale=540:960:force_original_aspect_ratio=increase,crop=540:960[a];"
                "[1:v]scale=540:960:force_original_aspect_ratio=increase,crop=540:960[b];"
                "[a][b]hstack=inputs=2",
                "-frames:v", "1", str(split_img),
            ], capture_output=True, timeout=40)
            if not split_img.exists():
                raise Exception("Split-screen image creation failed")

            still_v = UPLOAD_DIR / f"dual_{p.id[:8]}_still.mp4"
            subprocess.run([
                "/usr/bin/ffmpeg", "-y", "-loop", "1", "-i", str(split_img),
                "-c:v", "libx264", "-t", str(audio_dur + 1),
                "-pix_fmt", "yuv420p", "-r", "25",
                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                str(still_v),
            ], capture_output=True, timeout=90)
            if not still_v.exists():
                raise Exception("Still video creation failed")

            # 5) Submit to MH lipsync (single call on combined image + combined audio)
            await db.video_projects.update_one({"id": p.id}, {"$set": {"progress": 65}})
            mh = MagicHourClient(token=MAGIC_HOUR_API_KEY)
            mh_video = upload_to_magic_hour(mh, str(still_v), "video")
            mh_audio = upload_to_magic_hour(mh, str(combined), "audio")
            ls = await mh_create_lipsync_with_retry(
                mh,
                f"DualAvatar_{p.id[:8]}",
                {"video_source": "file", "video_file_path": mh_video, "audio_file_path": mh_audio},
                0.0, audio_dur,
            )
            ls_url = await mh_poll_video(
                mh, ls.id, max_wait=600,
                on_progress=lambda pr: db.video_projects.update_one(
                    {"id": p.id}, {"$set": {"progress": 65 + int(pr / 100 * 30)}}
                ),
            )
            if not ls_url:
                raise Exception("Dual lipsync timed out")

            # 6) Download result
            ls_local = UPLOAD_DIR / f"dual_{p.id[:8]}_ls.mp4"
            import httpx
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), follow_redirects=True) as c:
                resp = await c.get(ls_url)
                with open(ls_local, "wb") as f: f.write(resp.content)

            result_url = f"/api/serve-file/{ls_local.name}"
            await db.video_projects.update_one({"id": p.id}, {"$set": {
                "status": "completed", "progress": 100,
                "result_url": result_url,
                "completed_at": datetime.now(timezone.utc),
            }})

            # Async resolution downscale (don't block)
            try:
                import asyncio
                asyncio.create_task(apply_resolution_to_project(p.id, req.resolution or "720p", "video"))
            except Exception: pass

            # Best-effort cleanup of intermediate files
            for f_tmp in seg_paths + [list_txt, split_img, still_v, combined]:
                try:
                    if f_tmp and Path(f_tmp).exists(): Path(f_tmp).unlink()
                except Exception: pass

        except Exception as e:
            log.error("DualAvatar failed: %s", e)
            await db.video_projects.update_one(
                {"id": p.id},
                {"$set": {"status": "failed", "error": str(e)[:300]}},
            )

    background.add_task(_bg)
    await settle_credits(
        user.get('id'), cost,
        user_tier=user.get('subscription_tier'),
        project_id=p.id, asset_kind='video',
        background_tasks=background,
    )
    return {"project_id": p.id, "status": "processing", "credits_charged": cost}





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
