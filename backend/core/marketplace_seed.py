"""Phase-2 Marketplace — curated quick-reel templates (24 seed entries).

Each template is a wizard-ready preset:
  - title                                 (display)
  - category  : bhajan | viral | festival | emotional | romantic | ads | aesthetic | motivation
  - tagline   : 1-line hook for the card
  - emoji     : optional, used as fallback thumbnail
  - thumbnail : optional Pixabay image preview URL
  - wizard_mode : 'video' (default) | 'images'
  - wizard_idea, wizard_script, wizard_image_query
  - voice_id, voice_style, music_mood, motion, aspect_ratio
  - duration : final reel length in seconds
  - is_featured, is_trending, sort_order
"""
from __future__ import annotations
from datetime import datetime, timezone

# ---------- helpers ----------
_ID = lambda c, n: f"mp_{c}_{n:02d}"
_NOW = lambda: datetime.now(timezone.utc)


def _t(category: str, n: int, **kw) -> dict:
    # Sprint 30f: bhajan/devotional/aarti/mantra/patriotic/shayari templates
    # default to language='hinglish' so the wizard's voice_layer auto-routes
    # Premium users to Sarvam Bulbul-v2 (Vidya/Karun/Anushka) even though the
    # wizard_script is written in Roman Hindi. Other categories default to
    # 'english'. Override via the `language=` kwarg per template if needed.
    _hinglish_cats = {'bhajan', 'devotional', 'mantra', 'shloka', 'aarti',
                      'patriotic', 'shaayri', 'shayari', 'ghazal'}
    default_lang = 'hinglish' if category in _hinglish_cats else 'english'
    base = {
        "id": _ID(category, n),
        "category": category,
        "wizard_mode": "video",
        "voice_id": "en-US-JennyNeural",
        "voice_style": "story",
        "music_mood": "cinematic_epic",
        "motion": "auto",
        "aspect_ratio": "9:16",
        "duration": 10,
        "language": default_lang,
        "usage_count": 0,
        "view_count": 0,
        "is_featured": False,
        "is_trending": False,
        "is_active": True,
        "sort_order": n,
        # NEW — plan-tier gating + rich prompts (Phase 3)
        "plan_tier": "free",   # 'free' | 'creator' | 'pro'
        "prompts": [],          # list[str] of 3 rich prompts for the wizard
        "created_at": _NOW(),
    }
    base.update(kw)
    return base


def _build_rich_prompts(idea: str, script: str, image_query: str, mood: str) -> list[str]:
    """Compose 3 rich prompt variants from the seed fields — used as wizard prefill."""
    base = (idea or "").strip().rstrip(".")
    s = (script or "").replace("\n", " ").strip()
    iq = (image_query or "").strip()
    m = (mood or "").replace("_", " ").strip()
    return [
        f"{base}. {s} Visual style: {iq}, cinematic 9:16 vertical, {m} mood.",
        f"Cinematic reel — {base}. Hook: '{s.split('.')[0] if '.' in s else s}'. Use {iq} imagery, slow zoom, warm color grade.",
        f"Story arc — {base}. Three beats: setup → emotion → resolution. Visuals: {iq}. BGM: {m}.",
    ]


