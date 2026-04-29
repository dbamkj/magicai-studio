"""Pattern Lab — Gemini-informed auto-generated Inspiration templates.

Runs via scheduler (Mon + Thu @ 3am IST). Each run:
  1. Asks Gemini for 5 trend-informed reel FORMATS (1 per category).
  2. For each format, generates a unique thumbnail via Nano Banana.
  3. Inserts as active templates with source='pattern_lab', expires_at=now+14d.

Templates auto-expire after 14 days (filtered in /api/templates).
Flagged ≥5 times auto-deactivates (see admin.py).

Compliance: Gemini prompt strictly forbids copyrighted references. We produce
only FORMAT patterns (hook structures, vibes) — never specific song/video titles.
"""
from __future__ import annotations
import asyncio
import base64
import hashlib
import json
import logging
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .creator_pipeline import pick_bgm

log = logging.getLogger('pattern_lab')
THUMBS_DIR = Path('/app/backend/static/pattern_lab_thumbs')
THUMBS_DIR.mkdir(parents=True, exist_ok=True)

CATEGORIES = [
    ('devotional',  'Hindi bhakti / temple / deity context'),
    ('motivation',  'Hustle, discipline, aspirational English/Hindi'),
    ('story',       'Short narrative arc, emotional English/Hindi'),
    ('funny',       'Relatable Indian everyday-life comedy'),
    ('divine_transformation',
     'Festival or deity transformation (Janmashtami, Navratri, Shivratri)'),
]

TIER_ROTATION = ['free', 'free', 'starter', 'starter', 'pro']  # 2 free / 2 starter / 1 pro

SYSTEM_PROMPT = """You are a creative director for a short-form AI video app in India.
Return EXACTLY 5 trend-informed reel FORMATS — one per category — as strict JSON.

STRICT RULES:
 - NO copyrighted content, brand names, specific song/video/movie titles.
 - Only FORMAT patterns (hook structures, visual motifs, BGM moods, CTAs).
 - Indian cultural context. Language: Hindi / English / Hinglish as fits.
 - Each option must feel genuinely FRESH and trending (as of now).

JSON schema (return this shape, nothing else):
{"templates": [
  {"category": "devotional|motivation|story|funny|divine_transformation",
   "title": "<short catchy, emoji OK>",
   "hook_text": "<1 strong spoken line, <=100 chars>",
   "lyrics": "<optional 2-3 line script with [pause:0.5] markers, or empty>",
   "image_prompt": "<8-15 word Nano Banana image prompt, vertical 9:16, photographic realism>",
   "voice_style": "devotional|motivation|story|neutral|funny",
   "voice_id": "hi-IN-MadhurNeural|hi-IN-SwaraNeural|en-US-JennyNeural|en-US-RyanMultilingualNeural",
   "music_mood": "cinematic_epic|calm|playful|suspense|devotional|motivational",
   "motion": "ken_burns|zoom_in_slow|zoom_in_fast|slow_pan_left|slow_pan_right|cinematic_zoom",
   "aspect_ratio": "9:16",
   "gradient_colors": ["#HEX", "#HEX", "#HEX"]
  }, ... 5 total
]}"""


