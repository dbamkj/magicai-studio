"""Local royalty-free BGM catalog for Pattern Lab + Creator Wizard.

Pixabay Music API doesn't exist (404s publicly) and Pexels has no music
API either. So we ship a small curated catalog of royalty-free mp3s under
`/app/backend/static/bgm/` and let Gemini pick the best-matching track for
a given mood.

When the catalog grows, Gemini semantically matches `mood_description`
against the user's chosen vibe. This keeps zero ongoing cost + full
commercial-use licensing.

Licenses: All tracks added here MUST be royalty-free with commercial use
rights (Pixabay content license, CC0, or equivalent).
"""
from __future__ import annotations
import os
import random
from pathlib import Path
from typing import Optional

BGM_DIR = Path('/app/backend/static/bgm')
BGM_DIR.mkdir(parents=True, exist_ok=True)

# Initial seed catalog. We ship with 1 cinematic track already in the project
# and can extend this list anytime by dropping .mp3 files into /static/bgm/.
CATALOG: list[dict] = [
    {
        'id': 'cinematic_score',
        'filename': 'cinematic_score.mp3',
        'mood': 'cinematic_epic',
        'vibes': ['epic', 'cinematic', 'dramatic', 'devotional', 'motivational'],
        'bpm': 90,
        'description': 'Sweeping orchestral cinematic score with drums and strings. Works for motivation, devotional reveals, epic transformations.',
        'license': 'Pixabay content license',
    },
    # Session 25 round 11 — procedural ambient pads generated at startup
    # by core/bgm_procedural.py. Royalty-free (pure ffmpeg synthesis).
    {
        'id': 'ambient_calm',
        'filename': 'ambient_calm.mp3',
        'mood': 'devotional',
        'vibes': ['calm', 'devotional', 'spiritual', 'meditation', 'soft'],
        'bpm': 60,
        'description': 'Soft sustained sine pad in low register (A2 + E3 + A3). Devotional, meditative, calming. Best for spiritual content and quiet emotional moments.',
        'license': 'MIT generated (procedural ffmpeg synthesis)',
    },
    {
        'id': 'playful_pulse',
        'filename': 'playful_pulse.mp3',
        'mood': 'playful',
        'vibes': ['playful', 'funny', 'comedy', 'cute', 'upbeat'],
        'bpm': 120,
        'description': 'Bright tremoloed C-major triad pad with fast wobble. Light, fun mood for comedy / kids content.',
        'license': 'MIT generated (procedural ffmpeg synthesis)',
    },
    {
        'id': 'motivational_pulse',
        'filename': 'motivational_pulse.mp3',
        'mood': 'motivational',
        'vibes': ['motivational', 'inspirational', 'uplifting', 'energy', 'driving'],
        'bpm': 100,
        'description': 'Rich C-major chord pad (root + third + fifth + octave) with mid-energy tremolo. Inspirational, motivating, suitable for hook/CTA moments.',
        'license': 'MIT generated (procedural ffmpeg synthesis)',
    },
]


def get_catalog() -> list[dict]:
    """Return only tracks whose mp3 is actually present on disk."""
    out: list[dict] = []
    for t in CATALOG:
        if (BGM_DIR / t['filename']).exists():
            out.append(t)
    return out


def random_for_mood(mood: str) -> Optional[dict]:
    """Non-LLM fallback: pick any track that matches the mood keyword.

    Accepts both compound mood ids (e.g. 'cinematic_epic') and bare
    vibe tags (e.g. 'cinematic'). Matching is substring-based in both
    directions so that 'cinematic_epic' matches a track tagged with
    'cinematic' or 'epic', and vice-versa.
    """
    if not mood:
        return None
    needle = mood.strip().lower()
    # Split compound moods like 'cinematic_epic' into ['cinematic', 'epic']
    tokens = [t for t in needle.replace('-', '_').split('_') if t]

    def matches(track: dict) -> bool:
        tmood = (track.get('mood') or '').lower()
        tvibes = [v.lower() for v in track.get('vibes', [])]
        # 1) exact mood or exact vibe match
        if tmood == needle or needle in tvibes:
            return True
        # 2) token-level overlap (handles 'cinematic_epic' <-> 'cinematic')
        for t in tokens:
            if t == tmood or t in tvibes:
                return True
            # substring hit in either direction for safety
            if any(t in v or v in t for v in tvibes):
                return True
        return False

    catalog = get_catalog()
    # Priority 1: exact mood match (e.g. needle='playful' -> track.mood=='playful')
    exact = [t for t in catalog if (t.get('mood') or '').lower() == needle]
    if exact:
        return random.choice(exact)
    # Priority 2: mood token in vibes (e.g. 'cinematic_epic' -> vibes has 'cinematic')
    pool = [t for t in catalog if matches(t)]
    if not pool:
        pool = catalog
    return random.choice(pool) if pool else None


def serve_url(track: dict) -> str:
    return f'/api/serve-file/{track["filename"]}'