# =====================================================================
# 24 SEED TEMPLATES (3 per category × 8 categories)
# =====================================================================
SEED_TEMPLATES: list[dict] = [
    # ============ BHAJAN ============
    _t("bhajan", 1,
       title="Krishna Bhakti Reel",
       tagline="Divine flute melody · soulful Krishna devotion",
       emoji="🪈",
       wizard_idea="A devotional reel about Lord Krishna's flute calling devotees to bliss",
       wizard_script="Krishna's flute calls to my soul. Every note opens my heart. In Vrindavan eternal love flows.",
       wizard_image_query="krishna",
       voice_id="hi-IN-MadhurNeural",
       voice_style="devotional",
       music_mood="devotional_peaceful",
       is_featured=True),
    _t("bhajan", 2,
       title="Shiv Tandav",
       tagline="Cosmic dance of Lord Shiva · powerful divine reel",
       emoji="🔱",
       wizard_idea="Powerful Shiv Tandav reel showing the cosmic dance of destruction and rebirth",
       wizard_script="Om Namah Shivaya. Lord of cosmic dance. Destroyer of darkness. Awakener of consciousness.",
       wizard_image_query="shiva temple",
       voice_id="hi-IN-MadhurNeural",
       voice_style="powerful",
       music_mood="devotional_intense",
       is_trending=True),
    _t("bhajan", 3,
       title="Hanuman Chalisa Vibes",
       tagline="Strength · devotion · Sankat Mochan",
       emoji="🐒",
       wizard_idea="Hanuman ji devotional reel with Bajrangbali chants and strength imagery",
       wizard_script="Jai Hanuman. Bajrangbali. Sankat Mochan Maharaj. Bless me with courage and devotion.",
       wizard_image_query="hanuman temple",
       voice_id="hi-IN-MadhurNeural",
       voice_style="devotional",
       music_mood="devotional_uplifting"),

    # ============ VIRAL ============
    _t("viral", 1,
       title="POV: Monday Morning",
       tagline="Relatable Monday struggle · viral hook",
       emoji="😵",
       wizard_idea="POV reel about the Monday morning struggle every working professional faces",
       wizard_script="POV: It's Monday. Alarm rings five times. You hate the world. Coffee saves life.",
       wizard_image_query="monday office work",
       voice_style="conversational",
       music_mood="upbeat_funny",
       is_trending=True,
       is_featured=True),
    _t("viral", 2,
       title="That One Friend Who…",
       tagline="The friend group meme · TikTok-style hook",
       emoji="🤣",
       wizard_idea="Funny viral reel about that one friend who is always late",
       wizard_script="That one friend who says 'on my way' from their bed. We've all been there. Tag them.",
       wizard_image_query="friends laughing",
       voice_style="conversational",
       music_mood="upbeat_funny"),
    _t("viral", 3,
       title="Wait For It…",
       tagline="Mystery hook · keep watching ending",
       emoji="👀",
       wizard_idea="Suspense viral reel that keeps viewers hooked until the surprise reveal",
       wizard_script="Most people don't know this. But what happens next will shock you. Wait for it.",
       wizard_image_query="mystery clouds",
       voice_style="dramatic",
       music_mood="suspense_buildup"),

    # ============ FESTIVAL ============
    _t("festival", 1,
       title="Diwali Lights",
       tagline="Festival of lights · diya · sparkle reel",
       emoji="🪔",
       wizard_idea="Beautiful Diwali festival reel with diyas, fireworks, and rangoli",
       wizard_script="Diwali. The festival of lights. Diyas glow. Hearts shine. Wishing you joy and prosperity.",
       wizard_image_query="diwali diya",
       voice_style="warm",
       music_mood="festive_celebration",
       is_featured=True),
    _t("festival", 2,
       title="Holi Colors",
       tagline="Colors · joy · spring festival energy",
       emoji="🎨",
       wizard_idea="Vibrant Holi reel celebrating colors, friendship, and spring joy",
       wizard_script="Holi hai! Colors fly. Hearts unite. Forget all worries today. Burra na maano Holi hai.",
       wizard_image_query="holi colors",
       voice_id="hi-IN-SwaraNeural",
       voice_style="joyful",
       music_mood="festive_upbeat"),
    _t("festival", 3,
       title="Janmashtami Krishna",
       tagline="Krishna's birthday · midnight celebration",
       emoji="👶",
       wizard_idea="Janmashtami reel celebrating the birth of Lord Krishna with dahi handi vibes",
       wizard_script="Janmashtami night. Krishna is born. The world rejoices. Bal Gopal blesses every home.",
       wizard_image_query="krishna birth",
       voice_id="hi-IN-MadhurNeural",
       voice_style="devotional",
       music_mood="devotional_uplifting"),

    # ============ EMOTIONAL ============
    _t("emotional", 1,
       title="Mother's Love",
       tagline="The unconditional love of a mother",
       emoji="❤️",
       wizard_idea="Emotional reel about a mother's selfless love and sacrifices",
       wizard_script="She gave up everything for you. Her smile hides her tears. Maa is the first hero you ever meet.",
       wizard_image_query="mother child",
       voice_style="emotional",
       music_mood="emotional_strings"),
    _t("emotional", 2,
       title="Father's Sacrifice",
       tagline="The silent strength of a father",
       emoji="👔",
       wizard_idea="Emotional reel about a father's silent sacrifices for his family",
       wizard_script="He never showed his pain. He carried the weight of the family alone. Papa, the silent hero.",
       wizard_image_query="father walking",
       voice_style="emotional",
       music_mood="emotional_piano"),
    _t("emotional", 3,
       title="Childhood Memories",
       tagline="Nostalgia · simple times · old days",
       emoji="🌅",
       wizard_idea="Nostalgic reel about simple childhood memories that we miss as adults",
       wizard_script="Remember when life was simple? Cycle rides. School friends. Mom's tiffin. Take me back.",
       wizard_image_query="childhood village",
       voice_style="warm",
       music_mood="nostalgic_warm"),

    # ============ ROMANTIC ============
    _t("romantic", 1,
       title="First Love",
       tagline="That butterflies feeling · pehla pyaar",
       emoji="💕",
       wizard_idea="Romantic reel about the unforgettable feeling of first love",
       wizard_script="The first time you saw her. Time stopped. Heart raced. First love never really fades.",
       wizard_image_query="couple sunset",
       voice_style="romantic",
       music_mood="romantic_soft",
       is_trending=True),
    _t("romantic", 2,
       title="Long Distance Love",
       tagline="Miles apart · hearts together",
       emoji="📞",
       wizard_idea="Touching reel about a long-distance relationship and missing your partner",
       wizard_script="Different cities. Same heart. Every call is a hug. Every video call is a dream. Worth the wait.",
       wizard_image_query="couple phone call",
       voice_style="emotional",
       music_mood="romantic_emotional"),
    _t("romantic", 3,
       title="Anniversary Special",
       tagline="Years together · love grows stronger",
       emoji="💍",
       wizard_idea="Romantic anniversary reel celebrating years of love together",
       wizard_script="Years ago you said yes. Today I'd say it again. With you, every day is the best day.",
       wizard_image_query="couple wedding",
       voice_style="romantic",
       music_mood="romantic_cinematic"),

    # ============ ADS ============
    _t("ads", 1,
       title="Product Launch",
       tagline="Cinematic product reveal · tech-style",
       emoji="🚀",
       wizard_idea="High-energy product launch reel for a new tech product",
       wizard_script="Introducing the future. Sleeker. Faster. Smarter. Available now. Don't miss it.",
       wizard_image_query="modern technology",
       voice_style="confident",
       music_mood="cinematic_epic",
       is_featured=True),
    _t("ads", 2,
       title="Restaurant Promo",
       tagline="Drool-worthy food reel · cafe vibe",
       emoji="🍔",
       wizard_idea="Mouthwatering restaurant promo reel showing signature dishes",
       wizard_script="Fresh ingredients. Bold flavors. Made with love. Visit us today and taste the difference.",
       wizard_image_query="delicious food",
       voice_style="warm",
       music_mood="upbeat_lifestyle"),
    _t("ads", 3,
       title="Fitness Studio",
       tagline="Transform your body · studio energy",
       emoji="💪",
       wizard_idea="Motivating fitness studio reel showcasing workouts and transformation",
       wizard_script="Stronger than yesterday. Push your limits. Join us. Become the best version of yourself.",
       wizard_image_query="gym workout",
       voice_style="powerful",
       music_mood="energetic_pump"),

    # ============ AESTHETIC ============
    _t("aesthetic", 1,
       title="Coffee Shop Morning",
       tagline="Cozy cafe · slow living · soft glow",
       emoji="☕",
       wizard_idea="Soft aesthetic reel of a peaceful coffee shop morning",
       wizard_script="Coffee. Sunlight. Slow mornings. Find peace in the simple things. Slow down. Breathe.",
       wizard_image_query="coffee shop morning",
       voice_style="soft",
       music_mood="ambient_chill",
       is_trending=True),
    _t("aesthetic", 2,
       title="Rainy Window",
       tagline="Rain · books · cozy reading vibes",
       emoji="🌧️",
       wizard_idea="Cozy aesthetic reel of rain on the window with a warm reading nook",
       wizard_script="Rain falls. Pages turn. The world disappears. Some moments are made for you alone.",
       wizard_image_query="rain window",
       voice_style="soft",
       music_mood="ambient_rainy"),
    _t("aesthetic", 3,
       title="Mountain Sunrise",
       tagline="Wanderlust · golden hour · peaks",
       emoji="🏔️",
       wizard_idea="Breathtaking aesthetic reel of a mountain sunrise with golden hour light",
       wizard_script="Golden hour. Cold air. The world wakes up. Some views are worth waking up for.",
       wizard_image_query="mountain sunrise",
       voice_style="warm",
       music_mood="ambient_uplifting"),

    # ============ MOTIVATION ============
    _t("motivation", 1,
       title="CEO Mindset",
       tagline="Hustle · success · billionaire vibes",
       emoji="📈",
       wizard_idea="Powerful motivation reel about the mindset required to build a successful business",
       wizard_script="They sleep. You grind. They scroll. You build. Discipline beats talent every single time.",
       wizard_image_query="ceo skyline",
       voice_style="powerful",
       music_mood="cinematic_epic",
       is_featured=True,
       is_trending=True),
    _t("motivation", 2,
       title="Never Give Up",
       tagline="Comeback story · resilience reel",
       emoji="🔥",
       wizard_idea="Motivational comeback reel for anyone fighting through a tough phase",
       wizard_script="They counted you out. Good. Use it. Your comeback will be louder than their doubt.",
       wizard_image_query="runner dawn",
       voice_style="powerful",
       music_mood="energetic_pump"),
    _t("motivation", 3,
       title="5 AM Club",
       tagline="Wake up early · win the day",
       emoji="⏰",
       wizard_idea="Motivational reel about waking up at 5am and winning the day",
       wizard_script="5 AM. The world sleeps. You rise. Two hours that change everything. Be the one who shows up.",
       wizard_image_query="sunrise running",
       voice_style="confident",
       music_mood="cinematic_uplifting"),

    # ====================================================================
    # PRO-tier templates (1 per category) — premium cinematic concepts
    # added to ensure each category covers all 4 plans (free/starter/creator/pro)
    # ====================================================================
    _t("bhajan", 4,
       title="Devi Maa Aarti",
       tagline="Mother Goddess · powerful divine grace",
       emoji="🌺",
       wizard_idea="Powerful Devi Maa devotional reel celebrating Maa Durga and Maa Kali's divine grace",
       wizard_script="Jai Mata Di. Maa Durga awakens within you. Strength of Kali. Grace of Saraswati. The mother protects always.",
       wizard_image_query="durga temple",
       voice_id="hi-IN-MadhurNeural",
       voice_style="devotional",
       music_mood="devotional_intense",
       is_featured=True),
    _t("viral", 4,
       title="Cinematic Storytime",
       tagline="Multi-scene viral hook · binge-worthy reveal",
       emoji="🎬",
       wizard_idea="Cinematic viral storytime reel with multiple scenes building to a surprise twist",
       wizard_script="It started like any other day. But what happened next? You will not believe it. Wait for the end.",
       wizard_image_query="cinematic story",
       voice_style="dramatic",
       music_mood="cinematic_epic",
       is_trending=True),
    _t("festival", 4,
       title="Eid Mubarak",
       tagline="Crescent moon · family · cinematic celebration",
       emoji="🌙",
       wizard_idea="Cinematic Eid Mubarak reel with crescent moon, lanterns, and family celebration",
       wizard_script="Eid Mubarak. The moon rises. Hearts unite. Forgiveness. Family. Joy. May this Eid bring blessings.",
       wizard_image_query="eid lantern moon",
       voice_style="warm",
       music_mood="festive_cinematic"),
    _t("emotional", 4,
       title="Soldier's Sacrifice",
       tagline="The price of freedom · patriotic cinematic",
       emoji="🪖",
       wizard_idea="Patriotic cinematic reel about a soldier's silent sacrifice for his nation and family",
       wizard_script="He stood at the border. So you could sleep at home. Salute the brave. Their sacrifice is our freedom.",
       wizard_image_query="soldier flag",
       voice_style="powerful",
       music_mood="cinematic_emotional",
       is_featured=True),
    _t("romantic", 4,
       title="Wedding Vows",
       tagline="The day she said yes · cinematic wedding reel",
       emoji="💒",
       wizard_idea="Cinematic wedding day reel celebrating the moment two souls become one forever",
       wizard_script="The aisle. The look. The vow. From this day forward, hand in hand, for all our days. Forever begins.",
       wizard_image_query="indian wedding",
       voice_style="romantic",
       music_mood="romantic_cinematic"),
    _t("ads", 4,
       title="Luxury Brand Story",
       tagline="High-end cinematic · slow motion product hero",
       emoji="💎",
       wizard_idea="Premium luxury brand cinematic reel with slow motion product showcase and elegant lighting",
       wizard_script="Crafted with intention. Designed for those who notice. Every detail. Every moment. Pure luxury.",
       wizard_image_query="luxury product",
       voice_style="confident",
       music_mood="cinematic_epic",
       is_featured=True,
       is_trending=True),
    _t("aesthetic", 4,
       title="Northern Lights",
       tagline="Aurora skies · once-in-a-lifetime travel",
       emoji="🌌",
       wizard_idea="Breathtaking aesthetic reel of the Northern Lights aurora dancing across an arctic sky",
       wizard_script="Above the Arctic. Green ribbons fall from the sky. The universe paints alive. Bucket list. Witness it.",
       wizard_image_query="aurora borealis",
       voice_style="warm",
       music_mood="ambient_cinematic"),
    _t("motivation", 4,
       title="World Champion",
       tagline="Years of grind · the moment of victory",
       emoji="🏆",
       wizard_idea="Cinematic motivation reel about a world champion athlete's years of grind paying off",
       wizard_script="Years of pain. Sacrifice. Doubt. Then the moment. The roar of the crowd. World champion. Worth it all.",
       wizard_image_query="champion victory",
       voice_style="powerful",
       music_mood="cinematic_epic",
       is_trending=True),
]