async def _gemini_generate_formats() -> list[dict]:
    """Ask Gemini 2.5 Flash for 5 format concepts."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        api_key = os.environ.get('EMERGENT_LLM_KEY') or os.environ.get('GEMINI_API_KEY') or ''
        if not api_key:
            log.warning('No Emergent LLM key — pattern lab cannot run')
            return []
        chat = LlmChat(
            api_key=api_key,
            session_id=f'patternlab_{datetime.now(timezone.utc).strftime("%Y%m%d")}',
            system_message=SYSTEM_PROMPT,
        ).with_model('gemini', 'gemini-2.5-flash')
        msg = UserMessage(text=(
            f"Today is {datetime.now(timezone.utc).strftime('%B %Y')}. "
            "Generate the 5 templates JSON now for these categories in order: "
            f"{[c for c, _ in CATEGORIES]}. Return JSON only."
        ))
        resp = await chat.send_message(msg)
        text = resp.strip()
        if text.startswith('```'):
            text = text.split('```', 2)[1]
            if text.startswith('json'):
                text = text[4:].lstrip()
        data = json.loads(text)
        return data.get('templates', [])[:5]
    except Exception as e:
        log.exception('Gemini pattern lab failed: %s', e)
        return []


async def _nano_banana_thumb(prompt: str, tpl_id: str) -> str | None:
    """Generate a 9:16 thumbnail via Gemini Nano Banana (gemini-3.1-flash-image-preview).

    Returns a `/api/serve-file/pattern_lab_thumbs/<file>.png` URL on success.
    """
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        api_key = os.environ.get('EMERGENT_LLM_KEY') or os.environ.get('GEMINI_API_KEY') or ''
        if not api_key:
            log.warning('No Emergent LLM key for Nano Banana')
            return None
        chat = LlmChat(
            api_key=api_key,
            session_id=f'pl_img_{tpl_id}',
            system_message='You are an AI image generator specialised in vertical 9:16 short-video thumbnails.',
        )
        chat = chat.with_model('gemini', 'gemini-3.1-flash-image-preview').with_params(modalities=['image', 'text'])
        full_prompt = (prompt or 'cinematic vertical portrait').strip() + \
            ' — 9:16 vertical composition, cinematic realism, dramatic lighting, no text overlay, poster style.'
        msg = UserMessage(text=full_prompt)
        text, images = await chat.send_message_multimodal_response(msg)
        if not images:
            log.warning('Nano banana returned no images for prompt="%s..."', (prompt or '')[:60])
            return None
        img = images[0]
        raw = base64.b64decode(img.get('data') or '')
        if not raw or len(raw) < 500:
            return None
        fname = f'pl_{tpl_id}.png'
        out = THUMBS_DIR / fname
        out.write_bytes(raw)
        log.info('pattern_lab: nano banana thumb saved %s (%db)', fname, len(raw))
        return f'/api/serve-file/{fname}'
    except Exception as e:
        log.exception('Nano banana thumb gen failed: %s', e)
        return None


async def run_refresh(db) -> dict:
    """Full Pattern Lab refresh — 5 templates, with Nano-Banana thumbnails."""
    start = datetime.now(timezone.utc)
    log.info('pattern_lab: refresh started')
    formats = await _gemini_generate_formats()
    if not formats:
        return {'ok': False, 'reason': 'gemini_failed', 'inserted': 0}
    inserted = 0
    expires = (start + timedelta(days=14)).isoformat()
    for i, f in enumerate(formats):
        try:
            tier = TIER_ROTATION[i] if i < len(TIER_ROTATION) else 'free'
            cat = f.get('category') or CATEGORIES[i % len(CATEGORIES)][0]
            tpl_id = f'pl_{datetime.now(timezone.utc).strftime("%Y%m%d")}_{i}_{uuid.uuid4().hex[:6]}'
            thumb = await _nano_banana_thumb(f.get('image_prompt', f.get('title', '')), tpl_id)
            bgm = pick_bgm(f.get('music_mood', 'cinematic_epic'))
            doc = {
                'id': tpl_id,
                'title': f.get('title', 'Pattern Lab template'),
                'category': cat,
                'subcategory': None,
                'hook_text': f.get('hook_text', ''),
                'lyrics': f.get('lyrics') or None,
                'festival_pack': 'janmashtami' if cat == 'divine_transformation' else None,
                'character_gender': 'any',
                'transition_effect': 'golden_flash',
                'bgm_url': (f'/api/serve-file/{bgm["filename"]}' if bgm else None),
                'gradient_colors': f.get('gradient_colors') or ['#FBBF24', '#8B5CF6', '#EC4899'],
                'voice_id': f.get('voice_id', 'en-US-JennyNeural'),
                'voice_style': f.get('voice_style', 'story'),
                'motion': f.get('motion', 'ken_burns'),
                'sound_effect': 'divine_bell',
                'aspect_ratio': f.get('aspect_ratio', '9:16'),
                'duration': 6,
                'thumbnail_url': thumb,
                'preview_url': None,  # no MP4 preview for Pattern Lab (thumb-only)
                'tier': tier,
                'source': 'pattern_lab',
                'is_active': True,
                'is_trending': True,
                'flag_count': 0,
                'flags': [],
                'usage_count': 0,
                'completion_count': 0,
                'share_count': 0,
                'rating_sum': 0.0,
                'rating_count': 0,
                'score': 70.0,
                'created_at': start.isoformat(),
                'updated_at': start.isoformat(),
                'expires_at': expires,
            }
            await db.templates.insert_one(doc)
            inserted += 1
            log.info('pattern_lab: inserted %s tier=%s cat=%s thumb=%s', tpl_id, tier, cat, bool(thumb))
        except Exception as e:
            log.exception('pattern_lab: failed insert for %s: %s', i, e)
    return {'ok': True, 'inserted': inserted, 'total_attempted': len(formats), 'started_at': start.isoformat()}
