"""Cinematic preset registry for the AI Avatar Studio.

A "preset" is a one-tap bundle of creative knobs that turns a plain
talking-avatar generation into a cinematic, viral-ready video. Each
preset wires together:

  - emotion (used for dialogue tone + face overlay in Phase 2)
  - voice_style + voice_rate / voice_pitch (TTS expressiveness)
  - motion (ffmpeg motion effect — ken_burns, slow_zoom, dolly_in, ...)
  - camera (broader cinematography hint — Phase 3 will use this)
  - lighting + effects[] (post-process filters — Phase 3 will use this)
  - bgm (mood id consumed by core.bgm_catalog.random_for_mood)
  - plan_tier — "free" | "pro". Used for feature-gating: free users
    can pick free presets unlimited, pro presets show a 🔒 + paywall.

Phase-1 ship:
  - Backend exposes the catalog via GET /api/cinematic-presets (this
    module's `list_presets` returns a JSON-friendly list with `locked`
    annotated per-user).
  - POST /api/create-talking-avatar accepts optional `preset_id`.
    When set, server-side `apply_preset_to_request` overrides the
    request's voice_style / motion / bgm_style fields with the
    preset's values (request fields still win when explicitly sent).
  - Free presets always render with watermark; pro presets are locked
    for free users (returns 402 PAYMENT_REQUIRED).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# ──────────────────────────── Preset catalog ────────────────────────────
#
# Order matters — this is the order users see in the picker.
# Free presets first so free users find a working option fast.

PRESETS: List[Dict[str, Any]] = [
    {
        "id": "funny",
        "label": "Funny",
        "emoji": "😂",
        "tagline": "Quick zoom, meme energy",
        "plan_tier": "free",
        "config": {
            "emotion": "playful",
            "intensity": 0.9,
            "voice_style": "playful",
            "voice_rate": 0.05,
            "voice_pitch": "+0Hz",
            "motion": "ken_burns",
            "camera": "fast_zoom",
            "lighting": "bright",
            "effects": ["shake", "punch_in"],
            "bgm": "playful",
        },
    },
    {
        "id": "emotional",
        "label": "Emotional",
        "emoji": "💔",
        "tagline": "Heart-tugging slow drama",
        "plan_tier": "free",
        "config": {
            "emotion": "calm",
            "intensity": 0.75,
            "voice_style": "calm",
            "voice_rate": -0.1,
            "voice_pitch": "+0Hz",
            "motion": "ken_burns",
            "camera": "slow_pan",
            "lighting": "soft",
            "effects": ["vignette", "soft_blur"],
            "bgm": "ambient_calm",
        },
    },
    {
        "id": "bhakti",
        "label": "Bhakti",
        "emoji": "🪔",
        "tagline": "Calm devotional vibes",
        "plan_tier": "pro",
        "config": {
            "emotion": "calm",
            "intensity": 0.7,
            "voice_style": "calm",
            "voice_rate": -0.05,
            "voice_pitch": "+0Hz",
            "motion": "ken_burns",
            "camera": "slow_zoom",
            "lighting": "soft_glow",
            "effects": ["vignette", "soft_glow"],
            "bgm": "devotional",
        },
    },
    {
        "id": "motivation",
        "label": "Motivation",
        "emoji": "🔥",
        "tagline": "Forward lean, build energy",
        "plan_tier": "pro",
        "config": {
            "emotion": "confident",
            "intensity": 0.85,
            "voice_style": "confident",
            "voice_rate": 0.05,
            "voice_pitch": "+0Hz",
            "motion": "ken_burns",
            "camera": "dolly_in",
            "lighting": "punchy",
            "effects": ["vignette", "glow"],
            "bgm": "motivational",
        },
    },
    {
        "id": "influencer",
        "label": "Influencer",
        "emoji": "✨",
        "tagline": "Bright, sharp, social",
        "plan_tier": "pro",
        "config": {
            "emotion": "excited",
            "intensity": 0.85,
            "voice_style": "excited",
            "voice_rate": 0.05,
            "voice_pitch": "+0Hz",
            "motion": "ken_burns",
            "camera": "ken_burns",
            "lighting": "bright",
            "effects": ["glow", "bokeh"],
            "bgm": "playful",
        },
    },
    {
        "id": "cinematic",
        "label": "Cinematic",
        "emoji": "🎬",
        "tagline": "Epic, dramatic, theatrical",
        "plan_tier": "pro",
        "config": {
            "emotion": "confident",
            "intensity": 0.9,
            "voice_style": "confident",
            "voice_rate": -0.02,
            "voice_pitch": "+0Hz",
            "motion": "ken_burns",
            "camera": "dolly_in",
            "lighting": "moody",
            "effects": ["vignette", "depth_of_field"],
            "bgm": "cinematic_epic",
        },
    },
]


# Tiers that count as "paid" for unlocking pro presets.
PAID_TIERS = {"starter", "creator", "pro", "premium"}


def _is_paid(tier: Optional[str]) -> bool:
    return (tier or "free").lower() in PAID_TIERS


def list_presets(user_tier: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all presets with a `locked` flag computed for the user.

    Free users see free presets unlocked + pro presets locked.
    Paid users see everything unlocked.
    """
    paid = _is_paid(user_tier)
    out: List[Dict[str, Any]] = []
    for p in PRESETS:
        locked = (p["plan_tier"] == "pro") and not paid
        out.append({
            "id": p["id"],
            "label": p["label"],
            "emoji": p["emoji"],
            "tagline": p["tagline"],
            "plan_tier": p["plan_tier"],
            "locked": locked,
            # Hand the config to the client so the preset chip can drive
            # live preview tweaks (Phase 4 before/after toggle).
            "config": p["config"],
        })
    return out