# ---------------------------------------------------------------------
# Post-seed enrichment — auto-assign plan_tier + rich prompts[]
# ---------------------------------------------------------------------
# Each category covers all 4 plans (free | starter | creator | pro) so users
# always see at least one option per tier.
_FREE_IDS = {
    "mp_bhajan_01",      # Krishna Bhakti
    "mp_viral_01",       # Monday Morning
    "mp_festival_01",    # Diwali Lights
    "mp_emotional_01",   # Mother's Love
    "mp_romantic_01",    # First Love
    "mp_ads_02",         # Restaurant Promo
    "mp_aesthetic_01",   # Coffee Shop Morning
    "mp_motivation_03",  # 5 AM Club
}
_STARTER_IDS = {
    "mp_bhajan_03",      # Hanuman Chalisa
    "mp_viral_02",       # That One Friend
    "mp_festival_02",    # Holi Colors
    "mp_emotional_03",   # Childhood Memories
    "mp_romantic_02",    # Long Distance
    "mp_ads_03",         # Fitness Studio
    "mp_aesthetic_02",   # Rainy Window
    "mp_motivation_02",  # Never Give Up
}
_CREATOR_IDS = {
    "mp_bhajan_02",      # Shiv Tandav
    "mp_viral_03",       # Wait For It
    "mp_festival_03",    # Janmashtami
    "mp_emotional_02",   # Father's Sacrifice
    "mp_romantic_03",    # Anniversary Special
    "mp_ads_01",         # Product Launch
    "mp_aesthetic_03",   # Mountain Sunrise
    "mp_motivation_01",  # CEO Mindset
}
_PRO_IDS = {
    "mp_bhajan_04",      # Devi Maa Aarti (NEW)
    "mp_viral_04",       # Cinematic Storytime (NEW)
    "mp_festival_04",    # Eid Mubarak (NEW)
    "mp_emotional_04",   # Soldier's Sacrifice (NEW)
    "mp_romantic_04",    # Wedding Vows (NEW)
    "mp_ads_04",         # Luxury Brand Story (NEW)
    "mp_aesthetic_04",   # Northern Lights (NEW)
    "mp_motivation_04",  # World Champion (NEW)
}

