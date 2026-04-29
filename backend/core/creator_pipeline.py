"""Creator Pipeline — shared service used by Pattern Lab + Creator Wizard.

Responsibilities:
 - Generate 3 structured prompt options from a user idea (via ChatGPT/Gemini).
 - Fetch images from Pixabay.
 - Curate BGM via Gemini from local catalog.
 - (Backend TTS & FFmpeg assembly stays in server.py — this module orchestrates.)
"""
from __future__ import annotations
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from .bgm_catalog import get_catalog, random_for_mood
from . import pixabay

log = logging.getLogger(__name__)
CACHE_DIR = Path('/app/backend/static/llm_cache')
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_S = 24 * 3600


def _cache(key: str, value: dict | None = None) -> Optional[dict]:
    fp = CACHE_DIR / f'{hashlib.sha256(key.encode()).hexdigest()[:24]}.json'
    if value is not None:
        fp.write_text(json.dumps(value))
        return value
    if fp.exists() and time.time() - fp.stat().st_mtime < CACHE_TTL_S:
        try:
            return json.loads(fp.read_text())
        except Exception:
            return None
    return None


PROMPT_SYSTEM = """You are a creative director for an Indian short-form AI video app called MagicAi Studio. Generate EXACTLY 3 distinct reel concepts from the user's idea.

Strict rules:
 - Output ONLY valid JSON, no prose.
 - NO copyrighted content, brand names, specific song/movie/video titles.
 - Focus on FORMAT patterns (hooks, pacing, visual motifs, BGM moods).
 - Indian cultural context. The TARGET LANGUAGE for the spoken script is given in the user message.
 - Each option should feel DIFFERENT in tone (e.g. devotional / emotional / viral-fun).

CRITICAL — image_query rules:
 - image_query MUST contain the SPECIFIC nouns from the user's idea.
 - If the idea mentions "Krishna", image_query MUST include "krishna" (e.g. "krishna flute peacock", "krishna devotional sunset").
 - If the idea mentions "Shiva", include "shiva" or "mahadev".
 - If the idea mentions "Ganesha", include "ganesha" or "ganpati".
 - If the idea is a festival (Diwali, Holi, Eid, Janmashtami), include the festival name.
 - DO NOT use generic queries like "indian devotional" or "spiritual" — they return wrong stock footage.
 - Image_query stays in ENGLISH always (Pixabay does not search Devanagari well).

CRITICAL — script rules:
 - Length depends on the reel duration the user implies. Default: 4-6 lines or 25-45 spoken words (about 12-15s when read aloud).
 - For "bhajan" / "song" / "lyrics" / "geet" / "bhakti": output 4-8 SHORT lyric-like lines, each on its own line. Use poetic devotional phrasing. End every other line with a soft Hindi rhyme if the language is Hindi/Hinglish.
 - For a normal reel: 2-4 sentences with [pause:0.5] markers between hooks.
 - When language is Hindi: write the script in DEVANAGARI script (श्री कृष्ण की मधुर बंसी ...).
 - When language is Hinglish: mix Hindi words written in Roman with English (e.g. "Bansi bajaye Krishna, every soul awakens...").
 - When language is English: pure English.

JSON schema:
{"options": [
  {"title": "<short catchy>", "tone": "devotional|emotional|viral|motivational|funny|story",
   "script": "<spoken text, multi-line for songs/bhajans, include [pause:0.5] if useful>",
   "image_query": "<2-4 keywords for Pixabay image search; ENGLISH only, must include subject nouns from idea>",
   "voice_style": "devotional|motivation|story|neutral|funny",
   "music_mood": "cinematic_epic|calm|playful|suspense|devotional|motivational",
   "motion": "ken_burns|zoom_in_slow|zoom_in_fast|slow_pan_right|slow_pan_left|cinematic_zoom"
  }, ... (3 total)
]}"""


# Map UI language code → human-readable name we feed into the LLM prompt.
_LANG_MAP = {
    'english':  'English',
    'hindi':    'Hindi (Devanagari)',
    'hinglish': 'Hinglish (Hindi words in Roman script mixed with English)',
}


