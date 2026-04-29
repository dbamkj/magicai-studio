"""Generate real Magic-Hour sample MP4s for 2-3 Inspiration templates.

One-time admin task:
- Picks representative templates (1 per major category)
- Calls MH text_to_video.create with hook_text/title as prompt
- Polls until ready, downloads locally to /app/backend/static/previews/
- Updates each template's `preview_url` so the Inspiration tab can play it inline

Run: python scripts/generate_inspiration_previews.py
"""
from __future__ import annotations
import asyncio
import os
import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import subprocess
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

from magic_hour import Client as MagicHourClient  # type: ignore

# We need access to the TTS generator from server.py. Import lazily.
from server import generate_tts_audio, UPLOAD_DIR  # type: ignore

try:
    from core.config import DB_NAME as _CFG_DB_NAME, MONGO_URL as _CFG_MONGO
except Exception:
    _CFG_DB_NAME = os.environ.get('DB_NAME_BETA', 'magicai_beta')
    _CFG_MONGO = os.environ['MONGO_URL']

MAGIC_HOUR_API_KEY = os.environ.get('MAGIC_HOUR_API_KEY', '')
PREVIEWS_DIR = Path('/app/backend/static/previews')
PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)


# Which templates to generate previews for.
# We pick 6 (diverse across tiers & categories) to validate quality, but the
# script processes them ONE AT A TIME — after the first is generated the
# operator inspects the result (voice + BGM + SFX + fade) and decides whether
# to continue. Pass `--limit N` to cap how many runs in a single invocation.
TARGETS = [
    # ---- Test specimen: Rich config (BGM + SFX + golden_flash transition) ----
    {
        'template_id': 'insp_fest_jan_free_divine_warrior',
        'prompt': (
            'Cinematic transformation of an ancient Indian divine warrior with '
            'glowing aura dissolving into a modern human silhouette, warm golden '
            'temple light, peacock-feather motifs, 9:16 vertical, devotional epic mood'
        ),
    },
    # ---- Test batch ----
    {
        'template_id': 'insp_story_free_startup_journey',
        'prompt': (
            'Young entrepreneur at a desk with glowing laptop in a dim bedroom, '
            'dreamy motivational atmosphere, cinematic slow zoom, golden hour light, '
            '9:16 vertical, story-telling mood'
        ),
    },
    {
        'template_id': 'insp_mot_pro_ceo_mindset',
        'prompt': (
            'Confident silhouette of a young CEO walking through a modern glass '
            'office at dusk, city lights behind, cinematic slow motion, moody '
            'amber lighting, aspirational, 9:16 vertical'
        ),
    },
    {
        'template_id': 'insp_fest_jan_pro_krishna_bhakti',
        'prompt': (
            'Glowing Lord Krishna playing flute under a sacred banyan tree, '
            'divine peacock crown, warm golden aura, slow cinematic pan, '
            'bhakti devotional mood, 9:16 vertical'
        ),
    },
    {
        'template_id': 'insp_dev_starter_om_namah_shivaya',
        'prompt': (
            'Lord Shiva meditating in Himalayan snow peaks with trident, cosmic '
            'blue aura swirling around him, moonlit night, cinematic camera '
            'pushing forward, 9:16 vertical, serene devotional epic'
        ),
    },
    {
        'template_id': 'insp_funny_free_monday_mood',
        'prompt': (
            'Sleepy young office worker faceplanting onto desk at 9am then '
            'jumping up awake at 5pm, fun quick motion, warm cafe lighting, '
            '9:16 vertical, playful comedic mood'
        ),
    },
]


async def _download(url: str, out_path: Path):
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), follow_redirects=True) as c:
        r = await c.get(url)
        r.raise_for_status()
        with open(out_path, 'wb') as f:
            f.write(r.content)
    return out_path.stat().st_size


async def _poll(mh, job_id: str, max_wait_s: int = 1200) -> str | None:
    """Poll MH job until complete, return download URL."""
    import time
    start = time.time()
    while time.time() - start < max_wait_s:
        try:
            s = mh.v1.video_projects.get(id=job_id)
            status = getattr(s, 'status', None)
            print(f'  [poll {int(time.time()-start)}s] status={status} progress={getattr(s, "progress", None)}')
            if status == 'complete':
                downloads = getattr(s, 'downloads', None) or []
                if downloads:
                    return downloads[0].url
                return None
            if status in ('error', 'failed', 'canceled'):
                print(f'  [!] MH job {job_id} ended with {status}: {getattr(s, "error_message", None)}')
                return None
        except Exception as e:
            print(f'  [poll err] {e}')
        await asyncio.sleep(6)
    print(f'  [!] MH job {job_id} timed out after {max_wait_s}s')
    return None


# Map template `sound_effect` names to SFX_CATALOG ids (closest match).
# Templates use creative names (divine_bell, aura_rise, conch, light_burst) that
# don't exist in the catalog — map them to the nearest cinematic stinger.
SFX_MAP = {
    'divine_bell':   'epic_hit',        # deep resonant hit
    'aura_rise':     'cinematic_rise',  # perfect match
    'light_burst':   'dramatic',        # big dramatic hit
    'conch':         'epic_hit',        # deep cinematic
    'whoosh':        'whoosh',
    'swish':         'swish',
    'pop':           'pop',
    'drum_roll':     'drum_roll',
    'boing':         'boing',
}


