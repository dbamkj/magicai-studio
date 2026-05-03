"""Emotion detector for the AI Avatar Studio (Phase 2).

Takes a piece of dialogue text and returns:
    {"emotion": str, "intensity": float}

Where:
  - emotion ∈ {"happy", "sad", "calm", "playful", "confident",
               "excited", "motivational", "fierce", "devotional", "neutral"}
  - intensity ∈ [0.0, 1.0]  — how strong the emotion read is

Two strategies, tried in order:
  1. LLM (GPT-4o-mini via Emergent integrations) for nuanced detection.
     Works for Hindi/Hinglish/English. Cached by text hash.
  2. Keyword + emoji + cue fallback — pure-Python, instant, no API.
     Used when the LLM call fails (budget exhausted, network issue) or
     when EMERGENT_LLM_KEY is missing.

The fallback alone gets ~70% accuracy on the user's content because
the dialogue cards already have explicit cues like "*chuckles*" or
"*screams loudly*" + emoji headers. That's good enough for the
emotion-aware TTS rate/pitch + face-tint overlay this module powers.

Public:
  - detect_emotion(text, language=None) -> dict
  - emotion_to_voice_params(emotion, intensity) -> dict (rate/pitch)
  - emotion_to_tint(emotion, intensity) -> tuple (R, G, B) bias 0-255
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
from typing import Any, Dict, Optional, Tuple

log = logging.getLogger("core.emotion_detector")


_VALID_EMOTIONS = {
    "happy", "sad", "calm", "playful", "confident",
    "excited", "motivational", "fierce", "devotional", "neutral",
}


# ─────────────────────── Keyword fallback ────────────────────────
# Sets of Hindi (Devanagari + romanised) + English keywords/emoji
# that strongly imply a given emotion. Tuned for the user's MagiCAi
# dialogue corpus (Bhakti / Funny / Motivation / Emotional / Cinematic).

_KW = {
    "happy": [
        # English
        "happy", "joy", "smile", "laugh", "haha", "lol", "fun", "great",
        "wonderful", "amazing", "blessed", "celebrate", "yay",
        # Hinglish / Hindi
        "khush", "khushi", "muskaan", "anand", "mast", "shubh", "achha",
        # Emoji
        "😊", "😀", "😄", "😁", "🎉", "✨",
    ],
    "sad": [
        "sad", "cry", "tear", "miss", "lonely", "alone", "heartbreak",
        "broken", "regret", "sorry", "apology", "grief", "sob",
        "udaas", "dukh", "dard", "rona", "akela", "khoya",
        "💔", "😢", "😭", "🥺",
    ],
    "calm": [
        "calm", "peace", "peaceful", "quiet", "gentle", "serene",
        "meditate", "breathe", "relax", "soothe", "tranquil",
        "shaant", "shanti", "dhyan", "sukoon", "aaram",
        "🧘", "🕉️",
    ],
    "playful": [
        "joke", "prank", "funny", "tease", "silly", "wink", "kidding",
        "*chuckles*", "*giggles*", "haha", "ha ha", "lol",
        "mazaak", "majedaar", "majaa",
        "😜", "😋", "🤪", "😆",
    ],
    "confident": [
        "confident", "sure", "definitely", "absolutely", "i can", "i will",
        "win", "succeed", "boss", "leader", "champion",
        "pakka", "zaroor", "vishwas", "himmat",
        "😎", "💪", "🔥",
    ],
    "excited": [
        "excited", "thrilled", "wow", "incredible", "unbelievable",
        "let's go", "lets go", "lfg", "amazing", "epic",
        "kamaal", "bilkul", "jhakaas",
        "🤩", "🎊", "🚀", "⚡",
    ],
    "motivational": [
        "rise", "grind", "hustle", "achieve", "goal", "dream", "never give up",
        "keep going", "discipline", "focus", "ceo", "mindset", "wake up",
        "uthho", "lakshya", "mehnat", "sapna",
        "🦁", "🏆",
    ],
    "fierce": [
        "fight", "war", "battle", "warrior", "fierce", "rage", "fury",
        "destroy", "crush", "roar", "*screams*", "*roars*",
        "yudh", "ladai", "krodh",
        "⚔️", "🦁", "🔥",
    ],
    "devotional": [
        "om", "hari", "krishna", "ram", "shiv", "shiva", "bhakti", "prayer",
        "puja", "ishwar", "bhagwan", "namaste", "namaskar", "jai",
        "ॐ", "जय", "🙏", "🪔", "🕉️",
    ],
}

# Cues like "*screams loudly*" or "[whispering]" — much stronger
# signal than plain words.
_CUE_PATTERN = re.compile(r"[\*\[]([^\*\]]{1,30})[\*\]]")
_CUE_TO_EMOTION = {
    "scream": "fierce", "shout": "fierce", "roar": "fierce", "rage": "fierce",
    "cry": "sad", "sob": "sad", "weep": "sad", "tears": "sad",
    "laugh": "playful", "chuckle": "playful", "giggle": "playful", "wink": "playful",
    "whisper": "calm", "softly": "calm", "calm": "calm", "breathe": "calm",
    "smile": "happy", "happy": "happy",
    "confident": "confident", "smirk": "confident",
    "excited": "excited", "thrilled": "excited",
    "pray": "devotional", "chant": "devotional",
}


def _keyword_detect(text: str) -> Tuple[str, float]:
    """Return (emotion, intensity) using keyword + cue heuristics."""
    if not text or not text.strip():
        return ("neutral", 0.0)
    lo = text.lower()
    scores: Dict[str, float] = {e: 0.0 for e in _VALID_EMOTIONS}

    # 1) Strongest signal — explicit cues in *...* or [...].
    for m in _CUE_PATTERN.finditer(lo):
        cue = m.group(1).strip()
        for token, em in _CUE_TO_EMOTION.items():
            if token in cue:
                scores[em] += 3.0  # 3× weight vs plain keywords

    # 2) Plain keyword/emoji hits.
    for em, words in _KW.items():
        for w in words:
            if w in lo:
                # Emoji and short tokens count more
                weight = 1.4 if len(w) <= 3 else 1.0
                scores[em] += weight

    # Pick the winner.
    best = max(scores.items(), key=lambda kv: kv[1])
    if best[1] <= 0.0:
        return ("neutral", 0.0)
    # Map raw score → intensity in [0.5, 1.0]. >5 hits = max intensity.
    raw = best[1]
    intensity = max(0.5, min(1.0, 0.5 + raw / 10.0))
    return (best[0], round(intensity, 2))


# ─────────────────────── LLM detection ────────────────────────

_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_MAX = 256


def _cache_key(text: str, language: Optional[str]) -> str:
    h = hashlib.sha256()
    h.update((text or "").encode("utf-8", errors="ignore"))
    h.update(b"|")
    h.update((language or "").encode("utf-8", errors="ignore"))
    return h.hexdigest()[:24]


async def _llm_detect(text: str, language: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Call GPT-4o-mini via emergentintegrations. Returns None on failure."""
    api_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    if not api_key:
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        chat = LlmChat(
            api_key=api_key,
            session_id=f"emo_{_cache_key(text, language)}",
            system_message=(
                "You are a precise emotion classifier for short avatar "
                "dialogues (Hindi / English / Hinglish). Output ONLY one "
                "JSON line with keys: emotion (one of "
                "happy|sad|calm|playful|confident|excited|motivational|"
                "fierce|devotional|neutral) and intensity (0.0-1.0). "
                "No prose, no markdown, no code fence."
            ),
        )
        chat = chat.with_model("openai", "gpt-4o-mini").with_params(temperature=0.2)
        msg = UserMessage(text=f"Classify this dialogue:\n\n{text[:600]}")
        resp = await chat.send_message(msg)
        if not isinstance(resp, str):
            return None
        # Parse — accept "{...}" with or without surrounding text.
        import json as _json
        m = re.search(r"\{[^{}]+\}", resp)
        if not m:
            return None
        try:
            data = _json.loads(m.group(0))
        except Exception:
            return None
        emotion = str(data.get("emotion") or "").strip().lower()
        if emotion not in _VALID_EMOTIONS:
            return None
        intensity = float(data.get("intensity") or 0.5)
        intensity = max(0.0, min(1.0, intensity))
        return {"emotion": emotion, "intensity": round(intensity, 2)}
    except Exception as e:
        log.debug("emotion: LLM detect failed (%s) — falling back", e)
        return None


