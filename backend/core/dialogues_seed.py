"""Phase-4B + 4C — viral dialogues bank + funny avatar templates.

Two seed datasets stored in Mongo for reuse across the Cartoon Avatar System,
Quick Reel wizard, and the Marketplace:

  • viral_dialogues  — 100 one-liners across 10 vibes (Sass, Roast, Motivation,
    Heartbreak, Office, Aunty/Uncle, Coding-bro, Bhakti, Punjabi, Hinglish-meme).

  • marketplace_templates — additional 10 "funny avatar" presets that plug
    straight into the existing Phase-2 marketplace. They use mode='video' so
    Quick Reel can render them with the existing pipeline; mode='cartoon' is
    reserved for the Phase-4A cartoon avatar pipeline (next iteration).

All seeders are idempotent — they no-op if the collection is already populated
with that data set's ids.
"""
from __future__ import annotations
from datetime import datetime, timezone


_NOW = lambda: datetime.now(timezone.utc)


# =====================================================================
# 1. VIRAL DIALOGUES — 100 one-liners (vibe-tagged)
# =====================================================================
# Each row: (vibe, language, text, suggested_emotion, share_score 1..5)
VIRAL_DIALOGUES: list[dict] = []


def _d(vibe: str, lang: str, text: str, emotion: str = "neutral", score: int = 3) -> dict:
    return {
        "id": f"vd_{len(VIRAL_DIALOGUES) + 1:03d}",
        "vibe": vibe, "lang": lang, "text": text,
        "emotion": emotion, "share_score": score,
        "is_active": True, "usage_count": 0,
        "created_at": _NOW(),
    }


# --- SASS / ATTITUDE (10)
for t, e in [
    ("If you're not the main character, scroll faster.", "happy"),
    ("They liked you when you were quiet. Imagine now.", "happy"),
    ("Plot twist: I'm the lesson.", "happy"),
    ("My standards aren't high. They're just not yours.", "happy"),
    ("Soft heart, sharper mind, sharpest replies.", "happy"),
    ("I don't argue. I confirm what I already knew.", "happy"),
    ("Energy doesn't lie. Stop testing it.", "neutral"),
    ("Receipts? I have a folder.", "happy"),
    ("If silence offends you, healing terrifies you.", "neutral"),
    ("I'm not for everyone. I'm for the right one.", "happy"),
]:
    VIRAL_DIALOGUES.append(_d("sass", "en", t, e, 4))


# --- ROAST / SAVAGE (10)
for t, e in [
    ("You're not deep, you're just unanswered.", "neutral"),
    ("Confidence without competence is just noise.", "angry"),
    ("Tag yourself — I'm the disappointment.", "happy"),
    ("Audacity is free. Manners aren't.", "angry"),
    ("Imagine peaking in WhatsApp groups.", "happy"),
    ("Your vibe? Loading… still loading…", "happy"),
    ("'Just kidding' is the funeral of every truth.", "neutral"),
    ("Big talk, small follow-through. Classic.", "angry"),
    ("Healing is hard when ego is louder.", "neutral"),
    ("You're the moral of someone's growth story.", "happy"),
]:
    VIRAL_DIALOGUES.append(_d("roast", "en", t, e, 4))


# --- MOTIVATION (10)
for t, e in [
    ("They sleep. You build. That's the whole secret.", "happy"),
    ("The version of you they doubted is coming.", "happy"),
    ("Quiet grind. Loud results.", "happy"),
    ("If it scares you, it's the right door.", "surprised"),
    ("Discipline is loving your future self.", "happy"),
    ("The world rewards the unstoppable, not the gifted.", "happy"),
    ("Be the one who shows up when no one's watching.", "happy"),
    ("Pain is rent. Pay it and walk past.", "neutral"),
    ("Every 'no' funded my 'yes'.", "happy"),
    ("Your dream is afraid of you giving up.", "happy"),
]:
    VIRAL_DIALOGUES.append(_d("motivation", "en", t, e, 5))