for _t_ in SEED_TEMPLATES:
    # Plan tier
    if _t_["id"] in _PRO_IDS:
        _t_["plan_tier"] = "pro"
    elif _t_["id"] in _CREATOR_IDS:
        _t_["plan_tier"] = "creator"
    elif _t_["id"] in _STARTER_IDS:
        _t_["plan_tier"] = "starter"
    else:
        _t_["plan_tier"] = "free"
    # Rich prompts
    if not _t_.get("prompts"):
        _t_["prompts"] = _build_rich_prompts(
            _t_.get("wizard_idea", ""),
            _t_.get("wizard_script", ""),
            _t_.get("wizard_image_query", ""),
            _t_.get("music_mood", ""),
        )


CATEGORY_META = [
    {"id": "bhajan",     "label": "Bhajan",     "emoji": "🕉️",  "color": "#F59E0B", "order": 1},
    {"id": "viral",      "label": "Viral",      "emoji": "🔥",  "color": "#EF4444", "order": 2},
    {"id": "festival",   "label": "Festival",   "emoji": "🪔",  "color": "#FBBF24", "order": 3},
    {"id": "emotional",  "label": "Emotional",  "emoji": "❤️",  "color": "#EC4899", "order": 4},
    {"id": "romantic",   "label": "Romantic",   "emoji": "💕",  "color": "#F472B6", "order": 5},
    {"id": "ads",        "label": "Ads",        "emoji": "📢",  "color": "#10B981", "order": 6},
    {"id": "aesthetic",  "label": "Aesthetic",  "emoji": "✨",  "color": "#A78BFA", "order": 7},
    {"id": "motivation", "label": "Motivation", "emoji": "💪",  "color": "#6366F1", "order": 8},
]


