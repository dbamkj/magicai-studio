"""
Fix mismatched media in the LEGACY `templates` collection (the one used by
the Trending and Inspiration Reels screens — separate from
`marketplace_templates`).

Discovered bugs (from user's screenshots):
  • Krishna Bhakti Reel  → ramen-noodles photo (Pexels 8108078) ❌
  • Shri Krishna Govind  → same noodles photo
  • Bollywood Dance Off  → "monday_mood" preview_url (duplicate)
  • Divine Ascetic → Calm Human + Blue Aura Shiva Moment → SAME thumb + SAME video
  • Bhartiya Mataye      → wrong video
  • Janmashtami Krishna  → Lord Ganesha image  (in marketplace_templates)
  • Aunty Roast title    → user wants renamed to "AI Baba" with comedic AI baba theme

Strategy:
  1. Hand-curate every problematic template id with TWO Pixabay queries:
     one for the still thumbnail, one for the short preview MP4.
  2. Always prefer Pixabay's webformatURL (640w, stable CDN) and the
     `tiny` MP4 variant.
  3. After updating, HEAD-check each URL — anything non-200 falls back to
     the next query in the alternates list.
  4. Cover BOTH `templates` (legacy/insp) AND `marketplace_templates`
     (mp_*) collections so every screen renders correctly.

Run:
  cd /app/backend && python -m scripts.fix_legacy_template_media
"""
from __future__ import annotations
import asyncio
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env')

from motor.motor_asyncio import AsyncIOMotorClient
from core import pixabay


# id → list of (image_query, video_query) alternates. Picker tries each in
# order until both URLs return HTTP 200.
LEGACY_OVERRIDES: dict[str, list[tuple[str, str]]] = {
    # ---- Devotional / Krishna ----
    'insp_dev_free_krishna_govind':       [('krishna idol temple', 'krishna idol bhakti')],
    'insp_fest_jan_pro_krishna_bhakti':   [('krishna flute peacock', 'krishna idol temple')],
    'insp_fest_jan_free_divine_warrior':  [('arjuna chariot', 'mahabharata warrior')],

    # ---- Shiva ----
    'insp_dev_starter_om_namah_shivaya':  [('shiva mahadev statue', 'shiva linga temple')],
    'insp_fest_mah_pro_blue_aura':        [('shiva blue meditation', 'shiva linga aarti')],
    'insp_fest_mah_free_ascetic':         [('hindu sadhu meditation', 'sadhu monk meditation')],

    # ---- Devi ----
    'insp_fest_nav_starter_devi_bhakti':  [('durga goddess statue', 'durga puja idol')],

    # ---- Bhartiya Mataye / women ----
    'insp_fest_jan_starter_bhartiya':     [('indian women saree group', 'indian women dancing')],
    'pl_20260424_3_bd991e':               [('indian mother saree family', 'indian mother child')],

    # ---- Other duplicates flagged in DB sweep ----
    'insp_dev_pro_ganesh_vandana':        [('ganesha idol temple', 'ganesh idol aarti')],
    'insp_mot_free_rise_and_grind':       [('sunrise mountain runner', 'man running sunrise')],
    'insp_mot_starter_champions_mindset': [('athlete training gym', 'athlete training')],
    'insp_mot_pro_ceo_mindset':           [('businessman skyline office', 'business meeting modern')],
    'insp_story_free_startup_journey':    [('startup team coworking', 'office team meeting')],
    'insp_story_starter_village_to_city': [('village india road', 'indian village field')],
    'insp_story_pro_mountain_climb':      [('mountain climber peak', 'snow mountain summit')],
    'insp_funny_starter_coffee_spill':    [('coffee mug morning', 'coffee pour morning')],
    'insp_fest_jan_starter_flute_player': [('krishna flute playing', 'flute musician')],
    'insp_fest_mah_starter_trident_monk': [('trident statue monk', 'monk meditation')],
    'insp_fest_nav_free_warrior_goddess': [('durga warrior goddess', 'durga puja celebration')],
    'insp_fest_nav_pro_goddess_energy':   [('goddess statue energy', 'durga maa puja')],
    'pl_20260424_0_ce7359':               [('peaceful meditation lotus', 'meditation peaceful')],
    'pl_20260424_1_67618f':               [('businessman success stairs', 'businessman climbing')],
    'pl_20260424_2_f23f97':               [('indian metro train commute', 'mumbai metro train')],
    'pl_20260424_4_9122eb':               [('sunrise dawn light', 'sunrise time-lapse')],

    # ---- Funny / Lifestyle ----
    'insp_funny_pro_dance_off':           [('bollywood dance party', 'indian dance celebration')],
    'insp_funny_free_monday_mood':        [('tired person desk', 'tired man laptop')],
}