# --- HEARTBREAK / EMOTIONAL (10)
for t, e in [
    ("You weren't hard to love. They were hard to grow.", "sad"),
    ("Some endings are mercy in disguise.", "sad"),
    ("I miss you. I'm also healing. Both can be true.", "sad"),
    ("Closure is something you give yourself.", "neutral"),
    ("They left because peace was foreign to them.", "sad"),
    ("Your softness scared the people who can't feel.", "sad"),
    ("Loving you was never the mistake — losing me was theirs.", "sad"),
    ("I outgrew the comfort of being misunderstood.", "neutral"),
    ("Some chapters end so the right ones can begin.", "neutral"),
    ("I forgive, but I remember.", "neutral"),
]:
    VIRAL_DIALOGUES.append(_d("heartbreak", "en", t, e, 5))


# --- OFFICE / WORK (10)
for t, e in [
    ("Meetings: where minutes are taken and hours are lost.", "happy"),
    ("'Quick sync' has never been quick.", "angry"),
    ("My personality is just unread emails now.", "happy"),
    ("Per my last email — please open the first one.", "angry"),
    ("Salary on time. Sanity? Out of office.", "happy"),
    ("Monday is just Sunday's revenge.", "sad"),
    ("Unpaid overtime is just billable trauma.", "angry"),
    ("Boss said 'we are family' — I'm asking for inheritance.", "happy"),
    ("Friday smiles like Sunday cries.", "happy"),
    ("Started the week strong. Ended it on a cope.", "sad"),
]:
    VIRAL_DIALOGUES.append(_d("office", "en", t, e, 4))


# --- AUNTY / UNCLE GOSSIP (Hinglish, 10)
for t, e in [
    ("Sharma ji ka beta phir se topper aa gaya.", "surprised"),
    ("Beta, shaadi kab? Bas yehi sawaal hai zindagi me.", "happy"),
    ("Khaana ban gaya? Phir bhi kuch banao na.", "happy"),
    ("Aunty ki nazar ko kala teeka chahiye.", "happy"),
    ("Itna phone mat dekh, aankhein kharab hojaayegi.", "angry"),
    ("Padhai chhod ke reel banata hai.", "angry"),
    ("Apne age ke logon ko dekh — sab settle ho gaye.", "neutral"),
    ("Muh dho ke aaja, kuch khaa le.", "happy"),
    ("Aaj kuch alag dikh rahe ho — kuch chal raha hai?", "surprised"),
    ("Ladki ka naam le ke dekh, ammi ko bata dungi.", "angry"),
]:
    VIRAL_DIALOGUES.append(_d("aunty", "hi-en", t, e, 5))


# --- CODING / TECH BRO (10)
for t, e in [
    ("Works on my machine. Always has.", "happy"),
    ("Stack Overflow is my therapist.", "happy"),
    ("99 little bugs in the code, 99 little bugs.", "happy"),
    ("First, solve the problem. Then, write the code.", "neutral"),
    ("It's not a bug, it's an undocumented feature.", "happy"),
    ("Production is my testing environment.", "surprised"),
    ("Coffee.length === 0 → exception thrown.", "happy"),
    ("Real engineers ship. The rest discuss frameworks.", "neutral"),
    ("Git commit -m 'final final FINAL.zip'", "happy"),
    ("AI didn't take my job — it just made it weirder.", "surprised"),
]:
    VIRAL_DIALOGUES.append(_d("coding", "en", t, e, 4))


# --- BHAKTI / DEVOTIONAL (Hindi+English, 10)
for t, e in [
    ("Krishna ke saath, har raah aasaan hai.", "happy"),
    ("Jab Hari saath ho, har dukh chhota lagta hai.", "happy"),
    ("Om Namah Shivaya — courage in three words.", "happy"),
    ("Maa ke charano me hi shanti hai.", "happy"),
    ("Hanuman ji, sankat haran, mangal karan.", "happy"),
    ("Bhagwan dene wala hai, maangne wale ko sharminda nahi karta.", "happy"),
    ("Ram naam mein hi sukoon hai.", "happy"),
    ("Trust the timing of the divine.", "neutral"),
    ("When the mind is calm, the world becomes Vrindavan.", "happy"),
    ("Surrender is not weakness — it's the strongest love.", "neutral"),
]:
    VIRAL_DIALOGUES.append(_d("bhakti", "hi-en", t, e, 5))