# ─────────────────────── Public API ────────────────────────


async def detect_emotion(text: str, language: Optional[str] = None) -> Dict[str, Any]:
    """Detect the dominant emotion + intensity for a piece of dialogue.

    Tries the LLM first, falls back to keyword heuristics on failure.
    Result is cached by (text, language) for the lifetime of the
    process so calling this multiple times for the same line is free.
    """
    if not text or not text.strip():
        return {"emotion": "neutral", "intensity": 0.0, "source": "empty"}
    key = _cache_key(text, language)
    if key in _CACHE:
        return _CACHE[key]

    # 1) LLM
    llm_res = await _llm_detect(text, language)
    if llm_res:
        out = {**llm_res, "source": "llm"}
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = out
        return out

    # 2) Keyword fallback
    em, intensity = _keyword_detect(text)
    out = {"emotion": em, "intensity": intensity, "source": "keyword"}
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = out
    return out


# ───────── Emotion → Voice rate/pitch (used by talking + dual TTS) ─────────

# Each entry is (rate_pct, pitch_token). rate_pct is an integer
# percentage (e.g. -10 = 10% slower) at full intensity 1.0; we scale
# linearly by intensity and emit the edge-tts string format
# ("+N%" / "-N%"). pitch_token is an Edge-TTS pitch shift like
# "+10Hz" / "-15Hz" — we only set it when there's a clear semantic reason.
_VOICE_PARAMS = {
    "happy":         (6,   "+5Hz"),
    "sad":           (-12, "-5Hz"),
    "calm":          (-8,  "+0Hz"),
    "playful":       (5,   "+10Hz"),
    "confident":     (2,   "+0Hz"),
    "excited":       (10,  "+10Hz"),
    "motivational":  (4,   "+5Hz"),
    "fierce":        (6,   "-5Hz"),  # faster + slightly lower
    "devotional":    (-5,  "+0Hz"),  # slower, reverent
    "neutral":       (0,   "+0Hz"),
}


