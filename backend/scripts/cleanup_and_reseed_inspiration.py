"""Cleanup & reseed the Inspiration templates.

Rules (per user feedback):
- Exactly 3 templates per display category (1 Free + 1 Starter + 1 Pro).
- Dedup "Flute Player -> Peaceful Soul" (was duplicated ~3×).
- Replace generic Motivation / Funny templates with more relevant ones.
- For `divine_transformation` (festivals tab) — 3 templates per festival
  pack (janmashtami / mahashivratri / navratri), each with free + starter + pro.

Run: python scripts/cleanup_and_reseed_inspiration.py
"""
from __future__ import annotations
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

MONGO_URL = os.environ['MONGO_URL']
# Use core.config so we get the ENV-aware DB (BETA -> magicai_beta) that the
# templates router uses. Falls back to raw DB_NAME env if core is unavailable.
try:
    from core.config import DB_NAME as _CFG_DB_NAME
    DB_NAME = _CFG_DB_NAME
except Exception:  # pragma: no cover
    DB_NAME = os.environ.get('DB_NAME', 'magicai_beta')

# Use Pexels / Unsplash direct image URLs (free, CDN-hot-linkable).
# These act as placeholder cover art until real AI-generated previews exist.
IMG = {
    'bhakti':        'https://images.pexels.com/photos/32601772/pexels-photo-32601772.jpeg?w=600',
    'shiva':         'https://images.pexels.com/photos/18364244/pexels-photo-18364244.jpeg?w=600',
    'goddess':       'https://images.pexels.com/photos/5083400/pexels-photo-5083400.jpeg?w=600',
    'flute':         'https://images.pexels.com/photos/6069551/pexels-photo-6069551.jpeg?w=600',
    'diya':          'https://images.pexels.com/photos/5713894/pexels-photo-5713894.jpeg?w=600',
    'ganesh':        'https://images.pexels.com/photos/33053289/pexels-photo-33053289.jpeg?auto=compress&cs=tinysrgb&w=600',
    'mountain':      'https://images.pexels.com/photos/1252500/pexels-photo-1252500.jpeg?w=600',
    'sunrise_run':   'https://images.pexels.com/photos/1571939/pexels-photo-1571939.jpeg?w=600',
    'gym':           'https://images.pexels.com/photos/1552242/pexels-photo-1552242.jpeg?w=600',
    'ceo':           'https://images.pexels.com/photos/3760067/pexels-photo-3760067.jpeg?w=600',
    'book':          'https://images.pexels.com/photos/316465/pexels-photo-316465.jpeg?w=600',
    'journey':       'https://images.pexels.com/photos/1076758/pexels-photo-1076758.jpeg?w=600',
    'startup':       'https://images.pexels.com/photos/3184465/pexels-photo-3184465.jpeg?w=600',
    'monday':        'https://images.pexels.com/photos/4046718/pexels-photo-4046718.jpeg?w=600',
    'coffee_fail':   'https://images.pexels.com/photos/302899/pexels-photo-302899.jpeg?w=600',
    'dance':         'https://images.pexels.com/photos/1701194/pexels-photo-1701194.jpeg?w=600',
    'village':       'https://images.pexels.com/photos/2325446/pexels-photo-2325446.jpeg?w=600',
}

BGM_KRISHNA = '/api/serve-file/cinematic_score.mp3'
BGM_SHIVA   = '/api/serve-file/cinematic_score.mp3'
BGM_DEVI    = '/api/serve-file/cinematic_score.mp3'

# Tier rotation for each 3-template category
TIERS3 = ['free', 'starter', 'pro']


def make_tpl(*, id_: str, title: str, category: str, tier: str,
             hook_text: str | None = None,
             lyrics: str | None = None,
             thumbnail_url: str | None = None,
             preview_url: str | None = None,
             festival_pack: str | None = None,
             gradient_colors: list[str] | None = None,
             voice_style: str = 'devotional',
             voice_id: str = 'hi-IN-MadhurNeural',
             motion: str = 'ken_burns',
             sound_effect: str = 'divine_bell',
             transition_effect: str = 'glow_dissolve',
             bgm_url: str | None = None,
             character_gender: str = 'any',
             is_trending: bool = True,
             score: float = 50.0,
             subcategory: str | None = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        'id': id_,
        'title': title,
        'category': category,
        'subcategory': subcategory,
        'hook_text': hook_text,
        'lyrics': lyrics,
        'festival_pack': festival_pack,
        'character_gender': character_gender,
        'transition_effect': transition_effect,
        'bgm_url': bgm_url,
        'gradient_colors': gradient_colors,
        'voice_id': voice_id,
        'voice_style': voice_style,
        'motion': motion,
        'sound_effect': sound_effect,
        'aspect_ratio': '9:16',
        'duration': 6,
        'thumbnail_url': thumbnail_url,
        'preview_url': preview_url,
        'tier': tier,
        'source': 'curated',
        'is_active': True,
        'is_trending': is_trending,
        'usage_count': 0,
        'completion_count': 0,
        'share_count': 0,
        'rating_sum': 0.0,
        'rating_count': 0,
        'score': score,
        'created_at': now,
        'updated_at': now,
    }


