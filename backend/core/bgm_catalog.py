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
]


def get_catalog() -> list[dict]:
    """Return only tracks whose mp3 is actually present on disk."""
    out: list[dict] = []
    for t in CATALOG:
        if (BGM_DIR / t['filename']).exists():
            out.append(t)
    return out


def random_for_mood(mood: str) -> Optional[dict]:
    """Non-LLM fallback: pick any track that matches the mood keyword."""
    pool = [t for t in get_catalog() if mood in t.get('vibes', [])]
    if not pool:
        pool = get_catalog()
    return random.choice(pool) if pool else None


def serve_url(track: dict) -> str:
    return f'/api/serve-file/{track["filename"]}'