async def ensure_seeded(db, *, force: bool = False) -> dict:
    """Idempotent: insert seed templates if marketplace_templates is empty.
    Also performs a non-destructive migration on every restart:
      • inserts any seed template whose `id` does not yet exist in the DB
      • backfills `plan_tier` and `prompts` for legacy templates
      • re-syncs `plan_tier` to match SEED_TEMPLATES whenever it differs
        (so re-categorising templates between sessions Just Works™)
    Always returns counts so callers can log."""
    existing = await db.marketplace_templates.count_documents({})
    if existing == 0 or force:
        if force and existing > 0:
            await db.marketplace_templates.delete_many({})
        await db.marketplace_templates.insert_many([dict(t) for t in SEED_TEMPLATES])
        return {"seeded": True, "inserted": len(SEED_TEMPLATES), "existing": 0 if force else existing, "forced": force}

    # ---- Insert any NEW seed templates that don't exist yet ---------------
    seed_by_id = {t["id"]: t for t in SEED_TEMPLATES}
    db_ids = {d["id"] async for d in db.marketplace_templates.find({}, {"id": 1})}
    new_inserts = [dict(t) for tid, t in seed_by_id.items() if tid not in db_ids]
    if new_inserts:
        await db.marketplace_templates.insert_many(new_inserts)

    # ---- Migrate / re-sync existing docs ----------------------------------
    migrated = 0
    cursor = db.marketplace_templates.find(
        {},
        {"id": 1, "plan_tier": 1, "prompts": 1, "wizard_idea": 1,
         "wizard_script": 1, "wizard_image_query": 1, "music_mood": 1, "title": 1},
    )
    docs = await cursor.to_list(length=400)
    for d in docs:
        seed = seed_by_id.get(d.get("id"))
        patch = {}
        # plan_tier — RE-SYNC to seed tier whenever it differs (idempotent)
        seed_tier = (seed or {}).get("plan_tier") if seed else None
        if seed_tier and d.get("plan_tier") != seed_tier:
            patch["plan_tier"] = seed_tier
        elif not d.get("plan_tier"):
            # Doc not in SEED (e.g. mp_funny_*) and missing tier → default to free
            patch["plan_tier"] = "free"
        # prompts — only fill if currently empty
        if not d.get("prompts"):
            if seed and seed.get("prompts"):
                patch["prompts"] = seed["prompts"]
            else:
                patch["prompts"] = _build_rich_prompts(
                    d.get("wizard_idea") or d.get("title", ""),
                    d.get("wizard_script", ""),
                    d.get("wizard_image_query", ""),
                    d.get("music_mood", ""),
                )
        if patch:
            await db.marketplace_templates.update_one({"id": d["id"]}, {"$set": patch})
            migrated += 1
    return {
        "seeded": False,
        "inserted": len(new_inserts),
        "existing": existing,
        "migrated": migrated,
    }


