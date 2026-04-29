"""Magic Hour credit costs, quality tiers, and SFX catalog.
Pure data constants — no side-effects. Importable everywhere.
"""
from typing import Optional

# Magic Hour credit cost table (credits/sec for videos, credits/image for stills)
MH_CREDIT_COSTS = {
    "lip_sync_per_sec": 7,          # Lip Sync: ~7 credits/sec of output video
    "face_swap_per_sec": 3,         # Face Swap Video: ~3 credits/sec
    "face_swap_photo": 6,           # Face Swap Image: ~6 credits/image
    "head_swap": 10,                # Head Swap image: ~10 credits
    "ai_clothes_changer": 10,       # Body/Outfit Swap: ~10 credits per image
    "ai_image_generator": 5,        # AI Image: ~5 credits per image
    "text_to_video_per_sec": 10,    # Text-to-Video: ~10 credits/sec
    "image_to_video_per_sec": 10,   # Image-to-Video: ~10 credits/sec
    "video_to_video_per_sec": 8,    # Video-to-Video: ~8 credits/sec
    "video_redub_per_sec": 7,       # Video Re-dub (uses lip_sync): ~7 credits/sec
}

# Magic Hour quality tiers — user-facing model selector mapped to MH quality_mode value.
# Credit multiplier vs. per-sec base cost (Studio = 1.0, Quick = 0.8, Cinematic = 1.5).
# Cinematic is UI-disabled (greyed) for now — shows users what's coming.
MH_QUALITY_TIERS = [
    {"id": "quick",     "label": "Quick",     "enabled": True,  "multiplier": 0.8, "desc": "Faster + cheaper (Kling Lite)"},
    {"id": "studio",    "label": "Studio",    "enabled": True,  "multiplier": 1.0, "default": True, "desc": "Default balanced (Kling 2.5)"},
    {"id": "cinematic", "label": "Cinematic", "enabled": False, "multiplier": 1.5, "desc": "Premium (coming soon)"},
]

# Full SFX catalog (Magic Hour-inspired, using royalty-free Pixabay CDN URLs).
# Backend downloads and ffmpeg-mixes these into final videos.
# Frontend sees everything EXCEPT the raw `url` (kept server-side).
SFX_CATALOG = [
    {"id": "none", "name": "None", "icon": "volume-mute", "category": "None", "url": None},
    # Crowd / Reaction
    {"id": "applause", "name": "Applause", "icon": "happy", "category": "Reaction",
     "url": "https://cdn.pixabay.com/download/audio/2022/03/10/audio_d6f7e95e22.mp3"},
    {"id": "laugh_track", "name": "Laugh Track", "icon": "happy-outline", "category": "Reaction",
     "url": "https://cdn.pixabay.com/download/audio/2022/03/15/audio_942d31d789.mp3"},
    {"id": "cheer", "name": "Crowd Cheer", "icon": "people", "category": "Reaction",
     "url": "https://cdn.pixabay.com/download/audio/2022/03/24/audio_ada3e0b14e.mp3"},
    {"id": "gasp", "name": "Gasp", "icon": "alert-circle", "category": "Reaction",
     "url": "https://cdn.pixabay.com/download/audio/2022/03/10/audio_15c4edb3f7.mp3"},
    # Cinematic
    {"id": "dramatic", "name": "Dramatic Hit", "icon": "flash", "category": "Cinematic",
     "url": "https://cdn.pixabay.com/download/audio/2022/01/18/audio_d0c6ff1b1f.mp3"},
    {"id": "cinematic_rise", "name": "Cinematic Rise", "icon": "trending-up", "category": "Cinematic",
     "url": "https://cdn.pixabay.com/download/audio/2022/09/07/audio_3c79b88c65.mp3"},
    {"id": "suspense", "name": "Suspense", "icon": "eye", "category": "Cinematic",
     "url": "https://cdn.pixabay.com/download/audio/2022/04/20/audio_adac5e4a6b.mp3"},
    {"id": "epic_hit", "name": "Epic Impact", "icon": "nuclear", "category": "Cinematic",
     "url": "https://cdn.pixabay.com/download/audio/2022/04/26/audio_18d2a41c81.mp3"},
    # Transitions
    {"id": "whoosh", "name": "Whoosh", "icon": "airplane", "category": "Transition",
     "url": "https://cdn.pixabay.com/download/audio/2022/03/15/audio_8cb749dc5c.mp3"},
    {"id": "swish", "name": "Swish", "icon": "chevron-forward", "category": "Transition",
     "url": "https://cdn.pixabay.com/download/audio/2022/03/10/audio_bda85b0fa7.mp3"},
    {"id": "pop", "name": "Pop", "icon": "ellipse", "category": "Transition",
     "url": "https://cdn.pixabay.com/download/audio/2022/03/10/audio_1abd0c7b7d.mp3"},
    # Funny / Meme
    {"id": "bgm_funny", "name": "Funny BGM", "icon": "musical-notes", "category": "Funny",
     "url": "https://cdn.pixabay.com/download/audio/2023/03/20/audio_15c31f8d03.mp3"},
    {"id": "boing", "name": "Boing", "icon": "sync", "category": "Funny",
     "url": "https://cdn.pixabay.com/download/audio/2022/03/15/audio_b3ceb1bd4e.mp3"},
    {"id": "drum_roll", "name": "Drum Roll", "icon": "pulse", "category": "Funny",
     "url": "https://cdn.pixabay.com/download/audio/2022/11/22/audio_ddaa0a46c4.mp3"},
    # Music beds
    {"id": "bgm_cinematic", "name": "Cinematic Score", "icon": "film", "category": "Music",
     "url": "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3"},
    {"id": "bgm_upbeat", "name": "Upbeat Vibe", "icon": "flash-outline", "category": "Music",
     "url": "https://cdn.pixabay.com/download/audio/2022/03/15/audio_c8c8a73467.mp3"},
    {"id": "bgm_chill", "name": "Chill Lofi", "icon": "snow", "category": "Music",
     "url": "https://cdn.pixabay.com/download/audio/2022/10/25/audio_946bc5fcc6.mp3"},
]