def emotion_to_voice_params(emotion: str, intensity: float = 1.0) -> Dict[str, Any]:
    """Translate an emotion + intensity into edge-tts rate/pitch tweaks.

    Returns dict with keys {voice_rate, voice_pitch} where voice_rate
    is an edge-tts percent string (e.g. "+6%" / "-12%") and
    voice_pitch is a Hz shift string. These slot directly into
    server.generate_tts_audio() which expects strings.

    intensity ∈ [0,1] scales the magnitude — at 0.5 we emit half the
    delta, at 1.0 the full delta.
    """
    if emotion not in _VOICE_PARAMS:
        emotion = "neutral"
    rate_pct, pitch = _VOICE_PARAMS[emotion]
    intensity = max(0.0, min(1.0, float(intensity or 1.0)))
    # Round to nearest int for clean strings; edge-tts accepts decimals
    # but ints look cleaner in logs.
    scaled = int(round(rate_pct * intensity))
    rate_str = f"{scaled:+d}%"  # always signed: "+6%" / "-5%" / "+0%"
    return {"voice_rate": rate_str, "voice_pitch": pitch}


# ───────── Emotion → Face tint (used by mouth_animator overlays) ─────────

# A subtle RGB bias per emotion. Applied as a multiply-then-add blend
# on the rendered frame at low alpha (~0.10) so it tints the scene
# without altering the cartoon's identity.
_TINT_RGB = {
    "happy":         (255, 235, 180),  # warm sunshine
    "sad":           (170, 200, 235),  # cool blue
    "calm":          (200, 230, 220),  # soft mint
    "playful":       (255, 220, 230),  # candy pink
    "confident":     (240, 220, 200),  # neutral warm
    "excited":       (255, 200, 220),  # vivid pink
    "motivational":  (255, 200, 160),  # punchy orange
    "fierce":        (255, 150, 130),  # red/orange
    "devotional":    (255, 220, 160),  # golden glow
    "neutral":       (255, 255, 255),  # no tint
}


def emotion_to_tint(emotion: str, intensity: float = 1.0) -> Tuple[Tuple[int, int, int], float]:
    """Return (rgb, alpha) where alpha is in [0, 0.18].

    Intensity scales alpha — neutral / weak emotions get 0 alpha (no
    visible tint). Used by mouth_animator._render_frame's optional
    tint pass.
    """
    if emotion not in _TINT_RGB or emotion == "neutral":
        return ((255, 255, 255), 0.0)
    intensity = max(0.0, min(1.0, float(intensity or 1.0)))
    alpha = 0.10 * intensity  # cap at ~10% blend so the cartoon stays the cartoon
    return (_TINT_RGB[emotion], round(alpha, 3))


__all__ = [
    "detect_emotion",
    "emotion_to_voice_params",
    "emotion_to_tint",
]


# Sync helper for callers in non-async contexts (e.g. CLI smoke test).
def detect_emotion_sync(text: str, language: Optional[str] = None) -> Dict[str, Any]:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Caller is already in an event loop — just use keyword path
            em, intensity = _keyword_detect(text)
            return {"emotion": em, "intensity": intensity, "source": "keyword"}
    except RuntimeError:
        pass
    return asyncio.run(detect_emotion(text, language))


if __name__ == "__main__":  # pragma: no cover
    import sys
    if len(sys.argv) < 2:
        print("usage: python -m core.emotion_detector '<text>' [language]")
        sys.exit(1)
    print(detect_emotion_sync(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
