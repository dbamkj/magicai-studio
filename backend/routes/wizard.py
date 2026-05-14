"""Creator Wizard — 0-MH Instant Reel + MH Cinematic upsell.

Endpoints:
  POST   /api/wizard/prompts          → idea → 3 structured prompt options
  POST   /api/wizard/preview-images   → image_query → Pixabay vertical hits
  POST   /api/wizard/create-reel      → assemble Instant Reel (background job)
  GET    /api/wizard/job/{job_id}     → poll status / result_url
  POST   /api/wizard/upsell-cinematic → route selected option to Magic Hour
  GET    /api/wizard/bgm-catalog      → list BGM tracks for the swap-BGM edit

Instant Reel composition (zero MH credits):
  1. Download 4 Pixabay images (vertical 9:16)
  2. Animate each via ffmpeg zoompan (ken-burns) → 2.5s clip
  3. Concat the 4 clips → 10s silent video
  4. Generate TTS from script (voice+style+rate/pitch)
  5. Mix TTS (voice, 0dB) + BGM (-15dB ducked) → 10s audio
  6. Mux audio onto video → final MP4
"""
from __future__ import annotations
import asyncio
import logging
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

from core.creator_pipeline import generate_3_options, pick_bgm
from core import pixabay
from core.bgm_catalog import get_catalog, serve_url as bgm_serve_url
from core.mh_guardrails import can_spend
from core.config import DB_NAME

load_dotenv()

log = logging.getLogger('wizard')
router = APIRouter(prefix='/api/wizard', tags=['wizard'])

MONGO_URL = os.environ['MONGO_URL']
_client = AsyncIOMotorClient(MONGO_URL)
db = _client[DB_NAME]

UPLOAD_DIR = Path('/app/backend/uploads')
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
BGM_DIR = Path('/app/backend/static/bgm')


# ---------------- Schemas ----------------
class PromptsRequest(BaseModel):
    idea: str = Field(..., min_length=3, max_length=400)
    # Sprint 30e: target language for the spoken script.
    # 'english' | 'hindi' | 'hinglish'. Default 'english' for back-compat.
    lang: Optional[str] = 'english'


class PreviewImagesRequest(BaseModel):
    image_query: str = Field(..., min_length=2, max_length=120)
    count: int = 5


class PreviewVideosRequest(BaseModel):
    video_query: str = Field(..., min_length=2, max_length=120)
    count: int = 5


class CreateReelRequest(BaseModel):
    idea: Optional[str] = None
    title: Optional[str] = None
    script: str = Field(..., min_length=3)
    image_query: str = Field(..., min_length=2)
    images: Optional[list[str]] = None      # optional pre-selected image URLs (overrides query fetch)
    # NEW Phase-1: choose visual source
    mode: str = 'images'                    # 'images' (Nano-Banana / Pixabay images) | 'video' (Pixabay stock video)
    bg_video_url: Optional[str] = None      # explicit Pixabay video file URL (overrides query fetch)
    total_duration: float = 10.0            # used for 'video' mode (clipped/looped to this length)
    voice_id: str = 'en-US-JennyNeural'
    voice_style: Optional[str] = 'story'
    voice_rate: Optional[str] = None
    voice_pitch: Optional[str] = None
    music_mood: str = 'cinematic_epic'
    bgm_url: Optional[str] = None            # explicit BGM override (/api/serve-file/…)
    motion: str = 'ken_burns'
    aspect_ratio: str = '9:16'
    duration_per_shot: float = 2.5
    # NEW Sprint 30 — Creative Plan Engine wiring. When set, the worker will
    # fetch the plan from `creative_plans` collection and use:
    #   • plan.script[]         → spoken voiceover (joined)
    #   • plan.scene_keywords[] → ONE Pixabay video per scene (concat)
    #   • plan.voice_style      → TTS emotion preset (mapped)
    #   • plan.bgm_style        → BGM picker (keyword match)
    creative_plan_id: Optional[str] = None
    # Sprint 30d: tier-aware voice routing. Frontend sends the logged-in
    # user's subscription_tier so the backend can auto-route premium users
    # to Sarvam Bulbul-v2 for Indic content. Defaults to 'free'.
    user_tier: Optional[str] = 'free'
    # Optional explicit hint from the frontend that the script is in an
    # Indic language (Hindi/Hinglish/Tamil/etc). Empty → auto-detect from text.
    lang: Optional[str] = None


class UpsellRequest(BaseModel):
    script: str
    image_path: Optional[str] = None
    voice_id: str = 'en-US-JennyNeural'
    motion: str = 'ken_burns'
    duration: int = 5
    aspect_ratio: str = '9:16'


# ---------------- Helpers ----------------
async def _download_img(url: str, out_dir: Path, attempts: int = 3) -> Optional[Path]:
    last_err = None
    for i in range(attempts):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), follow_redirects=True) as c:
                r = await c.get(url)
                if r.status_code == 200 and len(r.content) >= 500:
                    ext = '.jpg'
                    if '.png' in url.lower():
                        ext = '.png'
                    out = out_dir / f'wimg_{uuid.uuid4().hex[:10]}{ext}'
                    out.write_bytes(r.content)
                    return out
                last_err = f'status={r.status_code} len={len(r.content)}'
        except Exception as e:
            last_err = str(e)
        # backoff
        await asyncio.sleep(0.4 * (i + 1))
    log.warning('download_img failed after %d attempts: %s url=%s', attempts, last_err, url[:120])
    return None


async def _download_video(url: str, out_dir: Path, attempts: int = 3) -> Optional[Path]:
    """Download a Pixabay stock video to a local mp4 path."""
    last_err = None
    for i in range(attempts):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0), follow_redirects=True) as c:
                r = await c.get(url)
                if r.status_code == 200 and len(r.content) >= 5000:
                    ext = '.mp4'
                    low = url.lower().split('?')[0]
                    if low.endswith('.mov'):
                        ext = '.mov'
                    out = out_dir / f'wvid_{uuid.uuid4().hex[:10]}{ext}'
                    out.write_bytes(r.content)
                    return out
                last_err = f'status={r.status_code} len={len(r.content)}'
        except Exception as e:
            last_err = str(e)
        await asyncio.sleep(0.6 * (i + 1))
    log.warning('download_video failed after %d attempts: %s url=%s', attempts, last_err, url[:120])
    return None