def get_preset(preset_id: str) -> Optional[Dict[str, Any]]:
    """Look up a preset by id. Case-insensitive. Returns None if missing."""
    if not preset_id:
        return None
    needle = preset_id.strip().lower()
    for p in PRESETS:
        if p["id"] == needle:
            return p
    return None


def apply_preset_to_request(
    preset_id: Optional[str],
    user_tier: Optional[str],
    voice_style: Optional[str] = None,
    motion: Optional[str] = None,
    bgm_style: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve a preset and merge its config with explicit request fields.

    Explicit fields the client sent (non-empty) WIN over preset defaults
    so power users can mix-and-match. Returns a dict with the resolved
    `voice_style`, `motion`, `bgm_style`, `emotion`, `intensity`,
    `effects`, `camera`, `lighting`, plus `_preset_id`, `_locked`.

    On invalid / locked preset:
      - returns {"_error": "locked", "_locked": True}  (caller should 402)
      - returns {} for missing/empty preset_id (no overrides)
    """
    if not preset_id:
        return {}
    preset = get_preset(preset_id)
    if not preset:
        return {"_error": "unknown_preset"}
    # Pro preset on free user → caller should 402.
    if preset["plan_tier"] == "pro" and not _is_paid(user_tier):
        return {"_error": "locked", "_locked": True, "_preset_id": preset["id"]}

    cfg = preset["config"]
    return {
        "_preset_id": preset["id"],
        "_locked": False,
        "voice_style": voice_style or cfg.get("voice_style"),
        "voice_rate": cfg.get("voice_rate"),
        "voice_pitch": cfg.get("voice_pitch"),
        "motion": motion or cfg.get("motion"),
        "bgm_style": bgm_style or cfg.get("bgm"),
        "emotion": cfg.get("emotion"),
        "intensity": cfg.get("intensity"),
        "camera": cfg.get("camera"),
        "lighting": cfg.get("lighting"),
        "effects": list(cfg.get("effects") or []),
    }


__all__ = [
    "PRESETS",
    "list_presets",
    "get_preset",
    "apply_preset_to_request",
]