# --- PUNJABI VIBE (10)
for t, e in [
    ("Pind to bahar nikla, sapne le ke aaya.", "happy"),
    ("Apna time aayega — patiala vala.", "happy"),
    ("Sherni di chaal aapne aap aandi hai.", "happy"),
    ("Jatt da style alag, attitude alag.", "happy"),
    ("Pyaar nibhana sikhya pind ne, lekin sambhalna mehnat ne.", "neutral"),
    ("Sardiyaan aayian, yaaran nu chhad gayian.", "sad"),
    ("Saath chad gaye, par yaadan mukk ni hundian.", "sad"),
    ("Kothe te chad ke, kude, sun le main aagayi haan.", "happy"),
    ("Apna yaar, apni gaddi, apna naam.", "happy"),
    ("Punjab di mitti, USA da sapna.", "happy"),
]:
    VIRAL_DIALOGUES.append(_d("punjabi", "pa", t, e, 4))


# --- HINGLISH MEME (10)
for t, e in [
    ("Plot twist: main hi villain hu.", "surprised"),
    ("Tu ek kaam karega? Bas reel mat dekh.", "angry"),
    ("Mood: vibe check, but make it Bollywood.", "happy"),
    ("Kahaani me twist nahi tha, twist hi kahaani thi.", "surprised"),
    ("Sapne dekhna free hai, lekin paani-puri 30 ki.", "happy"),
    ("Itna toh boards me bhi nahi soche the.", "surprised"),
    ("Itna soft mat dikh, log advantage le lete hain.", "neutral"),
    ("Pyaar ek dhoka hai, paisa ek nasha.", "happy"),
    ("Status mat daal — privacy bhi rakh.", "happy"),
    ("Reels banao, nahi to relate hone do.", "happy"),
]:
    VIRAL_DIALOGUES.append(_d("hinglish", "hi-en", t, e, 5))


# =====================================================================
# 2. 10 FUNNY AVATAR TEMPLATES — slot into marketplace_templates
# =====================================================================
def _t(category: str, n: int, **kw) -> dict:
    base = {
        "id": f"mp_funny_{n:02d}",
        "category": category,
        "wizard_mode": "video",
        "voice_id": "en-US-JennyNeural",
        "voice_style": "conversational",
        "music_mood": "upbeat_funny",
        "motion": "auto",
        "aspect_ratio": "9:16",
        "duration": 8,
        "usage_count": 0, "view_count": 0,
        "is_featured": False, "is_trending": False, "is_active": True,
        "sort_order": 100 + n,        # placed after the original 24
        "created_at": _NOW(),
        "tags": ["funny", "viral", "avatar"],
    }
    base.update(kw)
    return base


