"""Phase 2 — Story Mode.

3-scene cinematic reel builder. Wraps the existing `process_multishot_bg`
pipeline with 5 narrative templates that auto-fill the 3 scene prompts.

Cost: fixed STORY_MODE_COST=80 (vs raw Multishot 150). Cheaper because the
user gets a guided experience with pre-written prompts + pacing.

Flow:
  1. Frontend GET  /api/story/templates → 5 narrative templates.
  2. Frontend POST /api/story/create with template_id + variables.
  3. Backend fills prompt placeholders, builds 3-shot payload, reserves
     80 credits, kicks off process_multishot_bg, returns project_id.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient

from core.config import MONGO_URL, DB_NAME
from core.billing import preflight_and_reserve, settle_credits

logger = logging.getLogger("story")
logger.setLevel(logging.INFO)

_client = AsyncIOMotorClient(MONGO_URL)
db = _client[DB_NAME]

router = APIRouter(prefix="/api/story", tags=["story"])

STORY_MODE_COST = 80


# ========== Template catalogue ==========
# Each template = narrative blueprint with 3 scenes.
# `{var}` placeholders are filled from user-supplied `variables` dict.
#
# `suggested_voice_style` picks a pre-existing Sprint 2 Audio Emotion preset
# (energetic / calm / dramatic / inspirational / playful) so story tempo is
# automatically matched.
STORY_TEMPLATES = [
    {
        "id": "hero_journey",
        "label": "Hero's Journey",
        "emoji": "🦸",
        "desc": "Ordinary → Challenge → Triumph — classic 3-beat arc.",
        "variables": [
            {"key": "name", "label": "Name / character", "placeholder": "Arjun"},
            {"key": "goal", "label": "Goal / dream", "placeholder": "becoming a cricket star"},
        ],
        "suggested_voice_style": "inspirational",
        "suggested_transition": "crossfade",
        "scenes": [
            {
                "title": "Ordinary world",
                "prompt": "Cinematic establishing shot of {name}, an ordinary person going about daily life, contemplating {goal}. Warm morning light, documentary style.",
                "dialogue": "{name} had a dream. But every day felt the same.",
                "motion": "zoom_in_slow",
                "duration": 5,
            },
            {
                "title": "The challenge",
                "prompt": "Dynamic shot of {name} facing a tough moment — sweat, focus, intensity. Dramatic lighting, cinematic.",
                "dialogue": "Then came the moment that would change everything.",
                "motion": "pan_right",
                "duration": 5,
            },
            {
                "title": "Triumph",
                "prompt": "Powerful hero shot of {name} achieving {goal}. Golden hour light, triumphant pose, crowd cheering in background, cinematic wide shot.",
                "dialogue": "This is how dreams become real.",
                "motion": "dolly_out",
                "duration": 5,
            },
        ],
    },
    {
        "id": "before_after",
        "label": "Before / After",
        "emoji": "🔁",
        "desc": "Transformation reel — perfect for glow-ups & product demos.",
        "variables": [
            {"key": "subject", "label": "Subject / product", "placeholder": "my skincare routine"},
            {"key": "result",  "label": "Result / benefit",  "placeholder": "clear glowing skin"},
        ],
        "suggested_voice_style": "energetic",
        "suggested_transition": "cut",
        "scenes": [
            {
                "title": "Before",
                "prompt": "Close-up shot showing the 'before' state of {subject} — tired, dull, unflattering. Natural light, honest.",
                "dialogue": "Before.",
                "motion": "zoom_in",
                "duration": 4,
            },
            {
                "title": "The process",
                "prompt": "Quick montage of the transformation process for {subject}. Hands, movement, action, product shots.",
                "dialogue": "Here's what changed everything.",
                "motion": "pan_left",
                "duration": 5,
            },
            {
                "title": "After",
                "prompt": "Stunning close-up of {result} — vibrant, glowing, confident. Soft beauty lighting.",
                "dialogue": "After. The difference is real.",
                "motion": "dolly_in",
                "duration": 5,
            },
        ],
    },
    {
        "id": "problem_solution",
        "label": "Problem → Solution",
        "emoji": "💡",
        "desc": "Pain-point then product — classic 3-act marketing reel.",
        "variables": [
            {"key": "problem",  "label": "The problem", "placeholder": "running out of phone battery"},
            {"key": "solution", "label": "Your solution", "placeholder": "our 10,000mAh power bank"},
        ],
        "suggested_voice_style": "energetic",
        "suggested_transition": "fade",
        "scenes": [
            {
                "title": "The pain",
                "prompt": "Relatable frustrated moment showing the struggle of {problem}. Authentic, real-life setting.",
                "dialogue": "We've all been there.",
                "motion": "shake_subtle",
                "duration": 4,
            },
            {
                "title": "The reveal",
                "prompt": "Clean product-shot reveal of {solution}. Studio lighting, hero angle.",
                "dialogue": "Introducing {solution}.",
                "motion": "dolly_out",
                "duration": 5,
            },
            {
                "title": "The win",
                "prompt": "Happy user successfully using {solution}, smiling, relieved. Warm natural light.",
                "dialogue": "Problem solved.",
                "motion": "zoom_out_slow",
                "duration": 5,
            },
        ],
    },
    {
        "id": "morning_routine",
        "label": "Morning Routine",
        "emoji": "☀️",
        "desc": "Aspirational morning reel — day-in-the-life format.",
        "variables": [
            {"key": "city", "label": "City / vibe", "placeholder": "Mumbai"},
            {"key": "drink", "label": "Drink / meal", "placeholder": "masala chai"},
        ],
        "suggested_voice_style": "calm",
        "suggested_transition": "crossfade",
        "scenes": [
            {
                "title": "Sunrise",
                "prompt": "Soft sunrise over the {city} skyline. Warm golden light streaming through window, peaceful.",
                "dialogue": "Good morning, {city}.",
                "motion": "pan_right",
                "duration": 4,
            },
            {
                "title": "Ritual",
                "prompt": "Close-up of hands preparing {drink} — steam rising, slow gentle motion, cozy cinematic.",
                "dialogue": "A moment of calm before the world wakes up.",
                "motion": "zoom_in_slow",
                "duration": 5,
            },
            {
                "title": "Ready",
                "prompt": "Confident person stepping out into the {city} morning, stylish, ready for the day. Wide cinematic shot.",
                "dialogue": "Let's make it count.",
                "motion": "dolly_out",
                "duration": 5,
            },
        ],
    },
    {
        "id": "festival_story",
        "label": "Festival Story",
        "emoji": "🎉",
        "desc": "3-scene festival reel (Diwali / Holi / Eid / any celebration).",
        "variables": [
            {"key": "festival", "label": "Festival", "placeholder": "Diwali"},
            {"key": "family",   "label": "Who's celebrating", "placeholder": "our family"},
        ],
        "suggested_voice_style": "playful",
        "suggested_transition": "crossfade",
        "scenes": [
            {
                "title": "Preparation",
                "prompt": "Warm shot of {family} preparing for {festival} — decorating home, lights being lit, excitement in the air. Golden hour warm tones.",
                "dialogue": "{festival} is here.",
                "motion": "pan_left",
                "duration": 4,
            },
            {
                "title": "Celebration",
                "prompt": "Joyful wide shot of the {festival} celebration at its peak — music, laughter, lights, food, cultural details. Vibrant cinematic.",
                "dialogue": "The moments that matter most.",
                "motion": "zoom_out",
                "duration": 5,
            },
            {
                "title": "Together",
                "prompt": "Intimate close-up of {family} embracing / smiling together. Soft warm lighting, emotional cinematic.",
                "dialogue": "This is {festival}. This is family.",
                "motion": "dolly_in",
                "duration": 5,
            },
        ],
    },
]


def _template_by_id(tid: str):
    for t in STORY_TEMPLATES:
        if t["id"] == tid:
            return t
    return None


def _fill(text: str, variables: dict) -> str:
    if not text:
        return text
    out = text
    for k, v in (variables or {}).items():
        if v is None:
            continue
        out = out.replace("{" + k + "}", str(v))
    return out


# ========== Request/response models ==========
class StorySceneOverride(BaseModel):
    prompt: Optional[str] = None
    dialogue: Optional[str] = None
    motion: Optional[str] = None
    duration: Optional[int] = None
    start_image_path: Optional[str] = None  # optional per-scene image


class StoryCreateRequest(BaseModel):
    template_id: str
    variables: dict = Field(default_factory=dict)
    scene_overrides: Optional[List[StorySceneOverride]] = None
    aspect_ratio: str = Field("9:16")
    voice_style: Optional[str] = None  # override template's suggested style
    voice_id: Optional[str] = "hi-IN-SwaraNeural"
    language: Optional[str] = "en"  # hint for TTS / prompt


# ========== Read-only ==========
@router.get("/templates")
async def list_templates():
    """Return all 5 story templates (strip internal scene `motion` defaults
    only if we want to hide — keep visible so frontend can preview)."""
    return {"templates": STORY_TEMPLATES, "cost": STORY_MODE_COST}


@router.get("/templates/{template_id}")
async def get_template(template_id: str):
    t = _template_by_id(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return t


# ========== Main create endpoint ==========
@router.post("/create")
async def story_create(
    req: StoryCreateRequest,
    background_tasks: BackgroundTasks,
    request: Request = None,
):
    tpl = _template_by_id(req.template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Unknown template_id")

    # Tier-gate: Story Mode wraps multi-shot → require allow_multishot, but
    # use shots=1 to bypass the 2-shot cap since Story is a fixed 3-scene
    # wizard with its own flat price (STORY_MODE_COST).
    user, _ = await preflight_and_reserve(
        request,
        job_type="multishot",
        feature="multishot",
        shots=1,
        duration=5,
    )
    cost = STORY_MODE_COST

    # Build 3-shot payload from the template, applying variables + overrides.
    shots = []
    for idx, scene in enumerate(tpl["scenes"]):
        ov = req.scene_overrides[idx] if (req.scene_overrides and idx < len(req.scene_overrides)) else None
        prompt = _fill(scene["prompt"], req.variables)
        dialogue = _fill(scene.get("dialogue") or "", req.variables)
        motion = scene.get("motion")
        duration = int(scene.get("duration") or 5)
        start_image_path = None
        if ov:
            if ov.prompt:
                prompt = _fill(ov.prompt, req.variables)
            if ov.dialogue is not None:
                dialogue = _fill(ov.dialogue, req.variables)
            if ov.motion:
                motion = ov.motion
            if ov.duration:
                duration = int(ov.duration)
            if ov.start_image_path:
                start_image_path = ov.start_image_path
        shots.append({
            "prompt": prompt,
            "duration": duration,
            "dialogue": dialogue or None,
            "voice_id": req.voice_id or "hi-IN-SwaraNeural",
            "voice_style": req.voice_style or tpl.get("suggested_voice_style"),
            "motion": motion,
            "start_image_path": start_image_path,
            "transition_out": tpl.get("suggested_transition") or "crossfade",
            "quality_mode": "studio",
        })

    # Persist project doc (same shape as multishot — reuse /api/project)
    project_id = str(uuid.uuid4())
    proj = {
        "id": project_id,
        "name": f"Story_{tpl['id']}_{datetime.now(timezone.utc).strftime('%H%M%S')}",
        "type": "story",
        "user_id": user.get("user_id") or user.get("id"),
        "status": "processing",
        "progress": 0,
        "aspect_ratio": req.aspect_ratio or "9:16",
        "input_payload": {
            "template_id": req.template_id,
            "variables": req.variables,
            "shots": shots,
        },
        "endpoint": "/api/story/create",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.video_projects.insert_one(proj)

    # Kick off the underlying multishot pipeline (lazy import to avoid circular).
    try:
        from server import process_multishot_bg  # type: ignore
    except Exception as e:
        logger.exception("Could not import process_multishot_bg")
        raise HTTPException(status_code=500, detail=f"Multishot pipeline unavailable: {e}")

    background_tasks.add_task(
        process_multishot_bg,
        project_id,
        shots,
        req.aspect_ratio or "9:16",
    )

    # Settle credits (+ free-tier watermark as background)
    await settle_credits(
        user.get("id"),
        cost,
        user_tier=user.get("subscription_tier"),
        project_id=project_id,
        asset_kind="video",
        background_tasks=background_tasks,
    )

    return {
        "project_id": project_id,
        "status": "processing",
        "credits_charged": cost,
        "template_id": req.template_id,
        "scene_count": len(shots),
    }
