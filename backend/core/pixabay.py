"""Pixabay integration — images & videos (their free public API).

IMPORTANT: Pixabay Music endpoint does NOT exist as a public API (the
`/api/music/` path returns 404 HTML). For BGM we fall back to the locally
curated catalog in `core/bgm_catalog.py`.

Docs: https://pixabay.com/api/docs/
Rate: 100 req / 60 s per API key.
Caching: Pixabay's ToS requires us to cache results for 24 h minimum.
         We cache on disk for 7 days by SHA256(query+params).
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

import httpx

PIXABAY_API_KEY = os.environ.get('PIXABAY_API_KEY', '')
BASE = 'https://pixabay.com/api/'
CACHE_DIR = Path('/app/backend/static/pixabay_cache')
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_S = 7 * 24 * 3600  # 7 days


def _cache_key(params: dict) -> Path:
    raw = json.dumps({k: v for k, v in sorted(params.items()) if k != 'key'}, sort_keys=True)
    h = hashlib.sha256(raw.encode()).hexdigest()[:24]
    return CACHE_DIR / f'{h}.json'


def _read_cache(p: Path) -> Optional[dict]:
    if not p.exists():
        return None
    if time.time() - p.stat().st_mtime > CACHE_TTL_S:
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


async def _call(path: str, params: dict) -> dict:
    if not PIXABAY_API_KEY:
        raise RuntimeError('PIXABAY_API_KEY not set')
    params = {**params, 'key': PIXABAY_API_KEY}
    cache_file = _cache_key({**params, '_path': path})
    cached = _read_cache(cache_file)
    if cached is not None:
        return cached
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as c:
        r = await c.get(f'{BASE}{path}', params=params)
        r.raise_for_status()
        data = r.json()
    cache_file.write_text(json.dumps(data))
    return data


async def search_images(query: str, count: int = 5, orientation: str = 'vertical',
                         min_width: int = 720, safe: bool = True) -> list[dict]:
    """Search Pixabay photo library. Returns list of hit dicts with keys:
    `id, webformatURL, largeImageURL, tags, imageWidth, imageHeight, user`."""
    params = {
        'q': query.strip()[:90],
        'image_type': 'photo',
        'per_page': max(3, min(count, 30)),
        'safesearch': 'true' if safe else 'false',
        'orientation': orientation,  # all | horizontal | vertical
        'min_width': min_width,
    }
    try:
        data = await _call('', params)
        return data.get('hits', [])[:count]
    except Exception:
        return []


async def search_videos(query: str, count: int = 3, min_width: int = 720) -> list[dict]:
    """Pixabay videos. Returns hits with `videos.large.url`, `picture_id`."""
    params = {
        'q': query.strip()[:90],
        'per_page': max(3, min(count, 20)),
        'safesearch': 'true',
        'min_width': min_width,
    }
    try:
        data = await _call('videos/', params)
        return data.get('hits', [])[:count]
    except Exception:
        return []


async def download_to_cache(url: str, subdir: str = 'media') -> Optional[Path]:
    """Download a single Pixabay asset into local cache folder. Returns local Path."""
    if not url.startswith('http'):
        return None
    h = hashlib.sha256(url.encode()).hexdigest()[:24]
    ext = '.jpg'
    low = url.lower().split('?')[0]
    if low.endswith(('.png', '.webp', '.mp4', '.mov')):
        ext = '.' + low.rsplit('.', 1)[-1]
    out_dir = CACHE_DIR / subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'{h}{ext}'
    if out.exists() and out.stat().st_size > 500:
        return out
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0), follow_redirects=True) as c:
            r = await c.get(url)
            if r.status_code != 200 or len(r.content) < 500:
                return None
            out.write_bytes(r.content)
            return out
    except Exception:
        return None