def _normalize_image(src: Path, target_w: int, target_h: int) -> Path:
    """Normalize to target WxH portrait JPG (used before motion)."""
    try:
        from PIL import Image
        img = Image.open(src).convert('RGB')
        # scale to cover target
        sw, sh = img.size
        scale = max(target_w / sw, target_h / sh)
        nw, nh = int(sw * scale), int(sh * scale)
        img = img.resize((nw, nh), Image.LANCZOS)
        x = (nw - target_w) // 2
        y = (nh - target_h) // 2
        img = img.crop((x, y, x + target_w, y + target_h))
        out = src.with_suffix('.norm.jpg')
        img.save(out, 'JPEG', quality=88)
        return out
    except Exception:
        return src


# --------------------- Creative Plan Engine helpers (Sprint 30) -------------
# Maps the LLM's free-form voice_style description (e.g. "devotional warm slow")
# to the closest VOICE_STYLES preset id used by core.constants. This is what
# generate_tts_audio actually consumes.
_VOICE_STYLE_KEYWORDS = {
    'devotional': 'devotional',
    'spiritual':  'devotional',
    'sacred':     'devotional',
    'prayer':     'devotional',
    'motivat':    'motivation',
    'energ':      'motivation',
    'powerful':   'motivation',
    'inspir':     'motivation',
    'epic':       'motivation',
    'confident':  'motivation',
    'funny':      'funny',
    'playful':    'funny',
    'comedy':     'funny',
    'story':      'story',
    'narrat':     'story',
    'cinematic':  'story',
    'warm':       'story',
    'emotion':    'story',
    'romantic':   'story',
}

def _map_voice_style(llm_style: Optional[str], fallback: str = 'story') -> str:
    """Map free-form LLM voice_style → VOICE_STYLES preset id."""
    if not llm_style:
        return fallback
    s = llm_style.lower()
    for kw, preset in _VOICE_STYLE_KEYWORDS.items():
        if kw in s:
            return preset
    return fallback


_BGM_MOOD_KEYWORDS = {
    'devotional':       'devotional_peaceful',
    'classical flute':  'devotional_peaceful',
    'flute':            'devotional_peaceful',
    'spiritual':        'devotional_peaceful',
    'temple':           'devotional_peaceful',
    'chant':            'devotional_uplifting',
    'cinematic':        'cinematic_epic',
    'orchestral':       'cinematic_epic',
    'epic':             'cinematic_epic',
    'dramatic':         'cinematic_epic',
    'lofi':             'ambient_chill',
    'chill':            'ambient_chill',
    'ambient':          'ambient_chill',
    'lounge':           'ambient_chill',
    'electronic':       'energetic_pump',
    'energetic':        'energetic_pump',
    'pump':             'energetic_pump',
    'workout':          'energetic_pump',
    'romantic':         'romantic_soft',
    'soft':             'romantic_soft',
    'piano':            'emotional_piano',
    'emotional':        'emotional_strings',
    'sad':              'emotional_strings',
    'festive':          'festive_celebration',
    'celebration':      'festive_celebration',
    'upbeat':           'upbeat_funny',
    'funny':            'upbeat_funny',
    'suspense':         'suspense_buildup',
    'mystery':          'suspense_buildup',
    'nostalgic':        'nostalgic_warm',
    'warm':             'nostalgic_warm',
}

def _map_bgm_style(llm_bgm_style: Optional[str], fallback: str = 'cinematic_epic') -> str:
    """Map free-form LLM bgm_style → music_mood id used by pick_bgm()."""
    if not llm_bgm_style:
        return fallback
    s = llm_bgm_style.lower()
    for kw, mood in _BGM_MOOD_KEYWORDS.items():
        if kw in s:
            return mood
    return fallback


async def _fetch_video_for_keyword(query: str, work_dir: Path,
                                    target_w: int, target_h: int,
                                    duration: float, idx: int) -> Optional[Path]:
    """Fetch ONE Pixabay video for a keyword query, normalize/clip to target size+duration.
    Returns the path to the rendered clip (or None on failure)."""
    try:
        hits = await pixabay.search_videos(query, count=4)
    except Exception:
        return None
    candidates = []
    for h in hits:
        vids = h.get('videos') or {}
        for q in ('large', 'medium', 'small', 'tiny'):
            v = vids.get(q) or {}
            url = v.get('url')
            w, ht = int(v.get('width') or 0), int(v.get('height') or 0)
            if url and w and ht:
                candidates.append({'url': url, 'w': w, 'h': ht, 'is_vertical': ht > w})
                break
    if not candidates:
        return None
    candidates.sort(key=lambda c: (not c['is_vertical'], -min(c['w'], c['h'])))
    pick = candidates[0]
    src = await _download_video(pick['url'], work_dir)
    if not src:
        return None
    out = work_dir / f'scene_{idx:02d}.mp4'
    vf = (
        f'scale={target_w*2}:{target_h*2}:force_original_aspect_ratio=increase,'
        f'crop={target_w}:{target_h},'
        f'scale={target_w}:{target_h},'
        f'format=yuv420p'
    )
    cmd = [
        '/usr/bin/ffmpeg', '-y',
        '-stream_loop', '-1',
        '-i', str(src),
        '-t', f'{duration:.3f}',
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22',
        '-pix_fmt', 'yuv420p', '-r', '25',
        '-an',
        str(out),
    ]
    try:
        r = await asyncio.to_thread(subprocess.run, cmd, capture_output=True,
                                     timeout=max(60, int(duration * 14)))
        if r.returncode == 0 and out.exists() and out.stat().st_size > 1000:
            return out
    except Exception:
        pass
    return None


MOTION_EXPR = {
    'ken_burns': {
        'z': 'min(zoom+0.0015,1.3)',
        'x': 'iw/2-(iw/zoom/2)',
        'y': 'ih/2-(ih/zoom/2)',
    },
    'zoom_in': {
        'z': 'min(zoom+0.0025,1.4)',
        'x': 'iw/2-(iw/zoom/2)',
        'y': 'ih/2-(ih/zoom/2)',
    },
    'zoom_out': {
        'z': 'if(lte(zoom,1.0),1.4,max(1.0,zoom-0.0025))',
        'x': 'iw/2-(iw/zoom/2)',
        'y': 'ih/2-(ih/zoom/2)',
    },
    'pan_right': {
        'z': '1.25',
        'x': '(iw-iw/zoom)*on/{D}',
        'y': 'ih/2-(ih/zoom/2)',
    },
    'pan_left': {
        'z': '1.25',
        'x': '(iw-iw/zoom)*(1-on/{D})',
        'y': 'ih/2-(ih/zoom/2)',
    },
    'cinematic_zoom': {
        'z': 'min(zoom+0.002,1.35)',
        'x': 'iw/2-(iw/zoom/2)',
        'y': 'ih/2-(ih/zoom/2)',
    },
}


