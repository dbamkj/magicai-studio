"""Shared Pydantic request/response models.
Extracted from server.py (Batch 1 refactor) for reuse across routes and to enable
clean decorator hooks in Sprint 4 (credit system).
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class VideoProject(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    name: str
    type: str
    status: Literal["created", "processing", "completed", "failed"] = "created"
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    result_url: Optional[str] = None
    result_segments: Optional[List[dict]] = None
    d_id_talk_id: Optional[str] = None
    aspect_ratio: str = "16:9"
    face_count: int = 1
    sound_effect: Optional[str] = None
    trim_start: Optional[float] = None
    trim_end: Optional[float] = None
    video_duration: Optional[float] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error_message: Optional[str] = None
    progress: int = 0
    credits_charged: Optional[int] = None
    # --- Sprint 1: versioning ---
    parent_id: Optional[str] = None
    version: int = 1
    action: Literal["original", "edit", "recreate", "regenerate"] = "original"
    input_payload: Optional[dict] = None
    endpoint: Optional[str] = None
    refunded: bool = False


class CreateLipSyncRequest(BaseModel):
    image_urls: Optional[List[str]] = []
    dialogue_lines: List[dict]
    voice_id: Optional[str] = "hi-IN-SwaraNeural"
    voice_ids: Optional[dict] = None
    audio_url: Optional[str] = None
    aspect_ratio: Optional[str] = "16:9"
    sound_effect: Optional[str] = None
    ref_video_path: Optional[str] = None
    mode: Optional[str] = "images_only"
    target_duration: Optional[float] = None
    resolution: Optional[str] = "720p"
    parent_id: Optional[str] = None
    voice_style: Optional[str] = None
    voice_rate: Optional[str] = None
    voice_pitch: Optional[str] = None


class CreateFaceSwapRequest(BaseModel):
    source_image_paths: List[str]
    target_video_path: str
    target_type: Optional[str] = "video"
    face_indices: Optional[List[int]] = None
    aspect_ratio: Optional[str] = "16:9"
    trim_start: Optional[float] = None
    trim_end: Optional[float] = None
    video_duration: Optional[float] = None
    resolution: Optional[str] = "720p"
    parent_id: Optional[str] = None


class CreateHeadSwapRequest(BaseModel):
    head_image_path: str
    body_image_path: str
    provider: Optional[str] = "magichour"
    resolution: Optional[str] = "720p"
    parent_id: Optional[str] = None


class CreateBodySwapRequest(BaseModel):
    person_image_path: str
    garment_image_path: str
    garment_type: Optional[str] = "entire_outfit"
    resolution: Optional[str] = "720p"
    parent_id: Optional[str] = None


class GenerateImageRequest(BaseModel):
    prompt: str
    aspect_ratio: Optional[str] = "16:9"
    quality: Optional[str] = "high"
    style: Optional[str] = "natural"
    resolution: Optional[str] = "720p"
    quality_mode: Optional[str] = "studio"
    parent_id: Optional[str] = None


class GenerateVideoRequest(BaseModel):
    prompt: str
    aspect_ratio: Optional[str] = "16:9"
    duration: Optional[int] = 5
    lyrics: Optional[str] = None
    voice_id: Optional[str] = "hi-IN-SwaraNeural"
    style: Optional[str] = "bhajan"
    sound_effect: Optional[str] = None
    audio_path: Optional[str] = None
    quality_mode: Optional[str] = "studio"
    resolution: Optional[str] = "720p"
    parent_id: Optional[str] = None
    voice_style: Optional[str] = None
    voice_rate: Optional[str] = None
    voice_pitch: Optional[str] = None


class VideoRedubRequest(BaseModel):
    video_url: str
    script_text: str
    voice_id: Optional[str] = "hi-IN-SwaraNeural"
    audio_url: Optional[str] = None
    target_duration: Optional[float] = None
    resolution: Optional[str] = "720p"
    voice_style: Optional[str] = None


class AnimateImageRequest(BaseModel):
    image_path: str
    motion: str
    duration: Optional[float] = 5.0
    resolution: Optional[str] = "720p"


class CreateTalkingAvatarRequest(BaseModel):
    image_path: str
    script: str
    voice_id: Optional[str] = "hi-IN-SwaraNeural"
    voice_style: Optional[str] = None
    voice_rate: Optional[str] = None
    voice_pitch: Optional[str] = None
    motion: Optional[str] = None
    aspect_ratio: Optional[str] = "9:16"
    resolution: Optional[str] = "720p"
    parent_id: Optional[str] = None
    # Session 25 round 11 — optional BGM mood (cinematic_epic | devotional |
    # playful | motivational). When set, server picks a track from
    # core.bgm_catalog and mixes it under the voice at -15dB before
    # sending to MH lipsync. None / empty = no BGM (legacy behavior).
    bgm_style: Optional[str] = None


# ========== Sprint 6 — Content Intelligence: Templates ==========
class Template(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    category: Literal["devotional", "motivation", "story", "funny", "comedy", "trending", "divine_transformation", "other"] = "other"
    subcategory: Optional[str] = None  # e.g. "bhajan", "shloka", "fitness", "success"
    hook_text: Optional[str] = None  # for hook-based templates
    lyrics: Optional[str] = None     # for bhajan/devotional templates
    # Festival Packs (Sprint 6 Phase 3)
    festival_pack: Optional[Literal["janmashtami", "mahashivratri", "navratri"]] = None
    character_gender: Optional[Literal["male", "female", "any"]] = None
    transition_effect: Optional[str] = None  # glow_dissolve|smoke_fade|golden_flash|particle_dissolve|aura_burst
    bgm_url: Optional[str] = None            # royalty-free BGM URL
    gradient_colors: Optional[List[str]] = None  # 2-3 colors for placeholder thumbnail fallback
    # Render recipe
    voice_id: str = "hi-IN-SwaraNeural"
    voice_style: Optional[str] = None
    motion: Optional[str] = None  # motion preset id
    sound_effect: Optional[str] = None  # SFX id
    aspect_ratio: str = "9:16"
    duration: int = 5
    thumbnail_url: Optional[str] = None  # base image for preview
    preview_url: Optional[str] = None    # generated preview mp4
    # Metadata
    tier: Literal["free", "starter", "pro", "premium"] = "free"
    source: Literal["ai_generated", "curated", "user"] = "ai_generated"
    is_active: bool = True
    is_trending: bool = False
    # Ranking metrics
    usage_count: int = 0
    completion_count: int = 0
    share_count: int = 0
    rating_sum: float = 0.0
    rating_count: int = 0
    score: float = 0.0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GenerateBhajanRequest(BaseModel):
    theme: str  # e.g. "Krishna", "Shiva", "Ganesh"
    style: Literal["traditional", "modern"] = "traditional"
    language: Literal["sanskrit", "hindi", "mixed"] = "hindi"
    lines: Optional[int] = 4  # number of verses


class GenerateHookRequest(BaseModel):
    category: Literal["motivation", "story", "funny", "comedy", "fitness", "success", "other"] = "motivation"
    topic: Optional[str] = None  # e.g. "morning routine", "startup grind"
    count: Optional[int] = 3


class CreateTemplateRequest(BaseModel):
    title: str
    category: str
    subcategory: Optional[str] = None
    hook_text: Optional[str] = None
    lyrics: Optional[str] = None
    voice_id: Optional[str] = "hi-IN-SwaraNeural"
    voice_style: Optional[str] = None
    motion: Optional[str] = None
    sound_effect: Optional[str] = None
    aspect_ratio: Optional[str] = "9:16"
    duration: Optional[int] = 5
    thumbnail_url: Optional[str] = None
    tier: Optional[str] = "free"
    source: Optional[str] = "ai_generated"