async def generate_3_options(user_idea: str, lang: str = 'english') -> list[dict]:
    """Ask Gemini for 3 prompt options in the requested language. Cache by
    (idea, lang) for 24h."""
    lang_norm = (lang or 'english').lower().strip()
    if lang_norm not in _LANG_MAP:
        lang_norm = 'english'
    lang_label = _LANG_MAP[lang_norm]
    key = f'prompts_v3|{lang_norm}|{user_idea.strip().lower()[:140]}'
    cached = _cache(key)
    if cached:
        return cached.get('options', [])
    try:
        # Use Emergent LLM key via emergentintegrations (Gemini 2.5 Flash).
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        api_key = os.environ.get('EMERGENT_LLM_KEY') or os.environ.get('GEMINI_API_KEY') or ''
        if not api_key:
            log.warning('No Emergent LLM key; returning empty options')
            return []
        chat = LlmChat(
            api_key=api_key,
            session_id=f'wizard_{hashlib.md5((user_idea + lang_norm).encode()).hexdigest()[:10]}',
            system_message=PROMPT_SYSTEM,
        ).with_model('gemini', 'gemini-2.5-flash')
        user_msg = (
            f'User idea: {user_idea!r}\n'
            f'TARGET LANGUAGE for the spoken script: {lang_label}\n'
            f'Reminder: image_query MUST stay in English and MUST contain specific subject '
            f'nouns from the idea (deity names, festival names, etc).\n'
            f'Return the JSON now.'
        )
        resp = await chat.send_message(UserMessage(text=user_msg))
        # Strip markdown code fences if present
        text = resp.strip()
        if text.startswith('```'):
            text = text.split('```', 2)[1]
            if text.startswith('json'):
                text = text[4:].lstrip()
        data = json.loads(text)
        opts = data.get('options', [])[:3]
        # Post-process: ensure image_query contains the idea's main nouns.
        opts = _enforce_image_query_nouns(opts, user_idea)
        _cache(key, {'options': opts})
        return opts
    except Exception as e:
        log.exception('Gemini prompt generation failed: %s', e)
        return []


# Common Indian deity / festival nouns we want to make sure end up in image_query
# verbatim (lowercase). The LLM sometimes drops them in favour of generic terms
# like "indian temple", which yields wrong Pixabay footage.
_ANCHOR_NOUNS = [
    'krishna', 'shiva', 'mahadev', 'ganesha', 'ganpati', 'durga', 'kali',
    'lakshmi', 'saraswati', 'hanuman', 'rama', 'ram', 'sita', 'radha',
    'buddha', 'jesus', 'allah',
    'diwali', 'holi', 'janmashtami', 'navratri', 'eid', 'christmas',
    'ganesh chaturthi', 'maha shivratri', 'raksha bandhan', 'karva chauth',
    'dussehra', 'onam', 'pongal', 'lohri', 'baisakhi',
    'taj mahal', 'ganga', 'himalaya', 'temple', 'mandir',
]


def _enforce_image_query_nouns(opts: list[dict], user_idea: str) -> list[dict]:
    """Ensure each option's image_query contains the most important
    subject noun from the user's idea (e.g. 'krishna'). Without this,
    Gemini sometimes returns generic queries like 'indian devotional'
    which return wrong / generic Pixabay stock footage.

    Uses word-boundary matching so 'ram' inside 'stotram' / 'program'
    doesn't accidentally trigger anchoring to 'ram'.
    """
    import re as _re
    idea_lc = (user_idea or '').lower()
    # Word-boundary match: 'ram' matches "ram" but NOT "stotram", "program", etc.
    # Multi-word anchors like 'maha shivratri' use a substring fallback.
    anchors_in_idea: list[str] = []
    for n in _ANCHOR_NOUNS:
        if ' ' in n:  # multi-word anchor
            if n in idea_lc:
                anchors_in_idea.append(n)
        else:
            if _re.search(rf'\b{_re.escape(n)}\b', idea_lc):
                anchors_in_idea.append(n)
    if not anchors_in_idea:
        return opts  # nothing specific to anchor on

    # Order matters: prefer LONGER anchors (more specific). e.g. for "Shiv Tandav"
    # we want 'shiva' over 'tandav' if both matched.
    anchors_in_idea.sort(key=len, reverse=True)
    primary = anchors_in_idea[0]
    fixed = []
    for o in opts:
        if not isinstance(o, dict):
            continue
        q = (o.get('image_query') or '').lower()
        # Same word-boundary check on the existing query
        if not _re.search(rf'\b{_re.escape(primary)}\b', q):
            o['image_query'] = f'{primary} {o.get("image_query") or ""}'.strip()
            log.info("creator_pipeline: anchored image_query with '%s' → %r", primary, o['image_query'])
        fixed.append(o)
    return fixed


async def fetch_images_for(image_query: str, count: int = 5) -> list[str]:
    """Return Pixabay largeImageURL list, falling back to empty."""
    hits = await pixabay.search_images(image_query, count=count, orientation='vertical')
    return [h.get('largeImageURL') or h.get('webformatURL') for h in hits if h.get('largeImageURL') or h.get('webformatURL')]


def pick_bgm(music_mood: str) -> Optional[dict]:
    """Non-LLM fast path — pick BGM track from local catalog by mood."""
    # vibes list uses simple keyword match
    mood = (music_mood or '').lower()
    if mood in ('calm', 'devotional'):
        return random_for_mood('devotional') or random_for_mood('cinematic')
    if mood in ('playful', 'funny'):
        return random_for_mood('playful') or random_for_mood('cinematic')
    if mood in ('motivational', 'epic', 'cinematic_epic'):
        return random_for_mood('motivational') or random_for_mood('cinematic')
    catalog = get_catalog()
    return catalog[0] if catalog else None