def sfx_by_id(sfx_id: Optional[str]) -> Optional[dict]:
    """Return catalog entry for given SFX id, or None for 'none'/unknown."""
    if not sfx_id or sfx_id == "none":
        return None
    for s in SFX_CATALOG:
        if s["id"] == sfx_id:
            return s
    return None


# ========== Sprint 2 — Audio Emotion Engine ==========
# Voice style presets. Each bundles rate/pitch adjustments, a suggested BGM SFX,
# mix-level defaults, and a pause multiplier for [pause:Xs] markers in text.
# Frontend renders these as emoji chips; users apply one preset at submit time.
VOICE_STYLES = [
    {
        "id": "neutral",
        "label": "Neutral",
        "emoji": "🎙️",
        "desc": "Default, no adjustments.",
        "rate": None,           # edge-tts rate (e.g. '+10%'); None = no change
        "pitch": None,          # edge-tts pitch (e.g. '+5Hz')
        "bgm_suggest": "none",  # suggested SFX id; user can override
        "bgm_volume": 0.25,     # ffmpeg mix volume for BGM
        "voice_volume": 1.2,    # ffmpeg mix volume for voice
        "pause_multiplier": 1.0,
    },
    {
        "id": "devotional",
        "label": "Devotional",
        "emoji": "🪔",
        "desc": "Slow, reverent, warm — good for bhajans, shlokas, spiritual content.",
        "rate": "-10%",
        "pitch": "-5Hz",
        "bgm_suggest": "bgm_cinematic",
        "bgm_volume": 0.32,
        "voice_volume": 1.25,
        "pause_multiplier": 1.5,
    },
    {
        "id": "motivation",
        "label": "Motivation",
        "emoji": "🔥",
        "desc": "Punchy, confident, energetic — for motivational reels and fitness.",
        "rate": "+12%",
        "pitch": "+10Hz",
        "bgm_suggest": "bgm_upbeat",
        "bgm_volume": 0.30,
        "voice_volume": 1.3,
        "pause_multiplier": 0.7,
    },
    {
        "id": "story",
        "label": "Story",
        "emoji": "📖",
        "desc": "Natural narrator tone — for stories, explainers, kid content.",
        "rate": "-3%",
        "pitch": None,
        "bgm_suggest": "bgm_chill",
        "bgm_volume": 0.22,
        "voice_volume": 1.2,
        "pause_multiplier": 1.2,
    },
    {
        "id": "funny",
        "label": "Funny",
        "emoji": "😂",
        "desc": "Faster, higher-pitched, playful — for comedy skits and memes.",
        "rate": "+18%",
        "pitch": "+15Hz",
        "bgm_suggest": "bgm_funny",
        "bgm_volume": 0.28,
        "voice_volume": 1.25,
        "pause_multiplier": 0.6,
    },
]