def _fade_filter_for(transition_effect: str | None, duration: float) -> str:
    """Build an ffmpeg video filter that applies a fade-in/out based on the
    template's transition_effect. Always returns a safe fade-in + fade-out."""
    t_in = 0.4
    t_out = 0.4
    out_start = max(0.0, duration - t_out)
    # All effects get the same structural fades; colour tint varies where useful.
    return f'fade=t=in:st=0:d={t_in}:c=white,fade=t=out:st={out_start:.2f}:d={t_out}:c=black' \
        if transition_effect in ('golden_flash', 'aura_burst') \
        else f'fade=t=in:st=0:d={t_in},fade=t=out:st={out_start:.2f}:d={t_out}'


async def _probe_duration(fp: Path) -> float:
    """Return duration in seconds of the given media file via ffprobe."""
    try:
        res = subprocess.run(
            ['/usr/bin/ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=nokey=1:noprint_wrappers=1', str(fp)],
            capture_output=True, timeout=15,
        )
        return float(res.stdout.strip() or 0.0)
    except Exception:
        return 0.0


async def _download_sfx_file(sfx_catalog_id: str) -> Path | None:
    """Cache a Pixabay SFX locally. Mirrors server._download_sfx logic."""
    try:
        from core.constants import sfx_by_id  # type: ignore
    except Exception:
        return None
    sfx = sfx_by_id(sfx_catalog_id)
    if not sfx or not sfx.get('url'):
        return None
    cached = UPLOAD_DIR / f'sfx_cache_{sfx_catalog_id}.mp3'
    if cached.exists() and cached.stat().st_size > 500:
        return cached
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0), follow_redirects=True) as c:
            r = await c.get(sfx['url'])
            if r.status_code == 200 and len(r.content) > 500:
                cached.write_bytes(r.content)
                return cached
    except Exception as e:
        print(f'    SFX download failed: {e}')
    return None


async def _mux_audio(video_path: Path, tts_text: str, voice_id: str, voice_style: str,
                     bgm_url: str | None, sfx_tpl_name: str | None,
                     transition_effect: str | None, out_path: Path) -> bool:
    """Generate TTS + optional SFX + BGM, apply fade-in/out, and mux onto
    ``video_path``. Writes to ``out_path``. Returns True on success."""
    vid_dur = await _probe_duration(video_path) or 5.0

    # 1) TTS voice
    voice_audio = UPLOAD_DIR / f'preview_tts_{uuid.uuid4().hex}.mp3'
    try:
        await generate_tts_audio(tts_text, voice_id, voice_audio, min_duration=3.0, voice_style=voice_style)
    except Exception as e:
        print(f'    TTS gen failed: {e}')
        return False
    if not voice_audio.exists() or voice_audio.stat().st_size < 500:
        print('    TTS produced empty file')
        return False

    # 2) BGM file (optional)
    bgm_local: Path | None = None
    if bgm_url and bgm_url.startswith('/api/serve-file/'):
        fn = bgm_url.split('/api/serve-file/', 1)[1]
        for base in ('/app/backend/static/bgm', '/app/backend/uploads'):
            cand = Path(base) / fn
            if cand.exists():
                bgm_local = cand
                break

    # 3) SFX file (optional — played at start of clip as an impact stinger)
    sfx_local: Path | None = None
    sfx_catalog_id = SFX_MAP.get((sfx_tpl_name or '').lower()) if sfx_tpl_name else None
    if sfx_catalog_id:
        sfx_local = await _download_sfx_file(sfx_catalog_id)
        print(f'    sfx "{sfx_tpl_name}" -> catalog "{sfx_catalog_id}" -> {sfx_local}')

    # 4) Video filter — apply transition fade-in/out
    vf = _fade_filter_for(transition_effect, vid_dur)

    # 5) Build ffmpeg command
    inputs: list[str] = ['-i', str(video_path), '-i', str(voice_audio)]
    idx_voice = 1
    idx_bgm = -1
    idx_sfx = -1
    next_idx = 2
    if bgm_local:
        inputs.extend(['-stream_loop', '-1', '-i', str(bgm_local)])
        idx_bgm = next_idx
        next_idx += 1
    if sfx_local:
        inputs.extend(['-i', str(sfx_local)])
        idx_sfx = next_idx
        next_idx += 1

    # Audio mix
    audio_parts: list[str] = [f'[{idx_voice}:a]volume=1.35[vo]']
    mix_inputs = ['[vo]']
    if idx_bgm >= 0:
        audio_parts.append(f'[{idx_bgm}:a]volume=0.22[bg]')
        mix_inputs.append('[bg]')
    if idx_sfx >= 0:
        # SFX plays at start, limited to first ~1.8s, slight fade-out
        audio_parts.append(f'[{idx_sfx}:a]volume=0.8,atrim=end=1.8,afade=t=out:st=1.2:d=0.6,apad[sx]')
        mix_inputs.append('[sx]')
    if len(mix_inputs) == 1:
        audio_parts.append('[vo]anull[a]')
    else:
        audio_parts.append(
            f'{"".join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=2,'
            'dynaudnorm=f=150:g=15[a]'
        )
    filt = ';'.join(audio_parts)

    cmd: list[str] = ['/usr/bin/ffmpeg', '-y', *inputs,
                      '-filter_complex', filt,
                      '-vf', vf,
                      '-map', '0:v:0', '-map', '[a]',
                      '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-pix_fmt', 'yuv420p',
                      '-c:a', 'aac', '-b:a', '192k', '-ac', '2',
                      '-shortest', str(out_path)]
    res = subprocess.run(cmd, capture_output=True, timeout=240)
    voice_audio.unlink(missing_ok=True)
    if res.returncode != 0:
        print(f'    ffmpeg failed: {res.stderr[-300:].decode(errors="ignore") if res.stderr else "?"}')
        return False
    return out_path.exists() and out_path.stat().st_size > 5000


