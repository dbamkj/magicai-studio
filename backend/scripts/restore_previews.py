"""Round-5 fix: restore baked-audio previews + dedupe + Wizard revert.

User feedback (Apr 29, 2026):
  • Several Inspiration Reels lost their narrated audio after Round-2/3
    curate replaced the local `preview_<id>_audio.mp4` files with silent
    Pixabay tiny.mp4 clips.
  • Some templates ended up with duplicate previews (Devi Bhakti = Goddess
    Energy, Krishna Govinda = Om Namah Shivay).
  • Several templates have NO video at all in the user's app (preview_url
    that fails to load on mobile).

Strategy:
  (1) For every template where a `preview_<id>_audio.mp4` exists on disk
      (so /api/serve-file/preview_<id>_audio.mp4 is reachable), set
      `preview_url` back to that URL → restores the original narration.
  (2) For the 4 explicit duplicates the user flagged, force-pick a fresh
      Pixabay clip with a different query.
"""
from __future__ import annotations
import asyncio, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env')

import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from core import pixabay


# ---- All template ids that have a local _audio.mp4 file -----------------
# Output of `ls static/previews/*_audio.mp4`
LOCAL_AUDIO_IDS = [
    'insp_dev_free_krishna_govind',
    'insp_dev_starter_om_namah_shivaya',
    'insp_fest_jan_free_divine_warrior',
    'insp_fest_jan_pro_krishna_bhakti',
    'insp_fest_nav_free_warrior_goddess',
    'insp_funny_free_monday_mood',
    'insp_mot_free_rise_and_grind',
    'insp_mot_pro_ceo_mindset',
    'insp_story_free_startup_journey',
]

# ---- Templates the user wants UNIQUE NEW Pixabay clips for ---------------
DEDUPE_TARGETS = {
    'insp_fest_nav_pro_goddess_energy':   ('hindu goddess statue', 'durga puja procession'),
    # duplicate of 'om namah shivay' - need different
    'insp_dev_starter_om_namah_shivaya':  None,  # restored from local audio file
    # 'devi bhakti' is dev_starter_devi_bhakti — already had its own
    'insp_fest_nav_starter_devi_bhakti':  None,  # leave as is
    # restore previews for items that previously played but now don't (and
    # have no local audio file)
    'insp_story_starter_village_to_city': ('indian village street rural', 'india village field walk'),
    'insp_story_pro_mountain_climb':      ('mountain climber summit', 'snow mountain peak hike'),
    'insp_funny_starter_coffee_spill':    ('coffee pour cafe morning', 'coffee espresso barista'),
    'insp_fest_jan_starter_flute_player': ('bansuri flute player', 'flute musician traditional'),
}


async def head_ok(url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as c:
            r = await c.head(url)
            return 200 <= r.status_code < 400
    except Exception:
        return False


async def pick_video(image_q: str | None, video_q: str) -> tuple[str | None, str | None]:
    img_url = vid_url = None
    if image_q:
        try:
            for h in await pixabay.search_images(image_q, count=8, orientation='vertical'):
                u = h.get('webformatURL') or h.get('largeImageURL')
                if u and await head_ok(u):
                    img_url = u; break
        except Exception:
            pass
    try:
        for v in (await pixabay.search_videos(video_q, count=8)) or []:
            for sz in ('tiny', 'small', 'medium'):
                cand = (v.get('videos', {}).get(sz) or {}).get('url')
                if cand and await head_ok(cand):
                    vid_url = cand; break
            if vid_url:
                break
    except Exception:
        pass
    return img_url, vid_url


async def go():
    backend = os.getenv('EXPO_PUBLIC_BACKEND_URL') or 'https://creative-plan-engine.preview.emergentagent.com'
    base = backend.rstrip('/') + '/api/serve-file'
    client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = client['magicai_beta']

    print('=== (1) Restoring baked-audio previews ===')
    for tid in LOCAL_AUDIO_IDS:
        url = f'{base}/preview_{tid}_audio.mp4'
        # The serve-file FastAPI route only handles GET, not HEAD — and the
        # files are already verified to exist on disk in
        # `/app/backend/static/previews/`. Skip the HEAD check and patch.
        await db.templates.update_one(
            {'id': tid},
            {'$set': {'preview_url': url, 'preview_source': 'baked'}},
        )
        print(f'  ✓  {tid:<40s} → {url}')

    print('\n=== (2) Patching duplicates / no-video items ===')
    for tid, q in DEDUPE_TARGETS.items():
        if q is None:
            continue
        image_q, video_q = q
        img, vid = await pick_video(image_q, video_q)
        patch = {}
        if img:
            patch['thumbnail_url'] = img
        if vid:
            patch['preview_url'] = vid
            patch['preview_source'] = 'pixabay'
        if patch:
            await db.templates.update_one({'id': tid}, {'$set': patch})
            print(f'  ✓ {tid:<40s}  vid={"Y" if vid else "N"}  img={"Y" if img else "N"}')

    print('\nDone.')


if __name__ == '__main__':
    asyncio.run(go())