def _render_motion_clip(src: Path, motion_id: str, duration: float,
                         target_w: int, target_h: int, out: Path) -> Optional[Path]:
    """Render a motion clip at arbitrary target WxH (supports portrait 9:16)."""
    expr = MOTION_EXPR.get(motion_id) or MOTION_EXPR['ken_burns']
    fps = 25
    dur = max(1.0, float(duration))
    total_frames = int(round(dur * fps))
    z = expr['z']
    x = expr['x'].replace('{D}', str(total_frames))
    y = expr['y'].replace('{D}', str(total_frames))
    scale_w, scale_h = int(target_w * 1.5), int(target_h * 1.5)
    vf = (
        f'scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,'
        f'crop={scale_w}:{scale_h},'
        f"zoompan=z='{z}':x='{x}':y='{y}':d={total_frames}:s={target_w}x{target_h}:fps={fps},"
        f'format=yuv420p'
    )
    cmd = [
        '/usr/bin/ffmpeg', '-y',
        '-loop', '1', '-i', str(src),
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22',
        '-pix_fmt', 'yuv420p', '-r', str(fps),
        '-frames:v', str(total_frames),
        str(out),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=max(30, int(dur * 12)))
        if r.returncode == 0 and out.exists() and out.stat().st_size > 1000:
            return out
        log.warning('motion(%s) fail: %s', motion_id, r.stderr[-200:].decode(errors='ignore') if r.stderr else '')
    except Exception as e:
        log.warning('motion(%s) exc: %s', motion_id, e)
    return None


async def _concat_with_xfade(scene_paths: list[Path], scene_durations: list[float],
                              out_path: Path, target_w: int, target_h: int,
                              transition_dur: float = 0.4) -> bool:
    """Multi-Scene Story Engine — concat N scene clips with cinematic xfade
    transitions between every pair, plus a uniform colour grade so the reel
    feels like one cohesive story rather than stitched stock clips.

    Returns True on success, False on failure (caller should fall back to a
    plain concat).
    """
    n = len(scene_paths)
    if n < 2:
        return False
    # Build filter graph:  [0:v]eq=…[v0]; [1:v]eq=…[v1]; …
    # then xfade chain:    [v0][v1]xfade=fade:offset=t1[v01]; [v01][v2]xfade=…
    inputs: list[str] = []
    filt_parts: list[str] = []
    # Per-scene normalisation + uniform colour grade (slight saturation +
    # contrast bump) so every clip has the same look.
    for i in range(n):
        inputs += ['-i', str(scene_paths[i])]
        filt_parts.append(
            f'[{i}:v]'
            f'scale={target_w}:{target_h}:force_original_aspect_ratio=increase,'
            f'crop={target_w}:{target_h},setsar=1,'
            f'eq=saturation=1.10:contrast=1.05:gamma=1.02,'
            f'format=yuv420p[v{i}]'
        )
    # Compute cumulative offsets where each xfade starts.
    # Effective playback length per scene after a fade = scene_dur - fade_dur
    # (because the fade overlaps the next clip).
    cur_offset = scene_durations[0] - transition_dur
    last_label = 'v0'
    for i in range(1, n):
        next_label = f'x{i}'
        filt_parts.append(
            f'[{last_label}][v{i}]xfade=transition=fade:'
            f'duration={transition_dur:.3f}:offset={cur_offset:.3f}[{next_label}]'
        )
        last_label = next_label
        cur_offset += scene_durations[i] - transition_dur
    filter_complex = ';'.join(filt_parts)
    cmd = [
        '/usr/bin/ffmpeg', '-y',
        *inputs,
        '-filter_complex', filter_complex,
        '-map', f'[{last_label}]',
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22',
        '-pix_fmt', 'yuv420p', '-r', '25',
        '-an',
        str(out_path),
    ]
    try:
        r = await asyncio.to_thread(
            subprocess.run, cmd, capture_output=True,
            timeout=max(120, int(sum(scene_durations) * 14)),
        )
        if r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 1000:
            return True
        log.warning('xfade concat failed: %s', r.stderr[-300:].decode(errors='ignore') if r.stderr else '')
    except Exception as e:
        log.warning('xfade concat exc: %s', e)
    return False


def _update_job(job_id: str, **patch):
    # fire-and-forget async update from a sync context
    async def _do():
        patch['updated_at'] = datetime.now(timezone.utc).isoformat()
        await db.wizard_jobs.update_one({'job_id': job_id}, {'$set': patch}, upsert=True)
    try:
        asyncio.get_event_loop().create_task(_do())
    except RuntimeError:
        asyncio.run(_do())


async def _async_update_job(job_id: str, **patch):
    patch['updated_at'] = datetime.now(timezone.utc).isoformat()
    await db.wizard_jobs.update_one({'job_id': job_id}, {'$set': patch}, upsert=True)


# ---------------- Endpoints ----------------
@router.post('/prompts')
async def post_prompts(req: PromptsRequest, request: Request):
    """Generate 3 structured prompt options from a user idea.

    Sprint 30e — `lang` (english|hindi|hinglish) is now plumbed through to
    Gemini so the spoken script comes back in the user's chosen language.
    Without this, "Krishna bhajan" + Hindi UI selection still produced an
    English script (which then routed to an English voice — wrong).
    """
    # Moderation gate (text) — Session 37 Sprint 3: auto-strikes via moderate_and_enforce.
    from core.moderation import moderate_and_enforce
    await moderate_and_enforce(req.idea, request=request, source='wizard.idea')
    opts = await generate_3_options(req.idea, lang=req.lang or 'english')
    if not opts:
        raise HTTPException(status_code=502, detail='LLM did not return options. Try again.')
    return {'idea': req.idea, 'options': opts, 'count': len(opts), 'lang': req.lang}


