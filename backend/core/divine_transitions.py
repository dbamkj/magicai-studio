"""Phase 1 — Divine Transformation: cinematic FFmpeg transitions + deity presets.

All transitions work as prepended overlay clips that FADE INTO the main video.
Each transition is rendered as a short (0.5-1.5s) prefix clip that is concat'd
with the main animated face-swap output, or as an FFmpeg filter applied to the
first N frames of the main clip.

Zero additional cost (runs locally via ffmpeg).
"""
from typing import Optional


# ========== Cinematic FFmpeg Transitions ==========
# Each transition defines a prefix-clip + optional fade-in on the main video.
# `prefix_filter_complex` is an FFmpeg filter that generates a short intro clip
# from a solid color / test source. `main_fade_in_duration` is how long the main
# clip should crossfade from the prefix end.
#
# Schema:
#   id, label, emoji, desc
#   prefix_duration_sec: float         # length of the intro clip
#   prefix_ffmpeg_args: List[str]      # ffmpeg args to produce the prefix clip (before -i / output)
#   overlay_fade_in: float             # seconds of fade-in on the main clip after prefix
DIVINE_TRANSITIONS = [
    {
        "id": "divine_reveal",
        "label": "Divine Reveal",
        "emoji": "✨",
        "desc": "Pure white flash fades to reveal the divine form.",
        "prefix_duration_sec": 0.8,
        "prefix_color": "white",
        "overlay_fade_in": 0.5,
    },
    {
        "id": "light_burst",
        "label": "Light Burst",
        "emoji": "💥",
        "desc": "Radial golden burst expands outward into the scene.",
        "prefix_duration_sec": 1.0,
        "prefix_color": "#FFD700",  # gold
        "overlay_fade_in": 0.6,
    },
    {
        "id": "golden_glow",
        "label": "Golden Glow",
        "emoji": "🌟",
        "desc": "Warm golden gradient washes over before settling.",
        "prefix_duration_sec": 0.6,
        "prefix_color": "#F59E0B",  # amber
        "overlay_fade_in": 0.7,
    },
    {
        "id": "celestial_fade",
        "label": "Celestial Fade",
        "emoji": "🌌",
        "desc": "Deep cosmic purple dissolves into the divine scene.",
        "prefix_duration_sec": 0.9,
        "prefix_color": "#1E0C3A",  # cosmic purple
        "overlay_fade_in": 0.8,
    },
    {
        "id": "lotus_bloom",
        "label": "Lotus Bloom",
        "emoji": "🪷",
        "desc": "Soft pink-rose bloom reveals the divine form.",
        "prefix_duration_sec": 0.7,
        "prefix_color": "#FF6B9D",  # rose pink
        "overlay_fade_in": 0.6,
    },
]


def transition_by_id(tid: Optional[str]):
    if not tid or tid == "none":
        return None
    for t in DIVINE_TRANSITIONS:
        if t["id"] == tid:
            return t
    return None


# ========== Divine SFX catalog (appended to main SFX_CATALOG) ==========
# Royalty-free Pixabay URLs — cached + mixed by server.py ffmpeg pipeline.
DIVINE_SFX = [
    {"id": "om_chant",        "name": "Om Chant",        "icon": "musical-note",  "category": "Divine",
     "url": "https://cdn.pixabay.com/download/audio/2022/05/13/audio_ac41b2ca57.mp3"},
    {"id": "temple_bell",     "name": "Temple Bell",     "icon": "notifications", "category": "Divine",
     "url": "https://cdn.pixabay.com/download/audio/2022/10/14/audio_ce9a1bfa80.mp3"},
    {"id": "celestial_chime", "name": "Celestial Chime", "icon": "sparkles",      "category": "Divine",
     "url": "https://cdn.pixabay.com/download/audio/2022/03/10/audio_0625c1539c.mp3"},
    {"id": "conch_shankh",    "name": "Conch Shankh",    "icon": "megaphone",     "category": "Divine",
     "url": "https://cdn.pixabay.com/download/audio/2023/06/06/audio_04e9a7b0b5.mp3"},
    {"id": "divine_whoosh",   "name": "Divine Whoosh",   "icon": "flash",         "category": "Divine",
     "url": "https://cdn.pixabay.com/download/audio/2022/02/23/audio_e5b3a3edec.mp3"},
]


