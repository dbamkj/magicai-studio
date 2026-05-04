"""Catalog / meta GET endpoints (Session 27d refactor out of server.py).

Session 27e: Added /sound-effects, /voice-styles, /motion-presets.
Session 34:  Added /preview-voice (Phase-B round 2).

Currently houses:
  GET /api/voices          — list of available TTS voices
  GET /api/preview-voice   — stream a short MP3 sample of a given voice (cached)
  GET /api/sound-effects   — BGM / SFX catalog (w/o raw URLs)
  GET /api/voice-styles    — Audio Emotion Engine presets
  GET /api/motion-presets  — Ken-Burns motion presets for still → video
"""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from core.voice_library import VOICE_LIBRARY
from core.constants import (
    SFX_CATALOG,
    VOICE_STYLES as _VOICE_STYLES,
    MOTION_PRESETS as _MOTION_PRESETS,
)

log = logging.getLogger("routes.catalog")
router = APIRouter(prefix='/api', tags=['catalog'])

# Voice previews are cached to disk under <repo>/uploads/voice_preview_<id>.mp3
# so a returning user (or a clicker mashing a chip) doesn't keep re-hitting
# edge-tts / Sarvam APIs.
_UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
_UPLOAD_DIR.mkdir(exist_ok=True)


@router.get('/voices')
async def get_voices():
    return {'voices': VOICE_LIBRARY}


@router.get('/preview-voice')
async def preview_voice(voice_id: str):
    """Stream a short MP3 sample of the given voice. Caches results to disk.

    voice_id can be either:
      • a raw edge-tts voice id (hi-IN-SwaraNeural, en-US-JennyNeural, ...)
      • a Sarvam id prefixed with `sarvam:` (sarvam:anushka, ...)
      • a pseudo-effect id with `:` separator
        (deep:hi-IN-MadhurNeural, baby_girl_hi_1:hi-IN-SwaraNeural, ...)

    The heavy `generate_tts_audio` helper (edge-tts + Sarvam + ffmpeg pitch
    fx) still lives in server.py. We lazy-import it to avoid a circular
    import at module load.
    """
    safe_key = voice_id.replace(':', '__').replace('/', '_')
    cache_path = _UPLOAD_DIR / f"voice_preview_{safe_key}.mp3"

    # Pick the sample text from the voice library if known; fall back to a
    # generic English line otherwise.
    voice = next((v for v in VOICE_LIBRARY if v["id"] == voice_id), None)
    sample_text = voice["preview_text"] if voice else "Hello, this is a voice preview sample."

    if not (cache_path.exists() and cache_path.stat().st_size > 500):
        try:
            from server import generate_tts_audio  # type: ignore  # lazy
            await generate_tts_audio(sample_text, voice_id, cache_path, min_duration=1.5)
        except Exception as e:
            log.warning("Preview voice failed for %s: %s", voice_id, e)
            raise HTTPException(status_code=500, detail=f"Voice preview failed: {str(e)[:100]}")

    if not cache_path.exists() or cache_path.stat().st_size < 500:
        raise HTTPException(status_code=500, detail="Voice preview generation failed")

    def _iter():
        with open(cache_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        _iter(),
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get('/sound-effects')
async def get_sound_effects():
    # Return catalog minus the raw URL (kept server-side for signed serving)
    return {'effects': [{k: v for k, v in s.items() if k != 'url'} for s in SFX_CATALOG]}


@router.get('/voice-styles')
async def get_voice_styles():
    """Return voice style presets (devotional / motivation / story / funny / neutral).

    Each preset bundles rate/pitch adjustments, a suggested BGM SFX, mix levels,
    and a pause multiplier used when [pause:Xs] markers appear in dialogue text.
    """
    return {'styles': _VOICE_STYLES}


@router.get('/motion-presets')
async def get_motion_presets():
    """Return motion / ken-burns presets for animating still images (Sprint 3 Phase A)."""
    trimmed = [{k: v for k, v in m.items() if k != 'zoompan_expr'} for m in _MOTION_PRESETS]
    return {'presets': trimmed}