async def generate_one(mh, db, template_id: str, prompt: str):
    print(f'\n==> {template_id}')
    tpl = await db.templates.find_one({'id': template_id})
    if not tpl:
        print(f'  !! template not found, skipping')
        return False

    # --- Step A: Get the video (either reuse existing preview, or generate fresh) ---
    fname = f'preview_{template_id}.mp4'
    video_path = PREVIEWS_DIR / fname
    if video_path.exists() and video_path.stat().st_size > 10000:
        print(f'  >> reusing existing MH video ({video_path.stat().st_size/1024:.0f} KB)')
    else:
        ar = tpl.get('aspect_ratio', '9:16')
        end_s = 5.0
        print(f'  prompt="{prompt[:90]}" ar={ar} end={end_s}')
        try:
            r = mh.v1.text_to_video.create(
                name=f'InspirationPreview_{template_id[-12:]}',
                end_seconds=end_s,
                aspect_ratio=ar,
                style={'prompt': prompt, 'quality_mode': 'quick'},
            )
            job_id = r.id
            print(f'  ✓ MH job id={job_id}, polling...')
        except Exception as e:
            print(f'  !! MH create failed: {e}')
            return False
        url = await _poll(mh, job_id, max_wait_s=1200)
        if not url:
            return False
        size = await _download(url, video_path)
        print(f'  ✓ downloaded MH video {size/1024:.0f} KB')

    # --- Step B: Mux TTS + SFX + BGM with fade transitions ---
    tts_text = tpl.get('hook_text') or tpl.get('lyrics') or tpl.get('title', '').replace('→', 'to')
    voice_id = tpl.get('voice_id') or 'en-US-JennyNeural'
    voice_style = tpl.get('voice_style') or 'story'
    bgm_url = tpl.get('bgm_url')
    sfx_tpl = tpl.get('sound_effect')
    trans = tpl.get('transition_effect')
    print(f'  tts_text="{tts_text[:70]}"')
    print(f'  voice={voice_id} style={voice_style} bgm={bgm_url} sfx={sfx_tpl} transition={trans}')

    fn_audio = f'preview_{template_id}_audio.mp4'
    final_path = PREVIEWS_DIR / fn_audio
    ok = await _mux_audio(video_path, tts_text, voice_id, voice_style, bgm_url, sfx_tpl, trans, final_path)
    if not ok:
        print(f'  !! audio mux failed — keeping silent video')
        serve_path = f'/api/serve-file/{fname}'
    else:
        print(f'  ✓ audio muxed -> {final_path.stat().st_size/1024:.0f} KB')
        serve_path = f'/api/serve-file/{fn_audio}'

    await db.templates.update_one(
        {'id': template_id},
        {'$set': {
            'preview_url': serve_path,
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }},
    )
    print(f'  ✓ DB updated preview_url={serve_path}')
    return True


async def main():
    if not MAGIC_HOUR_API_KEY:
        print('!! MAGIC_HOUR_API_KEY not set — aborting')
        return
    # Simple --limit N flag
    limit = len(TARGETS)
    force = False
    for i, a in enumerate(sys.argv[1:]):
        if a == '--limit' and i + 2 <= len(sys.argv) - 1:
            try:
                limit = int(sys.argv[i + 2])
            except Exception:
                pass
        if a == '--force':
            force = True
    print(f'Using DB={_CFG_DB_NAME}  limit={limit}  force={force}')
    client = AsyncIOMotorClient(_CFG_MONGO)
    db = client[_CFG_DB_NAME]
    mh = MagicHourClient(token=MAGIC_HOUR_API_KEY)
    ok = 0
    for t in TARGETS[:limit]:
        if force:
            # re-mux even if preview_url already set — but KEEP cached MH mp4
            pass
        result = await generate_one(mh, db, t['template_id'], t['prompt'])
        if result:
            ok += 1
    print(f'\nDone — {ok}/{min(limit, len(TARGETS))} previews generated')


if __name__ == '__main__':
    asyncio.run(main())