FUNNY_AVATAR_TEMPLATES: list[dict] = [
    _t("viral", 1,
       title="Boss Meme Energy",
       tagline="When boss types 'we need to talk' on Friday EOD",
       emoji="😨",
       wizard_idea="Funny POV reel about boss surprise meeting on Friday",
       wizard_script="POV: It's 5:55 PM Friday. Slack ping. 'Got 5 mins?' Heart drops. Plans cancel. Cry in cubicle.",
       wizard_image_query="office scared employee",
       voice_style="conversational",
       music_mood="suspense_funny",
       is_trending=True),
    _t("viral", 2,
       title="Monday Mode",
       tagline="That undefeated weekly comeback story",
       emoji="🥱",
       wizard_idea="Funny relatable reel about Monday morning struggle for working professionals",
       wizard_script="Alarm. Snooze. Repeat five times. Coffee saves life. Inbox attacks. We survive somehow.",
       wizard_image_query="monday office tired",
       music_mood="upbeat_funny"),
    _t("viral", 3,
       title="Aunty Roast",
       tagline="Sharma ji ka beta strikes again",
       emoji="🫣",
       wizard_idea="Hinglish funny reel about classic Indian aunty interrogation at family gatherings",
       wizard_script="Aunty arrives. Beta, shaadi kab? Salary kitni? Padhai khatam? Phone rakh do. Tag your aunty.",
       wizard_image_query="indian family aunty",
       voice_id="hi-IN-SwaraNeural",
       voice_style="conversational",
       music_mood="upbeat_funny",
       is_featured=True),
    _t("viral", 4,
       title="Coder Life",
       tagline="The 'works on my machine' arc",
       emoji="💻",
       wizard_idea="Funny coder reel about debugging chaos and Stack Overflow worship",
       wizard_script="Code works at home. Breaks in production. Stack Overflow is my therapist. Coffee is fuel. We ship.",
       wizard_image_query="programmer keyboard",
       music_mood="upbeat_funny"),
    _t("viral", 5,
       title="Gym Bro Daily",
       tagline="One more rep, one more excuse",
       emoji="💪",
       wizard_idea="Funny relatable reel about gym bros and missed leg day",
       wizard_script="Bro, today is leg day. Bro, my legs need rest. Bro, every day is leg day. Bro… leg day cancelled.",
       wizard_image_query="gym fitness",
       voice_style="powerful",
       music_mood="energetic_pump"),
    _t("viral", 6,
       title="Diet Day 1 vs Day 3",
       tagline="The undefeated 48-hour meal-plan saga",
       emoji="🍕",
       wizard_idea="Funny reel about how diets fail spectacularly within 3 days",
       wizard_script="Day 1: salad and discipline. Day 2: half the salad. Day 3: pizza and self-acceptance.",
       wizard_image_query="pizza diet food",
       music_mood="upbeat_funny"),
    _t("viral", 7,
       title="Weekend Plans",
       tagline="From 'going out' to 'going to bed'",
       emoji="🛏️",
       wizard_idea="Funny relatable reel about weekend plans always becoming Netflix and bed",
       wizard_script="Friday: club, cafe, beach. Saturday: maybe later. Sunday: Netflix and dosa. Repeat.",
       wizard_image_query="netflix couch weekend",
       music_mood="ambient_chill"),
    _t("viral", 8,
       title="Bollywood Reaction",
       tagline="That dramatic head-turn meme energy",
       emoji="🎬",
       wizard_idea="Funny Bollywood-style overdramatic reaction reel",
       wizard_script="Plot twist incoming. Camera zoom. Dramatic music. Gasp. Background dancers. Drama achieved.",
       wizard_image_query="bollywood drama dance",
       voice_style="dramatic",
       music_mood="suspense_buildup"),
    _t("viral", 9,
       title="Online Class Mood",
       tagline="Camera off, pajamas on, learning… kinda",
       emoji="📚",
       wizard_idea="Funny student reel about online classes with camera off",
       wizard_script="Camera off. Mic muted. Instagram open. Teacher: any doubts? Me: snoring softly.",
       wizard_image_query="student laptop class",
       music_mood="upbeat_funny"),
    _t("viral", 10,
       title="Mom's WiFi Speech",
       tagline="The annual 'pay your own bills' arc",
       emoji="📶",
       wizard_idea="Funny Hinglish reel about Indian moms and WiFi privileges",
       wizard_script="Mom enters. Wifi off. Lecture on. 'Apne paise se le lo'. Promise made. Promise broken. Cycle repeats.",
       wizard_image_query="indian mother wifi",
       voice_id="hi-IN-SwaraNeural",
       voice_style="conversational",
       music_mood="upbeat_funny",
       is_featured=True),
]


# =====================================================================
# SEEDERS
# =====================================================================
async def ensure_dialogues_seeded(db) -> dict:
    existing = await db.viral_dialogues.count_documents({})
    if existing == 0:
        await db.viral_dialogues.insert_many([dict(d) for d in VIRAL_DIALOGUES])
        return {"seeded": True, "inserted": len(VIRAL_DIALOGUES), "existing": 0}
    return {"seeded": False, "inserted": 0, "existing": existing}


async def ensure_funny_avatar_templates_seeded(db) -> dict:
    """Inserts the 10 funny avatar templates into marketplace_templates if any are missing.
    Idempotent — only inserts items whose `id` does not already exist."""
    ids = [t["id"] for t in FUNNY_AVATAR_TEMPLATES]
    cursor = db.marketplace_templates.find({"id": {"$in": ids}}, {"id": 1})
    existing_ids = {x["id"] async for x in cursor}
    to_insert = [dict(t) for t in FUNNY_AVATAR_TEMPLATES if t["id"] not in existing_ids]
    if to_insert:
        await db.marketplace_templates.insert_many(to_insert)
    return {
        "inserted": len(to_insert),
        "skipped_existing": len(existing_ids),
        "total_funny": len(FUNNY_AVATAR_TEMPLATES),
    }
