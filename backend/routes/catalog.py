"""Catalog / meta GET endpoints (Session 27d refactor out of server.py).

Session 27e: Added /sound-effects, /voice-styles, /motion-presets.

Currently houses:
  GET /api/voices          — list of available TTS voices
  GET /api/sound-effects   — BGM / SFX catalog (w/o raw URLs)
  GET /api/voice-styles    — Audio Emotion Engine presets
  GET /api/motion-presets  — Ken-Burns motion presets for still → video
"""
from fastapi import APIRouter

from core.voice_library import VOICE_LIBRARY
from core.constants import (
    SFX_CATALOG,
    VOICE_STYLES as _VOICE_STYLES,
    MOTION_PRESETS as _MOTION_PRESETS,
)

router = APIRouter(prefix='/api', tags=['catalog'])


@router.get('/voices')
async def get_voices():
    return {'voices': VOICE_LIBRARY}


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