def voice_style_by_id(style_id: Optional[str]):
    """Look up a voice style preset by id. Returns None if not found or id is None/empty."""
    if not style_id:
        return None
    for s in VOICE_STYLES:
        if s["id"] == style_id:
            return s
    return None


# ========== Sprint 3 Phase A — Expression Engine: FFmpeg Motion Presets ==========
# Each preset is a Ken-Burns style camera move applied to a still image via ffmpeg `zoompan`.
# Zero credit cost (local ffmpeg), instant results, perfect for Quick mode.
#
# Schema: { id, label, emoji, desc, zoompan_expr } where zoompan_expr defines z/x/y over frames.
# Target output: {resolution} at 25fps for a given duration. Duration is dynamic (d=25*seconds).
#
# The `zoompan_expr` placeholder '{D}' is replaced at render time with the total frame count.
MOTION_PRESETS = [
    {
        "id": "none",
        "label": "None",
        "emoji": "⏸️",
        "desc": "Static image (no motion).",
        "zoompan_expr": None,
    },
    {
        "id": "zoom_in",
        "label": "Zoom In",
        "emoji": "🔍",
        "desc": "Slow zoom toward the center — classic cinematic reveal.",
        "zoompan_expr": {
            "z": "min(zoom+0.0015,1.5)",
            "x": "iw/2-(iw/zoom/2)",
            "y": "ih/2-(ih/zoom/2)",
        },
    },
    {
        "id": "zoom_out",
        "label": "Zoom Out",
        "emoji": "🔎",
        "desc": "Pull back from a close-up — reveal the scene.",
        "zoompan_expr": {
            "z": "if(lte(zoom,1.0),1.5,max(1.001,zoom-0.0018))",
            "x": "iw/2-(iw/zoom/2)",
            "y": "ih/2-(ih/zoom/2)",
        },
    },
    {
        "id": "pan_left",
        "label": "Pan Left",
        "emoji": "⬅️",
        "desc": "Camera drifts left across the scene.",
        "zoompan_expr": {
            "z": "1.25",
            "x": "iw - (iw/zoom) - (on/{D})*(iw - iw/zoom)",
            "y": "ih/2-(ih/zoom/2)",
        },
    },
    {
        "id": "pan_right",
        "label": "Pan Right",
        "emoji": "➡️",
        "desc": "Camera drifts right across the scene.",
        "zoompan_expr": {
            "z": "1.25",
            "x": "(on/{D})*(iw - iw/zoom)",
            "y": "ih/2-(ih/zoom/2)",
        },
    },
    {
        "id": "pan_up",
        "label": "Pan Up",
        "emoji": "⬆️",
        "desc": "Camera tilts upward — great for reveals of faces/sky.",
        "zoompan_expr": {
            "z": "1.25",
            "x": "iw/2-(iw/zoom/2)",
            "y": "ih - (ih/zoom) - (on/{D})*(ih - ih/zoom)",
        },
    },
    {
        "id": "pan_down",
        "label": "Pan Down",
        "emoji": "⬇️",
        "desc": "Camera tilts downward — great for introductions.",
        "zoompan_expr": {
            "z": "1.25",
            "x": "iw/2-(iw/zoom/2)",
            "y": "(on/{D})*(ih - ih/zoom)",
        },
    },
    {
        "id": "ken_burns",
        "label": "Ken Burns",
        "emoji": "🎞️",
        "desc": "Slow zoom + diagonal drift — documentary feel.",
        "zoompan_expr": {
            "z": "min(zoom+0.0012,1.35)",
            "x": "(on/{D})*(iw - iw/zoom)",
            "y": "(on/{D})*(ih - ih/zoom)",
        },
    },
]


def motion_preset_by_id(pid: Optional[str]):
    if not pid or pid == "none":
        return None
    for m in MOTION_PRESETS:
        if m["id"] == pid:
            return m
    return None