@router.post('/preview-images')
async def post_preview_images(req: PreviewImagesRequest):
    """Search Pixabay for vertical images matching the query."""
    hits = await pixabay.search_images(req.image_query, count=max(3, min(req.count, 15)), orientation='vertical')
    imgs = []
    for h in hits:
        url = h.get('largeImageURL') or h.get('webformatURL')
        if url:
            imgs.append({
                'url': url,
                'preview': h.get('previewURL') or h.get('webformatURL') or url,
                'tags': h.get('tags', ''),
                'user': h.get('user', ''),
                'width': h.get('imageWidth'),
                'height': h.get('imageHeight'),
            })
    return {'query': req.image_query, 'images': imgs, 'source': 'stock'}


# =============================================================================
#  Phase D2 — AI scene image generation (gpt-image-1 via Emergent LLM Key)
# =============================================================================
#
# POST /api/wizard/ai-images
#   Body: { image_query: str, count?: int=3, aspect?: "9:16"|"1:1"|"16:9",
#           style_hint?: str, quality?: "low"|"medium"|"high" }
#
# Returns the SAME shape as /preview-images so the FE can swap between
# stock ↔ AI without parsing two response schemas. Generated PNGs are
# cached to disk under /app/backend/uploads/ai_scene/ by sha256(prompt|style|aspect)
# so repeating the same query is free. Tier-gated: free & starter fall
# back to stock (not exposed here — FE shouldn't show the button for them).


class AiImagesRequest(BaseModel):
    image_query: str = Field(..., min_length=3, max_length=300)
    count: int = 3
    aspect: Optional[str] = '9:16'    # '9:16' | '1:1' | '16:9'
    style_hint: Optional[str] = None  # e.g. 'cinematic', 'aesthetic', 'documentary'
    quality: Optional[str] = 'medium'  # 'low' | 'medium' | 'high' (maps to gpt-image-1)


_AI_SCENE_DIR = Path('/app/backend/uploads/ai_scene')
_AI_SCENE_DIR.mkdir(parents=True, exist_ok=True)


def _ai_aspect_to_size(aspect: str) -> str:
    """gpt-image-1 supports 1024x1024, 1024x1536, 1536x1024."""
    a = (aspect or '9:16').strip()
    if a == '1:1':  return '1024x1024'
    if a == '16:9': return '1536x1024'
    return '1024x1536'   # default to 9:16 portrait (reel default)


def _ai_tier_allowed(tier: str) -> bool:
    return (tier or 'free').lower() in ('creator', 'pro', 'elite')


async def _resolve_ai_user(request: Request) -> dict:
    """Read user tier from JWT if present; default to free otherwise."""
    try:
        from core.auth import decode_token  # type: ignore
        auth = (request.headers.get('authorization') or '').strip()
        if auth.lower().startswith('bearer '):
            tok = auth.split(' ', 1)[1].strip()
            data = decode_token(tok)
            if data and data.get('sub'):
                u = await db.users.find_one({'id': data['sub']}, {'_id': 0, 'password_hash': 0})
                if u:
                    return {
                        'id': u.get('id'),
                        'tier': (u.get('subscription_tier') or 'free').lower(),
                    }
    except Exception:
        pass
    return {'id': None, 'tier': 'free'}


@router.post('/ai-images')
async def post_ai_images(req: AiImagesRequest, request: Request):
    """Generate 1-4 scene images via gpt-image-1. Creator+/Pro only.

    Returns same shape as /preview-images so the FE can swap stock ↔ AI
    without parsing two response schemas.
    """
    user = await _resolve_ai_user(request)
    if not _ai_tier_allowed(user['tier']):
        raise HTTPException(status_code=403, detail={
            'code': 'tier_locked',
            'message': 'AI-generated visuals are available on Creator and Pro plans. '
                       'Upgrade to unlock premium unique imagery for your scenes.',
            'tier': user['tier'],
            'required_tier': 'creator',
        })

    api_key = os.environ.get('EMERGENT_LLM_KEY') or os.environ.get('OPENAI_API_KEY')
    if not api_key:
        raise HTTPException(status_code=503, detail='AI image generation not configured.')

    count = max(1, min(int(req.count or 3), 4))
    aspect = (req.aspect or '9:16').strip()
    size = _ai_aspect_to_size(aspect)
    style_hint = (req.style_hint or '').strip()

    # Lightly enrich the prompt so gpt-image-1 produces scene-appropriate
    # reel visuals, not portraits.
    base_prompt = req.image_query.strip()
    style_modifiers = {
        'cinematic': 'cinematic wide-angle shot, dramatic lighting, rich contrast, shallow depth of field, 35mm film look',
        'aesthetic': 'soft aesthetic warm tones, golden hour lighting, dreamy atmosphere, pastel palette, magazine-editorial quality',
        'documentary': 'natural candid documentary-style photograph, realistic, unposed, authentic textures, photojournalism look',
        'handheld':   'natural handheld shot, motion blur edges, authentic lifestyle feel',
        'meme':       'bright saturated pop art meme aesthetic, playful, high-contrast internet-culture vibe',
    }
    style_suffix = style_modifiers.get(style_hint, 'high-quality photograph, vertical composition, reel-ready visual')
    enriched = (
        f"{base_prompt}. {style_suffix}. "
        f"Vertical {aspect} aspect ratio composition, no text overlay, no logos, no watermarks, "
        f"no human faces overlay text, production-ready social-media reel visual."
    )

    # Cache key — same prompt+size+style returns cached files
    import hashlib
    cache_root = _AI_SCENE_DIR / hashlib.sha256(f"{enriched}|{size}".encode()).hexdigest()[:16]
    cache_root.mkdir(parents=True, exist_ok=True)

    existing = sorted(cache_root.glob('img_*.png'))
    imgs: list[dict] = []

    # Import the generator lazily so failures don't take the whole route module down
    try:
        from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration
    except Exception as e:
        raise HTTPException(status_code=503, detail=f'AI image module unavailable: {e}')

    tokens_used = 0
    if len(existing) >= count:
        chosen = existing[:count]
        cached = True
    else:
        # Need to generate new ones
        gen = OpenAIImageGeneration(api_key=api_key)
        try:
            images = await gen.generate_images(
                prompt=enriched,
                model='gpt-image-1',
                number_of_images=count,
            )
        except Exception as e:
            log.exception('ai-images: generation failed: %s', e)
            raise HTTPException(status_code=502, detail=f'AI image generation failed: {e}')

        # Write bytes to disk
        saved_paths: list[Path] = []
        for idx, img_bytes in enumerate(images):
            if not img_bytes:
                continue
            p = cache_root / f'img_{idx:02d}_{uuid.uuid4().hex[:6]}.png'
            p.write_bytes(img_bytes)
            saved_paths.append(p)
        chosen = saved_paths[:count]
        tokens_used = count * 1500   # approximate, gpt-image-1 is priced per image
        cached = False

    # Build URL list. We return RELATIVE /api/serve-file URLs so that the
    # frontend resolves against its own origin (works with the reverse-proxy
    # that routes /api/* to this backend) — returning localhost:8001 URLs
    # would 404 in the browser preview.
    for p in chosen:
        url = f'/api/serve-file/{p.name}'
        imgs.append({
            'url': url,
            'preview': url,
            'tags': style_hint or 'ai-generated',
            'user': 'MagiCAi AI',
            'width': int(size.split('x')[0]),
            'height': int(size.split('x')[1]),
            'ai_generated': True,
        })

    return {
        'query': req.image_query,
        'images': imgs,
        'source': 'ai',
        'cached': cached,
        'tokens_used': tokens_used,
        'tier': user['tier'],
        'style_hint': style_hint or 'default',
    }