# ========== Deity presets ==========
# Each deity has a Gemini-friendly prompt; users can either (a) upload their
# own divine reference photo, or (b) press "Generate deity portrait" which runs
# the prompt through the existing /api/generate-idea-image flow.
DEITY_PRESETS = [
    {
        "id": "krishna",
        "label": "Lord Krishna",
        "emoji": "🦚",
        "festival_pack": "janmashtami",
        "gradient": ["#FBBF24", "#F97316"],
        "prompt": "Divine close-up portrait of Lord Krishna, blue-skinned, peacock feather crown, flute in hand, golden aura, Vrindavan forest background, serene smile, cinematic lighting, 4k",
        "suggested_transition": "golden_glow",
        "suggested_sfx": "om_chant",
    },
    {
        "id": "shiva",
        "label": "Lord Shiva",
        "emoji": "🔱",
        "festival_pack": "mahashivratri",
        "gradient": ["#1E3A8A", "#0EA5E9"],
        "prompt": "Majestic close-up of Lord Shiva meditating, third eye glowing, crescent moon on head, snake around neck, ash-smeared skin, Mount Kailash in background, blue cosmic aura, cinematic",
        "suggested_transition": "celestial_fade",
        "suggested_sfx": "conch_shankh",
    },
    {
        "id": "durga",
        "label": "Goddess Durga",
        "emoji": "🔥",
        "festival_pack": "navratri",
        "gradient": ["#DC2626", "#FBBF24"],
        "prompt": "Powerful close-up of Goddess Durga, red sari, multiple arms holding divine weapons, tiger mount, golden crown, fierce yet serene expression, red and gold aura, cinematic",
        "suggested_transition": "light_burst",
        "suggested_sfx": "temple_bell",
    },
    {
        "id": "ganesha",
        "label": "Lord Ganesha",
        "emoji": "🐘",
        "festival_pack": None,
        "gradient": ["#F97316", "#EC4899"],
        "prompt": "Close-up portrait of Lord Ganesha, elephant head, broken tusk, golden crown, red vermillion, gentle smile, divine glow, lotus background, cinematic",
        "suggested_transition": "divine_reveal",
        "suggested_sfx": "om_chant",
    },
    {
        "id": "ram",
        "label": "Lord Ram",
        "emoji": "🏹",
        "festival_pack": None,
        "gradient": ["#10B981", "#FBBF24"],
        "prompt": "Regal close-up of Lord Ram with bow and arrow, golden crown, noble serene expression, Ayodhya palace background, divine aura, cinematic",
        "suggested_transition": "lotus_bloom",
        "suggested_sfx": "celestial_chime",
    },
    {
        "id": "hanuman",
        "label": "Lord Hanuman",
        "emoji": "🙏",
        "festival_pack": None,
        "gradient": ["#F97316", "#DC2626"],
        "prompt": "Powerful close-up of Lord Hanuman, red monkey face, golden mace (gada), muscular devotional stance, mountain background, glowing divine aura, cinematic",
        "suggested_transition": "divine_reveal",
        "suggested_sfx": "divine_whoosh",
    },
]


def deity_by_id(did: Optional[str]):
    if not did:
        return None
    for d in DEITY_PRESETS:
        if d["id"] == did:
            return d
    return None


# ========== Credit cost ==========
# Divine Transformation = face_swap_photo (6 MH credits) + motion + transition + SFX.
# We bundle a premium cinematic uplift so the end-user price reflects effort.
DIVINE_TRANSFORM_COST = 120
