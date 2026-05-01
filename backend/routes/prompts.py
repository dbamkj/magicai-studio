"""Prompt generation module — V2.0 ChatGPT-style Prompt Selection.

Endpoint contract (to be implemented):

    POST /api/generate-prompts
    Body: { "idea": "Krishna bhajan", "language": "hindi", "aspect": "9:16" }
    Response: {
      "detected": {
        "category": "devotional",
        "mood": "sacred_warm",
        "suggested_voice": "warm_storyteller_male",
        "scene_keywords": ["flute player", "forest sunrise", ...]
      },
      "prompts": [
        {
          "id": "p1",
          "title": "Krishna's Flute — Whisper of Peace",
          "hook": "Even armies fell silent when Krishna played...",
          "voice_type": "warm_male",
          "music_type": "sacred_ambient_flute",
          "duration": 20,
          "mood": "devotional_awe",
          "style_tag": "cinematic"
        },
        { ... 2 more ... }
      ],
      "cached": false,
      "tokens_used": 420
    }

Pipeline integration:
    Selected prompt  →  Creative Plan Engine (core/creative_plan)
                      →  Pixabay scene search
                      →  Sarvam TTS
                      →  BGM pick
                      →  FFmpeg render

Caching & cost control:
    - In-memory LRU (max 512 keys, 30-min TTL) keyed on hash(idea+lang+aspect)
    - Frontend is expected to debounce the user's typing at 600ms

This module is the landing zone for the V2.0 feature. The stub below lets the
router wire cleanly into FastAPI today; the full implementation lands in the
next commit.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from core.db import db  # noqa: F401 — available for future usage/telemetry writes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["prompts"])


# ────────────────────────────── Request / Response models ──────────────────

class GeneratePromptsRequest(BaseModel):
    idea: str = Field(..., min_length=3, max_length=400)
    language: Optional[str] = Field(
        default="english",
        description="Preferred narration language (english/hindi/tamil/...).",
    )
    aspect: Optional[str] = Field(default="9:16", description="9:16 / 1:1 / 16:9")
    category_hint: Optional[str] = Field(default=None, description="Optional user-supplied category")


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


class GeneratePromptsResponse(BaseModel):
    detected: DetectedContext
    prompts: List[PromptOption]
    cached: bool = False
    tokens_used: int = 0


# ────────────────────────────── In-memory LRU cache ────────────────────────

class _LRU:
    """Tiny dict-based LRU with TTL. Keeps the hot path dependency-free."""

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


def _cache_key(idea: str, language: str, aspect: str) -> str:
    raw = f"{idea.strip().lower()}|{language.strip().lower()}|{aspect}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ────────────────────────────── Placeholder stub ───────────────────────────
# Full GPT-4o-mini implementation lands in the next commit (V2.0 Phase B).
# This stub keeps the contract honest: router is wired, schemas are in place,
# cache is ready. Callers today receive a `501` so no silent fallback noise.

@router.post("/generate-prompts", response_model=GeneratePromptsResponse)
async def generate_prompts(body: GeneratePromptsRequest, request: Request) -> GeneratePromptsResponse:
    """V2.0 ChatGPT-style prompt generator (stub).

    Not yet implemented — returns HTTP 501 until the GPT-4o-mini pipeline is
    wired up in the next commit. Present so the frontend can develop against a
    stable URL and payload contract.
    """
    raise HTTPException(
        status_code=501,
        detail={
            "error": "generate_prompts_not_implemented",
            "message": "ChatGPT-style prompt generator ships in V2.0 Phase B.",
            "contract_version": "1.0",
        },
    )


# Handy helpers kept module-local so the Phase-B implementation inherits them.
__all__ = [
    "router",
    "GeneratePromptsRequest",
    "GeneratePromptsResponse",
    "DetectedContext",
    "PromptOption",
    "_cache",
    "_cache_key",
]