async def enrich_thumbnails(db, *, force: bool = False) -> dict:
    """Phase-2 polish — pull a Pixabay vertical image for every template that
    doesn't already have a thumbnail (or all of them if force=True).
    Runs as a background task at startup so the UI gets real visuals on next page-load."""
    from core import pixabay  # lazy to avoid circular import on module load
    import logging
    log = logging.getLogger("marketplace_seed")
    q: dict = {"is_active": True}
    if not force:
        q["$or"] = [{"thumbnail": {"$exists": False}}, {"thumbnail": None}, {"thumbnail": ""}]
    cursor = db.marketplace_templates.find(q, {"id": 1, "wizard_image_query": 1, "title": 1})
    items = await cursor.to_list(length=200)
    enriched = 0
    skipped = 0
    for it in items:
        try:
            query = (it.get("wizard_image_query") or it.get("title") or "").strip()
            if not query:
                skipped += 1
                continue
            hits = await pixabay.search_images(query, count=4, orientation="vertical")
            if not hits:
                skipped += 1
                continue
            best = hits[0]
            thumb = best.get("largeImageURL") or best.get("webformatURL") or best.get("previewURL")
            if not thumb:
                skipped += 1
                continue
            await db.marketplace_templates.update_one(
                {"id": it["id"]},
                {"$set": {"thumbnail": thumb, "thumbnail_source": "pixabay"}},
            )
            enriched += 1
        except Exception as e:
            log.debug("thumbnail enrich failed for %s: %s", it.get("id"), e)
            skipped += 1
    log.info("marketplace: enriched %d thumbnails (skipped %d)", enriched, skipped)
    return {"enriched": enriched, "skipped": skipped, "total_candidates": len(items)}
