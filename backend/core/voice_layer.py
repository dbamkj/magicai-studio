"""Voice abstraction layer (Sprint 30c)

A single async helper `generate_voice(text, style, lang, ...)` that downstream
pipelines (wizard, avatar, future creative-plan TTS) call. This isolates the
TTS provider so we can swap Edge-TTS → Sarvam Bulbul / Gemini-TTS in the
future without touching the consumers.

Sprint 30d (TIER-AWARE ROUTING):
  • Free / Starter      → Edge-TTS (free, 200+ neural voices)
  • Creator / Pro       → Sarvam AI Bulbul-v2 for Indic languages,
                          Edge-TTS premium voices for English.

Sarvam Bulbul-v2 is markedly better than Edge-TTS for Hindi / devotional /
emotive Indic content (native pronunciation, accent, code-mix), so premium
users automatically get it whenever they're generating Indic-language reels.
English content stays on Edge-TTS premium voices for both tiers because
Sarvam's English isn't superior to Edge's Aria/Jenny/Guy neural voices.
"""
from __future__ import annotations
import logging
import os
import re
import asyncio
import subprocess
from pathlib import Path
from typing import Optional

log = logging.getLogger("voice_layer")


# ---- Style → pitch / rate map (Edge-TTS friendly) ------------------------
STYLE_RATE_PITCH: dict[str, tuple[str, str]] = {
    'neutral':    ('+0%',  '+0Hz'),
    'story':      ('-5%',  '-2Hz'),
    'devotional': ('-12%', '-5Hz'),
    'motivation': ('+8%',  '+4Hz'),
    'funny':      ('+12%', '+8Hz'),
}


# ---- SSML break duration per style (ms) ---------------------------------
# More devotional / cinematic styles want longer breaths between lines.
STYLE_BREAK_MS: dict[str, int] = {
    'neutral':    250,
    'story':      350,
    'devotional': 600,
    'motivation': 250,
    'funny':      200,
}


def _split_lines(text: str) -> list[str]:
    """Split a multi-line script into individual lines for SSML breaks.
    Preserves Devanagari and other Unicode."""
    # Split on newlines first, then on Hindi (।) or English sentence enders.
    raw = re.split(r'(?<=[।.!?])\s+|\n+', (text or '').strip())
    return [line.strip() for line in raw if line and line.strip()]


# ─────────────────────────────────────────────────────────────────────────
# Tier-aware voice routing  (Sprint 30d)
# ─────────────────────────────────────────────────────────────────────────
TIER_RANK = {'guest': 0, 'free': 0, 'starter': 1, 'creator': 2, 'pro': 3}

# Sarvam Bulbul-v2 speaker pool — we rotate through these for premium users
# generating Indic content. Selection is style-aware: devotional → Vidya,
# motivation → Karun, story → Anushka, etc. (see SARVAM_STYLE_PICK below).
SARVAM_STYLE_PICK = {
    'devotional': 'sarvam:vidya',     # warm, slow, soulful female
    'story':      'sarvam:anushka',   # smooth narrative female
    'neutral':    'sarvam:manisha',   # neutral conversational female
    'motivation': 'sarvam:karun',     # punchy, energetic male
    'funny':      'sarvam:hitesh',    # playful male
}
# Pro tier gets all 7 speakers; Creator gets the curated 4 above.
SARVAM_PRO_EXTRA = {
    'devotional_male': 'sarvam:abhilash',
    'story_alt':       'sarvam:arya',
}

# Edge-TTS premium voices (used for English content + free-tier fallback).
# Free / Starter gets the basic set; Creator+ gets premium "Studio" voices.
EDGE_PREMIUM_EN = {
    'devotional': 'en-US-AriaNeural',
    'story':      'en-US-JennyNeural',
    'neutral':    'en-US-AriaNeural',
    'motivation': 'en-US-GuyNeural',
    'funny':      'en-US-AndrewNeural',
}
EDGE_BASIC_EN = {
    'devotional': 'en-US-AriaNeural',
    'story':      'en-US-JennyNeural',
    'neutral':    'en-US-JennyNeural',
    'motivation': 'en-US-GuyNeural',
    'funny':      'en-US-GuyNeural',
}
# Edge-TTS Hindi voices (free, neural). Used for free/starter users whose
# script is Indic — they can't access Sarvam Bulbul, but English voices fail
# to pronounce Devanagari, so we fall back to Microsoft's free Hindi voices.
EDGE_HINDI = {
    'devotional': 'hi-IN-MadhurNeural',  # warm male, soulful
    'story':      'hi-IN-SwaraNeural',   # smooth narrative female
    'neutral':    'hi-IN-SwaraNeural',
    'motivation': 'hi-IN-MadhurNeural',  # firm, energetic male
    'funny':      'hi-IN-SwaraNeural',
}


def _detect_indic(text: str, lang: Optional[str] = None) -> bool:
    """True if `text` contains Devanagari / Tamil / Telugu / Bengali characters
    OR `lang` explicitly indicates an Indic language. Hinglish counts because
    even pure-roman Hindi reads better through Sarvam Bulbul."""
    if lang:
        l = lang.lower()
        if any(k in l for k in ('hi', 'hindi', 'hinglish', 'ta', 'tamil',
                                'te', 'telugu', 'bn', 'bengali', 'ml',
                                'malayalam', 'kn', 'kannada', 'mr',
                                'marathi', 'gu', 'gujarati', 'pa',
                                'punjabi', 'indic')):
            return True
    if text:
        # Devanagari U+0900..U+097F · Tamil U+0B80..U+0BFF · Telugu U+0C00..U+0C7F
        if re.search(r'[\u0900-\u097F\u0B80-\u0BFF\u0C00-\u0C7F\u0980-\u09FF\u0A80-\u0AFF\u0A00-\u0A7F\u0C80-\u0CFF\u0D00-\u0D7F]', text):
            return True
    return False