TEMPLATES: list[dict] = [
    # ============ DEVOTIONAL (3) ============
    make_tpl(
        id_='insp_dev_free_krishna_govind',
        title='🎶 Shri Krishna Govind',
        category='devotional', tier='free',
        hook_text='Hare Krishna Hare Krishna — Krishna Krishna Hare Hare',
        lyrics='Hare Krishna Hare Krishna\n[pause:0.8]\nKrishna Krishna Hare Hare\n[pause:1.0]\nHare Rama Hare Rama',
        thumbnail_url=IMG['flute'], bgm_url=BGM_KRISHNA,
        gradient_colors=['#FBBF24', '#F97316', '#6366F1'], score=85.0,
    ),
    make_tpl(
        id_='insp_dev_starter_om_namah_shivaya',
        title='🔱 Om Namah Shivaya',
        category='devotional', tier='starter',
        hook_text='Har Har Mahadev — The name that liberates',
        lyrics='Om Namah Shivaya\n[pause:1.0]\nHar Har Mahadev\n[pause:0.8]\nShiv Shiv Shambho',
        thumbnail_url=IMG['shiva'], bgm_url=BGM_SHIVA,
        gradient_colors=['#1E3A8A', '#475569', '#0EA5E9'],
        voice_id='hi-IN-MadhurNeural', score=82.0,
    ),
    make_tpl(
        id_='insp_dev_pro_ganesh_vandana',
        title='🕉️ Ganesh Vandana',
        category='devotional', tier='pro',
        hook_text='Vakratunda Mahakaya — Remover of every obstacle',
        lyrics='Vakratunda Mahakaya\n[pause:0.8]\nSuryakoti Samaprabha\n[pause:1.0]\nNirvighnam Kuru Me Deva',
        thumbnail_url=IMG['ganesh'], bgm_url=BGM_KRISHNA,
        gradient_colors=['#F97316', '#DC2626', '#FBBF24'],
        transition_effect='aura_burst', score=88.0,
    ),

    # ============ MOTIVATION (3) — replaced with more relevant ============
    make_tpl(
        id_='insp_mot_free_rise_and_grind',
        title='🌅 Rise & Grind',
        category='motivation', tier='free',
        hook_text='Every sunrise is a second chance — make it count.',
        thumbnail_url=IMG['sunrise_run'], voice_style='motivation',
        voice_id='en-US-JennyNeural',
        gradient_colors=['#F97316', '#FBBF24', '#DC2626'],
        motion='zoom_in_slow', sound_effect='aura_rise', score=70.0,
    ),
    make_tpl(
        id_='insp_mot_starter_champions_mindset',
        title='💪 Champion\'s Mindset',
        category='motivation', tier='starter',
        hook_text='Discipline beats motivation. Show up every single day.',
        thumbnail_url=IMG['gym'], voice_style='motivation',
        voice_id='en-US-GuyNeural',
        gradient_colors=['#0EA5E9', '#6366F1', '#111827'],
        motion='cinematic_zoom', sound_effect='whoosh', score=75.0,
    ),
    make_tpl(
        id_='insp_mot_pro_ceo_mindset',
        title='👑 CEO Mindset',
        category='motivation', tier='pro',
        hook_text='Stop waiting for permission — build the life you imagine.',
        thumbnail_url=IMG['ceo'], voice_style='motivation',
        voice_id='en-US-RyanMultilingualNeural',
        gradient_colors=['#111827', '#FBBF24', '#F97316'],
        transition_effect='particle_dissolve',
        motion='slow_pan_right', sound_effect='light_burst', score=80.0,
    ),

    # ============ STORY (3) ============
    make_tpl(
        id_='insp_story_free_startup_journey',
        title='🚀 The Startup Journey',
        category='story', tier='free',
        hook_text='It started with a dream... and one laptop.',
        thumbnail_url=IMG['startup'], voice_style='story',
        voice_id='en-US-JennyNeural',
        gradient_colors=['#6366F1', '#EC4899', '#FBBF24'],
        motion='ken_burns', sound_effect='whoosh', score=65.0,
    ),
    make_tpl(
        id_='insp_story_starter_village_to_city',
        title='🏘️ Village to City',
        category='story', tier='starter',
        hook_text='From the fields to the skyscrapers — a journey of grit.',
        thumbnail_url=IMG['village'], voice_style='story',
        voice_id='hi-IN-SwaraNeural',
        gradient_colors=['#0EA5E9', '#FBBF24', '#F97316'],
        motion='slow_pan_left', sound_effect='aura_rise', score=62.0,
    ),
    make_tpl(
        id_='insp_story_pro_mountain_climb',
        title='🏔️ The Summit',
        category='story', tier='pro',
        hook_text='The mountain didn\'t get smaller. I got stronger.',
        thumbnail_url=IMG['mountain'], voice_style='story',
        voice_id='en-US-RyanMultilingualNeural',
        gradient_colors=['#111827', '#0EA5E9', '#FBBF24'],
        transition_effect='particle_dissolve', motion='cinematic_zoom',
        sound_effect='light_burst', score=68.0,
    ),

    # ============ FUNNY (3) — replaced ============
    make_tpl(
        id_='insp_funny_free_monday_mood',
        title='😴 Monday Mood',
        category='funny', tier='free',
        hook_text='Me on a Monday morning vs. me on Monday evening.',
        thumbnail_url=IMG['monday'], voice_style='story',
        voice_id='en-US-JennyNeural',
        gradient_colors=['#6366F1', '#EC4899', '#FBBF24'],
        motion='zoom_in_fast', sound_effect='whoosh', score=55.0,
    ),
    make_tpl(
        id_='insp_funny_starter_coffee_spill',
        title='☕ Before Coffee',
        category='funny', tier='starter',
        hook_text='That moment when you haven\'t had your chai yet...',
        thumbnail_url=IMG['coffee_fail'], voice_style='story',
        voice_id='hi-IN-MadhurNeural',
        gradient_colors=['#F97316', '#FBBF24', '#DC2626'],
        motion='ken_burns', sound_effect='whoosh', score=58.0,
    ),
    make_tpl(
        id_='insp_funny_pro_dance_off',
        title='💃 Bollywood Dance Off',
        category='funny', tier='pro',
        hook_text='When your favorite song plays and you forget you\'re in public.',
        thumbnail_url=IMG['dance'], voice_style='story',
        voice_id='en-US-JennyNeural',
        gradient_colors=['#EC4899', '#FBBF24', '#8B5CF6'],
        transition_effect='aura_burst', motion='zoom_in_fast',
        sound_effect='light_burst', score=60.0,
    ),

    # ============ DIVINE TRANSFORMATION (festivals tab) ============
    # 3 festivals × (free+starter+pro) = 9 templates

    # -- Janmashtami --
    make_tpl(
        id_='insp_fest_jan_free_divine_warrior',
        title='🦚 Divine Warrior → Modern Man',
        category='divine_transformation', tier='free',
        festival_pack='janmashtami',
        hook_text='जब भगवान का आशीर्वाद हो — हर कठिनाई एक अवसर बन जाती है',
        thumbnail_url=IMG['bhakti'], bgm_url=BGM_KRISHNA,
        gradient_colors=['#FBBF24', '#F97316', '#6366F1'],
        character_gender='male', motion='zoom_in_slow',
        transition_effect='golden_flash', sound_effect='divine_bell',
        score=90.0,
    ),
    make_tpl(
        id_='insp_fest_jan_starter_flute_player',
        title='🎶 Flute Player → Peaceful Soul',
        category='divine_transformation', tier='starter',
        festival_pack='janmashtami',
        hook_text='बाँसुरी की मधुर ध्वनि में खुद को खो दो',
        thumbnail_url=IMG['flute'], bgm_url=BGM_KRISHNA,
        gradient_colors=['#FBBF24', '#EC4899', '#8B5CF6'],
        character_gender='male', motion='ken_burns',
        transition_effect='glow_dissolve', sound_effect='whoosh',
        voice_style='story', score=78.0,
    ),
    make_tpl(
        id_='insp_fest_jan_pro_krishna_bhakti',
        title='🪷 Krishna Bhakti Reel',
        category='divine_transformation', tier='pro',
        festival_pack='janmashtami',
        hook_text='हे गोविंद हे गोपाल — तेरे नाम में शक्ति है',
        lyrics='हे गोविंद हे गोपाल\n[pause:0.8]\nराधे राधे\n[pause:1.0]\nमन में बसो हरि',
        thumbnail_url=IMG['bhakti'], bgm_url=BGM_KRISHNA,
        gradient_colors=['#FBBF24', '#F97316', '#6366F1'],
        character_gender='any', motion='slow_pan_right',
        transition_effect='aura_burst', sound_effect='conch',
        score=95.0,
    ),

    # -- Mahashivratri --
    make_tpl(
        id_='insp_fest_mah_free_ascetic',
        title='🔱 Divine Ascetic → Calm Human',
        category='divine_transformation', tier='free',
        festival_pack='mahashivratri',
        hook_text='शिव में समर्पण ही मोक्ष का मार्ग है',
        thumbnail_url=IMG['shiva'], bgm_url=BGM_SHIVA,
        gradient_colors=['#1E3A8A', '#475569', '#0EA5E9'],
        character_gender='male', motion='zoom_in_slow',
        transition_effect='smoke_fade', sound_effect='aura_rise',
        score=72.0,
    ),
    make_tpl(
        id_='insp_fest_mah_starter_trident_monk',
        title='🌙 Trident Warrior → Silent Monk',
        category='divine_transformation', tier='starter',
        festival_pack='mahashivratri',
        hook_text='ॐ नमः शिवाय — शांति का मूल मंत्र',
        thumbnail_url=IMG['mountain'], bgm_url=BGM_SHIVA,
        gradient_colors=['#1E3A8A', '#6366F1', '#0EA5E9'],
        character_gender='male', motion='cinematic_zoom',
        transition_effect='particle_dissolve', sound_effect='divine_bell',
        voice_style='story', score=76.0,
    ),
    make_tpl(
        id_='insp_fest_mah_pro_blue_aura',
        title='💙 Blue Aura Shiva Moment',
        category='divine_transformation', tier='pro',
        festival_pack='mahashivratri',
        hook_text='हर हर महादेव — शक्ति और शांति का संगम',
        lyrics='ॐ नमः शिवाय\n[pause:1.2]\nहर हर महादेव\n[pause:0.8]\nशिव शिव शंभो',
        thumbnail_url=IMG['shiva'], bgm_url=BGM_SHIVA,
        gradient_colors=['#1E3A8A', '#475569', '#0EA5E9'],
        character_gender='any', motion='center_hold',
        transition_effect='smoke_fade', sound_effect='light_burst',
        score=92.0,
    ),

    # -- Navratri --
    make_tpl(
        id_='insp_fest_nav_free_warrior_goddess',
        title='🔥 Warrior Goddess → Strong Woman',
        category='divine_transformation', tier='free',
        festival_pack='navratri',
        hook_text='शक्ति तुममें है — बस पहचानो',
        thumbnail_url=IMG['goddess'], bgm_url=BGM_DEVI,
        gradient_colors=['#DC2626', '#F59E0B', '#FBBF24'],
        character_gender='female', motion='zoom_in_fast',
        transition_effect='golden_flash', sound_effect='aura_rise',
        voice_style='motivation', voice_id='hi-IN-SwaraNeural',
        score=98.0,
    ),
    make_tpl(
        id_='insp_fest_nav_starter_devi_bhakti',
        title='🌺 Devi Bhakti Reel',
        category='divine_transformation', tier='starter',
        festival_pack='navratri',
        hook_text='जय माता दी — हर दिल में शक्ति',
        lyrics='जय माता दी\n[pause:0.8]\nअंबे माता\n[pause:1.0]\nशक्ति का वरदान',
        thumbnail_url=IMG['diya'], bgm_url=BGM_DEVI,
        gradient_colors=['#DC2626', '#F59E0B', '#FBBF24'],
        character_gender='female', motion='slow_pan_left',
        transition_effect='aura_burst', sound_effect='conch',
        voice_id='hi-IN-SwaraNeural', score=80.0,
    ),
    make_tpl(
        id_='insp_fest_nav_pro_goddess_energy',
        title='✨ Goddess Energy Transformation',
        category='divine_transformation', tier='pro',
        festival_pack='navratri',
        hook_text='देवी की कृपा से हर रूप सुंदर है',
        thumbnail_url=IMG['goddess'], bgm_url=BGM_DEVI,
        gradient_colors=['#DC2626', '#EC4899', '#FBBF24'],
        character_gender='female', motion='ken_burns',
        transition_effect='particle_dissolve', sound_effect='divine_bell',
        voice_style='story', voice_id='hi-IN-SwaraNeural',
        score=85.0,
    ),
]


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    print(f'[cleanup] DB={DB_NAME}')

    # 1) Deactivate ALL existing templates (soft delete keeps historical analytics)
    res = await db.templates.update_many({}, {'$set': {'is_active': False}})
    print(f'[cleanup] deactivated {res.modified_count} old templates')

    # 2) Hard-delete duplicates to prevent id collisions on re-seed
    deleted = await db.templates.delete_many({'id': {'$in': [t['id'] for t in TEMPLATES]}})
    print(f'[cleanup] removed {deleted.deleted_count} existing docs with our new ids (if any)')

    # 3) Insert curated set
    await db.templates.insert_many(TEMPLATES)
    print(f'[seed] inserted {len(TEMPLATES)} curated templates')

    # Report summary
    from collections import Counter
    by_cat = Counter()
    for t in TEMPLATES:
        by_cat[(t['category'], t['tier'])] += 1
    print('[summary]')
    for (cat, tier), n in sorted(by_cat.items()):
        print(f'  {cat:30s}  {tier:8s} × {n}')


if __name__ == '__main__':
    asyncio.run(main())
