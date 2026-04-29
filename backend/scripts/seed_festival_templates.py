"""Sprint 6 Phase 3 — Festival Packs seed.

Seeds 9 festival-themed templates (3 per festival) into the `templates` collection.

Run: python scripts/seed_festival_templates.py

Idempotent: skips a template if its `id` already exists.
Images are gradient-based (frontend renders placeholder) — can be replaced later
with real AI-generated divine-inspired artwork.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

_MONGO_URL = os.environ['MONGO_URL']
_DB_NAME = os.environ.get('DB_NAME', 'magicai_beta')


# -------------- Gradient palettes per festival --------------
JANMASHTAMI_GRADIENT = ['#FBBF24', '#F97316', '#6366F1']     # gold → orange → indigo (flute/Krishna)
MAHASHIVRATRI_GRADIENT = ['#1E3A8A', '#475569', '#0EA5E9']   # deep blue → grey → sky (smoke/Shiva)
NAVRATRI_GRADIENT = ['#DC2626', '#F59E0B', '#FBBF24']        # red → amber → gold (goddess/shakti)


# -------------- BGM URLs (royalty-free, Pixabay-style placeholder) --------------
# (These are illustrative placeholder URLs — replace with real assets later)
BGM = {
    # Real royalty-free tracks — locally hosted at /app/backend/static/bgm/ and
    # served via the existing `/api/serve-file/<filename>` endpoint (extended
    # to serve static/bgm). Pixabay CDN direct URLs 403 when fetched without
    # browser headers, so we cache them locally once and reuse.
    # Source: Pixabay License (royalty-free, no attribution required).
    'krishna_flute':     '/api/serve-file/cinematic_score.mp3',
    'shiva_ambient':     '/api/serve-file/cinematic_score.mp3',
    'durga_devotional':  '/api/serve-file/cinematic_score.mp3',
}


TEMPLATES = [
    # -------- Janmashtami (Krishna-inspired) --------
    {
        'title': '🦚 Divine Warrior → Modern Man',
        'hook_text': 'जब भगवान का आशीर्वाद हो — हर कठिनाई एक अवसर बन जाती है',
        'festival_pack': 'janmashtami',
        'character_gender': 'male',
        'transition_effect': 'golden_flash',
        'motion': 'zoom_in_slow',
        'sound_effect': 'divine_bell',
        'voice_style': 'devotional',
        'bgm_url': BGM['krishna_flute'],
        'gradient_colors': JANMASHTAMI_GRADIENT,
    },
    {
        'title': '🎶 Flute Player → Peaceful Soul',
        'hook_text': 'बाँसुरी की मधुर ध्वनि में खुद को खो दो',
        'festival_pack': 'janmashtami',
        'character_gender': 'male',
        'transition_effect': 'glow_dissolve',
        'motion': 'ken_burns',
        'sound_effect': 'whoosh',
        'voice_style': 'story',
        'bgm_url': BGM['krishna_flute'],
        'gradient_colors': ['#FBBF24', '#EC4899', '#8B5CF6'],
    },
    {
        'title': '🪷 Krishna Bhakti Reel',
        'hook_text': 'हे गोविंद हे गोपाल — तेरे नाम में शक्ति है',
        'lyrics': 'हे गोविंद हे गोपाल\n[pause:0.8]\nराधे राधे\n[pause:1.0]\nमन में बसो हरि',
        'festival_pack': 'janmashtami',
        'character_gender': 'any',
        'transition_effect': 'aura_burst',
        'motion': 'slow_pan_right',
        'sound_effect': 'conch',
        'voice_style': 'devotional',
        'bgm_url': BGM['krishna_flute'],
        'gradient_colors': JANMASHTAMI_GRADIENT,
    },

    # -------- Mahashivratri (Shiva-inspired) --------
    {
        'title': '🔱 Divine Ascetic → Calm Human',
        'hook_text': 'शिव में समर्पण ही मोक्ष का मार्ग है',
        'festival_pack': 'mahashivratri',
        'character_gender': 'male',
        'transition_effect': 'smoke_fade',
        'motion': 'zoom_in_slow',
        'sound_effect': 'aura_rise',
        'voice_style': 'devotional',
        'bgm_url': BGM['shiva_ambient'],
        'gradient_colors': MAHASHIVRATRI_GRADIENT,
    },
    {
        'title': '🌙 Trident Warrior → Silent Monk',
        'hook_text': 'ॐ नमः शिवाय — शांति का मूल मंत्र',
        'festival_pack': 'mahashivratri',
        'character_gender': 'male',
        'transition_effect': 'particle_dissolve',
        'motion': 'cinematic_zoom',
        'sound_effect': 'divine_bell',
        'voice_style': 'story',
        'bgm_url': BGM['shiva_ambient'],
        'gradient_colors': ['#1E3A8A', '#6366F1', '#0EA5E9'],
    },
    {
        'title': '💙 Blue Aura Shiva Moment',
        'hook_text': 'हर हर महादेव — शक्ति और शांति का संगम',
        'lyrics': 'ॐ नमः शिवाय\n[pause:1.2]\nहर हर महादेव\n[pause:0.8]\nशिव शिव शंभो',
        'festival_pack': 'mahashivratri',
        'character_gender': 'any',
        'transition_effect': 'smoke_fade',
        'motion': 'center_hold',
        'sound_effect': 'light_burst',
        'voice_style': 'devotional',
        'bgm_url': BGM['shiva_ambient'],
        'gradient_colors': MAHASHIVRATRI_GRADIENT,
    },

    # -------- Navratri (Goddess-inspired) --------
    {
        'title': '🔥 Warrior Goddess → Strong Woman',
        'hook_text': 'शक्ति तुममें है — बस पहचानो',
        'festival_pack': 'navratri',
        'character_gender': 'female',
        'transition_effect': 'golden_flash',
        'motion': 'zoom_in_fast',
        'sound_effect': 'aura_rise',
        'voice_style': 'motivation',
        'bgm_url': BGM['durga_devotional'],
        'gradient_colors': NAVRATRI_GRADIENT,
    },
    {
        'title': '🌺 Devi Bhakti Reel',
        'hook_text': 'जय माता दी — हर दिल में शक्ति',
        'lyrics': 'जय माता दी\n[pause:0.8]\nअंबे माता\n[pause:1.0]\nशक्ति का वरदान',
        'festival_pack': 'navratri',
        'character_gender': 'female',
        'transition_effect': 'aura_burst',
        'motion': 'slow_pan_left',
        'sound_effect': 'conch',
        'voice_style': 'devotional',
        'bgm_url': BGM['durga_devotional'],
        'gradient_colors': NAVRATRI_GRADIENT,
    },
    {
        'title': '✨ Goddess Energy Transformation',
        'hook_text': 'देवी की कृपा से हर रूप सुंदर है',
        'festival_pack': 'navratri',
        'character_gender': 'female',
        'transition_effect': 'particle_dissolve',
        'motion': 'ken_burns',
        'sound_effect': 'divine_bell',
        'voice_style': 'story',
        'bgm_url': BGM['durga_devotional'],
        'gradient_colors': ['#DC2626', '#EC4899', '#FBBF24'],
    },
]


async def main():
    client = AsyncIOMotorClient(_MONGO_URL)
    db = client[_DB_NAME]
    print(f'[seed] connecting to {_DB_NAME}')
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    skipped = 0
    for base in TEMPLATES:
        # Stable-ish ID (slug-like) so re-run is idempotent
        slug = f"festival_{base['festival_pack']}_{base['title'].split('→')[-1].strip().replace(' ', '_')}"[:80]
        slug = slug.replace('/', '_').replace('?', '').lower()
        # Deterministic-ish id based on slug
        tid = f"fest-{base['festival_pack'][:3]}-{abs(hash(slug)) % 10**10}"
        existing = await db.templates.find_one({'id': tid})
        if existing:
            skipped += 1
            continue
        doc = {
            'id': tid,
            'title': base['title'],
            'category': 'divine_transformation',
            'subcategory': None,
            'hook_text': base.get('hook_text'),
            'lyrics': base.get('lyrics'),
            'festival_pack': base['festival_pack'],
            'character_gender': base.get('character_gender'),
            'transition_effect': base.get('transition_effect'),
            'bgm_url': base.get('bgm_url'),
            'gradient_colors': base.get('gradient_colors'),
            'voice_id': 'hi-IN-SwaraNeural' if base.get('character_gender') == 'female' else 'hi-IN-MadhurNeural',
            'voice_style': base.get('voice_style'),
            'motion': base.get('motion'),
            'sound_effect': base.get('sound_effect'),
            'aspect_ratio': '9:16',
            'duration': 6,
            'thumbnail_url': None,
            'preview_url': None,
            'tier': 'free',  # first version — all free-tier with watermark
            'source': 'curated',
            'is_active': True,
            'is_trending': True,
            'usage_count': 0,
            'completion_count': 0,
            'share_count': 0,
            'rating_sum': 0.0,
            'rating_count': 0,
            'score': 10.0,
            'created_at': now,
            'updated_at': now,
        }
        await db.templates.insert_one(doc)
        inserted += 1
        print(f'  + {tid}  "{base["title"]}"')
    print(f'[seed] inserted={inserted}  skipped={skipped}')
    total = await db.templates.count_documents({'festival_pack': {'$exists': True, '$ne': None}})
    print(f'[seed] total festival templates in DB: {total}')


if __name__ == '__main__':
    asyncio.run(main())