# Marketplace_templates fixes (extends the earlier curate)
MP_OVERRIDES: dict[str, list[tuple[str, str]]] = {
    'mp_funny_03':        [('indian baba meme funny', 'bearded man laughing'), ('indian sage funny', 'guru meme')],
    'mp_bhajan_01':       [('krishna idol flute', 'krishna idol temple')],
    'mp_bhajan_04':       [('durga goddess statue', 'durga puja idol')],
    'mp_emotional_04':    [('indian army soldier salute', 'indian army parade flag')],
    'mp_festival_03':     [('janmashtami krishna idol', 'krishna idol temple aarti')],
    'mp_festival_01':     [('diwali diya lamps row', 'diwali fireworks')],
    'mp_festival_02':     [('holi colors festival india', 'holi celebration colors')],
    'mp_funny_01':        [('tired employee desk monday', 'tired man laptop')],
    'mp_funny_02':        [('coffee morning cafe', 'coffee espresso pour')],
    'mp_funny_04':        [('bollywood dance party', 'indian dance celebration')],
}

# Title rename map — aligns wording with user's spec
RENAMES: dict[str, dict] = {
    'mp_funny_03': {
        'title': 'AI Baba',
        'tagline': 'AI baba meme · viral comedy · Hinglish punchlines',
        'wizard_idea': 'Funny AI baba reel — modern guru giving hilarious life advice in hinglish',
        'wizard_script': 'Beta, jeevan ka raaz hai kya pata? Wi-Fi strong rakho, mind cool rakho. Aur reel banao — viral guarantee!',
        'wizard_image_query': 'indian baba meme',
        'voice_style': 'comedic',
        'music_mood': 'comedic_quirky',
    },
}


async def _head_ok(url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as c:
            r = await c.head(url)
            return 200 <= r.status_code < 400
    except Exception:
        return False


async def _pick(image_q: str, video_q: str) -> tuple[str | None, str | None]:
    """Return (image_url, video_url) for the queries, validated via HEAD."""
    img_url = None
    vid_url = None
    try:
        hits = await pixabay.search_images(image_q, count=10, orientation='vertical')
        for h in hits:
            url = h.get('webformatURL') or h.get('largeImageURL')
            if url and await _head_ok(url):
                img_url = url
                break
    except Exception as e:
        print(f'  ! image query {image_q!r} failed: {e}')
    try:
        if hasattr(pixabay, 'search_videos'):
            vhits = await pixabay.search_videos(video_q, count=10)
            for v in vhits or []:
                vids = v.get('videos') or {}
                for size in ('tiny', 'small', 'medium'):
                    cand = (vids.get(size) or {}).get('url')
                    if cand and await _head_ok(cand):
                        vid_url = cand
                        break
                if vid_url:
                    break
    except Exception as e:
        print(f'  ! video query {video_q!r} failed: {e}')
    return img_url, vid_url


async def _patch(db, collection: str, id_field: str, thumb_field: str,
                 prev_field: str, overrides: dict[str, list[tuple[str, str]]]):
    print(f'\n=== Patching {collection} ===')
    for tid, alternates in overrides.items():
        doc = await db[collection].find_one({id_field: tid}, {id_field: 1, 'title': 1})
        if not doc:
            print(f'  · {tid:<40s}  (skip — not present)')
            continue
        title = doc.get('title', '')
        print(f'  → {tid:<40s} {title!r}')
        img_url = vid_url = None
        for q_img, q_vid in alternates:
            img_url, vid_url = await _pick(q_img, q_vid)
            if img_url and vid_url:
                break
        patch = {}
        if img_url:
            patch[thumb_field] = img_url
            patch['thumbnail_source'] = 'pixabay'
        if vid_url:
            patch[prev_field] = vid_url
            patch['preview_source'] = 'pixabay'
        # Apply rename, if any
        if tid in RENAMES:
            for k, v in RENAMES[tid].items():
                patch[k] = v
        if patch:
            await db[collection].update_one({id_field: tid}, {'$set': patch})
            print(f'      ✓ thumb={"Y" if img_url else "N"}  vid={"Y" if vid_url else "N"}'
                  + ('  RENAMED' if tid in RENAMES else ''))
        else:
            print('      (no media found — left as is)')


async def go():
    client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    # Determine target DBs
    targets = []
    for n in ('magicai_beta', os.getenv('DB_NAME', 'videoai_database'),
              'magicai_prod', 'videoai_database'):
        if n in [t[0] for t in targets]:
            continue
        cnt = await client[n].marketplace_templates.count_documents({})
        if cnt > 0:
            targets.append((n, cnt))
    print(f'Targets: {targets}')
    for db_name, _ in targets:
        db = client[db_name]
        await _patch(db, 'templates', 'id', 'thumbnail_url', 'preview_url', LEGACY_OVERRIDES)
        await _patch(db, 'marketplace_templates', 'id', 'thumbnail', 'preview_url', MP_OVERRIDES)
    print('\nDone.')


if __name__ == '__main__':
    asyncio.run(go())