def select_voice_for_tier(
    *,
    requested_voice_id: Optional[str],
    text: str,
    user_tier: str = 'free',
    voice_style: str = 'story',
    lang: Optional[str] = None,
) -> str:
    """Return the voice_id that the TTS pipeline should use, given the user's
    tier, the script's language, and the chosen voice style.

    Rules:
      • If the user explicitly picked a Sarvam voice (`sarvam:xxx`), respect it
        IFF they're Creator+ (Premium). Free/Starter who somehow specified a
        Sarvam voice are downgraded to Edge-TTS.
      • If the script is Indic AND user is Creator+, route to Sarvam Bulbul-v2
        with a style-appropriate speaker.
      • Otherwise, use Edge-TTS — premium voices for Creator+, basic for Free.
      • Honors any non-Sarvam custom voice_id the caller passed.
    """
    tier = (user_tier or 'free').lower()
    rank = TIER_RANK.get(tier, 0)
    style = (voice_style or 'story').lower()
    is_premium = rank >= TIER_RANK['creator']

    # 1. User explicitly picked a Sarvam voice
    if requested_voice_id and requested_voice_id.startswith('sarvam:'):
        if is_premium:
            return requested_voice_id
        # downgrade silently
        log.info('voice_layer: %s tier requested Sarvam voice %s — downgrading to Edge-TTS',
                 tier, requested_voice_id)

    # 2. Indic content + premium → auto Sarvam
    if _detect_indic(text, lang):
        if is_premium:
            chosen = SARVAM_STYLE_PICK.get(style, SARVAM_STYLE_PICK['story'])
            # Pro alternate: rotate to abhilash for devotional male variety.
            if rank >= TIER_RANK['pro'] and style == 'devotional':
                if (hash(text or '') & 1) == 1:
                    chosen = SARVAM_PRO_EXTRA['devotional_male']
            return chosen
        # 2b. Indic content + free/starter → Edge Hindi voices (free, neural).
        # Falling back to en-US-* would fail because English neural voices can't
        # pronounce Devanagari ("No audio was received" error).
        return EDGE_HINDI.get(style, EDGE_HINDI['story'])

    # 3. English (or fallback) → Edge-TTS
    if requested_voice_id and not requested_voice_id.startswith('sarvam:'):
        # Caller explicitly chose an Edge voice — keep it.
        return requested_voice_id
    pool = EDGE_PREMIUM_EN if is_premium else EDGE_BASIC_EN
    return pool.get(style, pool['story'])



def build_ssml(text: str, voice: str, style: str = 'story') -> str:
    """Compose an SSML document Edge-TTS will accept.
    Adds `<break>` between sentences for natural cadence."""
    lines = _split_lines(text) or [text or '']
    rate, pitch = STYLE_RATE_PITCH.get(style, STYLE_RATE_PITCH['story'])
    break_ms = STYLE_BREAK_MS.get(style, 350)
    inner_parts: list[str] = []
    for i, line in enumerate(lines):
        # Escape XML-unsafe chars
        safe = (line.replace('&', '&amp;')
                    .replace('<', '&lt;').replace('>', '&gt;'))
        inner_parts.append(f'<s>{safe}</s>')
        if i < len(lines) - 1:
            inner_parts.append(f'<break time="{break_ms}ms"/>')
    inner = ''.join(inner_parts)
    return (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xml:lang="en-US">'
        f'<voice name="{voice}">'
        f'<prosody rate="{rate}" pitch="{pitch}">{inner}</prosody>'
        '</voice></speak>'
    )


async def generate_voice(
    text: str,
    *,
    voice_id: str = 'en-US-JennyNeural',
    style: str = 'story',
    lang: str = 'english',
    out_path: Path,
    prefer_gemini: bool = False,
) -> dict:
    """Generate ONE audio file for the entire `text` (no per-scene splitting).

    Returns: {provider, voice, style, lang, path, ssml_used, success}.
    """
    # FUTURE: branch to Gemini 2.5 Flash Preview TTS for premium users.
    # if prefer_gemini and (creator|pro): route to gemini_tts(...)
    # For now, always use Edge-TTS with SSML enhancements.
    ssml = build_ssml(text, voice_id, style)
    try:
        import edge_tts
        comm = edge_tts.Communicate(ssml, voice_id, ssml=True)
        await comm.save(str(out_path))
        ok = out_path.exists() and out_path.stat().st_size > 1000
        if not ok:
            # Fallback: plain text (no SSML) — some voice/style combos
            # reject our SSML. Edge-TTS still wraps text internally and
            # respects the rate/pitch passed via Communicate constructor.
            rate, pitch = STYLE_RATE_PITCH.get(style, STYLE_RATE_PITCH['story'])
            comm2 = edge_tts.Communicate(text, voice_id, rate=rate, pitch=pitch)
            await comm2.save(str(out_path))
            ok = out_path.exists() and out_path.stat().st_size > 1000
            return {
                'provider': 'edge-tts', 'voice': voice_id, 'style': style,
                'lang': lang, 'path': str(out_path) if ok else None,
                'ssml_used': False, 'success': ok,
            }
        return {
            'provider': 'edge-tts', 'voice': voice_id, 'style': style,
            'lang': lang, 'path': str(out_path), 'ssml_used': True,
            'success': True,
        }
    except Exception as e:
        log.exception('voice_layer: generate_voice failed: %s', e)
        return {
            'provider': 'edge-tts', 'voice': voice_id, 'style': style,
            'lang': lang, 'path': None, 'ssml_used': False, 'success': False,
            'error': str(e)[:200],
        }