@router.get('/ai-images/health')
async def ai_images_health():
    return {
        'ok': True,
        'llm_key_configured': bool(
            os.environ.get('EMERGENT_LLM_KEY') or os.environ.get('OPENAI_API_KEY')
        ),
        'model': 'gpt-image-1',
        'tier_gate': 'creator+',
    }


@router.post('/preview-videos')
async def post_preview_videos(req: PreviewVideosRequest):
    """Search Pixabay for stock videos matching the query.
    Returns vertical-first list with playable .mp4 URLs and thumbnails."""
    hits = await pixabay.search_videos(req.video_query, count=max(3, min(req.count, 12)))
    vids = []
    for h in hits:
        videos = h.get('videos') or {}
        # Pixabay returns dict with keys: large/medium/small/tiny → {url,width,height,size}
        candidates = []
        for q in ('large', 'medium', 'small', 'tiny'):
            v = videos.get(q) or {}
            url = v.get('url')
            w, ht = int(v.get('width') or 0), int(v.get('height') or 0)
            if url and w and ht:
                candidates.append({'quality': q, 'url': url, 'width': w, 'height': ht, 'is_vertical': ht > w})
        if not candidates:
            continue
        # Prefer vertical, then highest quality (largest min-dim)
        candidates.sort(key=lambda c: (not c['is_vertical'], -min(c['width'], c['height'])))
        best = candidates[0]
        pic_id = h.get('picture_id')
        thumb = f"https://i.vimeocdn.com/video/{pic_id}_295x166.jpg" if pic_id else None
        vids.append({
            'id': h.get('id'),
            'url': best['url'],
            'thumbnail': thumb,
            'width': best['width'],
            'height': best['height'],
            'is_vertical': best['is_vertical'],
            'duration': h.get('duration'),
            'tags': h.get('tags', ''),
            'user': h.get('user', ''),
        })
    return {'query': req.video_query, 'videos': vids}


@router.get('/bgm-catalog')
async def get_bgm_catalog():
    cat = get_catalog()
    return {
        'tracks': [
            {
                'id': t['id'],
                'name': t.get('description', t['id']).split('.')[0][:60],
                'mood': t.get('mood'),
                'bpm': t.get('bpm'),
                'url': bgm_serve_url(t),
            }
            for t in cat
        ]
    }


@router.post('/create-reel')
async def post_create_reel(req: CreateReelRequest, background: BackgroundTasks, request: Request):
    # Moderation gate (text) — block obscene / abusive / unsafe content before
    # we spend any compute or LLM/Pixabay credits.
    from core.moderation import moderate_text, raise_if_blocked
    for src, txt in (('idea', req.idea), ('title', req.title), ('script', req.script), ('image_query', req.image_query)):
        if txt:
            raise_if_blocked(await moderate_text(txt, source=f'wizard.{src}'))

    job_id = f'wz_{uuid.uuid4().hex[:12]}'
    now = datetime.now(timezone.utc).isoformat()
    # Attribute to user if present on request.state
    user_id = getattr(request.state, 'user_id', None) or 'guest'
    await db.wizard_jobs.insert_one({
        'job_id': job_id,
        'user_id': user_id,
        'status': 'queued',
        'progress': 0,
        'stage': 'queued',
        'idea': req.idea,
        'title': req.title or (req.idea or 'Instant Reel')[:60],
        'script': req.script,
        'image_query': req.image_query,
        'voice_id': req.voice_id,
        'voice_style': req.voice_style,
        'music_mood': req.music_mood,
        'motion': req.motion,
        'aspect_ratio': req.aspect_ratio,
        'created_at': now,
        'updated_at': now,
        'result_url': None,
        'error': None,
    })
    background.add_task(_process_reel, job_id, req.dict())
    return {'job_id': job_id, 'status': 'queued'}


@router.get('/job/{job_id}')
async def get_job(job_id: str):
    j = await db.wizard_jobs.find_one({'job_id': job_id}, {'_id': 0})
    if not j:
        raise HTTPException(status_code=404, detail='Job not found')
    return j


@router.post('/upsell-cinematic')
async def post_upsell(req: UpsellRequest, request: Request):
    """Gate the MH upsell through the circuit breaker."""
    # Rough MH credit cost estimate (image_to_video ~10 cr/s)
    needed = max(10, int(req.duration * 10))
    user_id = getattr(request.state, 'user_id', None) or 'guest'
    # assume pro-tier default quota unless we know better
    chk = await can_spend(db, user_id, needed, user_monthly_quota=500)
    if not chk.get('allowed'):
        return {'ok': False, 'reason': chk.get('reason'), 'queued': chk.get('queued', False)}
    # We don't actually kick the MH job here — frontend uses the existing
    # /api/create-image-to-video endpoint. This route simply confirms the
    # user is within budget so the CTA can be enabled.
    return {'ok': True, 'estimated_credits': needed, **chk}


# ---------------- Assembly worker ----------------
async def _process_reel(job_id: str, req: dict):
    """Background worker: download images → motion clips → concat → TTS → BGM → mux.
    Phase-1 extension: when ``mode == 'video'`` skip the image/animate/concat
    stages and use a Pixabay stock video as the visual track instead.
    Sprint 30: when ``creative_plan_id`` is provided, the worker fetches the
    Creative Plan (hook + script[] + scene_keywords[] + voice_style + bgm_style)
    and:
      • joins script[] into the spoken voiceover
      • fetches ONE Pixabay video PER scene_keyword (concat for video mode)
      • maps voice_style → TTS preset
      • maps bgm_style → BGM mood
    """
    try:
        # ============================================================
        # Sprint 30 — Pull Creative Plan (if any) and override req
        # ============================================================
        scene_keywords: list[str] = []
        plan_doc: Optional[dict] = None
        cp_id = req.get('creative_plan_id')
        if cp_id:
            try:
                plan_doc = await db.creative_plans.find_one({'creative_plan_id': cp_id})
            except Exception as e:
                log.warning('wizard: creative-plan lookup failed: %s', e)
            if plan_doc:
                # Compose voiceover: hook + script lines (joined with sentence pauses)
                hook = (plan_doc.get('hook') or '').strip()
                lines = plan_doc.get('script') or []
                if isinstance(lines, list):
                    voiceover = ' '.join([hook] + [str(s).strip() for s in lines if s])
                else:
                    voiceover = hook or req.get('script', '')
                if voiceover:
                    req['script'] = voiceover
                # scene_keywords drives Pixabay search (multi-scene concat)
                sk = plan_doc.get('scene_keywords') or []
                if isinstance(sk, list) and sk:
                    scene_keywords = [str(s).strip() for s in sk if s]
                # voice_style → TTS preset
                vs = plan_doc.get('voice_style')
                if vs:
                    req['voice_style'] = _map_voice_style(vs, fallback=req.get('voice_style') or 'story')
                # language → auto-pick a matching neural voice if user kept the default
                # English voice (so Hindi/Hinglish scripts get a Hindi neural voice
                # that can actually pronounce them).
                plan_lang = (plan_doc.get('language') or '').lower()
                cur_voice = req.get('voice_id') or 'en-US-JennyNeural'
                # Default English voices that should be auto-swapped when language
                # is Hindi/Hinglish — but respect any explicit Hindi voice the
                # user may have already chosen.
                if plan_lang in ('hindi', 'hinglish') and cur_voice.startswith('en-'):
                    # Prefer male voice for devotional/motivation, female for
                    # story/funny.
                    style_id = req.get('voice_style') or 'story'
                    if style_id in ('devotional', 'motivation'):
                        req['voice_id'] = 'hi-IN-MadhurNeural'
                    else:
                        req['voice_id'] = 'hi-IN-SwaraNeural'
                    log.info('wizard: auto-switched voice to Hindi %s for plan_lang=%s', req['voice_id'], plan_lang)
                # bgm_style → music_mood
                bs = plan_doc.get('bgm_style')
                if bs:
                    req['music_mood'] = _map_bgm_style(bs, fallback=req.get('music_mood') or 'cinematic_epic')
                # total_duration: use plan.duration if not explicitly set
                if plan_doc.get('duration') and not req.get('total_duration'):
                    req['total_duration'] = float(plan_doc['duration'])
                # Propagate plan language up to the request so the non-plan
                # code paths below (and select_voice_for_tier) can use it.
                if plan_doc.get('language') and not req.get('lang'):
                    req['lang'] = plan_doc['language']
                log.info(
                    'wizard: applied creative_plan %s — voice_style=%s music_mood=%s scenes=%d',
                    cp_id, req.get('voice_style'), req.get('music_mood'), len(scene_keywords),
                )

        # Sprint 30e — Lang-aware voice swap (works for BOTH creative-plan AND
        # option-based paths). If user picked Hindi/Hinglish but the voice_id
        # is still defaulted to an English Edge voice, swap to a Hindi neural
        # voice that can actually pronounce Devanagari. select_voice_for_tier()
        # below will then promote Premium users to Sarvam Bulbul-v2.
        cur_voice = req.get('voice_id') or 'en-US-JennyNeural'
        req_lang = (req.get('lang') or '').lower()
        if req_lang in ('hindi', 'hinglish') and cur_voice.startswith('en-'):
            style_id = req.get('voice_style') or 'story'
            if style_id in ('devotional', 'motivation'):
                req['voice_id'] = 'hi-IN-MadhurNeural'
            else:
                req['voice_id'] = 'hi-IN-SwaraNeural'
            log.info('wizard: auto-switched voice to Hindi %s for lang=%s (no plan path)', req['voice_id'], req_lang)

        mode = (req.get('mode') or 'images').lower()
        work_dir = UPLOAD_DIR / f'wz_{job_id}'
        work_dir.mkdir(parents=True, exist_ok=True)

        if req.get('aspect_ratio') == '9:16':
            target_w, target_h = 720, 1280
        else:
            target_w, target_h = 1280, 720

        silent_video: Optional[Path] = None
        total_dur: float = 0.0
        image_urls_used: list[str] = []
        bg_video_used: Optional[str] = None

        # ===========================================================
        # MODE A1: Creative Plan multi-scene VIDEO (1 Pixabay clip per scene)
        # ===========================================================
        if mode == 'video' and scene_keywords:
            await _async_update_job(job_id, status='processing', stage='fetch_scenes',
                                     progress=10, scene_count=len(scene_keywords))
            total_dur = float(req.get('total_duration') or 10.0)
            per_scene_dur = max(2.0, total_dur / max(1, len(scene_keywords)))
            scene_paths: list[Path] = []
            for idx, kw in enumerate(scene_keywords):
                clip = await _fetch_video_for_keyword(
                    kw, work_dir, target_w, target_h, per_scene_dur, idx,
                )
                if clip:
                    scene_paths.append(clip)
                await _async_update_job(
                    job_id, stage='fetch_scenes',
                    progress=10 + int(30 * (idx + 1) / max(1, len(scene_keywords))),
                )
            # Need at least 2 scene clips to keep the multi-scene concat coherent;
            # otherwise fall back to single-video mode below.
            if len(scene_paths) >= 2:
                silent_video = work_dir / 'silent.mp4'
                # Per-scene actual duration list (clips were trimmed to per_scene_dur,
                # but we use the requested duration to schedule xfade offsets).
                durations = [per_scene_dur for _ in scene_paths]
                # Multi-Scene Story Engine: try xfade transitions + uniform colour
                # grade first. If that fails (e.g. ffmpeg filter graph error),
                # fall back to a plain concat demuxer.
                ok = await _concat_with_xfade(scene_paths, durations, silent_video,
                                               target_w, target_h, transition_dur=0.4)
                if not ok:
                    log.info('wizard: xfade concat fell through — using plain concat')
                    concat_list = work_dir / 'concat_scenes.txt'
                    with open(concat_list, 'w') as f:
                        for cp in scene_paths:
                            f.write(f"file '{cp}'\n")
                    concat_cmd = [
                        '/usr/bin/ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                        '-i', str(concat_list),
                        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-an',
                        str(silent_video),
                    ]
                    r = await asyncio.to_thread(subprocess.run, concat_cmd, capture_output=True, timeout=240)
                    if r.returncode != 0 or not silent_video.exists():
                        log.warning('wizard: scene concat failed — falling back to single-video mode')
                        silent_video = None
                # On xfade success: account for transition overlap shaving total.
                if silent_video is not None:
                    if ok:
                        # xfade overlap shaves (n-1)*0.4s from total
                        total_dur = sum(durations) - 0.4 * (len(scene_paths) - 1)
                    else:
                        total_dur = per_scene_dur * len(scene_paths)
                    bg_video_used = f'multi_scene[{len(scene_paths)}{"+xfade" if ok else ""}]'
            else:
                log.warning('wizard: only %d scene clips fetched — falling back to single-video mode',
                            len(scene_paths))

        # ===========================================================
        # MODE A: Pixabay STOCK VIDEO (Phase-1, default for "Quick Reel")
        # ===========================================================
        if silent_video is None and mode == 'video':
            await _async_update_job(job_id, status='processing', stage='fetch_video', progress=10)
            bg_video_url = req.get('bg_video_url')
            # Fetch a vertical-first Pixabay video for the query
            if not bg_video_url:
                hits = await pixabay.search_videos(req['image_query'], count=8)
                # Try with original query first; if no vertical results, fall back to any
                vertical_first = []
                any_video = []
                for h in hits:
                    videos = h.get('videos') or {}
                    for q in ('large', 'medium', 'small', 'tiny'):
                        v = videos.get(q) or {}
                        url = v.get('url')
                        w, ht = int(v.get('width') or 0), int(v.get('height') or 0)
                        if url and w and ht:
                            entry = {'url': url, 'w': w, 'h': ht, 'is_vertical': ht > w}
                            (vertical_first if entry['is_vertical'] else any_video).append(entry)
                            break  # take the first available quality per hit
                pick = (vertical_first or any_video)[:1]
                if pick:
                    bg_video_url = pick[0]['url']

            if not bg_video_url:
                # Hard fallback: degrade to image mode so user still gets a reel
                log.warning('wizard: no Pixabay video for query "%s" — falling back to image mode', req.get('image_query'))
                mode = 'images'
            else:
                bg_video_used = bg_video_url
                bg_path = await _download_video(bg_video_url, work_dir)
                if not bg_path:
                    await _async_update_job(job_id, status='failed', error='Pixabay video download failed.', progress=100)
                    return

                await _async_update_job(job_id, stage='process_video', progress=40)
                total_dur = float(req.get('total_duration') or 10.0)
                # Scale + center-crop to portrait (or landscape) and clamp to total_dur (loop if shorter)
                silent_video = work_dir / 'silent.mp4'
                vf = (
                    f'scale={target_w * 2}:{target_h * 2}:force_original_aspect_ratio=increase,'
                    f'crop={target_w}:{target_h},'
                    f'scale={target_w}:{target_h},'
                    f'format=yuv420p'
                )
                cmd_v = [
                    '/usr/bin/ffmpeg', '-y',
                    '-stream_loop', '-1',
                    '-i', str(bg_path),
                    '-t', f'{total_dur:.3f}',
                    '-vf', vf,
                    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22',
                    '-pix_fmt', 'yuv420p', '-r', '25',
                    '-an',
                    str(silent_video),
                ]
                r = await asyncio.to_thread(subprocess.run, cmd_v, capture_output=True, timeout=240)
                if r.returncode != 0 or not silent_video.exists() or silent_video.stat().st_size < 1000:
                    err_tail = r.stderr[-200:].decode(errors='ignore') if r.stderr else ''
                    await _async_update_job(job_id, status='failed', error=f'Video process failed: {err_tail}', progress=100)
                    return

        # ===========================================================
        # MODE B (default / fallback): IMAGE pipeline (4 Pixabay images + ken-burns)
        # ===========================================================
        if silent_video is None:
            await _async_update_job(job_id, status='processing', stage='fetch_images', progress=10)

            # --- 1. Fetch images (4 by default) ---
            image_urls: list[str] = req.get('images') or []
            if not image_urls:
                hits = await pixabay.search_images(req['image_query'], count=6, orientation='vertical')
                image_urls = [h.get('largeImageURL') or h.get('webformatURL') for h in hits if h.get('largeImageURL') or h.get('webformatURL')]
            image_urls = image_urls[:4]
            if len(image_urls) < 2:
                await _async_update_job(job_id, status='failed', error='Not enough images found for the query.', progress=100)
                return

            paths: list[Path] = []
            for u in image_urls:
                p = await _download_img(u, work_dir)
                if p:
                    paths.append(p)
            if not paths:
                await _async_update_job(job_id, status='failed', error='Image download failed.', progress=100)
                return
            image_urls_used = image_urls[: len(paths)]

            await _async_update_job(job_id, stage='animate', progress=30, image_count=len(paths))

            # --- 2. Animate each image (2.5s clips) ---
            # NOTE: image pipeline uses 480x854 to keep ken-burns fast; final mux still respects the chosen ratio
            img_w, img_h = (480, 854) if req.get('aspect_ratio') == '9:16' else (854, 480)
            dur_each = float(req.get('duration_per_shot') or 2.5)
            motion = req.get('motion') or 'ken_burns'
            rotate = ['ken_burns', 'zoom_in', 'pan_right', 'zoom_out']
            clip_paths: list[Path] = []
            for idx, p in enumerate(paths):
                norm = _normalize_image(p, img_w, img_h)
                m = motion if motion != 'auto' else rotate[idx % len(rotate)]
                clip = _render_motion_clip(norm, m, dur_each, img_w, img_h, work_dir / f'clip_{idx:02d}.mp4')
                if clip and clip.exists():
                    clip_paths.append(clip)
            if len(clip_paths) < 2:
                await _async_update_job(job_id, status='failed', error='Motion clip render failed.', progress=100)
                return

            await _async_update_job(job_id, stage='concat', progress=55)

            # --- 3. Concat ---
            silent_video = work_dir / 'silent.mp4'
            concat_list = work_dir / 'concat.txt'
            with open(concat_list, 'w') as f:
                for cp in clip_paths:
                    f.write(f"file '{cp}'\n")
            concat_cmd = [
                '/usr/bin/ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(concat_list),
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-an', str(silent_video),
            ]
            r = await asyncio.to_thread(subprocess.run, concat_cmd, capture_output=True, timeout=180)
            if r.returncode != 0 or not silent_video.exists():
                await _async_update_job(job_id, status='failed', error=f'Concat failed: {r.stderr[-200:].decode(errors="ignore") if r.stderr else ""}', progress=100)
                return

            total_dur = dur_each * len(clip_paths)

        # ===========================================================
        # COMMON: TTS → BGM → mux
        # ===========================================================

        # --- 4. TTS ---
        await _async_update_job(job_id, stage='tts', progress=70)
        tts_path = work_dir / 'voice.mp3'
        from server import generate_tts_audio  # reuse
        # Sprint 30d: tier-aware voice routing — Premium users (creator/pro)
        # automatically get Sarvam Bulbul-v2 for Indic content, premium Edge-TTS
        # voices for English. See backend/core/voice_layer.py.
        try:
            from core.voice_layer import select_voice_for_tier
            chosen_voice = select_voice_for_tier(
                requested_voice_id=req.get('voice_id'),
                text=req.get('script') or '',
                user_tier=req.get('user_tier') or 'free',
                voice_style=req.get('voice_style') or 'story',
                lang=req.get('lang'),
            )
            log.info('wizard: tts voice routed: tier=%s requested=%s → chosen=%s',
                     req.get('user_tier'), req.get('voice_id'), chosen_voice)
        except Exception as e:
            log.warning('wizard: voice_layer.select_voice_for_tier failed: %s — using requested voice', e)
            chosen_voice = req.get('voice_id') or 'en-US-JennyNeural'
        ok = await generate_tts_audio(
            req['script'], chosen_voice,
            tts_path, min_duration=max(2.5, total_dur - 0.5),
            voice_style=req.get('voice_style'),
            voice_rate=req.get('voice_rate'),
            voice_pitch=req.get('voice_pitch'),
        )
        has_voice = bool(ok) and tts_path.exists() and tts_path.stat().st_size > 1000

        # --- 5. BGM ---
        bgm_path: Optional[Path] = None
        bgm_url = req.get('bgm_url')
        if bgm_url and bgm_url.startswith('/api/serve-file/'):
            candidate = BGM_DIR / bgm_url.split('/')[-1]
            if not candidate.exists():
                candidate = UPLOAD_DIR / bgm_url.split('/')[-1]
            if candidate.exists():
                bgm_path = candidate
        if not bgm_path:
            tr = pick_bgm(req.get('music_mood') or 'cinematic_epic')
            if tr:
                cand = BGM_DIR / tr['filename']
                if cand.exists():
                    bgm_path = cand

        # --- 6. Mux: voice on top, BGM ducked ---
        await _async_update_job(job_id, stage='mux', progress=85)
        final_path = UPLOAD_DIR / f'wz_reel_{job_id}.mp4'
        cmd = None
        if has_voice and bgm_path:
            cmd = [
                '/usr/bin/ffmpeg', '-y',
                '-i', str(silent_video),
                '-i', str(tts_path),
                '-stream_loop', '-1', '-i', str(bgm_path),
                '-filter_complex',
                f'[2:a]volume=0.18,atrim=0:{total_dur},asetpts=PTS-STARTPTS[bgm];'
                f'[1:a]volume=1.2,apad=pad_dur=1[voice];'
                f'[voice][bgm]amix=inputs=2:duration=first:dropout_transition=0[aout]',
                '-map', '0:v', '-map', '[aout]',
                '-c:v', 'copy',
                '-c:a', 'aac', '-b:a', '192k',
                '-shortest',
                str(final_path),
            ]
        elif has_voice:
            cmd = [
                '/usr/bin/ffmpeg', '-y',
                '-i', str(silent_video),
                '-i', str(tts_path),
                '-map', '0:v', '-map', '1:a',
                '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest',
                str(final_path),
            ]
        elif bgm_path:
            cmd = [
                '/usr/bin/ffmpeg', '-y',
                '-i', str(silent_video),
                '-stream_loop', '-1', '-i', str(bgm_path),
                '-map', '0:v', '-map', '1:a',
                '-c:v', 'copy',
                '-af', f'volume=0.25,atrim=0:{total_dur}',
                '-c:a', 'aac', '-b:a', '192k', '-shortest',
                str(final_path),
            ]
        else:
            # no audio: copy silent
            import shutil
            shutil.copyfile(silent_video, final_path)

        if cmd is not None:
            r = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, timeout=180)
            if r.returncode != 0 or not final_path.exists() or final_path.stat().st_size < 1000:
                await _async_update_job(job_id, status='failed', error=f'Mux failed: {r.stderr[-200:].decode(errors="ignore") if r.stderr else ""}', progress=100)
                return

        await _async_update_job(
            job_id, status='completed', stage='done', progress=100,
            result_url=f'/api/serve-file/{final_path.name}',
            duration=total_dur,
            has_voice=has_voice,
            has_bgm=bool(bgm_path),
            mode=mode,
            image_urls_used=image_urls_used,
            bg_video_url=bg_video_used,
        )
        log.info('wizard: job %s completed (mode=%s, %s, %db)',
                 job_id, mode, final_path.name, final_path.stat().st_size)
    except Exception as e:
        log.exception('wizard job %s failed: %s', job_id, e)
        await _async_update_job(job_id, status='failed', error=str(e)[:400], progress=100)
