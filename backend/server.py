from fastapi import FastAPI, APIRouter, File, UploadFile, HTTPException, BackgroundTasks, Request, Response
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
load_dotenv()

# Auto-install ffmpeg if missing (container restarts lose it)
import shutil as _shutil
if not _shutil.which("ffmpeg"):
    import subprocess as _sp
    _sp.run(["apt-get", "update", "-qq"], capture_output=True, timeout=60)
    _sp.run(["apt-get", "install", "-y", "-qq", "ffmpeg"], capture_output=True, timeout=120)

from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import uuid
import tempfile
import asyncio
import subprocess
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime, timezone, timedelta
import httpx
import base64
from PIL import Image
from magic_hour import Client as MagicHourClient
import time
import edge_tts
import asyncio as aio
from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration
import requests as sync_requests

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'videoai_database')]

app = FastAPI(title="MagiCAi Studio API")
api_router = APIRouter(prefix="/api")

# ---------------------------------------------------------------------------
# Public landing page at "/" — V1.0 Builders Contest deployment fix.
# When users / contest judges visit https://creative-plan-engine.emergent.host/
# they used to see a raw {"detail":"Not Found"} 404 because the FastAPI app
# only defines /api/* routes. We now serve a polished marketing landing page
# (HTML + assets baked into /app/backend/static/landing/) that highlights the
# brand, CTAs, demo credentials, and links into the working share URL.
# ---------------------------------------------------------------------------
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles as _StaticFiles
_LANDING_DIR = ROOT_DIR / "static" / "landing"
_LANDING_INDEX = _LANDING_DIR / "index.html"
_LANDING_ASSETS_DIR = ROOT_DIR / "static" / "landing-assets"
if _LANDING_ASSETS_DIR.exists():
    app.mount("/landing-assets", _StaticFiles(directory=str(_LANDING_ASSETS_DIR)), name="landing-assets")


@app.get("/", response_class=HTMLResponse)
async def landing_page():
    """Serve the public marketing landing page. Also returned for /index.html."""
    if _LANDING_INDEX.exists():
        return HTMLResponse(_LANDING_INDEX.read_text(encoding="utf-8"))
    return HTMLResponse(
        "<h1>MagiCAi Studio API</h1><p>API is live at <code>/api/</code>.</p>",
        status_code=200,
    )


@app.get("/index.html", response_class=HTMLResponse)
async def landing_alias():
    return await landing_page()


@app.get("/favicon.ico")
async def favicon():
    fav = _LANDING_ASSETS_DIR / "app_icon_1024.png"
    if fav.exists():
        return FileResponse(str(fav), media_type="image/png")
    raise HTTPException(status_code=404)
# ---------------------------------------------------------------------------

D_ID_API_KEY = os.environ.get('D_ID_API_KEY', '')
D_ID_API_URL = os.environ.get('D_ID_API_URL', 'https://api.d-id.com')
MAGIC_HOUR_API_KEY = os.environ.get('MAGIC_HOUR_API_KEY', '')
WAVESPEED_API_KEY = os.environ.get('WAVESPEED_API_KEY', '')
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

UPLOAD_DIR = ROOT_DIR / "uploads"


def _resolve_upload_path(p: str) -> Path:
    """Robust image/media path resolver. Accepts:
      * absolute path (/app/backend/uploads/xyz.png)
      * serve-file URL (/api/serve-file/xyz.png)
      * upload URL (/uploads/xyz.png)
      * bare filename (xyz.png)
    Returns a Path inside UPLOAD_DIR. Used by /animate-image, /create-talking-avatar
    and /create-image-to-video so all paths behave consistently (Batch 3 fix).
    """
    if not p:
        return UPLOAD_DIR / "missing"
    pp = p.strip()
    for pfx in ("/api/serve-file/", "/uploads/"):
        if pp.startswith(pfx):
            return UPLOAD_DIR / pp[len(pfx):].lstrip("/")
    pcand = Path(pp)
    if pcand.is_absolute() and pcand.exists():
        return pcand
    return UPLOAD_DIR / pcand.name

UPLOAD_DIR.mkdir(exist_ok=True)

# ---- Extracted to /app/backend/core/* (session 17 refactor) -------------------
from core.constants import (
    MH_CREDIT_COSTS as _MH_CREDIT_COSTS,
    MH_QUALITY_TIERS as _MH_QUALITY_TIERS,
    SFX_CATALOG as _SFX_CATALOG,
    sfx_by_id as _core_sfx_by_id,
    VOICE_STYLES as _VOICE_STYLES,
    voice_style_by_id as _core_voice_style_by_id,
    MOTION_PRESETS as _MOTION_PRESETS,
    motion_preset_by_id as _core_motion_preset_by_id,
)
# Sprint-4 — Billing preflight + deduction (tier + credit + daily-cap checks)
from core.billing import preflight_and_reserve, settle_credits, refund_credits


async def _refund_for_failure(project_id: str, error_msg: str = ""):
    """Trust feature — when a paid background job fails, refund the spent credits.
    Idempotent (refund_credits short-circuits if project already marked refunded).
    Safe to call from inside an except handler — never raises."""
    try:
        proj = await db.video_projects.find_one({"id": project_id}, {"user_id": 1, "credits_spent": 1, "refunded": 1, "owner_id": 1})
        if not proj:
            proj = await db.projects.find_one({"id": project_id}, {"user_id": 1, "credits_spent": 1, "refunded": 1, "owner_id": 1})
        if not proj:
            return
        if proj.get("refunded"):
            return
        spent = int(proj.get("credits_spent") or 0)
        uid = proj.get("user_id") or proj.get("owner_id")
        if uid and spent > 0:
            await refund_credits(uid, spent, project_id=project_id, reason=f"job_failed:{(error_msg or '')[:80]}")
    except Exception as _re:
        logger.warning("refund_for_failure suppressed: %s", _re)
# Batch 1 refactor — Pydantic models extracted to core/models.py
from core.models import (
    VideoProject,
    CreateLipSyncRequest,
    CreateFaceSwapRequest,
    CreateHeadSwapRequest,
    CreateBodySwapRequest,
    GenerateImageRequest,
    GenerateVideoRequest,
    VideoRedubRequest,
    AnimateImageRequest as _CoreAnimateImageRequest,
    CreateTalkingAvatarRequest as _CoreCreateTalkingAvatarRequest,
    Template,
    GenerateBhajanRequest,
    GenerateHookRequest,
    CreateTemplateRequest,
)
# -----------------------------------------------------------------------------
VIDEO_DIR = ROOT_DIR / "videos"
VIDEO_DIR.mkdir(exist_ok=True)

# ============ AUTH HELPERS ============

async def get_current_user(request: Request) -> dict:
    """Get current user from JWT Bearer, legacy session cookie, or guest fallback.

    Sprint-4 addition: when Authorization Bearer contains a valid JWT (from
    routes/auth.py), resolve the real user from `users` collection and populate
    BOTH `id` and `user_id` keys so existing call sites (`user["user_id"]`) keep
    working unchanged.
    """
    from core.auth import decode_token as _jwt_decode  # lazy import to avoid circular

    token = None
    if "session_token" in request.cookies:
        token = request.cookies["session_token"]
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

    # 1) Try JWT first (Sprint-4)
    if token:
        try:
            data = _jwt_decode(token)
            if data and data.get('sub'):
                user = await db.users.find_one({'id': data['sub']}, {'_id': 0, 'password_hash': 0})
                if user:
                    user['user_id'] = user.get('id')
                    return user
        except Exception:
            pass

    # 2) Legacy session-cookie lookup (Google-SSO era) — DEV only now
    if not token:
        return {"user_id": "guest_default", "id": "guest_default", "email": "", "name": "Guest", "picture": ""}
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        return {"user_id": "guest_default", "id": "guest_default", "email": "", "name": "Guest", "picture": ""}
    expires_at = session.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return {"user_id": "guest_default", "id": "guest_default", "email": "", "name": "Guest", "picture": ""}
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user:
        return {"user_id": "guest_default", "id": "guest_default", "email": "", "name": "Guest", "picture": ""}
    user.setdefault('id', user.get('user_id'))
    return user

# ============ AUTH ROUTES ============

@api_router.post("/auth/session")
async def auth_session(request: Request, response: Response):
    """Exchange session_id for session_token"""
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as c:
            r = await c.get("https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data", headers={"X-Session-ID": session_id})
            if r.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid session_id")
            data = r.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auth error: {str(e)}")

    email = data.get("email")
    name = data.get("name", "")
    picture = data.get("picture", "")
    session_token = data.get("session_token", "")

    # Upsert user
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one({"email": email}, {"$set": {"name": name, "picture": picture, "updated_at": datetime.now(timezone.utc).isoformat()}})
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({"user_id": user_id, "email": email, "name": name, "picture": picture, "created_at": datetime.now(timezone.utc).isoformat()})

    # Store session
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.insert_one({"user_id": user_id, "session_token": session_token, "expires_at": expires.isoformat(), "created_at": datetime.now(timezone.utc).isoformat()})

    response.set_cookie("session_token", session_token, httponly=True, secure=True, samesite="none", path="/", max_age=7*24*3600)
    return {"user_id": user_id, "email": email, "name": name, "picture": picture, "session_token": session_token}

# NOTE: Legacy /auth/me + /auth/logout handlers removed — the Sprint-4 JWT-based
# versions in routes/auth.py are now authoritative (return {user, env, is_beta, ...}).

# ============ MODELS ============

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
    parent_id: Optional[str] = None              # id of the v1 root project. null for originals.
    version: int = 1                              # 1-indexed version in its family
    action: Literal["original", "edit", "recreate", "regenerate"] = "original"
    input_payload: Optional[dict] = None          # saved raw request body for recreate/regenerate
    endpoint: Optional[str] = None                # e.g., "/api/generate-video" — for routing on re-run
    refunded: bool = False                         # flipped true when status=failed and credits refunded

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
    voice_style: Optional[str] = None  # Sprint 2: 'neutral'|'devotional'|'motivation'|'story'|'funny'
    voice_rate: Optional[str] = None   # Sprint 2 Phase B: explicit rate override (e.g. '+5%')
    voice_pitch: Optional[str] = None  # Sprint 2 Phase B: explicit pitch override (e.g. '-10Hz')

class CreateFaceSwapRequest(BaseModel):
    source_image_paths: List[str]
    target_video_path: str
    target_type: Optional[str] = "video"  # "video" or "image"
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
    resolution: Optional[str] = "720p"  # "480p" | "720p" | "1080p"(greyed)
    quality_mode: Optional[str] = "studio"  # "quick" | "studio" | "cinematic"(greyed)
    parent_id: Optional[str] = None  # Sprint 1: link new project as a version of this parent family

class GenerateVideoRequest(BaseModel):
    prompt: str
    aspect_ratio: Optional[str] = "16:9"
    duration: Optional[int] = 5
    lyrics: Optional[str] = None
    voice_id: Optional[str] = "hi-IN-SwaraNeural"
    style: Optional[str] = "bhajan"
    sound_effect: Optional[str] = None  # SFX id from /api/sound-effects
    audio_path: Optional[str] = None    # path to uploaded/recorded dialogue audio
    quality_mode: Optional[str] = "studio"  # "quick" | "studio" | "cinematic"(greyed)
    resolution: Optional[str] = "720p"      # "480p" | "720p" | "1080p"(greyed)
    parent_id: Optional[str] = None         # Sprint 1: link new project as a version of this parent family
    voice_style: Optional[str] = None       # Sprint 2: audio emotion preset
    voice_rate: Optional[str] = None        # Sprint 2 Phase B: explicit rate override (e.g. '+5%')
    voice_pitch: Optional[str] = None       # Sprint 2 Phase B: explicit pitch override (e.g. '-10Hz')

class VideoRedubRequest(BaseModel):
    video_url: str
    script_text: str
    voice_id: Optional[str] = "hi-IN-SwaraNeural"
    audio_url: Optional[str] = None
    target_duration: Optional[float] = None
    resolution: Optional[str] = "720p"
    voice_style: Optional[str] = None       # Sprint 2: audio emotion preset

# ============ D-ID CLIENT ============

class DIDAPIError(Exception):
    pass

class DIDClient:
    def __init__(self):
        self.base_url = D_ID_API_URL
        self.api_key = D_ID_API_KEY
        self.timeout = httpx.Timeout(60.0)
    def _get_headers(self):
        return {"Authorization": f"Basic {self.api_key}", "Content-Type": "application/json"}
    async def upload_image(self, file_path):
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            with open(file_path, 'rb') as f:
                r = await c.post(f"{self.base_url}/images", files={'image': (os.path.basename(file_path), f, 'image/jpeg')}, headers={"Authorization": self._get_headers()["Authorization"]})
                if r.status_code == 201: return r.json().get('url')
                raise DIDAPIError(r.text)
    async def create_talk(self, source_url, script_text=None, audio_url=None, voice_id=None):
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            payload = {"source_url": source_url}
            if audio_url: payload["script"] = {"type": "audio", "audio_url": audio_url}
            elif script_text: payload["script"] = {"type": "text", "input": script_text, "provider": {"type": "microsoft", "voice_id": voice_id or "hi-IN-SwaraNeural"}}
            r = await c.post(f"{self.base_url}/talks", json=payload, headers=self._get_headers())
            if r.status_code in [200, 201]: return r.json()
            raise DIDAPIError(r.text)
    async def get_talk_status(self, talk_id):
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.get(f"{self.base_url}/talks/{talk_id}", headers=self._get_headers())
            if r.status_code == 200: return r.json()
            raise DIDAPIError(r.text)
    async def wait_for_completion(self, talk_id, max_wait=300):
        start = datetime.now(timezone.utc); delay = 3
        while True:
            if (datetime.now(timezone.utc) - start).total_seconds() > max_wait: raise DIDAPIError("Timeout")
            s = await self.get_talk_status(talk_id)
            if s.get('status') == 'done': return s
            elif s.get('status') in ['error', 'failed']: raise DIDAPIError(s.get('error', {}).get('description', 'Unknown'))
            await asyncio.sleep(delay); delay = min(delay * 1.2, 10)

# ============ MAGIC HOUR HELPERS ============

def upload_to_magic_hour(mh, local_path, file_type):
    ext = Path(local_path).suffix.lstrip('.').lower() or ('jpg' if file_type == 'image' else 'mp4')
    # Normalize extensions for audio: MH supports mp3, wav, aac, flac, webm, m4a
    if file_type == "audio":
        # webm files from web recorder should use webm ext
        if ext not in ("mp3", "wav", "aac", "flac", "webm", "m4a"):
            ext = "mp3"
    upload_type = file_type
    res = mh.v1.files.upload_urls.create(items=[{"extension": ext, "type_": upload_type}])
    item = res.items[0]
    ct = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'mp4': 'video/mp4', 'mov': 'video/quicktime', 'mp3': 'audio/mpeg', 'wav': 'audio/wav', 'aac': 'audio/aac', 'ogg': 'audio/ogg', 'm4a': 'audio/mp4', 'flac': 'audio/flac', 'webm': 'audio/webm' if file_type == 'audio' else 'video/webm'}.get(ext, f'{file_type}/{ext}')
    # Read entire file into memory to ensure Content-Length is set correctly (S3-style presigned URLs require this)
    with open(local_path, 'rb') as f:
        data = f.read()
    if not data:
        raise Exception(f"Cannot upload empty file to Magic Hour: {local_path}")
    resp = sync_requests.put(item.upload_url, data=data, headers={"Content-Type": ct, "Content-Length": str(len(data))})
    resp.raise_for_status()
    logger.info(f"MH upload OK: type={file_type} ext={ext} size={len(data)}b ct={ct} path={item.file_path}")
    return item.file_path

async def mh_create_lipsync_with_retry(mh, name, assets, start_seconds, end_seconds, max_retries=5):
    """Wraps MH lip_sync.create with retry on transient 5xx errors."""
    for attempt in range(max_retries):
        try:
            return mh.v1.lip_sync.create(name=name, assets=assets, start_seconds=start_seconds, end_seconds=end_seconds)
        except Exception as e:
            es = str(e)
            if any(c in es for c in ["502", "503", "504", "Bad Gateway", "Service Unavailable", "Gateway Timeout", "timeout"]):
                if attempt < max_retries - 1:
                    wait = min(3 + attempt * 2, 15)
                    logger.warning(f"MH create transient err #{attempt+1}: {es[:120]}, retrying in {wait}s...")
                    await asyncio.sleep(wait); continue
            raise

async def mh_poll_image(mh, job_id, max_wait=120):
    start = time.time(); err_count = 0
    while time.time() - start < max_wait:
        try:
            s = mh.v1.image_projects.get(id=job_id)
            err_count = 0
            if s.status == "complete":
                if s.downloads and len(s.downloads) > 0: return s.downloads[0].url
                return None
            elif s.status in ["error", "canceled"]:
                err_msg = getattr(s, 'error', None) or s.status
                raise Exception(f"MH image {s.status}: {err_msg}")
        except Exception as e:
            es = str(e)
            if any(c in es for c in ["502", "503", "504", "Bad Gateway", "Service Unavailable", "Gateway Timeout", "timeout"]):
                err_count += 1
                if err_count > 6: raise
                logger.warning(f"MH image poll transient err #{err_count}: {es[:120]}, retrying...")
                await asyncio.sleep(min(4 + err_count * 2, 12)); continue
            raise
        await asyncio.sleep(3)
    return None

async def mh_poll_video(mh, job_id, max_wait=300, on_progress=None, on_complete=None):
    """Polls MH video job. Optional on_progress(percent), on_complete(status_obj) callbacks."""
    start = time.time(); err_count = 0
    while time.time() - start < max_wait:
        try:
            s = mh.v1.video_projects.get(id=job_id)
            err_count = 0
            # Report progress if MH provides it
            if on_progress:
                try:
                    mh_progress = getattr(s, 'progress', None) or 0
                    if isinstance(mh_progress, (int, float)) and 0 <= mh_progress <= 100:
                        await on_progress(int(mh_progress))
                except Exception: pass
            if s.status == "complete":
                if on_complete:
                    try: await on_complete(s)
                    except Exception: pass
                if s.downloads and len(s.downloads) > 0: return s.downloads[0].url
                return None
            elif s.status in ["error", "canceled"]:
                err_msg = getattr(s, 'error', None) or s.status
                raise Exception(f"MH video {s.status}: {err_msg}")
        except Exception as e:
            es = str(e)
            if any(c in es for c in ["502", "503", "504", "Bad Gateway", "Service Unavailable", "Gateway Timeout", "timeout"]):
                err_count += 1
                if err_count > 6: raise
                logger.warning(f"MH video poll transient err #{err_count}: {es[:120]}, retrying...")
                await asyncio.sleep(min(4 + err_count * 2, 12)); continue
            raise
        await asyncio.sleep(4)
    return None


async def _capture_credits(project_id, status_obj):
    """Helper to capture credits_charged from MH response into our project row."""
    try:
        credits = getattr(status_obj, 'credits_charged', None)
        if credits is None and hasattr(status_obj, 'to_dict'):
            credits = status_obj.to_dict().get('credits_charged')
        if credits is not None and isinstance(credits, (int, float)):
            await db.video_projects.update_one({"id": project_id}, {"$set": {"credits_charged": int(credits)}})
    except Exception as e:
        logger.warning(f"_capture_credits: {e}")


def normalize_image_for_mh(src_path: str) -> str:
    """Re-encode any image to a clean 8-bit RGB JPEG that Magic Hour can always read.
    Handles HEIC, WebP, CMYK, 16-bit, alpha channels, bad EXIF, etc.
    Returns path to the normalised file (a sibling file ending in _norm.jpg)."""
    try:
        from PIL import Image as _Img
        p = Path(src_path)
        if not p.exists() or p.stat().st_size < 100:
            return src_path
        out = p.with_name(p.stem + "_norm.jpg")
        img = _Img.open(src_path)
        # Handle transparency: composite onto white bg
        if img.mode in ("RGBA", "LA", "P"):
            bg = _Img.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = bg
        elif img.mode == "CMYK":
            img = img.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")
        # Cap size to 2048 on longest side (MH max)
        max_dim = 2048
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), _Img.LANCZOS)
        # Save clean JPG (no EXIF)
        img.save(out, format="JPEG", quality=92, optimize=True)
        logger.info(f"normalize_image_for_mh: {src_path} ({img.size}) -> {out}")
        return str(out)
    except Exception as e:
        logger.warning(f"normalize_image_for_mh failed for {src_path}: {e}. Using original.")
        return src_path

SARVAM_API_KEY = os.environ.get('SARVAM_API_KEY', '')

# Sarvam AI voice catalogue (speakers supported on bulbul-v2 model)
SARVAM_SPEAKERS = {
    # Female
    "sarvam:anushka": {"speaker": "anushka", "name": "Anushka", "gender": "Female", "lang": "Hindi", "model": "bulbul:v2"},
    "sarvam:manisha": {"speaker": "manisha", "name": "Manisha", "gender": "Female", "lang": "Hindi", "model": "bulbul:v2"},
    "sarvam:vidya":   {"speaker": "vidya",   "name": "Vidya",   "gender": "Female", "lang": "Hindi", "model": "bulbul:v2"},
    "sarvam:arya":    {"speaker": "arya",    "name": "Arya",    "gender": "Female", "lang": "Hindi", "model": "bulbul:v2"},
    # Male
    "sarvam:abhilash": {"speaker": "abhilash", "name": "Abhilash", "gender": "Male", "lang": "Hindi", "model": "bulbul:v2"},
    "sarvam:karun":    {"speaker": "karun",    "name": "Karun",    "gender": "Male", "lang": "Hindi", "model": "bulbul:v2"},
    "sarvam:hitesh":   {"speaker": "hitesh",   "name": "Hitesh",   "gender": "Male", "lang": "Hindi", "model": "bulbul:v2"},
}


async def sarvam_tts(text: str, speaker: str, output_path: Path, language: str = "hi-IN") -> bool:
    """Generate TTS via Sarvam AI. Returns True on success.
    API: https://api.sarvam.ai/text-to-speech  (POST, api-subscription-key header)"""
    if not SARVAM_API_KEY:
        logger.warning("SARVAM_API_KEY missing")
        return False
    try:
        import base64 as _b64
        # Sarvam text-to-speech (bulbul-v2 model)
        url = "https://api.sarvam.ai/text-to-speech"
        payload = {
            "inputs": [text[:2000]],
            "target_language_code": language,
            "speaker": speaker,
            "pitch": 0,
            "pace": 1.0,
            "loudness": 1.0,
            "speech_sample_rate": 22050,
            "enable_preprocessing": True,
            "model": "bulbul:v2",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as c:
            resp = await c.post(url, json=payload, headers={"api-subscription-key": SARVAM_API_KEY, "Content-Type": "application/json"})
        if resp.status_code != 200:
            logger.warning(f"Sarvam TTS failed {resp.status_code}: {resp.text[:200]}")
            return False
        data = resp.json()
        audios = data.get("audios", [])
        if not audios:
            logger.warning(f"Sarvam TTS empty audios: {str(data)[:200]}")
            return False
        # Sarvam returns base64 WAV; decode and save as WAV then transcode to MP3
        raw_wav = _b64.b64decode(audios[0])
        tmp_wav = output_path.with_suffix(".raw.wav")
        with open(tmp_wav, "wb") as f:
            f.write(raw_wav)
        # Transcode to MP3 for consistent downstream handling
        subprocess.run(["/usr/bin/ffmpeg", "-y", "-i", str(tmp_wav), "-codec:a", "libmp3lame", "-b:a", "128k", str(output_path)], capture_output=True, timeout=30)
        try: tmp_wav.unlink(missing_ok=True)
        except Exception: pass
        if output_path.exists() and output_path.stat().st_size > 500:
            logger.info(f"Sarvam TTS OK: speaker={speaker} bytes={output_path.stat().st_size}")
            return True
        return False
    except Exception as e:
        logger.warning(f"Sarvam TTS error: {e}")
        return False


async def generate_tts_audio(text, voice_id, output_path, min_duration=2.5, voice_style=None, voice_rate=None, voice_pitch=None):
    """Generate TTS audio. Supports edge-tts (default) + Sarvam AI (voice IDs with 'sarvam:' prefix).
    Supports pseudo voice IDs like 'baby_boy_hi_1:hi-IN-MadhurNeural' which apply pitch/rate adjustments.

    Sprint 2 extensions:
    - voice_style (str): optional preset id from VOICE_STYLES ('devotional', 'motivation', 'story', 'funny').
      Applies rate/pitch overrides and pause_multiplier from the preset.
    - voice_rate / voice_pitch (str, e.g. '+5%' / '-10Hz'): optional explicit overrides — if provided,
      they take precedence over the preset and the pseudo-voice prefix.
    - [pause:Xs] markers inside text are honored — we split into segments, render each, and stitch with
      silent gaps of X seconds (scaled by style.pause_multiplier)."""
    # ========== PAUSE MARKER HANDLING ==========
    # Recognize [pause:1.5] or [pause:1.5s] (case-insensitive). Split the text around them.
    import re
    style_preset = _core_voice_style_by_id(voice_style) if voice_style else None
    pause_mult = float(style_preset["pause_multiplier"]) if style_preset and style_preset.get("pause_multiplier") else 1.0
    pause_re = re.compile(r"\[pause:\s*([0-9]*\.?[0-9]+)\s*s?\s*\]", re.IGNORECASE)
    if pause_re.search(text):
        # Split into [(text_chunk, pause_after_secs), ...]
        chunks = []
        last_end = 0
        for m in pause_re.finditer(text):
            chunk_text = text[last_end:m.start()].strip()
            gap = float(m.group(1)) * pause_mult
            chunks.append((chunk_text, gap))
            last_end = m.end()
        tail = text[last_end:].strip()
        if tail:
            chunks.append((tail, 0.0))
        # Render each chunk recursively (without pause markers), then concat with silence.
        tmp_dir = Path(output_path).parent
        parts = []
        for i, (ct, gap) in enumerate(chunks):
            if not ct:
                if gap > 0:
                    sil = tmp_dir / f"sil_{uuid.uuid4().hex[:8]}.mp3"
                    subprocess.run(["/usr/bin/ffmpeg", "-y", "-f", "lavfi", "-t", str(max(0.1, gap)), "-i", "anullsrc=channel_layout=stereo:sample_rate=44100", "-q:a", "9", "-acodec", "libmp3lame", str(sil)], capture_output=True, timeout=15)
                    if sil.exists(): parts.append(sil)
                continue
            piece = tmp_dir / f"tts_piece_{uuid.uuid4().hex[:8]}.mp3"
            await generate_tts_audio(ct, voice_id, piece, min_duration=0.5, voice_style=voice_style)
            if piece.exists() and piece.stat().st_size > 500:
                parts.append(piece)
            if gap > 0:
                sil = tmp_dir / f"sil_{uuid.uuid4().hex[:8]}.mp3"
                subprocess.run(["/usr/bin/ffmpeg", "-y", "-f", "lavfi", "-t", str(max(0.1, gap)), "-i", "anullsrc=channel_layout=stereo:sample_rate=44100", "-q:a", "9", "-acodec", "libmp3lame", str(sil)], capture_output=True, timeout=15)
                if sil.exists(): parts.append(sil)
        if not parts:
            raise Exception("TTS: pause-split produced no audible segments")
        # Concat via ffmpeg concat filter
        concat_list = tmp_dir / f"concat_{uuid.uuid4().hex[:8]}.txt"
        concat_list.write_text("\n".join([f"file '{p}'" for p in parts]))
        subprocess.run(["/usr/bin/ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(output_path)], capture_output=True, timeout=30)
        # Cleanup
        try:
            for p in parts:
                if p.exists(): p.unlink()
            if concat_list.exists(): concat_list.unlink()
        except Exception: pass
        return str(output_path)
    # ========== Sarvam AI branch ==========
    if isinstance(voice_id, str) and voice_id.startswith("sarvam:"):
        spec = SARVAM_SPEAKERS.get(voice_id)
        if spec:
            ok = await sarvam_tts(text, spec["speaker"], Path(output_path), language="hi-IN")
            if ok:
                # CRITICAL: must return the path string so wizard's
                # `has_voice = bool(ok)` evaluates to True (otherwise the
                # generated voice file is silently dropped and the reel ends
                # up as a BGM-only mux).
                return str(output_path)
            logger.warning(f"Sarvam failed for {voice_id}, falling back to edge-tts")
            # Fallback to edge-tts based on gender
            voice_id = "hi-IN-SwaraNeural" if spec.get("gender") == "Female" else "hi-IN-MadhurNeural"
        else:
            voice_id = "hi-IN-SwaraNeural"
    # Parse pseudo IDs -> actual voice + pitch/rate shift
    tts_pitch = None; tts_rate = None
    base_voice = voice_id or "hi-IN-SwaraNeural"
    if isinstance(voice_id, str) and ':' in voice_id:
        prefix, actual = voice_id.split(':', 1)
        base_voice = actual
        # Voice effect presets (pitch in Hz, rate in %)
        effect_table = {
            'baby_boy_hi_1': ('+40Hz', '+15%'), 'baby_boy_hi_2': ('+35Hz', '+10%'), 'baby_boy_hi_3': ('+45Hz', '+25%'), 'baby_boy_hi_4': ('+30Hz', '+8%'),  'baby_boy_hi_5': ('+50Hz', '+30%'),
            'baby_girl_hi_1': ('+40Hz', '+15%'), 'baby_girl_hi_2': ('+35Hz', '+10%'), 'baby_girl_hi_3': ('+45Hz', '+25%'), 'baby_girl_hi_4': ('+30Hz', '+8%'), 'baby_girl_hi_5': ('+50Hz', '+30%'),
            'baby_boy_en_1': ('+40Hz', '+15%'), 'baby_boy_en_2': ('+35Hz', '+10%'), 'baby_boy_en_3': ('+45Hz', '+25%'), 'baby_boy_en_4': ('+30Hz', '+8%'),  'baby_boy_en_5': ('+50Hz', '+30%'),
            'baby_girl_en_1': ('+40Hz', '+15%'), 'baby_girl_en_2': ('+35Hz', '+10%'), 'baby_girl_en_3': ('+45Hz', '+25%'), 'baby_girl_en_4': ('+30Hz', '+8%'), 'baby_girl_en_5': ('+50Hz', '+30%'),
            'young': ('+15Hz', '+5%'), 'old': ('-15Hz', '-10%'), 'deep': ('-30Hz', '-5%'), 'sweet': ('+5Hz', '+8%'),
            'baby_boy_hi': ('+30Hz', '+10%'), 'baby_girl_hi': ('+30Hz', '+10%'),
            'baby_boy_en': ('+30Hz', '+10%'), 'baby_girl_en': ('+30Hz', '+10%'),
        }
        if prefix in effect_table:
            tts_pitch, tts_rate = effect_table[prefix]
        elif prefix.startswith('baby_'): tts_pitch, tts_rate = '+30Hz', '+10%'
        elif prefix.startswith('old_'): tts_pitch, tts_rate = '-20Hz', '-10%'
    # Sprint 2 — Voice style preset override (if provided, takes precedence over pseudo-voice)
    if style_preset:
        if style_preset.get("pitch"): tts_pitch = style_preset["pitch"]
        if style_preset.get("rate"): tts_rate = style_preset["rate"]
    # Sprint 2 Phase B — Explicit custom rate/pitch overrides (advanced panel) win over preset
    if voice_rate: tts_rate = voice_rate
    if voice_pitch: tts_pitch = voice_pitch
    # Fallback voice chain (used if Azure rate-limits the primary voice)
    fallback_chain = {
        'hi-IN-ArjunNeural': ['hi-IN-MadhurNeural', 'en-US-GuyNeural'],
        'hi-IN-MadhurNeural': ['hi-IN-ArjunNeural', 'en-US-GuyNeural'],
        'hi-IN-SwaraNeural': ['hi-IN-AartiNeural', 'en-US-JennyNeural'],
        'hi-IN-AartiNeural': ['hi-IN-SwaraNeural', 'en-US-JennyNeural'],
        'en-US-GuyNeural': ['en-GB-RyanNeural', 'en-US-DavisNeural'],
        'en-US-JennyNeural': ['en-US-AriaNeural', 'en-GB-SoniaNeural'],
        'en-US-AnaNeural': ['en-GB-MaisieNeural', 'en-US-JennyNeural'],
        'en-GB-MaisieNeural': ['en-US-AnaNeural', 'en-US-JennyNeural'],
    }
    voices_to_try = [base_voice] + fallback_chain.get(base_voice, ['en-US-JennyNeural'])
    last_error = None
    tts_text = text.strip()
    if len(tts_text) < 5:
        tts_text = tts_text + " ..."
    for voice_attempt in voices_to_try:
        for retry in range(3):
            try:
                kwargs = {}
                if tts_pitch: kwargs["pitch"] = tts_pitch
                if tts_rate: kwargs["rate"] = tts_rate
                comm = edge_tts.Communicate(tts_text, voice_attempt, **kwargs)
                await comm.save(str(output_path))
                if output_path.exists() and output_path.stat().st_size > 500:
                    if voice_attempt != base_voice:
                        logger.warning(f"TTS fallback used: '{base_voice}' -> '{voice_attempt}' (after {retry} retries)")
                    if tts_pitch or tts_rate:
                        logger.info(f"TTS effect applied: voice={voice_attempt} pitch={tts_pitch} rate={tts_rate}")
                    try:
                        dur_r = subprocess.run(["/usr/bin/ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(output_path)], capture_output=True, text=True, timeout=10)
                        dur = float(dur_r.stdout.strip()) if dur_r.stdout.strip() else 0
                        if dur > 0 and dur < min_duration:
                            padded = Path(str(output_path) + ".pad.mp3")
                            subprocess.run(["/usr/bin/ffmpeg", "-y", "-i", str(output_path), "-af", f"apad=pad_dur={round(min_duration - dur + 0.5, 2)}", "-t", str(min_duration + 0.5), str(padded)], capture_output=True, timeout=20)
                            if padded.exists() and padded.stat().st_size > 500:
                                padded.replace(output_path)
                    except Exception: pass
                    return str(output_path)
                else:
                    raise Exception(f"TTS produced empty file ({output_path.stat().st_size if output_path.exists() else 0} bytes)")
            except Exception as e:
                last_error = e
                err_str = str(e)[:150]
                logger.warning(f"TTS attempt failed voice={voice_attempt} retry={retry} err={err_str}")
                try:
                    if output_path.exists() and output_path.stat().st_size < 500: output_path.unlink()
                except Exception: pass
                if "NoAudioReceived" in err_str or "No audio was received" in err_str or "TimeoutError" in err_str or "Connection" in err_str:
                    await asyncio.sleep(1 + retry * 1.5)
                    continue
                else:
                    break
    raise Exception(f"TTS generation failed after all retries/fallbacks. Last error: {last_error}")

# Small in-memory cache for voice previews (voice_id -> file_path) to avoid regenerating
_preview_cache = {}

did_client = DIDClient()

def trim_video(inp, out, start, end):
    try: return subprocess.run(["ffmpeg", "-y", "-i", inp, "-ss", str(start), "-to", str(end), "-c", "copy", out], capture_output=True, timeout=120).returncode == 0
    except: return False

def get_video_duration(path):
    try: return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path], capture_output=True, text=True, timeout=10).stdout.strip())
    except: return 0.0

def _resolution_height(res: Optional[str]) -> Optional[int]:
    """Returns target height for requested res label. 1080p is greyed in UI but if sent, we cap at 720 (MH output)."""
    if not res: return None
    r = str(res).lower()
    if r in ("480p", "480"): return 480
    if r in ("720p", "720"): return 720
    if r in ("1080p", "1080"): return None  # greyed — leave as-is
    return None

def postprocess_video(in_path: Path, target_duration: Optional[float] = None, target_height: Optional[int] = None) -> Path:
    """Trim to target_duration (if shorter than current) and/or downscale to target_height.
    Returns a new Path if changes made, else original. Preserves aspect ratio."""
    try:
        in_str = str(in_path)
        cur_dur = get_video_duration(in_str) or 0.0
        need_trim = target_duration and cur_dur > (target_duration + 0.25)
        need_scale = target_height and target_height > 0
        if not need_trim and not need_scale:
            return in_path
        out = in_path.with_name(in_path.stem + f"_pp_{uuid.uuid4().hex[:6]}.mp4")
        vf = []
        if need_scale:
            # Downscale only (don't upscale) — if source is already ≤ target, skip
            vf.append(f"scale=-2:'min({target_height},ih)':flags=lanczos")
        cmd = ["/usr/bin/ffmpeg", "-y", "-i", in_str]
        if need_trim:
            cmd += ["-t", f"{float(target_duration):.2f}"]
        if vf:
            # Explicit map so audio is NEVER dropped during scale re-encode.
            # `?` = optional (no error if input has no audio stream).
            cmd += ["-map", "0:v:0", "-map", "0:a:0?",
                    "-vf", ",".join(vf),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                    "-c:a", "aac", "-b:a", "192k"]
        else:
            cmd += ["-c", "copy"]
        cmd += [str(out)]
        res = subprocess.run(cmd, capture_output=True, timeout=240)
        if res.returncode == 0 and out.exists() and out.stat().st_size > 1000:
            logger.info(f"postprocess_video OK: dur={target_duration} h={target_height} -> {out.name} ({out.stat().st_size}b)")
            return out
        logger.warning(f"postprocess_video failed: {res.stderr[-300:] if res.stderr else ''}")
        return in_path
    except Exception as e:
        logger.warning(f"postprocess_video exception: {e}")
        return in_path

def _validated_quality(q: Optional[str]) -> str:
    q = (q or "studio").lower()
    if q not in ("quick", "studio"):
        return "studio"  # cinematic greyed → fall back
    return q


def postprocess_image(in_path: Path, target_height: Optional[int] = None) -> Path:
    """Downscale an image to target_height preserving aspect ratio. Uses PIL.
    Returns a new Path if resized, else original. No-op for target_height>=source."""
    try:
        if not target_height or target_height <= 0:
            return in_path
        from PIL import Image as _PI
        with _PI.open(str(in_path)) as im:
            w, h = im.size
            if h <= target_height:
                return in_path
            new_h = target_height
            new_w = max(1, int(round(w * (new_h / h))))
            im2 = im.convert("RGB").resize((new_w, new_h), _PI.LANCZOS)
            out = in_path.with_name(in_path.stem + f"_r{target_height}.jpg")
            im2.save(str(out), format="JPEG", quality=88, optimize=True)
            logger.info(f"postprocess_image OK: {w}x{h} -> {new_w}x{new_h} ({out.name})")
            return out
    except Exception as e:
        logger.warning(f"postprocess_image failed: {e}")
    return in_path


async def apply_resolution_to_project(project_id: str, resolution: Optional[str], asset_kind: str = "video"):
    """Downscale a completed project's result_url to `resolution` in-place.
    `asset_kind`: 'video' | 'image'. Safe to call with resolution=None / '720p' / '1080p' (no-op).
    Run AFTER the project status has been set to 'completed'."""
    try:
        target_h = _resolution_height(resolution)
        if not target_h:
            return
        proj = await db.video_projects.find_one({"id": project_id})
        if not proj or proj.get("status") != "completed":
            return
        result_url = proj.get("result_url")
        if not result_url:
            return
        # Download remote URL to local cache, or resolve /api/serve-file/* locally
        local_path: Optional[Path] = None
        if result_url.startswith("/api/serve-file/"):
            fn = result_url.split("/api/serve-file/", 1)[1]
            candidate = UPLOAD_DIR / fn
            if candidate.exists(): local_path = candidate
        elif result_url.startswith("http"):
            ext = ".jpg" if asset_kind == "image" else ".mp4"
            cache = UPLOAD_DIR / f"pp_src_{uuid.uuid4().hex}{ext}"
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), follow_redirects=True) as c:
                    r = await c.get(result_url)
                    if r.status_code == 200:
                        with open(cache, "wb") as f: f.write(r.content)
                        local_path = cache
            except Exception as e:
                logger.warning(f"apply_resolution download failed: {e}")
        if not local_path or not local_path.exists():
            return
        if asset_kind == "image":
            pp = postprocess_image(local_path, target_height=target_h)
        else:
            pp = postprocess_video(local_path, target_duration=None, target_height=target_h)
        if pp == local_path:
            return  # no change made
        # Save as new served file
        ext = ".jpg" if asset_kind == "image" else ".mp4"
        new_fn = f"pp_{uuid.uuid4().hex}{ext}"
        new_path = UPLOAD_DIR / new_fn
        pp.rename(new_path)
        new_url = f"/api/serve-file/{new_fn}"
        await db.video_projects.update_one({"id": project_id}, {"$set": {"result_url": new_url, "updated_at": datetime.now(timezone.utc).isoformat()}})
        logger.info(f"apply_resolution: project={project_id} → {new_url} ({new_path.stat().st_size}b)")
    except Exception as e:
        logger.warning(f"apply_resolution error: {e}")


async def apply_watermark_if_free(project_id: str, user_tier: Optional[str], asset_kind: str = "video"):
    """Sprint-4 — Free-tier monetization gate.
    Overlays a 'MagiCAi' bottom-right watermark on completed results for Free users.
    No-op for Starter/Pro/guest/unknown tiers.
    Runs AFTER project is completed. Polls up to 3 minutes for result_url to appear."""
    if (user_tier or "").lower() != "free":
        return
    try:
        # Poll: wait for the background job to produce a result (cap ~3 min)
        proj = None
        for _ in range(60):  # 60 × 3s = 3 min
            proj = await db.video_projects.find_one({"id": project_id})
            if not proj:
                return
            if proj.get("status") == "completed" and proj.get("result_url"):
                break
            if proj.get("status") == "failed":
                return
            await asyncio.sleep(3)
        else:
            return
        result_url = proj.get("result_url")
        # Resolve local path (download remote if needed)
        local_path: Optional[Path] = None
        if result_url and result_url.startswith("/api/serve-file/"):
            fn = result_url.split("/api/serve-file/", 1)[1]
            candidate = UPLOAD_DIR / fn
            if candidate.exists(): local_path = candidate
        elif result_url and result_url.startswith("http"):
            ext = ".jpg" if asset_kind == "image" else ".mp4"
            cache = UPLOAD_DIR / f"wm_src_{uuid.uuid4().hex}{ext}"
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), follow_redirects=True) as c:
                    r = await c.get(result_url)
                    if r.status_code == 200:
                        with open(cache, "wb") as f: f.write(r.content)
                        local_path = cache
            except Exception as e:
                logger.warning(f"watermark download failed: {e}")
        if not local_path or not local_path.exists():
            return
        # Overlay "MagiCAi" bottom-right with drawtext filter.
        # Font-size auto-scales with min(W,H)/25; semi-opaque white with soft black shadow.
        ext = ".jpg" if asset_kind == "image" else ".mp4"
        out_path = UPLOAD_DIR / f"wm_{uuid.uuid4().hex}{ext}"
        drawtext = (
            "drawtext=text='MagiCAi':"
            "fontcolor=white@0.85:"
            "fontsize='h/22':"
            "x=w-tw-18:y=h-th-14:"
            "box=1:boxcolor=black@0.35:boxborderw=6:"
            "borderw=2:bordercolor=black@0.6"
        )
        if asset_kind == "image":
            cmd = ["/usr/bin/ffmpeg", "-y", "-i", str(local_path), "-vf", drawtext, "-q:v", "2", str(out_path)]
        else:
            cmd = ["/usr/bin/ffmpeg", "-y", "-i", str(local_path), "-vf", drawtext,
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                   "-c:a", "copy", str(out_path)]
        r = subprocess.run(cmd, capture_output=True, timeout=300)
        if r.returncode != 0 or not out_path.exists() or out_path.stat().st_size < 1000:
            logger.warning(f"watermark ffmpeg failed for project={project_id}: {r.stderr.decode()[-300:] if r.stderr else ''}")
            return
        new_url = f"/api/serve-file/{out_path.name}"
        await db.video_projects.update_one(
            {"id": project_id},
            {"$set": {"result_url": new_url, "watermarked": True, "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
        logger.info(f"watermark applied: project={project_id} → {new_url} ({out_path.stat().st_size}b)")
    except Exception as e:
        logger.warning(f"apply_watermark_if_free error: {e}")



# ============ BACKGROUND TASKS ============

async def _auto_merge_segments(project_id: str, segments: list) -> str | None:
    """Internal merge helper — concatenates completed segment videos into one mp4 and returns URL."""
    if not segments:
        return None
    if len(segments) == 1:
        return segments[0].get("result_url")
    try:
        merge_dir = UPLOAD_DIR / f"merge_{uuid.uuid4().hex}"
        merge_dir.mkdir(exist_ok=True)
        seg_files = []
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), follow_redirects=True) as c:
            for i, seg in enumerate(segments):
                url = seg.get("result_url")
                if not url: continue
                resp = await c.get(url)
                if resp.status_code == 200:
                    fp = merge_dir / f"seg_{i:03d}.mp4"
                    with open(fp, "wb") as f: f.write(resp.content)
                    seg_files.append(fp)
        if len(seg_files) < 2:
            return segments[0].get("result_url")
        list_path = merge_dir / "list.txt"
        with open(list_path, "w") as f:
            for sf in seg_files: f.write(f"file '{sf}'\n")
        out_path = UPLOAD_DIR / f"merged_{uuid.uuid4().hex}.mp4"
        result = subprocess.run(["/usr/bin/ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", str(out_path)], capture_output=True, timeout=180)
        if result.returncode != 0 or not out_path.exists():
            logger.warning(f"Auto-merge ffmpeg failed: {result.stderr.decode()[:200]}")
            return segments[0].get("result_url")
        import shutil
        shutil.rmtree(merge_dir, ignore_errors=True)
        return f"/api/serve-file/{out_path.name}"
    except Exception as e:
        logger.warning(f"Auto-merge failed: {e}")
        return segments[0].get("result_url") if segments else None


async def process_lipsync_multi(project_id, image_urls, dialogue_lines, voice_id=None, voice_ids=None, sound_effect=None, audio_url=None, ref_video_path=None, mode="images_only", voice_style=None, voice_rate=None, voice_pitch=None):
    try:
        logger.info(f"LS START project={project_id} mode={mode} images={len(image_urls)} lines={len(dialogue_lines)} voice_ids={voice_ids} ref_video={bool(ref_video_path)} audio_url={bool(audio_url)}")
        for i, l in enumerate(dialogue_lines):
            logger.info(f"LS line {i}: char={l.get('character_index')} voice={l.get('voice_id')} text='{l.get('text','')[:50]}' has_audio={bool(l.get('audio_url'))}")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "processing", "progress": 5, "updated_at": datetime.now(timezone.utc).isoformat()}})
        mh = MagicHourClient(token=MAGIC_HOUR_API_KEY)

        # ============ MODE B: Reference Video Only ============
        # Lip-sync the reference video itself with new audio (TTS or uploaded/recorded)
        if mode == "ref_video_only" or (ref_video_path and not image_urls):
            if not ref_video_path or not os.path.exists(ref_video_path):
                raise Exception("Reference video path is invalid or missing")
            await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 15, "updated_at": datetime.now(timezone.utc).isoformat()}})
            # Build a combined audio from all dialogue lines (TTS or pre-uploaded)
            combined_audio = UPLOAD_DIR / f"combined_tts_{uuid.uuid4().hex}.mp3"
            if audio_url and os.path.exists(audio_url):
                # Transcode to mp3 to ensure MH compatibility
                src_ext = Path(audio_url).suffix.lower().lstrip('.')
                if src_ext != "mp3":
                    subprocess.run(["/usr/bin/ffmpeg", "-y", "-i", audio_url, "-ar", "44100", "-ac", "2", "-b:a", "128k", "-f", "mp3", str(combined_audio)], capture_output=True, timeout=60)
                else:
                    import shutil as _sh
                    _sh.copy(audio_url, str(combined_audio))
            else:
                # Generate TTS for each line and concat
                parts = []
                # Normalize voice_ids keys to str (JSON numeric keys become strings)
                _vids = {str(k): v for k, v in (voice_ids or {}).items()} if voice_ids else {}
                for i, line in enumerate(dialogue_lines):
                    text = line.get("text", "").strip()
                    if not text: continue
                    char_idx = line.get("character_index", 0)
                    line_voice = line.get("voice_id") or _vids.get(str(char_idx)) or voice_id or "hi-IN-SwaraNeural"
                    part_path = UPLOAD_DIR / f"part_{uuid.uuid4().hex}.mp3"
                    await generate_tts_audio(text, line_voice, part_path, min_duration=0.5, voice_style=voice_style, voice_rate=voice_rate, voice_pitch=voice_pitch)
                    parts.append(part_path)
                    logger.info(f"LS refvideo part {i}: char={char_idx} voice={line_voice} text='{text[:50]}'")
                if not parts:
                    raise Exception("No dialogue lines provided for reference video mode")
                if len(parts) == 1:
                    parts[0].replace(combined_audio)
                else:
                    list_path = UPLOAD_DIR / f"audiolist_{uuid.uuid4().hex}.txt"
                    with open(list_path, "w") as f:
                        for p in parts: f.write(f"file '{p}'\n")
                    subprocess.run(["/usr/bin/ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(combined_audio)], capture_output=True, timeout=60)
                    for p in parts:
                        if p.exists(): p.unlink()
                    if list_path.exists(): list_path.unlink()
            # Pad if too short
            dur_r = subprocess.run(["/usr/bin/ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(combined_audio)], capture_output=True, text=True, timeout=10)
            audio_duration = float(dur_r.stdout.strip()) if dur_r.stdout.strip() else 5.0
            if audio_duration < 2.5:
                padded = Path(str(combined_audio) + ".pad.mp3")
                subprocess.run(["/usr/bin/ffmpeg", "-y", "-i", str(combined_audio), "-af", "apad=pad_dur=2.5", "-t", "3.0", str(padded)], capture_output=True, timeout=20)
                if padded.exists() and padded.stat().st_size > 500:
                    padded.replace(combined_audio); audio_duration = 3.0
            # Video duration = min(audio, video)
            vid_dur = get_video_duration(ref_video_path) or audio_duration
            end_s = min(audio_duration, vid_dur)
            await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 25, "updated_at": datetime.now(timezone.utc).isoformat()}})
            logger.info(f"LS refvideo: uploading video={os.path.getsize(ref_video_path)}b audio={combined_audio.stat().st_size}b end_s={end_s}")
            mh_video = upload_to_magic_hour(mh, ref_video_path, "video")
            mh_audio = upload_to_magic_hour(mh, str(combined_audio), "audio")
            await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 35, "updated_at": datetime.now(timezone.utc).isoformat()}})
            r = await mh_create_lipsync_with_retry(mh, f"LS_{project_id}_refvid", {"video_source": "file", "video_file_path": mh_video, "audio_file_path": mh_audio}, 0.0, end_s)
            logger.info(f"LS refvideo: job={r.id}")
            # Scale MH progress 0..100 into 35..95
            async def _on_prog(p):
                scaled = 35 + int((p / 100) * 60)
                await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": min(scaled, 95), "updated_at": datetime.now(timezone.utc).isoformat()}})
            result_url = await mh_poll_video(mh, r.id, max_wait=1200, on_progress=_on_prog)
            if not result_url: raise Exception("Lip sync timed out for reference video (MH queue overloaded, try again later)")
            segment = {"index": 0, "character_index": 0, "text": " | ".join([l.get("text","") for l in dialogue_lines if l.get("text","").strip()]), "voice_id": voice_id, "result_url": result_url}
            await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "completed", "result_url": result_url, "result_segments": [segment], "progress": 100, "updated_at": datetime.now(timezone.utc).isoformat()}})
            if combined_audio.exists(): combined_audio.unlink()
            return

        # ============ MODE A/C: Images (with optional ref video for context) ============
        segments = []; total = len(dialogue_lines)
        for i, line in enumerate(dialogue_lines):
            char_idx = line.get("character_index", 0); text = line.get("text", "")
            line_audio = line.get("audio_url")
            if not text.strip() and not line_audio and not audio_url: continue
            if not image_urls:
                raise Exception("No character images provided for images mode")
            img_url = image_urls[char_idx] if char_idx < len(image_urls) else image_urls[0]
            # Resolve voice: normalize voice_ids keys to strings (JSON stringifies numeric keys)
            _vids = {}
            if voice_ids:
                try: _vids = {str(k): v for k, v in voice_ids.items()}
                except Exception: _vids = voice_ids or {}
            line_voice = line.get("voice_id") or _vids.get(str(char_idx)) or voice_id or "hi-IN-SwaraNeural"
            logger.info(f"LS seg {i} resolving: char={char_idx} text_len={len(text)} has_line_audio={bool(line_audio)} resolved_voice={line_voice}")
            await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 5 + int((i/max(total,1))*85), "updated_at": datetime.now(timezone.utc).isoformat()}})
            # Step 1: Generate TTS audio using edge-tts (or use uploaded audio)
            audio_path = UPLOAD_DIR / f"tts_{uuid.uuid4().hex}.mp3"
            line_audio_url = line.get("audio_url")
            audio_is_external = False
            if line_audio_url and os.path.exists(line_audio_url):
                # Transcode external audio (m4a/webm/wav/etc) to mp3 for Magic Hour compatibility
                src_ext = Path(line_audio_url).suffix.lower().lstrip('.')
                converted = UPLOAD_DIR / f"tts_conv_{uuid.uuid4().hex}.mp3"
                if src_ext != "mp3":
                    conv_r = subprocess.run(["/usr/bin/ffmpeg", "-y", "-i", line_audio_url, "-ar", "44100", "-ac", "2", "-b:a", "128k", "-f", "mp3", str(converted)], capture_output=True, timeout=60)
                    if conv_r.returncode == 0 and converted.exists() and converted.stat().st_size > 500:
                        audio_path = converted; audio_is_external = False  # we own this copy
                        logger.info(f"LS seg {i}: transcoded {src_ext}->mp3 ({converted.stat().st_size}b)")
                    else:
                        audio_path = Path(line_audio_url); audio_is_external = True
                        logger.warning(f"LS seg {i}: transcode failed, using original {src_ext}: {conv_r.stderr.decode()[:200]}")
                else:
                    audio_path = Path(line_audio_url); audio_is_external = True
            elif audio_url and os.path.exists(audio_url):
                src_ext = Path(audio_url).suffix.lower().lstrip('.')
                converted = UPLOAD_DIR / f"tts_conv_{uuid.uuid4().hex}.mp3"
                if src_ext != "mp3":
                    conv_r = subprocess.run(["/usr/bin/ffmpeg", "-y", "-i", audio_url, "-ar", "44100", "-ac", "2", "-b:a", "128k", "-f", "mp3", str(converted)], capture_output=True, timeout=60)
                    if conv_r.returncode == 0 and converted.exists() and converted.stat().st_size > 500:
                        audio_path = converted; audio_is_external = False
                    else:
                        audio_path = Path(audio_url); audio_is_external = True
                else:
                    audio_path = Path(audio_url); audio_is_external = True
            else:
                await generate_tts_audio(text, line_voice, audio_path, voice_style=voice_style, voice_rate=voice_rate, voice_pitch=voice_pitch)
            # Step 2: Get the image (handle local paths and URLs)
            img_path = UPLOAD_DIR / f"lipsync_img_{uuid.uuid4().hex}.png"
            if img_url.startswith("/api/serve-file/"):
                fn = img_url.replace("/api/serve-file/", "")
                local_img = UPLOAD_DIR / fn
                if local_img.exists():
                    import shutil
                    shutil.copy(str(local_img), str(img_path))
                    logger.info(f"LS: Copied local image {local_img} -> {img_path} ({img_path.stat().st_size} bytes)")
                else:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0), follow_redirects=True) as c:
                        r = await c.get(f"http://localhost:8001{img_url}")
                        if r.status_code == 200:
                            with open(img_path, "wb") as f: f.write(r.content)
                            logger.info(f"LS: Downloaded local API image ({img_path.stat().st_size} bytes)")
            elif os.path.exists(img_url):
                import shutil
                shutil.copy(img_url, str(img_path))
                logger.info(f"LS: Copied from local path ({img_path.stat().st_size} bytes)")
            else:
                async with httpx.AsyncClient(timeout=httpx.Timeout(60.0), follow_redirects=True) as c:
                    r = await c.get(img_url)
                    if r.status_code == 200:
                        with open(img_path, "wb") as f: f.write(r.content)
                        logger.info(f"LS: Downloaded remote image ({img_path.stat().st_size} bytes)")
            if not img_path.exists() or img_path.stat().st_size == 0:
                raise Exception(f"Failed to get image for char {char_idx}: {img_url}")
            # Get audio duration
            dur_result = subprocess.run(["/usr/bin/ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)], capture_output=True, text=True, timeout=10)
            audio_duration = float(dur_result.stdout.strip()) if dur_result.stdout.strip() else 5.0
            # Ensure min 2.5s audio to satisfy Magic Hour (applies to BOTH TTS and user-uploaded/recorded audio)
            if audio_duration < 2.5:
                # If external file, copy to a new writable path first so we don't overwrite the user's upload
                if audio_is_external:
                    copy_path = UPLOAD_DIR / f"padded_{uuid.uuid4().hex}{audio_path.suffix}"
                    import shutil as _sh
                    _sh.copy(str(audio_path), str(copy_path))
                    audio_path = copy_path
                    audio_is_external = False  # we own this copy now
                padded = Path(str(audio_path) + ".pad.mp3")
                subprocess.run(["/usr/bin/ffmpeg", "-y", "-i", str(audio_path), "-af", "apad=pad_dur=2.5", "-t", "3.0", str(padded)], capture_output=True, timeout=20)
                if padded.exists() and padded.stat().st_size > 500:
                    padded.replace(audio_path); audio_duration = 3.0
                    logger.info(f"LS seg {i}: padded audio to 3.0s (was short)")
            # Step 3: Create still video from image using ffmpeg
            still_video_path = UPLOAD_DIR / f"still_{uuid.uuid4().hex}.mp4"
            ffmpeg_result = subprocess.run(["/usr/bin/ffmpeg", "-y", "-loop", "1", "-i", str(img_path), "-c:v", "libx264", "-t", str(audio_duration + 1), "-pix_fmt", "yuv420p", "-r", "25", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", str(still_video_path)], capture_output=True, timeout=60)
            if ffmpeg_result.returncode != 0:
                logger.error(f"FFmpeg still video error: {ffmpeg_result.stderr.decode()}")
                raise Exception(f"Failed to create still video: {ffmpeg_result.stderr.decode()[:200]}")
            if not still_video_path.exists() or still_video_path.stat().st_size == 0:
                raise Exception("Still video creation failed - output empty")
            # Step 4: Upload video and audio to Magic Hour
            logger.info(f"LS seg {i}: uploading video={still_video_path.stat().st_size}b audio={audio_path.stat().st_size}b dur={audio_duration:.2f}s")
            mh_video = upload_to_magic_hour(mh, str(still_video_path), "video")
            mh_audio = upload_to_magic_hour(mh, str(audio_path), "audio")
            logger.info(f"LS seg {i}: MH video={mh_video} audio={mh_audio}")
            # Step 5: Create Magic Hour lip sync
            r = await mh_create_lipsync_with_retry(mh, f"LS_{project_id}_{i}", {"video_source": "file", "video_file_path": mh_video, "audio_file_path": mh_audio}, 0.0, audio_duration)
            logger.info(f"LS seg {i}: job={r.id}")
            # Progress math: each segment occupies a slice of the 5-90% range
            base_progress = 5 + int((i / max(total, 1)) * 85)
            seg_share = int(85 / max(total, 1))
            result_url = await mh_poll_video(mh, r.id, max_wait=600, on_progress=lambda p: db.video_projects.update_one({"id": project_id}, {"$set": {"progress": base_progress + int(p/100 * seg_share), "updated_at": datetime.now(timezone.utc).isoformat()}}))
            if not result_url: raise Exception(f"Lip sync timed out for segment {i} (MH took too long)")
            segments.append({"index": i, "character_index": char_idx, "text": text, "voice_id": line_voice, "result_url": result_url})
            # Cleanup temp files
            for p in [img_path, still_video_path]:
                if p.exists(): p.unlink()
            if not audio_is_external and audio_path.exists(): audio_path.unlink()
        # Auto-merge if >1 segment
        await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 92, "updated_at": datetime.now(timezone.utc).isoformat()}})
        merged_url = await _auto_merge_segments(project_id, segments)
        final_url = merged_url or (segments[0]["result_url"] if segments else None)
        update_fields = {"status": "completed", "result_url": final_url, "result_segments": segments, "progress": 100, "updated_at": datetime.now(timezone.utc).isoformat()}
        if merged_url and merged_url != (segments[0]["result_url"] if segments else None):
            update_fields["merged_url"] = merged_url
        await db.video_projects.update_one({"id": project_id}, {"$set": update_fields})
    except Exception as e:
        logger.error(f"Lipsync failed: {e}")
        await _refund_for_failure(project_id, str(e))
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "failed", "error_message": str(e), "updated_at": datetime.now(timezone.utc).isoformat()}})

async def process_faceswap_bg(project_id, source_image_paths, target_video_path, face_indices=None, trim_start=None, trim_end=None, video_duration_hint=None):
    try:
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "processing", "progress": 5, "updated_at": datetime.now(timezone.utc).isoformat()}})
        actual_video = target_video_path
        if trim_start is not None and trim_end is not None and os.path.exists(target_video_path):
            trimmed = str(VIDEO_DIR / f"trimmed_{uuid.uuid4().hex}.mp4")
            if trim_video(target_video_path, trimmed, trim_start, trim_end): actual_video = trimmed
        mh = MagicHourClient(token=MAGIC_HOUR_API_KEY)
        vid_dur = get_video_duration(actual_video) if os.path.exists(actual_video) else 0
        if vid_dur <= 0 and video_duration_hint and video_duration_hint > 0: vid_dur = video_duration_hint
        if vid_dur <= 0: vid_dur = 300.0
        mh_video = upload_to_magic_hour(mh, actual_video, "video") if os.path.exists(actual_video) else actual_video
        await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 15, "updated_at": datetime.now(timezone.utc).isoformat()}})
        mh_imgs = []; img_detected = []
        for sp in source_image_paths:
            mi = upload_to_magic_hour(mh, sp, "image"); mh_imgs.append(mi)
            try:
                det = mh.v1.face_detection.create(assets={"target_file_path": mi})
                for _ in range(30):
                    ds = mh.v1.face_detection.get(id=det.id)
                    if ds.status == "complete" and ds.faces: img_detected.append(ds.faces[0].path); break
                    elif ds.status == "error": break
                    await asyncio.sleep(2)
            except: pass
        video_faces = []
        try:
            det_v = mh.v1.face_detection.create(assets={"target_file_path": mh_video})
            for _ in range(60):
                ds = mh.v1.face_detection.get(id=det_v.id)
                if ds.status == "complete": video_faces = ds.faces; break
                elif ds.status == "error": break
                await asyncio.sleep(2)
        except: pass
        await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 30, "updated_at": datetime.now(timezone.utc).isoformat()}})
        use_individual = len(video_faces) > 0 and len(img_detected) > 0
        face_result_url = None
        for fi, mi in enumerate(mh_imgs):
            p = 30 + int((fi / len(mh_imgs)) * 50)
            await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": p, "updated_at": datetime.now(timezone.utc).isoformat()}})
            if use_individual and fi < len(img_detected) and fi < len(video_faces):
                mapping = {"new_face": img_detected[fi], "original_face": video_faces[min(fi, len(video_faces)-1)].path}
                r = mh.v1.face_swap.create(name=f"FS_{project_id}", assets={"video_file_path": mh_video, "video_source": "file", "face_swap_mode": "individual-faces", "face_mappings": [mapping]}, start_seconds=0.0, end_seconds=min(vid_dur, 300.0))
            else:
                r = mh.v1.face_swap.create(name=f"FS_{project_id}", assets={"image_file_path": mi, "video_file_path": mh_video, "video_source": "file", "face_swap_mode": "all-faces"}, start_seconds=0.0, end_seconds=min(vid_dur, 300.0))
            start_t = time.time()
            while time.time() - start_t < 900:
                js = mh.v1.video_projects.get(id=r.id)
                if js.status == "complete":
                    face_result_url = js.downloads[0].url if js.downloads else None; break
                elif js.status in ["error", "canceled"]:
                    err_detail = getattr(js, 'error', None) or js.status
                    raise Exception(f"Face swap {js.status}: {err_detail}")
                ep = 30 + int(((time.time()-start_t)/900)*60)
                await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": min(ep, 95), "updated_at": datetime.now(timezone.utc).isoformat()}})
                await asyncio.sleep(5)
            if not face_result_url:
                await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "processing", "progress": 90, "error_message": f"Still rendering (job: {r.id})", "updated_at": datetime.now(timezone.utc).isoformat()}}); return
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "completed", "result_url": face_result_url, "progress": 100, "updated_at": datetime.now(timezone.utc).isoformat()}})
    except Exception as e:
        logger.error(f"Face swap failed: {e}")
        await _refund_for_failure(project_id, str(e))
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "failed", "error_message": str(e), "updated_at": datetime.now(timezone.utc).isoformat()}})

async def process_faceswap_image_bg(project_id, source_image_path, target_image_path):
    """Face swap on images (not videos) using Magic Hour"""
    try:
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "processing", "progress": 10, "updated_at": datetime.now(timezone.utc).isoformat()}})
        mh = MagicHourClient(token=MAGIC_HOUR_API_KEY)
        # Create a short still video from target image
        still_video_path = UPLOAD_DIR / f"fs_still_{uuid.uuid4().hex}.mp4"
        subprocess.run(["/usr/bin/ffmpeg", "-y", "-loop", "1", "-i", target_image_path, "-c:v", "libx264", "-t", "2", "-pix_fmt", "yuv420p", "-r", "25", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", str(still_video_path)], capture_output=True, timeout=30)
        if not still_video_path.exists():
            raise Exception("Failed to create still video from target image")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 20, "updated_at": datetime.now(timezone.utc).isoformat()}})
        # Upload to Magic Hour
        mh_video = upload_to_magic_hour(mh, str(still_video_path), "video")
        mh_source = upload_to_magic_hour(mh, source_image_path, "image")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 40, "updated_at": datetime.now(timezone.utc).isoformat()}})
        # Run face swap
        r = mh.v1.face_swap.create(name=f"FSI_{project_id}", assets={"image_file_path": mh_source, "video_file_path": mh_video, "video_source": "file", "face_swap_mode": "all-faces"}, start_seconds=0.0, end_seconds=2.0)
        result_url = await mh_poll_video(mh, r.id, max_wait=300)
        if not result_url:
            raise Exception("Image face swap timed out")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 85, "updated_at": datetime.now(timezone.utc).isoformat()}})
        # Extract a frame from the result video
        result_vid_path = UPLOAD_DIR / f"fsresult_{uuid.uuid4().hex}.mp4"
        frame_path = UPLOAD_DIR / f"fsframe_{uuid.uuid4().hex}.png"
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0), follow_redirects=True) as c:
            resp = await c.get(result_url)
            if resp.status_code == 200:
                with open(result_vid_path, "wb") as f: f.write(resp.content)
                logger.info(f"Downloaded result video: {result_vid_path.stat().st_size} bytes")
        ffr = subprocess.run(["/usr/bin/ffmpeg", "-y", "-i", str(result_vid_path), "-vframes", "1", "-q:v", "2", str(frame_path)], capture_output=True, timeout=15)
        logger.info(f"Frame extraction result: returncode={ffr.returncode}, frame exists={frame_path.exists()}")
        if frame_path.exists() and frame_path.stat().st_size > 0:
            fn = f"faceswap_img_{uuid.uuid4().hex}.png"
            final_path = UPLOAD_DIR / fn
            import shutil
            shutil.copy(str(frame_path), str(final_path))
            frame_path.unlink()
            final_url = f"/api/serve-file/{fn}"
            logger.info(f"Face swap image saved: {final_url}")
        else:
            logger.warning(f"Frame extraction failed, falling back to video URL")
            final_url = result_url
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "completed", "result_url": final_url, "progress": 100, "updated_at": datetime.now(timezone.utc).isoformat()}})
        # Cleanup
        for p in [still_video_path, result_vid_path]:
            if p.exists(): p.unlink()
    except Exception as e:
        logger.error(f"Image face swap failed: {e}")
        await _refund_for_failure(project_id, str(e))
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "failed", "error_message": str(e), "updated_at": datetime.now(timezone.utc).isoformat()}})

async def process_headswap_bg(project_id, head_image_path, body_image_path):
    try:
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "processing", "progress": 10, "updated_at": datetime.now(timezone.utc).isoformat()}})
        mh = MagicHourClient(token=MAGIC_HOUR_API_KEY)
        mh_head = upload_to_magic_hour(mh, head_image_path, "image")
        mh_body = upload_to_magic_hour(mh, body_image_path, "image")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 30, "updated_at": datetime.now(timezone.utc).isoformat()}})
        r = mh.v1.head_swap.create(name=f"HS_{project_id}", assets={"head_file_path": mh_head, "body_file_path": mh_body}, max_resolution=1024)
        result_url = await mh_poll_image(mh, r.id, max_wait=120)
        if not result_url: raise Exception("Head swap timed out")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "completed", "result_url": result_url, "progress": 100, "updated_at": datetime.now(timezone.utc).isoformat()}})
    except Exception as e:
        logger.error(f"Head swap failed: {e}")
        await _refund_for_failure(project_id, str(e))
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "failed", "error_message": str(e), "updated_at": datetime.now(timezone.utc).isoformat()}})

async def process_headswap_wavespeed_bg(project_id, head_image_path, body_image_path):
    try:
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "processing", "progress": 10, "updated_at": datetime.now(timezone.utc).isoformat()}})
        with open(head_image_path, 'rb') as f:
            head_b64 = base64.b64encode(f.read()).decode()
        with open(body_image_path, 'rb') as f:
            body_b64 = base64.b64encode(f.read()).decode()
        head_ext = Path(head_image_path).suffix.lstrip('.') or 'jpeg'
        body_ext = Path(body_image_path).suffix.lstrip('.') or 'jpeg'
        mime_map = {'jpg': 'jpeg', 'png': 'png', 'webp': 'webp'}
        head_mime = mime_map.get(head_ext, 'jpeg')
        body_mime = mime_map.get(body_ext, 'jpeg')
        head_data_url = f"data:image/{head_mime};base64,{head_b64}"
        body_data_url = f"data:image/{body_mime};base64,{body_b64}"
        await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 25, "updated_at": datetime.now(timezone.utc).isoformat()}})
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as c:
            r = await c.post(
                "https://api.wavespeed.ai/api/v3/wavespeed-ai/image-head-swap",
                json={"image": body_data_url, "face_image": head_data_url, "output_format": "png"},
                headers={"Authorization": f"Bearer {WAVESPEED_API_KEY}", "Content-Type": "application/json"}
            )
            if r.status_code != 200:
                raise Exception(f"WaveSpeed submit error: {r.text}")
            data = r.json()
            request_id = data.get("data", {}).get("id")
            if not request_id:
                raise Exception("No request ID from WaveSpeed")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 40, "updated_at": datetime.now(timezone.utc).isoformat()}})
        start_t = time.time()
        while time.time() - start_t < 180:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as c:
                r = await c.get(f"https://api.wavespeed.ai/api/v3/predictions/{request_id}/result", headers={"Authorization": f"Bearer {WAVESPEED_API_KEY}"})
                if r.status_code == 200:
                    result = r.json()
                    status = result.get("data", {}).get("status")
                    if status == "completed":
                        outputs = result.get("data", {}).get("outputs", [])
                        if outputs:
                            await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "completed", "result_url": outputs[0], "progress": 100, "updated_at": datetime.now(timezone.utc).isoformat()}})
                            return
                    elif status == "failed":
                        raise Exception("WaveSpeed processing failed")
            progress = min(40 + int((time.time() - start_t) / 180 * 55), 95)
            await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": progress, "updated_at": datetime.now(timezone.utc).isoformat()}})
            await asyncio.sleep(3)
        raise Exception("WaveSpeed head swap timed out")
    except Exception as e:
        logger.error(f"WaveSpeed head swap failed: {e}")
        await _refund_for_failure(project_id, str(e))
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "failed", "error_message": str(e), "updated_at": datetime.now(timezone.utc).isoformat()}})

async def process_bodyswap_bg(project_id, person_image_path, garment_image_path, garment_type="entire_outfit"):
    try:
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "processing", "progress": 10, "updated_at": datetime.now(timezone.utc).isoformat()}})
        mh = MagicHourClient(token=MAGIC_HOUR_API_KEY)
        mh_person = upload_to_magic_hour(mh, person_image_path, "image")
        mh_garment = upload_to_magic_hour(mh, garment_image_path, "image")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 30, "updated_at": datetime.now(timezone.utc).isoformat()}})
        r = mh.v1.ai_clothes_changer.create(name=f"BS_{project_id}", assets={"person_file_path": mh_person, "garment_file_path": mh_garment, "garment_type": garment_type})
        result_url = await mh_poll_image(mh, r.id, max_wait=120)
        if not result_url: raise Exception("Body swap timed out")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "completed", "result_url": result_url, "progress": 100, "updated_at": datetime.now(timezone.utc).isoformat()}})
    except Exception as e:
        logger.error(f"Body swap failed: {e}")
        await _refund_for_failure(project_id, str(e))
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "failed", "error_message": str(e), "updated_at": datetime.now(timezone.utc).isoformat()}})

async def process_image_gen_bg(project_id, prompt, aspect_ratio, quality, style):
    try:
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "processing", "progress": 10, "updated_at": datetime.now(timezone.utc).isoformat()}})
        enhanced_prompt = prompt
        if style and style != "natural":
            enhanced_prompt = f"{prompt}, {style} style"
        mh = MagicHourClient(token=MAGIC_HOUR_API_KEY)
        await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 30, "updated_at": datetime.now(timezone.utc).isoformat()}})
        ar = aspect_ratio if aspect_ratio in ["16:9", "9:16", "1:1"] else "16:9"
        r = mh.v1.ai_image_generator.create(name=f"IMG_{project_id}", image_count=1, aspect_ratio=ar, style={"prompt": enhanced_prompt, "tool": "general"})
        result_url = await mh_poll_image(mh, r.id, max_wait=120)
        if not result_url:
            raise Exception("Image generation timed out")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "completed", "result_url": result_url, "progress": 100, "updated_at": datetime.now(timezone.utc).isoformat()}})
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        await _refund_for_failure(project_id, str(e))
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "failed", "error_message": str(e), "updated_at": datetime.now(timezone.utc).isoformat()}})

async def process_video_gen_bg(project_id, prompt, aspect_ratio, duration, lyrics=None, voice_id=None, style=None, sound_effect=None, audio_path=None, quality_mode="studio", resolution="720p", voice_style=None, voice_rate=None, voice_pitch=None):
    """Generates a DYNAMIC MH text_to_video (with motion, not a static image slideshow).
    If lyrics / dialogue provided → overlays voiceover on the MH video via ffmpeg.
    If audio_path (user-uploaded/recorded) provided → uses that instead of TTS.
    sound_effect (Applause/Dramatic/etc) is passed to MH when supported.
    quality_mode: "quick" or "studio" (MH API param).
    resolution: "480p"|"720p"|"1080p"(greyed). Post-downscale via ffmpeg."""
    try:
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "processing", "progress": 5, "updated_at": datetime.now(timezone.utc).isoformat()}})
        mh = MagicHourClient(token=MAGIC_HOUR_API_KEY)
        ar = aspect_ratio if aspect_ratio in ["16:9", "9:16", "1:1"] else "9:16"
        qmode = _validated_quality(quality_mode)

        # Pass prompt AS-IS — no auto-suffix. (User feedback: "MH should use AS-IS").
        # If caller wants style emphasis they can embed it in the prompt themselves.
        enriched = prompt

        # Cap duration at 15s (UI enforces but re-check here)
        user_dur = float(duration or 5)
        user_dur = max(2.0, min(15.0, user_dur))
        # MH requires end_seconds >= 5; we'll trim down afterwards if user asked for < 5s
        mh_end_s = max(5.0, user_dur)
        await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 15, "updated_at": datetime.now(timezone.utc).isoformat()}})

        logger.info(f"T2V: prompt='{enriched[:100]}' user_dur={user_dur} mh_end_s={mh_end_s} ar={ar} quality={qmode} res={resolution}")
        r = mh.v1.text_to_video.create(
            name=f"T2V_{project_id}",
            end_seconds=mh_end_s,
            aspect_ratio=ar,
            style={"prompt": enriched, "quality_mode": qmode},
        )
        logger.info(f"T2V: job={r.id}")

        async def _on_prog(p):
            scaled = 15 + int((p / 100) * 60)  # 15..75
            await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": min(scaled, 75), "updated_at": datetime.now(timezone.utc).isoformat()}})
        async def _on_done(s): await _capture_credits(project_id, s)
        mh_video_url = await mh_poll_video(mh, r.id, max_wait=1200, on_progress=_on_prog, on_complete=_on_done)
        if not mh_video_url: raise Exception("MH text_to_video timed out")

        # Download MH result locally
        mh_local = UPLOAD_DIR / f"t2v_mh_{uuid.uuid4().hex}.mp4"
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), follow_redirects=True) as c:
            resp = await c.get(mh_video_url)
            with open(mh_local, "wb") as f: f.write(resp.content)
        logger.info(f"T2V: mh downloaded {mh_local.stat().st_size}b")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 80, "updated_at": datetime.now(timezone.utc).isoformat()}})

        # Overlay voiceover if dialogue (lyrics) or audio_path provided
        final_video_path = mh_local
        voice_audio_file = None
        if audio_path and os.path.exists(audio_path):
            voice_audio_file = Path(audio_path)
        elif lyrics and lyrics.strip():
            tts_voice = voice_id or "hi-IN-SwaraNeural"
            voice_audio_file = UPLOAD_DIR / f"t2v_tts_{uuid.uuid4().hex}.mp3"
            await generate_tts_audio(lyrics.strip(), tts_voice, voice_audio_file, min_duration=2.0, voice_style=voice_style, voice_rate=voice_rate, voice_pitch=voice_pitch)

        # Preload SFX file (if any) — Sprint 2 Phase B: auto-pick BGM from voice_style when none
        effective_sfx = sound_effect
        style_preset_t2v = _core_voice_style_by_id(voice_style) if voice_style else None
        if (not effective_sfx or effective_sfx == "none") and style_preset_t2v and style_preset_t2v.get("bgm_suggest") and style_preset_t2v.get("bgm_suggest") != "none":
            effective_sfx = style_preset_t2v["bgm_suggest"]
            logger.info(f"T2V: auto-BGM '{effective_sfx}' from voice_style '{voice_style}'")
        sfx_file = await _download_sfx(effective_sfx) if effective_sfx else None

        if voice_audio_file and voice_audio_file.exists() and voice_audio_file.stat().st_size > 500:
            # Mix: MH video's audio + voiceover + optional SFX
            mixed = UPLOAD_DIR / f"t2v_mixed_{uuid.uuid4().hex}.mp4"
            # Detect if MH video has audio track (T2V usually doesn't)
            _probe = subprocess.run(
                ["/usr/bin/ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(mh_local)],
                capture_output=True, timeout=10,
            )
            mh_has_audio = bool(_probe.stdout and b"audio" in _probe.stdout)
            if sfx_file and sfx_file.exists():
                # 3-way blend with SIDECHAIN DUCKING: SFX/BGM dips when voice plays
                if mh_has_audio:
                    filt = "[0:a]volume=0.22[bg];[1:a]volume=1.2,asplit=2[vo][vo_dup];[2:a]volume=0.7,apad[sfx];[sfx][vo_dup]sidechaincompress=threshold=0.03:ratio=9:attack=5:release=300[sfx_duck];[bg][vo][sfx_duck]amix=inputs=3:duration=first:dropout_transition=2[a]"
                else:
                    filt = "[1:a]volume=1.2,asplit=2[vo][vo_dup];[2:a]volume=0.7,apad[sfx];[sfx][vo_dup]sidechaincompress=threshold=0.03:ratio=9:attack=5:release=300[sfx_duck];[vo][sfx_duck]amix=inputs=2:duration=first:dropout_transition=2[a]"
                cmd = [
                    "/usr/bin/ffmpeg", "-y",
                    "-i", str(mh_local), "-i", str(voice_audio_file), "-stream_loop", "-1", "-i", str(sfx_file),
                    "-filter_complex", filt,
                    "-map", "0:v:0", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", str(mixed),
                ]
            else:
                if mh_has_audio:
                    filt = "[0:a]volume=0.35[bg];[1:a]volume=1.2[vo];[bg][vo]amix=inputs=2:duration=first:dropout_transition=2[a]"
                    cmd = [
                        "/usr/bin/ffmpeg", "-y",
                        "-i", str(mh_local), "-i", str(voice_audio_file),
                        "-filter_complex", filt,
                        "-map", "0:v:0", "-map", "[a]",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-shortest", str(mixed),
                    ]
                else:
                    # No MH audio — voice overlay direct (this was the old fallback path, now primary)
                    cmd = [
                        "/usr/bin/ffmpeg", "-y",
                        "-i", str(mh_local), "-i", str(voice_audio_file),
                        "-map", "0:v:0", "-map", "1:a:0",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-shortest", str(mixed),
                    ]
            res = subprocess.run(cmd, capture_output=True, timeout=180)
            if res.returncode == 0 and mixed.exists() and mixed.stat().st_size > 1000:
                final_video_path = mixed
                logger.info(f"T2V: voice+sfx mix OK {mixed.stat().st_size}b sfx={bool(sfx_file)}")
            else:
                # Fallback: try without amix (MH video has no audio track)
                cmd2 = [
                    "/usr/bin/ffmpeg", "-y",
                    "-i", str(mh_local), "-i", str(voice_audio_file),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-shortest", str(mixed),
                ]
                res2 = subprocess.run(cmd2, capture_output=True, timeout=180)
                if res2.returncode == 0 and mixed.exists() and mixed.stat().st_size > 1000:
                    final_video_path = mixed
                    logger.info(f"T2V: voice overlay (no-bg) OK")
                else:
                    logger.warning(f"T2V voice mix failed: {res2.stderr[-400:] if res2.stderr else ''}")
        elif sfx_file and sfx_file.exists():
            # No voice, but SFX wants to be applied
            mixed = UPLOAD_DIR / f"t2v_sfxonly_{uuid.uuid4().hex}.mp4"
            cmd = [
                "/usr/bin/ffmpeg", "-y",
                "-i", str(mh_local), "-stream_loop", "-1", "-i", str(sfx_file),
                "-filter_complex", "[0:a]volume=0.5[bg];[1:a]volume=0.65,apad[sfx];[bg][sfx]amix=inputs=2:duration=first:dropout_transition=2[a]",
                "-map", "0:v:0", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", str(mixed),
            ]
            res = subprocess.run(cmd, capture_output=True, timeout=180)
            if res.returncode == 0 and mixed.exists() and mixed.stat().st_size > 1000:
                final_video_path = mixed
                logger.info(f"T2V: sfx-only mix OK {mixed.stat().st_size}b")
            else:
                # fallback: just overlay sfx over silence
                cmd2 = [
                    "/usr/bin/ffmpeg", "-y",
                    "-i", str(mh_local), "-stream_loop", "-1", "-i", str(sfx_file),
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", str(mixed),
                ]
                res2 = subprocess.run(cmd2, capture_output=True, timeout=180)
                if res2.returncode == 0 and mixed.exists() and mixed.stat().st_size > 1000:
                    final_video_path = mixed

        # Post-process: trim to requested duration (MH min 5s) + downscale to target resolution
        target_h = _resolution_height(resolution)
        final_video_path = postprocess_video(final_video_path, target_duration=user_dur, target_height=target_h)

        fn = f"vidgen_{uuid.uuid4().hex}.mp4"
        final_path = UPLOAD_DIR / fn
        if final_video_path != final_path:
            final_video_path.rename(final_path)
        result_url = f"/api/serve-file/{fn}"
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "completed", "result_url": result_url, "progress": 100, "updated_at": datetime.now(timezone.utc).isoformat()}})
        # Cleanup intermediate file (keep only final)
        try:
            if mh_local.exists() and mh_local != final_path:
                mh_local.unlink()
            if voice_audio_file and voice_audio_file.exists():
                voice_audio_file.unlink()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Video generation failed: {e}")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "failed", "error_message": str(e)[:500], "updated_at": datetime.now(timezone.utc).isoformat()}})

async def process_video_redub_bg(project_id, video_url, script_text, voice_id):
    try:
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "processing", "progress": 10, "updated_at": datetime.now(timezone.utc).isoformat()}})
        mh = MagicHourClient(token=MAGIC_HOUR_API_KEY)
        # Handle local file path or URL
        vid_path = Path(video_url) if os.path.exists(video_url) else UPLOAD_DIR / f"redub_{uuid.uuid4().hex}.mp4"
        if not os.path.exists(str(vid_path)):
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), follow_redirects=True) as c:
                actual_url = f"http://localhost:8001{video_url}" if video_url.startswith("/api/") else video_url
                r = await c.get(actual_url)
                if r.status_code == 200:
                    with open(vid_path, "wb") as f: f.write(r.content)
        if not os.path.exists(str(vid_path)):
            raise Exception("Could not access video file")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 20, "updated_at": datetime.now(timezone.utc).isoformat()}})
        # Generate TTS audio
        audio_path = UPLOAD_DIR / f"redub_tts_{uuid.uuid4().hex}.mp3"
        await generate_tts_audio(script_text, voice_id or "hi-IN-SwaraNeural", audio_path)
        await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 35, "updated_at": datetime.now(timezone.utc).isoformat()}})
        # Get audio duration
        dur_result = subprocess.run(["/usr/bin/ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)], capture_output=True, text=True, timeout=10)
        audio_duration = float(dur_result.stdout.strip()) if dur_result.stdout.strip() else 10.0
        # Upload video and audio to Magic Hour
        mh_video = upload_to_magic_hour(mh, str(vid_path), "video")
        mh_audio = upload_to_magic_hour(mh, str(audio_path), "audio")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 30, "updated_at": datetime.now(timezone.utc).isoformat()}})
        # Create Magic Hour lip sync
        r = mh.v1.lip_sync.create(name=f"RD_{project_id}", assets={"video_source": "file", "video_file_path": mh_video, "audio_file_path": mh_audio}, start_seconds=0.0, end_seconds=audio_duration)
        async def _on_prog(p):
            scaled = 30 + int((p / 100) * 65)
            await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": min(scaled, 95), "updated_at": datetime.now(timezone.utc).isoformat()}})
        result_url = await mh_poll_video(mh, r.id, max_wait=300, on_progress=_on_prog)
        if not result_url:
            raise Exception("Redub processing timed out")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "completed", "result_url": result_url, "progress": 100, "updated_at": datetime.now(timezone.utc).isoformat()}})
        # Cleanup
        if audio_path.exists(): audio_path.unlink()
    except Exception as e:
        logger.error(f"Video redub failed: {e}")
        await _refund_for_failure(project_id, str(e))
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "failed", "error_message": str(e), "updated_at": datetime.now(timezone.utc).isoformat()}})

# ============ API ROUTES ============

@api_router.get("/")
async def root():
    return {"message": "MagiCAi Studio API", "version": "7.1.0"}

@api_router.post("/create-lipsync")
async def create_lipsync(req: CreateLipSyncRequest, background_tasks: BackgroundTasks, request: Request = None):
    # Sprint-4 billing: Lip Sync needs Starter+ tier; cost depends on duration.
    est_dur = int(getattr(req, 'target_duration', None) or 10)
    user, cost = await preflight_and_reserve(request, job_type='lipsync', feature='lip_sync', duration=est_dur)
    image_urls = req.image_urls or []
    p = VideoProject(name=f"Lipsync_{datetime.now(timezone.utc).strftime('%H%M%S')}", type="lipsync", user_id=user["user_id"], face_count=len(image_urls), aspect_ratio=req.aspect_ratio or "16:9", sound_effect=req.sound_effect, input_payload=req.dict(), endpoint="/api/create-lipsync")
    await db.video_projects.insert_one(p.dict())
    await _link_as_version(p.id, req.parent_id)
    background_tasks.add_task(process_lipsync_multi, p.id, image_urls, req.dialogue_lines, req.voice_id, req.voice_ids, req.sound_effect, req.audio_url, req.ref_video_path, req.mode, req.voice_style, req.voice_rate, req.voice_pitch)
    background_tasks.add_task(apply_resolution_to_project, p.id, req.resolution or "720p", "video")
    background_tasks.add_task(apply_watermark_if_free, p.id, user.get('subscription_tier'), "video")
    await settle_credits(user.get('id'), cost, user_tier=user.get('subscription_tier'), project_id=p.id, asset_kind='video', background_tasks=background_tasks)
    return {"project_id": p.id, "status": "processing", "credits_charged": cost}

@api_router.post("/create-faceswap")
async def create_faceswap(req: CreateFaceSwapRequest, background_tasks: BackgroundTasks, request: Request = None):
    user, cost = await preflight_and_reserve(request, job_type='faceswap', feature='face_swap', duration=int(getattr(req, 'video_duration', None) or 5))
    target_type = req.target_type or "video"
    proj_type = "faceswap" if target_type == "video" else "faceswap_img"
    p = VideoProject(name=f"FaceSwap_{datetime.now(timezone.utc).strftime('%H%M%S')}", type=proj_type, user_id=user["user_id"], video_url=req.target_video_path, aspect_ratio=req.aspect_ratio or "16:9", face_count=len(req.source_image_paths), trim_start=req.trim_start, trim_end=req.trim_end, video_duration=req.video_duration, input_payload=req.dict(), endpoint="/api/create-faceswap")
    await db.video_projects.insert_one(p.dict())
    await _link_as_version(p.id, req.parent_id)
    if target_type == "image":
        background_tasks.add_task(process_faceswap_image_bg, p.id, req.source_image_paths[0] if req.source_image_paths else "", req.target_video_path)
    else:
        background_tasks.add_task(process_faceswap_bg, p.id, req.source_image_paths, req.target_video_path, req.face_indices, req.trim_start, req.trim_end, req.video_duration)
    background_tasks.add_task(apply_resolution_to_project, p.id, req.resolution or "720p", "image" if target_type == "image" else "video")
    await settle_credits(user.get('id'), cost, user_tier=user.get('subscription_tier'), project_id=p.id, asset_kind='video', background_tasks=background_tasks)
    return {"project_id": p.id, "status": "processing", "credits_charged": cost}

@api_router.post("/create-headswap")
async def create_headswap(req: CreateHeadSwapRequest, background_tasks: BackgroundTasks, request: Request = None):
    user, cost = await preflight_and_reserve(request, job_type='headswap', feature='face_swap')
    provider = req.provider or "magichour"
    p = VideoProject(name=f"HeadSwap_{datetime.now(timezone.utc).strftime('%H%M%S')}", type="headswap", user_id=user["user_id"], input_payload=req.dict(), endpoint="/api/create-headswap")
    await db.video_projects.insert_one(p.dict())
    await _link_as_version(p.id, req.parent_id)
    if provider == "wavespeed":
        background_tasks.add_task(process_headswap_wavespeed_bg, p.id, req.head_image_path, req.body_image_path)
    else:
        background_tasks.add_task(process_headswap_bg, p.id, req.head_image_path, req.body_image_path)
    background_tasks.add_task(apply_resolution_to_project, p.id, req.resolution or "720p", "image")
    await settle_credits(user.get('id'), cost, user_tier=user.get('subscription_tier'), project_id=p.id, asset_kind='image', background_tasks=background_tasks)
    return {"project_id": p.id, "status": "processing", "credits_charged": cost}

@api_router.post("/create-bodyswap")
async def create_bodyswap(req: CreateBodySwapRequest, background_tasks: BackgroundTasks, request: Request = None):
    user, cost = await preflight_and_reserve(request, job_type='bodyswap', feature='face_swap')
    p = VideoProject(name=f"BodySwap_{datetime.now(timezone.utc).strftime('%H%M%S')}", type="bodyswap", user_id=user["user_id"], input_payload=req.dict(), endpoint="/api/create-bodyswap")
    await db.video_projects.insert_one(p.dict())
    await _link_as_version(p.id, req.parent_id)
    background_tasks.add_task(process_bodyswap_bg, p.id, req.person_image_path, req.garment_image_path, req.garment_type or "entire_outfit")
    background_tasks.add_task(apply_resolution_to_project, p.id, req.resolution or "720p", "image")
    await settle_credits(user.get('id'), cost, user_tier=user.get('subscription_tier'), project_id=p.id, asset_kind='image', background_tasks=background_tasks)
    return {"project_id": p.id, "status": "processing", "credits_charged": cost}

@api_router.get("/project/{project_id}")
async def get_project(project_id: str, request: Request = None):
    await get_current_user(request)
    p = await db.video_projects.find_one({"id": project_id}, {"_id": 0})
    if not p: raise HTTPException(status_code=404, detail="Not found")
    return p

# ================= SPRINT 1 — VERSIONING: Edit / Recreate / Regenerate =================

async def _link_as_version(new_project_id: str, parent_id: Optional[str]):
    """If parent_id is provided, link new project as a child version of the family.
    Sets parent_id, version=N+1, action='edit' on the new project doc."""
    if not parent_id:
        return
    root = await db.video_projects.find_one({"id": parent_id}, {"_id": 0, "parent_id": 1, "id": 1})
    if not root:
        return
    root_id = root.get("parent_id") or root["id"]
    existing = await db.video_projects.find(
        {"$or": [{"id": root_id}, {"parent_id": root_id}]},
        {"version": 1, "_id": 0},
    ).to_list(length=50)
    next_version = max([int(x.get("version", 1)) for x in existing if x.get("id") != new_project_id] or [1]) + 1
    await db.video_projects.update_one(
        {"id": new_project_id},
        {"$set": {"parent_id": root_id, "version": next_version, "action": "edit"}},
    )
    logger.info(f"Linked {new_project_id} as v{next_version} of family {root_id}")


@api_router.get("/project/{project_id}/versions")
async def list_project_versions(project_id: str, request: Request = None):
    """Return all versions in the same family (parent + children), sorted by version asc."""
    await get_current_user(request)
    p = await db.video_projects.find_one({"id": project_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    # Root of family = parent_id if set, else the project itself
    root_id = p.get("parent_id") or p["id"]
    # Query: the root project itself + all descendants (parent_id==root_id)
    cursor = db.video_projects.find(
        {"$or": [{"id": root_id}, {"parent_id": root_id}]},
        {"_id": 0},
    ).sort("version", 1)
    rows = await cursor.to_list(length=50)
    return {"parent_id": root_id, "count": len(rows), "versions": rows}


# Dispatcher — maps a stored endpoint string back to its background task + payload model.
# Keeps the rerun endpoint aware of what needs to be re-executed for each project type.
def _dispatch_rerun(endpoint: str, payload: dict, new_project_id: str, bg_tasks: BackgroundTasks):
    """Look up the background task for a given source endpoint and enqueue it with new_project_id."""
    ep = (endpoint or "").rstrip("/")
    if ep.endswith("/api/generate-video"):
        bg_tasks.add_task(
            process_video_gen_bg, new_project_id,
            payload.get("prompt"), payload.get("aspect_ratio"), payload.get("duration"),
            payload.get("lyrics"), payload.get("voice_id"), payload.get("style"),
            payload.get("sound_effect"), payload.get("audio_path"),
            payload.get("quality_mode") or "studio", payload.get("resolution") or "720p",
            payload.get("voice_style"),
        )
        bg_tasks.add_task(apply_resolution_to_project, new_project_id, payload.get("resolution") or "720p", "video")
        return True
    if ep.endswith("/api/generate-image"):
        bg_tasks.add_task(
            process_image_gen_bg, new_project_id,
            payload.get("prompt"), payload.get("aspect_ratio"), payload.get("quality"), payload.get("style"),
        )
        bg_tasks.add_task(apply_resolution_to_project, new_project_id, payload.get("resolution") or "720p", "image")
        return True
    if ep.endswith("/api/create-image-to-video"):
        bg_tasks.add_task(
            process_image_to_video, new_project_id,
            payload.get("image_path"), payload.get("prompt"), payload.get("duration") or 5,
            payload.get("aspect_ratio") or "9:16",
            payload.get("quality_mode") or "studio", payload.get("resolution") or "720p",
        )
        return True
    if ep.endswith("/api/create-video-to-video"):
        bg_tasks.add_task(
            process_video_to_video, new_project_id,
            payload.get("video_path"), payload.get("prompt"),
            payload.get("art_style") or "No Art Style",
            payload.get("duration") or 5, payload.get("start_seconds") or 0.0,
        )
        return True
    if ep.endswith("/api/create-multishot"):
        bg_tasks.add_task(
            process_multishot_bg, new_project_id,
            payload.get("shots") or [], payload.get("aspect_ratio") or "9:16",
        )
        return True
    if ep.endswith("/api/create-lipsync"):
        bg_tasks.add_task(
            process_lipsync_multi, new_project_id,
            payload.get("image_urls") or [], payload.get("dialogue_lines") or [],
            payload.get("voice_id"), payload.get("voice_ids"),
            payload.get("sound_effect"), payload.get("audio_url"),
            payload.get("ref_video_path"), payload.get("mode") or "images_only",
            payload.get("voice_style"),
        )
        bg_tasks.add_task(apply_resolution_to_project, new_project_id, payload.get("resolution") or "720p", "video")
        return True
    if ep.endswith("/api/create-faceswap"):
        target_type = payload.get("target_type") or "video"
        if target_type == "image":
            bg_tasks.add_task(
                process_faceswap_image_bg, new_project_id,
                (payload.get("source_image_paths") or [""])[0], payload.get("target_video_path"),
            )
            bg_tasks.add_task(apply_resolution_to_project, new_project_id, payload.get("resolution") or "720p", "image")
        else:
            bg_tasks.add_task(
                process_faceswap_bg, new_project_id,
                payload.get("source_image_paths") or [], payload.get("target_video_path"),
                payload.get("face_indices"), payload.get("trim_start"),
                payload.get("trim_end"), payload.get("video_duration"),
            )
            bg_tasks.add_task(apply_resolution_to_project, new_project_id, payload.get("resolution") or "720p", "video")
        return True
    if ep.endswith("/api/create-headswap"):
        bg_tasks.add_task(
            process_headswap_bg, new_project_id,
            payload.get("head_image_path"), payload.get("body_image_path"),
        )
        bg_tasks.add_task(apply_resolution_to_project, new_project_id, payload.get("resolution") or "720p", "image")
        return True
    if ep.endswith("/api/create-bodyswap"):
        bg_tasks.add_task(
            process_bodyswap_bg, new_project_id,
            payload.get("person_image_path"), payload.get("garment_image_path"),
            payload.get("garment_type") or "entire_outfit",
        )
        bg_tasks.add_task(apply_resolution_to_project, new_project_id, payload.get("resolution") or "720p", "image")
        return True
    if ep.endswith("/api/create-multi-swap"):
        bg_tasks.add_task(
            process_multi_swap_bg, new_project_id,
            payload.get("swap_type") or "bodyswap", payload.get("swaps") or [],
        )
        bg_tasks.add_task(apply_resolution_to_project, new_project_id, payload.get("resolution") or "720p", "image")
        return True
    return False


@api_router.post("/project/{project_id}/rerun")
async def rerun_project(project_id: str, background_tasks: BackgroundTasks, request: Request = None):
    """Create a new version of the family by replaying the source project's saved input_payload.

    Body: {action: "recreate" | "regenerate" | "edit", overrides?: {...}}
    - recreate: run with identical inputs
    - regenerate: adds a random seed to force variation (MH honors seed in prompt hint)
    - edit: merges `overrides` into the original payload before rerun
    Returns the new project_id.
    """
    user = await get_current_user(request)
    src = await db.video_projects.find_one({"id": project_id}, {"_id": 0})
    if not src:
        raise HTTPException(status_code=404, detail="Source project not found")
    try:
        body = await request.json() if request else {}
    except Exception:
        body = {}
    action = (body.get("action") or "recreate").lower()
    if action not in ("recreate", "regenerate", "edit"):
        raise HTTPException(status_code=400, detail="action must be recreate|regenerate|edit")
    overrides = body.get("overrides") or {}
    endpoint = src.get("endpoint")
    input_payload = src.get("input_payload")
    if not endpoint or not input_payload:
        raise HTTPException(status_code=400, detail="Source project is not replayable (no stored input_payload/endpoint)")

    # Build the new payload
    new_payload = dict(input_payload)  # shallow copy
    if action == "edit":
        new_payload.update(overrides)
    elif action == "regenerate":
        # Add a variation hint to the prompt so MH output differs deterministically-randomly
        seed = uuid.uuid4().hex[:6]
        if "prompt" in new_payload and isinstance(new_payload["prompt"], str):
            new_payload["prompt"] = f"{new_payload['prompt']} [variation:{seed}]"
        new_payload["_regenerate_seed"] = seed

    # Determine family root + next version number
    root_id = src.get("parent_id") or src["id"]
    # find max version in the family
    existing = await db.video_projects.find(
        {"$or": [{"id": root_id}, {"parent_id": root_id}]},
        {"version": 1, "_id": 0},
    ).to_list(length=50)
    next_version = max([int(x.get("version", 1)) for x in existing] or [1]) + 1

    # Create new project doc linked as child
    new_proj = VideoProject(
        name=f"{src.get('name', 'Project')} v{next_version}",
        type=src.get("type", "videogen"),
        user_id=user["user_id"],
        aspect_ratio=new_payload.get("aspect_ratio") or src.get("aspect_ratio") or "16:9",
        sound_effect=new_payload.get("sound_effect"),
        parent_id=root_id,
        version=next_version,
        action=action,
        input_payload=new_payload,
        endpoint=endpoint,
    )
    await db.video_projects.insert_one(new_proj.dict())

    # Dispatch the rerun
    ok = _dispatch_rerun(endpoint, new_payload, new_proj.id, background_tasks)
    if not ok:
        await db.video_projects.update_one(
            {"id": new_proj.id},
            {"$set": {"status": "failed", "error_message": f"Rerun not supported for endpoint: {endpoint}"}},
        )
        raise HTTPException(status_code=400, detail=f"Rerun not supported for endpoint: {endpoint}")

    logger.info(f"Rerun project {project_id} → new {new_proj.id} action={action} version={next_version}")
    return {
        "project_id": new_proj.id,
        "parent_id": root_id,
        "version": next_version,
        "action": action,
        "status": "processing",
    }

# ================= END SPRINT 1 =================


@api_router.get("/projects")
async def get_projects(request: Request = None):
    user = await get_current_user(request)
    return await db.video_projects.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)

@api_router.delete("/project/{project_id}")
async def delete_project(project_id: str, request: Request = None):
    await get_current_user(request)
    r = await db.video_projects.delete_one({"id": project_id})
    if r.deleted_count == 0: raise HTTPException(status_code=404, detail="Not found")
    return {"message": "Deleted"}

@api_router.get("/download-video")
async def download_video(url: str):
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), follow_redirects=True) as c:
        resp = await c.get(url)
        if resp.status_code != 200: raise HTTPException(status_code=502, detail="Download failed")
        ct = resp.headers.get("content-type", "video/mp4")
        ext = "mp4" if "video" in ct else "png"
        return StreamingResponse(iter([resp.content]), media_type=ct, headers={"Content-Disposition": f"attachment; filename=magicai_output.{ext}"})

@api_router.post("/create-multi-swap")
async def create_multi_swap(request: Request, background_tasks: BackgroundTasks):
    """Process multiple body/head swaps for different characters"""
    body = await request.json()
    swap_type = body.get("swap_type", "bodyswap")
    swaps = body.get("swaps", [])
    resolution = body.get("resolution", "720p")
    parent_id = body.get("parent_id")
    if not swaps: raise HTTPException(status_code=400, detail="No swaps specified")
    user, cost = await preflight_and_reserve(request, job_type='faceswap', feature='face_swap')
    # Multi-swap charges per item (capped at 10x):
    cost = max(cost, cost * min(len(swaps), 10))
    p = VideoProject(name=f"Multi{swap_type.title()}_{datetime.now(timezone.utc).strftime('%H%M%S')}", type=f"multi_{swap_type}", user_id=user["user_id"], input_payload={"swap_type": swap_type, "swaps": swaps, "resolution": resolution}, endpoint="/api/create-multi-swap")
    await db.video_projects.insert_one(p.dict())
    await _link_as_version(p.id, parent_id)
    background_tasks.add_task(process_multi_swap_bg, p.id, swap_type, swaps)
    background_tasks.add_task(apply_resolution_to_project, p.id, resolution, "image")
    await settle_credits(user.get('id'), cost, user_tier=user.get('subscription_tier'), project_id=p.id, asset_kind='image', background_tasks=background_tasks)
    return {"project_id": p.id, "status": "processing", "credits_charged": cost}

async def process_multi_swap_bg(project_id, swap_type, swaps):
    try:
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "processing", "progress": 5, "updated_at": datetime.now(timezone.utc).isoformat()}})
        mh = MagicHourClient(token=MAGIC_HOUR_API_KEY)
        results = []
        total = len(swaps)
        for i, swap in enumerate(swaps):
            progress = 5 + int((i / max(total, 1)) * 90)
            await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": progress, "updated_at": datetime.now(timezone.utc).isoformat()}})
            if swap_type == "bodyswap":
                person_path = swap.get("person_image_path")
                garment_path = swap.get("garment_image_path")
                garment_type = swap.get("garment_type", "entire_outfit")
                mh_person = upload_to_magic_hour(mh, person_path, "image")
                mh_garment = upload_to_magic_hour(mh, garment_path, "image")
                r = mh.v1.ai_clothes_changer.create(name=f"MS_{project_id}_{i}", assets={"person_file_path": mh_person, "garment_file_path": mh_garment, "garment_type": garment_type})
                result_url = await mh_poll_image(mh, r.id, max_wait=120)
            else:
                head_path = swap.get("head_image_path")
                body_path = swap.get("body_image_path")
                mh_head = upload_to_magic_hour(mh, head_path, "image")
                mh_body = upload_to_magic_hour(mh, body_path, "image")
                r = mh.v1.head_swap.create(name=f"MS_{project_id}_{i}", assets={"head_file_path": mh_head, "body_file_path": mh_body}, max_resolution=1024)
                result_url = await mh_poll_image(mh, r.id, max_wait=120)
            results.append({"index": i, "result_url": result_url, "label": swap.get("label", f"Swap {i+1}")})
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "completed", "result_url": results[0]["result_url"] if results else None, "result_segments": results, "progress": 100, "updated_at": datetime.now(timezone.utc).isoformat()}})
    except Exception as e:
        logger.error(f"Multi swap failed: {e}")
        await _refund_for_failure(project_id, str(e))
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "failed", "error_message": str(e), "updated_at": datetime.now(timezone.utc).isoformat()}})

@api_router.get("/serve-file/{filename}")
async def serve_file(filename: str):
    # Allow serving from /app/backend/uploads (default) OR /app/backend/static/bgm
    # OR /app/backend/static/previews (curated inspiration sample MP4s)
    # so we can ship locally-hosted royalty-free music + preview clips.
    fp = UPLOAD_DIR / filename
    if not fp.exists():
        # Phase D2: also allow Pixabay/AI scene images cached inside /ai_scene/ subdir.
        # We keep subdir navigation strictly inside UPLOAD_DIR to prevent path traversal.
        if '/' not in filename and '..' not in filename:
            nested = list(UPLOAD_DIR.glob(f"ai_scene/*/{filename}"))
            if nested:
                fp = nested[0]
        if not fp.exists():
            for alt in ("/app/backend/static/bgm", "/app/backend/static/previews"):
                alt_p = Path(alt) / filename
                if alt_p.exists():
                    fp = alt_p
                    break
            else:
                raise HTTPException(status_code=404, detail="File not found")
    if filename.endswith(".mp4"):
        ct = "video/mp4"
    elif filename.endswith(".mp3"):
        ct = "audio/mpeg"
    elif filename.endswith(".wav"):
        ct = "audio/wav"
    elif filename.endswith(".webp"):
        ct = "image/webp"
    elif filename.endswith(".jpg") or filename.endswith(".jpeg"):
        ct = "image/jpeg"
    else:
        ct = "image/png"
    return StreamingResponse(open(fp, "rb"), media_type=ct)

@api_router.post("/generate-image")
async def generate_image(req: GenerateImageRequest, background_tasks: BackgroundTasks, request: Request = None):
    user, cost = await preflight_and_reserve(request, job_type='image')
    p = VideoProject(name=f"ImageGen_{datetime.now(timezone.utc).strftime('%H%M%S')}", type="imagegen", user_id=user["user_id"], aspect_ratio=req.aspect_ratio or "16:9", input_payload=req.dict(), endpoint="/api/generate-image")
    await db.video_projects.insert_one(p.dict())
    await _link_as_version(p.id, req.parent_id)
    background_tasks.add_task(process_image_gen_bg, p.id, req.prompt, req.aspect_ratio, req.quality, req.style)
    background_tasks.add_task(apply_resolution_to_project, p.id, req.resolution or "720p", "image")
    await settle_credits(user.get('id'), cost, user_tier=user.get('subscription_tier'), project_id=p.id, asset_kind='image', background_tasks=background_tasks)
    return {"project_id": p.id, "status": "processing", "credits_charged": cost}

@api_router.post("/generate-video")
async def generate_video(req: GenerateVideoRequest, background_tasks: BackgroundTasks, request: Request = None):
    if req.duration and req.duration > 15:
        raise HTTPException(status_code=400, detail="Duration cannot exceed 15 seconds")
    user, cost = await preflight_and_reserve(request, job_type='video', duration=int(req.duration or 5))
    p = VideoProject(name=f"VideoGen_{datetime.now(timezone.utc).strftime('%H%M%S')}", type="videogen", user_id=user["user_id"], aspect_ratio=req.aspect_ratio or "16:9", sound_effect=req.sound_effect, input_payload=req.dict(), endpoint="/api/generate-video")
    await db.video_projects.insert_one(p.dict())
    await _link_as_version(p.id, req.parent_id)
    background_tasks.add_task(process_video_gen_bg, p.id, req.prompt, req.aspect_ratio, req.duration, req.lyrics, req.voice_id, req.style, req.sound_effect, req.audio_path, req.quality_mode or "studio", req.resolution or "720p", req.voice_style, req.voice_rate, req.voice_pitch)
    await settle_credits(user.get('id'), cost, user_tier=user.get('subscription_tier'), project_id=p.id, asset_kind='video', background_tasks=background_tasks)
    return {"project_id": p.id, "status": "processing", "credits_charged": cost}

@api_router.post("/video-redub")
async def video_redub(req: VideoRedubRequest, background_tasks: BackgroundTasks, request: Request = None):
    user, cost = await preflight_and_reserve(request, job_type='video', feature='lip_sync')
    p = VideoProject(name=f"Redub_{datetime.now(timezone.utc).strftime('%H%M%S')}", type="redub", user_id=user["user_id"])
    await db.video_projects.insert_one(p.dict())
    background_tasks.add_task(process_video_redub_bg, p.id, req.video_url, req.script_text, req.voice_id)
    background_tasks.add_task(apply_resolution_to_project, p.id, req.resolution or "720p", "video")
    await settle_credits(user.get('id'), cost, user_tier=user.get('subscription_tier'), project_id=p.id, asset_kind='video', background_tasks=background_tasks)
    return {"project_id": p.id, "status": "processing", "credits_charged": cost}

@api_router.get("/usage")
async def get_usage(request: Request):
    user = await get_current_user(request)
    pipeline = [{"$match": {"user_id": user["user_id"]}}, {"$group": {"_id": "$type", "count": {"$sum": 1}}}]
    counts = {}
    async for doc in db.video_projects.aggregate(pipeline):
        counts[doc["_id"]] = doc["count"]
    completed_pipeline = [{"$match": {"user_id": user["user_id"], "status": "completed"}}, {"$group": {"_id": "$type", "count": {"$sum": 1}}}]
    completed = {}
    async for doc in db.video_projects.aggregate(completed_pipeline):
        completed[doc["_id"]] = doc["count"]
    return {
        "lipsync": {"total": counts.get("lipsync", 0), "completed": completed.get("lipsync", 0)},
        "faceswap": {"total": counts.get("faceswap", 0), "completed": completed.get("faceswap", 0)},
        "headswap": {"total": counts.get("headswap", 0), "completed": completed.get("headswap", 0)},
        "bodyswap": {"total": counts.get("bodyswap", 0), "completed": completed.get("bodyswap", 0)},
        "total_projects": sum(counts.values()),
        "total_completed": sum(completed.values()),
    }

# Session 27d — VOICE_LIBRARY moved to core/voice_library.py
from core.voice_library import VOICE_LIBRARY  # noqa: E402


# Session 27d — /voices moved to routes/catalog.py


# Published Magic Hour credit costs (per-action estimates - used for UI display).
# Source: docs.magichour.ai/billing (approximate values as of 2026).
MH_CREDIT_COSTS = _MH_CREDIT_COSTS  # re-exported for backwards-compat in this file
MH_QUALITY_TIERS = _MH_QUALITY_TIERS


@api_router.get("/credits-info")
async def credits_info(request: Request = None):
    """Returns Magic Hour credit usage + per-action cost estimates.
    Since MH has no public balance endpoint, we sum credits_charged captured from completed jobs."""
    user_id = "anonymous"
    try:
        if request is not None:
            user = await get_current_user(request)
            user_id = user.get("id") or user.get("email") or "anonymous"
    except Exception:
        user_id = "anonymous"
    # Sum credits from completed projects
    try:
        pipeline = [
            {"$match": {"user_id": user_id, "status": "completed"}},
            {"$group": {"_id": None, "total": {"$sum": "$credits_charged"}, "count": {"$sum": 1}}},
        ]
        cur = db.video_projects.aggregate(pipeline)
        agg = await cur.to_list(length=1)
        total_used = int(agg[0]["total"]) if agg and agg[0].get("total") else 0
        total_count = int(agg[0]["count"]) if agg and agg[0].get("count") else 0
    except Exception as e:
        logger.warning(f"credits-info agg failed: {e}")
        total_used, total_count = 0, 0
    from core.pricing import MH_PER_SEC, MH_MIN_BILLED_SECONDS
    return {
        "credits_used_total": total_used,
        "completed_jobs": total_count,
        "cost_table": MH_CREDIT_COSTS,
        "pricing": {
            "min_billed_seconds": MH_MIN_BILLED_SECONDS,
            "per_sec": MH_PER_SEC,
            "video_5s_quick": MH_PER_SEC['quick'] * MH_MIN_BILLED_SECONDS,
            "video_5s_studio": MH_PER_SEC['studio'] * MH_MIN_BILLED_SECONDS,
            "video_5s_cinematic": MH_PER_SEC['cinematic'] * MH_MIN_BILLED_SECONDS,
            "image_flux_schnell": 4,
            "image_flux_dev": 6,
            "face_swap_photo": 60,
            "lip_sync_per_sec": 40,
            "talking_avatar_per_sec": 60,
        },
        "quality_tiers": MH_QUALITY_TIERS,
        "resolutions": ["480p", "720p", "1080p"],
        "resolutions_enabled": ["480p", "720p"],  # 1080p greyed for now
        "note": "MH enforces 5-second minimum billing. Shorter videos are still billed for 5s.",
    }


@api_router.get("/mh-models")
async def get_mh_models():
    """Returns MH quality tiers + REAL credit pricing (matches MH 2026 billing).

    Also returns per-feature ``duration_options`` and ``resolution_options`` so
    the frontend only exposes picker values that Magic Hour actually supports
    for the currently selected tool + model combination.

    Batch 1 (user feedback): These numbers are what MH actually charges on our
    account, so the cost shown in-app mirrors what the user will be debited.
    MH enforces 5-second minimum billed duration — any video shorter is still
    billed for 5s (backend locally trims with FFmpeg if the user picked <5s).
    """
    # Duration + resolution options are gated to what MH actually accepts.
    # * text_to_video / image_to_video / video_to_video: 5 / 10 / 15 s
    #   (MH min-billed = 5s; backend locally trims 2/3/4s requests before
    #    returning, but we only expose these ≥5s values in the UI because
    #    shorter values bill the user the same as 5s.)
    # * lip_sync / talking_avatar / redub: duration comes from audio/script
    #   (no picker required — we still return a sensible preview list).
    # * face_swap_photo: no duration concept.
    # * face_swap_video: matches source video duration (no picker).
    MH_VIDEO_DURATIONS = [5, 10, 15]
    MH_RES = {
        "480p":  {"id": "480p",  "label": "480p",          "enabled": True,  "note": "Fast, low data · same MH cost"},
        "720p":  {"id": "720p",  "label": "720p (HD)",     "enabled": True,  "note": "Default, HD · same MH cost"},
        "1080p": {"id": "1080p", "label": "1080p (Full HD)","enabled": False, "note": "Coming soon"},
    }
    std_res = [MH_RES["480p"], MH_RES["720p"], MH_RES["1080p"]]
    return {
        "quality_tiers": MH_QUALITY_TIERS,
        "min_billed_seconds": 5,
        "resolutions": std_res,  # legacy global list (kept for back-compat)
        "features": {
            "text_to_video": {
                "models": [
                    {"id": "quick", "label": "Kling Lite", "enabled": True, "credits_per_sec": 60, "min_cost": 300, "default": True, "desc": "Fast · cheapest"},
                    {"id": "studio", "label": "Kling 2.5", "enabled": True, "credits_per_sec": 80, "min_cost": 400, "desc": "Balanced quality"},
                    {"id": "cinematic", "label": "Kling 3.0 / Veo", "enabled": True, "credits_per_sec": 120, "min_cost": 600, "desc": "Top quality · premium"},
                ],
                "duration_options": MH_VIDEO_DURATIONS,
                "resolution_options": std_res,
            },
            "image_to_video": {
                "models": [
                    {"id": "quick", "label": "Kling Lite", "enabled": True, "credits_per_sec": 60, "min_cost": 300, "default": True, "desc": "Animate images fast"},
                    {"id": "studio", "label": "Kling 2.5", "enabled": True, "credits_per_sec": 80, "min_cost": 400, "desc": "Balanced animation"},
                    {"id": "cinematic", "label": "Kling 3.0 / Veo", "enabled": True, "credits_per_sec": 120, "min_cost": 600, "desc": "Premium animation"},
                ],
                "duration_options": MH_VIDEO_DURATIONS,
                "resolution_options": std_res,
            },
            "video_to_video": {
                "models": [
                    {"id": "quick", "label": "Fast Style", "enabled": True, "credits_per_sec": 50, "min_cost": 250, "default": True, "desc": "Fast style transfer"},
                    {"id": "studio", "label": "Studio Style", "enabled": True, "credits_per_sec": 70, "min_cost": 350, "desc": "Better quality"},
                ],
                "duration_options": MH_VIDEO_DURATIONS,
                "resolution_options": std_res,
            },
            "ai_image_generator": {
                "models": [
                    {"id": "quick", "label": "FLUX Schnell", "enabled": True, "credits_per_image": 4, "default": True, "desc": "Fastest (~2s)"},
                    {"id": "studio", "label": "FLUX Dev", "enabled": True, "credits_per_image": 6, "desc": "Balanced default"},
                    {"id": "cinematic", "label": "FLUX Pro", "enabled": True, "credits_per_image": 10, "desc": "Top quality"},
                ],
                "duration_options": None,  # N/A for still images
                "resolution_options": std_res,
            },
            "face_swap_photo": {
                "flat_cost": 60, "desc": "Photo face-swap (per image)",
                "duration_options": None, "resolution_options": std_res,
            },
            "face_swap_video": {
                "credits_per_sec": 80, "min_cost": 400, "desc": "Video face-swap",
                "duration_options": None,  # derived from source video
                "resolution_options": std_res,
            },
            "lip_sync": {
                "credits_per_sec": 40, "min_cost": 200, "desc": "Lip sync to audio",
                "duration_options": None,  # driven by audio length
                "resolution_options": std_res,
            },
            "talking_avatar": {
                "credits_per_sec": 60, "min_cost": 300, "desc": "AI Talking Photo",
                "duration_options": None,  # driven by script/audio length
                "resolution_options": std_res,
            },
        },
        "notice": "MH enforces 5-second minimum billing. Videos under 5s are still charged for 5s.",
    }


@api_router.get("/preview-voice")
async def preview_voice(voice_id: str):
    """Stream a short MP3 sample of the given voice. Caches results to disk."""
    # Sanitize cache key (replace special chars)
    safe_key = voice_id.replace(':', '__').replace('/', '_')
    cache_path = UPLOAD_DIR / f"voice_preview_{safe_key}.mp3"
    # Find the voice and sample text
    voice = next((v for v in VOICE_LIBRARY if v["id"] == voice_id), None)
    sample_text = voice["preview_text"] if voice else "Hello, this is a voice preview sample."
    # Use cache if present and non-empty
    if not (cache_path.exists() and cache_path.stat().st_size > 500):
        try:
            await generate_tts_audio(sample_text, voice_id, cache_path, min_duration=1.5)
        except Exception as e:
            logger.warning(f"Preview voice failed for {voice_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Voice preview failed: {str(e)[:100]}")
    if not cache_path.exists() or cache_path.stat().st_size < 500:
        raise HTTPException(status_code=500, detail="Voice preview generation failed")
    def _iter():
        with open(cache_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk: break
                yield chunk
    return StreamingResponse(_iter(), media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=3600"})

# Full SFX catalog (Magic Hour–inspired, using royalty-free CDN URLs).
# These get mixed into the final video via ffmpeg as a subtle background layer.
SFX_CATALOG = _SFX_CATALOG  # re-exported for any legacy references
_sfx_by_id = _core_sfx_by_id  # alias

async def _download_sfx(sfx_id: str) -> Optional[Path]:
    """Cache SFX file locally; returns path or None."""
    sfx = _sfx_by_id(sfx_id)
    if not sfx or not sfx.get("url"):
        return None
    cached = UPLOAD_DIR / f"sfx_cache_{sfx_id}.mp3"
    if cached.exists() and cached.stat().st_size > 500:
        return cached
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0), follow_redirects=True) as c:
            r = await c.get(sfx["url"])
            if r.status_code == 200 and len(r.content) > 500:
                with open(cached, "wb") as f:
                    f.write(r.content)
                return cached
    except Exception as e:
        logger.warning(f"SFX download failed {sfx_id}: {e}")
    return None

# Session 27e — /sound-effects moved to routes/catalog.py


# Sprint 2 — Audio Emotion Engine: Voice Styles catalog
# Session 27e — /voice-styles moved to routes/catalog.py


# ========== Sprint 3 Phase A — FFmpeg Motion Engine ==========
def animate_image_motion(src_path: Path, motion_id: str, duration: float, resolution: str = "720p", out_path: Optional[Path] = None) -> Optional[Path]:
    """Apply a motion preset (ken-burns/zoom/pan) to a still image via ffmpeg zoompan.
    Returns output video path on success, or None on failure."""
    preset = _core_motion_preset_by_id(motion_id)
    if not preset or not preset.get("zoompan_expr"):
        return None
    res_map = {"480p": (854, 480), "720p": (1280, 720), "1080p": (1920, 1080)}
    w, h = res_map.get(resolution, (1280, 720))
    fps = 25
    dur = max(1.0, float(duration or 5.0))
    total_frames = int(round(dur * fps))
    expr = preset["zoompan_expr"]
    z = expr["z"]
    x = expr["x"].replace("{D}", str(total_frames))
    y = expr["y"].replace("{D}", str(total_frames))

    if out_path is None:
        out_path = UPLOAD_DIR / f"motion_{uuid.uuid4().hex}.mp4"
    # Use 1.5x pre-upscale (not 3x) for speed. zoompan output frames are naturally `d` frames total
    # because input is a single looped PNG — we cap output with `-frames:v` (NOT -t on input, which
    # caused frame multiplication: 75 input × d=75 output = 5625 frames).
    scale_w, scale_h = int(w * 1.5), int(h * 1.5)
    vf = (
        f"scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,"
        f"crop={scale_w}:{scale_h},"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={total_frames}:s={w}x{h}:fps={fps},"
        f"format=yuv420p"
    )
    cmd = [
        "/usr/bin/ffmpeg", "-y",
        "-loop", "1", "-i", str(src_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-frames:v", str(total_frames),
        str(out_path),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, timeout=max(60, int(dur * 15)))
        if res.returncode == 0 and out_path.exists() and out_path.stat().st_size > 1000:
            logger.info(f"motion({motion_id}): OK → {out_path.name} dur={dur}s {w}x{h}")
            return out_path
        logger.warning(f"motion({motion_id}) ffmpeg fail: {res.stderr[-400:].decode('utf-8', errors='ignore') if res.stderr else 'no stderr'}")
    except subprocess.TimeoutExpired:
        logger.warning(f"motion({motion_id}) ffmpeg timeout")
    except Exception as e:
        logger.warning(f"motion({motion_id}) error: {e}")
    return None


# Session 27e — /motion-presets moved to routes/catalog.py


class AnimateImageRequest(BaseModel):
    image_path: str
    motion: str
    duration: Optional[float] = 5.0
    resolution: Optional[str] = "720p"


@api_router.post("/animate-image")
async def animate_image_endpoint(req: AnimateImageRequest, background_tasks: BackgroundTasks, request: Request = None):
    """Apply a motion preset to a still image (zero credit cost, local ffmpeg)."""
    user = await get_current_user(request)
    candidate = _resolve_upload_path(req.image_path)
    if not candidate.exists():
        raise HTTPException(status_code=400, detail=f"Image not found: {req.image_path}")
    preset = _core_motion_preset_by_id(req.motion)
    if not preset:
        raise HTTPException(status_code=400, detail=f"Unknown motion preset: {req.motion}")

    p = VideoProject(
        name=f"Motion_{preset['label']}_{datetime.now(timezone.utc).strftime('%H%M%S')}",
        type="animate_image",
        user_id=user["user_id"],
        input_payload=req.dict(),
        endpoint="/api/animate-image",
    )
    await db.video_projects.insert_one(p.dict())

    async def _bg():
        try:
            await db.video_projects.update_one({"id": p.id}, {"$set": {"status": "processing", "progress": 20}})
            out = animate_image_motion(candidate, req.motion, req.duration or 5.0, req.resolution or "720p")
            if out and out.exists():
                url = f"/api/serve-file/{out.name}"
                await db.video_projects.update_one({"id": p.id}, {"$set": {"status": "completed", "progress": 100, "result_url": url, "completed_at": datetime.now(timezone.utc)}})
            else:
                await db.video_projects.update_one({"id": p.id}, {"$set": {"status": "failed", "error": "Motion render failed"}})
        except Exception as e:
            await db.video_projects.update_one({"id": p.id}, {"$set": {"status": "failed", "error": str(e)[:300]}})

    background_tasks.add_task(_bg)
    return {"project_id": p.id, "status": "processing"}



# ========== Sprint 3 Phase C — Talking Avatar ==========
def apply_motion_to_video_clip(src_video: Path, motion_id: str, out_path: Optional[Path] = None) -> Optional[Path]:
    """Apply a ken-burns/zoom/pan preset to an existing VIDEO (not image) via ffmpeg zoompan with d=1.
    Used for layering camera motion on top of MH lip-sync output. Returns output path or None."""
    preset = _core_motion_preset_by_id(motion_id)
    if not preset or not preset.get("zoompan_expr"):
        return None
    try:
        probe = subprocess.run(
            ["/usr/bin/ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,nb_frames,r_frame_rate,duration",
             "-of", "json", str(src_video)],
            capture_output=True, timeout=15,
        )
        meta = json.loads(probe.stdout.decode() or "{}").get("streams", [{}])[0]
        w = int(meta.get("width", 1280))
        h = int(meta.get("height", 720))
        dur_str = meta.get("duration", "5.0")
        total_frames = int(meta.get("nb_frames", 0)) or int(float(dur_str) * 25)
    except Exception:
        w, h, total_frames = 1280, 720, 125

    expr = preset["zoompan_expr"]
    # Re-interpret expressions for video: use 'on' (output frame number) and TOTAL_FRAMES placeholder
    z = expr["z"]
    x = expr["x"].replace("{D}", str(total_frames))
    y = expr["y"].replace("{D}", str(total_frames))
    if out_path is None:
        out_path = UPLOAD_DIR / f"avatar_motion_{uuid.uuid4().hex}.mp4"

    # zoompan with d=1 on a video: treats each input frame as still, emits 1 output frame per input
    # We scale up to 1.3x first so zoom has room
    up_w, up_h = int(w * 1.3), int(h * 1.3)
    vf = (
        f"scale={up_w}:{up_h}:force_original_aspect_ratio=increase,crop={up_w}:{up_h},"
        f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={w}x{h}:fps=25,format=yuv420p"
    )
    cmd = [
        "/usr/bin/ffmpeg", "-y",
        "-i", str(src_video),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-pix_fmt", "yuv420p", "-r", "25",
        "-c:a", "copy",  # keep original audio
        str(out_path),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, timeout=max(90, total_frames // 5))
        if res.returncode == 0 and out_path.exists() and out_path.stat().st_size > 1000:
            logger.info(f"avatar motion({motion_id}): OK → {out_path.name} ({w}x{h})")
            return out_path
        logger.warning(f"avatar motion({motion_id}) ffmpeg fail: {res.stderr[-400:].decode('utf-8', errors='ignore') if res.stderr else ''}")
    except subprocess.TimeoutExpired:
        logger.warning(f"avatar motion({motion_id}) ffmpeg timeout")
    except Exception as e:
        logger.warning(f"avatar motion({motion_id}) error: {e}")
    return None


class CreateTalkingAvatarRequest(BaseModel):
    image_path: str              # uploaded image path
    script: str                  # script text (supports [pause:X.Xs] markers)
    voice_id: Optional[str] = "hi-IN-SwaraNeural"
    voice_style: Optional[str] = None
    voice_rate: Optional[str] = None
    voice_pitch: Optional[str] = None
    motion: Optional[str] = None  # ffmpeg motion preset for output video; None/'none' = static
    aspect_ratio: Optional[str] = "9:16"
    resolution: Optional[str] = "720p"
    parent_id: Optional[str] = None


@api_router.post("/create-talking-avatar")
async def create_talking_avatar(req: CreateTalkingAvatarRequest, background_tasks: BackgroundTasks, request: Request = None):
    """One-click Talking Avatar: image + script → MH lip-sync + optional ffmpeg camera motion.
    Composes Sprint 2 (voice_style, pauses, rate/pitch) + Sprint 3 Phase A (motion) + MH lip-sync."""
    # Robust path resolution (Batch 3: consolidated to _resolve_upload_path).
    img_abs = _resolve_upload_path(req.image_path)
    if not img_abs.exists():
        raise HTTPException(status_code=400, detail=f"Image not found: {req.image_path}")
    if not (req.script or "").strip():
        raise HTTPException(status_code=400, detail="Script is required")
    user, cost = await preflight_and_reserve(request, job_type='lipsync', feature='lip_sync')

    p = VideoProject(
        name=f"TalkingAvatar_{datetime.now(timezone.utc).strftime('%H%M%S')}",
        type="talking_avatar",
        user_id=user["user_id"],
        input_payload=req.dict(),
        endpoint="/api/create-talking-avatar",
    )
    await db.video_projects.insert_one(p.dict())
    await _link_as_version(p.id, req.parent_id)

    async def _bg():
        try:
            await db.video_projects.update_one({"id": p.id}, {"$set": {"status": "processing", "progress": 10}})
            mh = MagicHourClient(token=MAGIC_HOUR_API_KEY)
            # 1) Generate TTS audio (with style/pauses/rate/pitch)
            tts_path = UPLOAD_DIR / f"avatar_tts_{uuid.uuid4().hex}.mp3"
            await generate_tts_audio(req.script.strip(), req.voice_id or "hi-IN-SwaraNeural", tts_path, min_duration=2.5, voice_style=req.voice_style, voice_rate=req.voice_rate, voice_pitch=req.voice_pitch)
            if not tts_path.exists() or tts_path.stat().st_size < 500:
                raise Exception("TTS synthesis failed")
            await db.video_projects.update_one({"id": p.id}, {"$set": {"progress": 30}})

            # 2) Probe TTS duration, pad if needed (MH requires >= 2.5s)
            dur_r = subprocess.run(["/usr/bin/ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(tts_path)], capture_output=True, timeout=15)
            audio_dur = float((dur_r.stdout.decode() or "3.0").strip() or "3.0")
            if audio_dur < 2.5:
                padded = UPLOAD_DIR / f"avatar_tts_pad_{uuid.uuid4().hex}.mp3"
                subprocess.run(["/usr/bin/ffmpeg", "-y", "-i", str(tts_path), "-af", "apad=pad_dur=2.5", "-t", "3.0", str(padded)], capture_output=True, timeout=20)
                if padded.exists(): tts_path = padded; audio_dur = 3.0

            # 3) Create still video from the image (duration matches audio+1)
            still_v = UPLOAD_DIR / f"avatar_still_{uuid.uuid4().hex}.mp4"
            r1 = subprocess.run(["/usr/bin/ffmpeg", "-y", "-loop", "1", "-i", str(img_abs), "-c:v", "libx264", "-t", str(audio_dur + 1), "-pix_fmt", "yuv420p", "-r", "25", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", str(still_v)], capture_output=True, timeout=60)
            if r1.returncode != 0 or not still_v.exists():
                raise Exception(f"Still video creation failed: {r1.stderr[-200:].decode('utf-8', errors='ignore')}")

            # 4) Upload to MH + lip-sync
            await db.video_projects.update_one({"id": p.id}, {"$set": {"progress": 45}})
            mh_video = upload_to_magic_hour(mh, str(still_v), "video")
            mh_audio = upload_to_magic_hour(mh, str(tts_path), "audio")
            ls = await mh_create_lipsync_with_retry(mh, f"TalkingAvatar_{p.id[:8]}", {"video_source": "file", "video_file_path": mh_video, "audio_file_path": mh_audio}, 0.0, audio_dur)
            ls_url = await mh_poll_video(mh, ls.id, max_wait=600, on_progress=lambda pr: db.video_projects.update_one({"id": p.id}, {"$set": {"progress": 45 + int(pr/100 * 40)}}))
            if not ls_url:
                raise Exception("Lip-sync timed out")

            # 5) Download MH lip-sync result
            await db.video_projects.update_one({"id": p.id}, {"$set": {"progress": 88}})
            ls_local = UPLOAD_DIR / f"avatar_ls_{uuid.uuid4().hex}.mp4"
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), follow_redirects=True) as c:
                resp = await c.get(ls_url)
                with open(ls_local, "wb") as f: f.write(resp.content)

            # 6) Optionally apply motion (zoompan) on top of the talking video
            final = ls_local
            if req.motion and req.motion != "none":
                motioned = apply_motion_to_video_clip(ls_local, req.motion)
                if motioned and motioned.exists():
                    final = motioned

            # 7) Apply resolution downscale (reusing existing helper)
            result_url = f"/api/serve-file/{final.name}"
            await db.video_projects.update_one({"id": p.id}, {"$set": {"status": "completed", "progress": 100, "result_url": result_url, "completed_at": datetime.now(timezone.utc)}})
            # Async resolution downscale (don't block)
            try:
                asyncio.create_task(apply_resolution_to_project(p.id, req.resolution or "720p", "video"))
            except Exception: pass

            # Cleanup intermediate files
            for f_tmp in [tts_path, still_v]:
                try:
                    if f_tmp.exists() and f_tmp != final: f_tmp.unlink()
                except Exception: pass
        except Exception as e:
            logger.error(f"TalkingAvatar failed: {e}")
            await db.video_projects.update_one({"id": p.id}, {"$set": {"status": "failed", "error": str(e)[:300]}})

    background_tasks.add_task(_bg)
    await settle_credits(user.get('id'), cost, user_tier=user.get('subscription_tier'), project_id=p.id, asset_kind='video', background_tasks=background_tasks)
    return {"project_id": p.id, "status": "processing", "credits_charged": cost}
# Preset idea → AI image generation prompt mappings
IDEA_PROMPTS = {
    # Body/Outfit ideas
    "Business Suit": "Full body portrait of a person in a sharp tailored business suit, professional studio background, front-facing pose, high quality photography",
    "Wedding Lehenga": "Full body portrait of a person in an elegant traditional Indian wedding lehenga with intricate embroidery, bridal jewelry, decorated mandap background, front-facing pose",
    "Silk Saree": "Full body portrait of a person in an elegant silk saree, traditional Indian attire, festival setting, front-facing pose, soft lighting",
    "Kurta Pajama": "Full body portrait of a person in a traditional Indian kurta pajama, ethnic attire, elegant pose, festive background, front-facing",
    "Sports Jersey": "Full body portrait of a person in a vibrant sports jersey and athletic shorts, stadium background, confident sporty pose, front-facing",
    "Superhero Suit": "Full body portrait of a person in a dynamic superhero costume with cape, cinematic city background, heroic pose, front-facing",
    "Royal Attire": "Full body portrait of a person in regal royal attire with ornate embroidery and crown, palace throne room background, front-facing pose",
    "Beach Wear": "Full body portrait of a person in stylish beach wear, tropical beach background with sand and ocean, front-facing relaxed pose",
    # Head/Face ideas
    "Bollywood Hero": "Studio portrait of a charismatic Bollywood hero face, classic Indian cinema lighting, dramatic expression, close-up",
    "Movie Star": "Studio portrait of a glamorous Hollywood movie star face, high-fashion lighting, close-up headshot",
    "Mythological Deity": "Close-up face of an Indian mythological deity, divine glow, traditional crown and ornaments, serene expression",
    "Historical Figure": "Close-up portrait of a dignified historical Indian figure, period-accurate styling, sepia tones, noble expression",
    "Family Face": "Warm close-up family portrait face, friendly expression, soft natural lighting, front-facing",
    "Music Star": "Close-up portrait of a charismatic music star with stylish hair and sunglasses, concert stage lighting, confident expression",
    "Cricket Hero": "Close-up portrait of an Indian cricket hero in team uniform, stadium background, determined expression",
    "Royal / King": "Close-up regal portrait of an Indian king, ornate crown and royal robes, palace background, noble expression",
    # ===== Indian Gods & Goddesses (Mythological Deities) =====
    "Lord Krishna": "Divine close-up portrait of Lord Krishna, blue-skinned, peacock feather crown, flute in hand, Vrindavan background, golden glow, serene smiling expression",
    "Lord Shiva": "Majestic close-up portrait of Lord Shiva, meditating on Mount Kailash, third eye, crescent moon, snake around neck, trident (trishul), ash-smeared skin, divine aura",
    "Lord Ganesha": "Close-up portrait of Lord Ganesha, elephant head, broken tusk, golden crown, red vermillion, smiling gentle expression, divine glow",
    "Lord Ram": "Regal close-up portrait of Lord Ram with bow and arrow, golden crown, noble expression, Ayodhya palace background, divine aura",
    "Lord Hanuman": "Powerful close-up portrait of Lord Hanuman, orange-colored devoted expression, gada (mace), flying pose over mountain, sunrise sky",
    "Goddess Durga": "Divine close-up portrait of Goddess Durga, riding a tiger, ten arms holding weapons, red sari, golden crown, fierce yet compassionate expression",
    "Goddess Lakshmi": "Graceful close-up portrait of Goddess Lakshmi, seated on lotus, gold coins, red sari with gold border, four arms, elephants beside, divine lotus pond",
    "Goddess Saraswati": "Serene close-up portrait of Goddess Saraswati, white sari, veena (musical instrument), swan beside, white lotus, divine wisdom expression",
    "Goddess Kali": "Fierce close-up portrait of Goddess Kali, dark complexion, tongue out, garland of skulls, sword in hand, red glowing eyes, intense divine power",
    "Goddess Parvati": "Beautiful close-up portrait of Goddess Parvati, consort of Shiva, red and gold attire, traditional Indian jewelry, loving expression, mountain background",
    "Lord Vishnu": "Majestic close-up portrait of Lord Vishnu, blue-skinned, four arms holding shankh, chakra, gada, padma, lying on Shesha-naga in cosmic ocean, divine glow",
    "Lord Brahma": "Divine close-up portrait of Lord Brahma, four faces, long white beard, red robes, holding Vedas and lotus, seated on lotus, creator of universe aura",
}


class GenerateIdeaImageRequest(BaseModel):
    label: str  # preset idea label (e.g. "Business Suit")
    idea_type: Optional[str] = "outfit"  # "outfit" or "head"
    custom_prompt: Optional[str] = None
    aspect_ratio: Optional[str] = "9:16"


class ImageToVideoRequest(BaseModel):
    image_path: str  # local file path (from /api/upload-face-image)
    prompt: str
    duration: Optional[int] = 5  # 2..15 (≤15). Sub-5s values are trimmed post-MH.
    shot_count: Optional[int] = 1  # multi-shot: 1..4
    aspect_ratio: Optional[str] = "9:16"
    quality_mode: Optional[str] = "studio"  # "quick" | "studio"
    resolution: Optional[str] = "720p"  # "480p" | "720p" | "1080p"(greyed)
    sound_effect: Optional[str] = None
    audio_path: Optional[str] = None
    lyrics: Optional[str] = None
    voice_id: Optional[str] = "hi-IN-SwaraNeural"
    parent_id: Optional[str] = None


class VideoToVideoRequest(BaseModel):
    video_path: str  # local file path (from /api/upload-video)
    prompt: str
    art_style: Optional[str] = "No Art Style"
    duration: Optional[int] = 5
    shot_count: Optional[int] = 1
    start_seconds: Optional[float] = 0.0
    quality_mode: Optional[str] = "studio"
    resolution: Optional[str] = "720p"
    parent_id: Optional[str] = None


class SuggestScenesRequest(BaseModel):
    ref_video_path: Optional[str] = None  # reference video to analyze
    user_hint: Optional[str] = None  # optional topic hint from user
    count: Optional[int] = 4  # how many scene suggestions to return


class AIBgLipSyncRequest(BaseModel):
    character_image_path: str  # local path to character image
    scene_prompt: str  # scene prompt (e.g. "Krishna in Vrindavan garden")
    dialogue_text: str  # what the character should say
    voice_id: Optional[str] = "hi-IN-SwaraNeural"
    audio_path: Optional[str] = None  # optional user-provided audio instead of TTS
    duration: Optional[int] = 5  # seconds
    aspect_ratio: Optional[str] = "9:16"


@api_router.post("/generate-idea-image")
async def generate_idea_image(req: GenerateIdeaImageRequest):
    """Generate an outfit/head idea image using Magic Hour AI image generator.
    Returns a URL + file_path that can be used as garment/body/head image."""
    prompt = req.custom_prompt or IDEA_PROMPTS.get(req.label, f"High quality photo of {req.label}, front-facing, professional lighting")
    try:
        mh = MagicHourClient(token=MAGIC_HOUR_API_KEY)
        ar = req.aspect_ratio if req.aspect_ratio in ["16:9", "9:16", "1:1"] else "9:16"
        r = mh.v1.ai_image_generator.create(name=f"IDEA_{uuid.uuid4().hex[:8]}", image_count=1, aspect_ratio=ar, style={"prompt": prompt, "tool": "general"})
        result_url = await mh_poll_image(mh, r.id, max_wait=120)
        if not result_url:
            raise HTTPException(status_code=500, detail="Idea image generation timed out")
        # Download and save locally so it can be re-uploaded to MH for swap ops
        local_fn = f"idea_{uuid.uuid4().hex}.png"
        local_path = UPLOAD_DIR / local_fn
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0), follow_redirects=True) as c:
            resp = await c.get(result_url)
            if resp.status_code == 200:
                with open(local_path, "wb") as f:
                    f.write(resp.content)
        if not local_path.exists() or local_path.stat().st_size == 0:
            # Fallback: just return the remote URL (less reliable but works)
            return {"image_url": result_url, "file_path": None, "prompt": prompt}
        return {
            "image_url": f"/api/serve-file/{local_fn}",
            "file_path": str(local_path),
            "prompt": prompt,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Idea image generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Idea generation failed: {str(e)[:150]}")


# ================= IMAGE-TO-VIDEO ENDPOINT =================

async def process_image_to_video(project_id: str, image_path: str, prompt: str, duration: int, aspect_ratio: str, quality_mode: str = "studio", resolution: str = "720p"):
    try:
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "processing", "progress": 5}})
        mh = MagicHourClient(token=MAGIC_HOUR_API_KEY)
        qmode = _validated_quality(quality_mode)
        # Batch 3: Resolve image path robustly (was 400 when frontend sent absolute path)
        resolved = _resolve_upload_path(image_path)
        if not resolved.exists():
            raise HTTPException(status_code=400, detail=f"Image not found: {image_path}")
        image_path = str(resolved)
        # Normalise image to clean JPG (fixes HEIC/CMYK/16-bit/alpha issues MH rejects)
        norm_image = normalize_image_for_mh(image_path)
        mh_image = upload_to_magic_hour(mh, norm_image, "image")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 20}})
        # Cap duration at 15s; MH requires ≥5s
        user_dur = max(2.0, min(15.0, float(duration or 5)))
        mh_end_s = max(5.0, user_dur)
        logger.info(f"I2V: uploading image size={os.path.getsize(image_path)}b prompt='{prompt[:60]}' user_dur={user_dur}s mh_end_s={mh_end_s} quality={qmode} res={resolution}")
        r = mh.v1.image_to_video.create(
            name=f"I2V_{project_id}",
            assets={"image_file_path": mh_image},
            end_seconds=mh_end_s,
            style={"prompt": prompt, "high_quality": True, "quality_mode": qmode},
        )
        logger.info(f"I2V: job={r.id}")
        async def _on_prog(p):
            scaled = 20 + int((p / 100) * 70)
            await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": min(scaled, 90)}})
        async def _on_done(s): await _capture_credits(project_id, s)
        mh_video_url = await mh_poll_video(mh, r.id, max_wait=900, on_progress=_on_prog, on_complete=_on_done)
        if not mh_video_url: raise Exception("I2V timed out")

        # Post-process: trim to user duration + downscale to target res
        target_h = _resolution_height(resolution)
        needs_pp = (user_dur < mh_end_s - 0.25) or (target_h is not None)
        final_url = mh_video_url
        if needs_pp:
            await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 92}})
            mh_local = UPLOAD_DIR / f"i2v_mh_{uuid.uuid4().hex}.mp4"
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), follow_redirects=True) as c:
                    resp = await c.get(mh_video_url)
                    with open(mh_local, "wb") as f: f.write(resp.content)
                pp_path = postprocess_video(mh_local, target_duration=user_dur, target_height=target_h)
                fn = f"i2v_{uuid.uuid4().hex}.mp4"
                final_path = UPLOAD_DIR / fn
                if pp_path != final_path:
                    pp_path.rename(final_path)
                final_url = f"/api/serve-file/{fn}"
                # Cleanup intermediate
                try:
                    if mh_local.exists() and mh_local != final_path: mh_local.unlink()
                except Exception: pass
            except Exception as e:
                logger.warning(f"I2V postprocess failed: {e}; using raw MH url")
                final_url = mh_video_url

        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "completed", "progress": 100, "result_url": final_url, "updated_at": datetime.now(timezone.utc).isoformat()}})
    except Exception as e:
        logger.error(f"I2V failed: {e}")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "failed", "error_message": str(e)[:500]}})


@api_router.post("/create-image-to-video")
async def create_image_to_video(req: ImageToVideoRequest, background_tasks: BackgroundTasks, request: Request = None):
    if not os.path.exists(req.image_path):
        raise HTTPException(status_code=400, detail=f"Image not found: {req.image_path}")
    if req.duration and req.duration > 15:
        raise HTTPException(status_code=400, detail="Duration cannot exceed 15 seconds")
    shots = max(1, min(int(req.shot_count or 1), 4))
    # Session 27d — tier gate integrated into preflight_and_reserve (feature='ai_video')
    # so free/starter → 402 with "AI Video requires Creator plan..." before credit reserve.
    user, cost_per_shot = await preflight_and_reserve(
        request, job_type='video', feature='ai_video', duration=int(req.duration or 5),
    )
    total_cost = cost_per_shot * shots
    # Re-check balance for multi-shot against total
    if user.get('credits_balance') is not None and total_cost > user.get('credits_balance', 0):
        raise HTTPException(status_code=402, detail=f"Need {total_cost} credits for {shots} shots; you have {user.get('credits_balance')}.")
    project_ids = []
    for i in range(shots):
        p = VideoProject(name=f"I2V_shot{i+1}_{datetime.now(timezone.utc).strftime('%H%M%S')}", type="image_to_video", user_id=user["user_id"], aspect_ratio=req.aspect_ratio, input_payload=req.dict(), endpoint="/api/create-image-to-video")
        pd = p.dict()
        pd["created_at"] = pd["created_at"].isoformat() if isinstance(pd["created_at"], datetime) else pd["created_at"]
        pd["updated_at"] = pd["updated_at"].isoformat() if isinstance(pd["updated_at"], datetime) else pd["updated_at"]
        await db.video_projects.insert_one(pd)
        background_tasks.add_task(process_image_to_video, p.id, req.image_path, req.prompt, req.duration or 5, req.aspect_ratio or "9:16", req.quality_mode or "studio", req.resolution or "720p")
        project_ids.append(p.id)
    await settle_credits(user.get('id'), total_cost)
    return {"project_ids": project_ids, "project_id": project_ids[0], "shots": shots, "credits_charged": total_cost}


# ================= VIDEO-TO-VIDEO ENDPOINT =================

async def process_video_to_video(project_id: str, video_path: str, prompt: str, art_style: str, duration: int, start_seconds: float):
    try:
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "processing", "progress": 5}})
        mh = MagicHourClient(token=MAGIC_HOUR_API_KEY)
        mh_video = upload_to_magic_hour(mh, video_path, "video")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 20}})
        end_s = float(start_seconds + max(2, duration))
        logger.info(f"V2V: uploading video size={os.path.getsize(video_path)}b prompt='{prompt[:60]}' style={art_style} duration={duration}s")
        r = mh.v1.video_to_video.create(
            name=f"V2V_{project_id}",
            assets={"video_source": "file", "video_file_path": mh_video},
            start_seconds=float(start_seconds),
            end_seconds=end_s,
            style={"art_style": art_style, "prompt": prompt, "prompt_type": "append_default"},
        )
        logger.info(f"V2V: job={r.id}")
        async def _on_prog(p):
            scaled = 20 + int((p / 100) * 75)
            await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": min(scaled, 95)}})
        async def _on_done(s): await _capture_credits(project_id, s)
        result_url = await mh_poll_video(mh, r.id, max_wait=1200, on_progress=_on_prog, on_complete=_on_done)
        if not result_url: raise Exception("V2V timed out")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "completed", "progress": 100, "result_url": result_url, "updated_at": datetime.now(timezone.utc).isoformat()}})
    except Exception as e:
        logger.error(f"V2V failed: {e}")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "failed", "error_message": str(e)[:500]}})


@api_router.post("/create-video-to-video")
async def create_video_to_video(req: VideoToVideoRequest, background_tasks: BackgroundTasks, request: Request = None):
    if not os.path.exists(req.video_path):
        raise HTTPException(status_code=400, detail=f"Video not found: {req.video_path}")
    if req.duration and req.duration > 15:
        raise HTTPException(status_code=400, detail="Duration cannot exceed 15 seconds")
    shots = max(1, min(int(req.shot_count or 1), 4))
    # Session 27e — tier gate: Video-to-Video is an AI video generation → gated
    user, cost_per_shot = await preflight_and_reserve(request, job_type='video', feature='ai_video', duration=int(req.duration or 5))
    total_cost = cost_per_shot * shots
    if user.get('credits_balance') is not None and total_cost > user.get('credits_balance', 0):
        raise HTTPException(status_code=402, detail=f"Need {total_cost} credits for {shots} shots; you have {user.get('credits_balance')}.")
    project_ids = []
    for i in range(shots):
        p = VideoProject(name=f"V2V_shot{i+1}_{datetime.now(timezone.utc).strftime('%H%M%S')}", type="video_to_video", user_id=user["user_id"], input_payload=req.dict(), endpoint="/api/create-video-to-video")
        pd = p.dict()
        pd["created_at"] = pd["created_at"].isoformat() if isinstance(pd["created_at"], datetime) else pd["created_at"]
        pd["updated_at"] = pd["updated_at"].isoformat() if isinstance(pd["updated_at"], datetime) else pd["updated_at"]
        await db.video_projects.insert_one(pd)
        background_tasks.add_task(process_video_to_video, p.id, req.video_path, req.prompt, req.art_style or "No Art Style", req.duration or 5, req.start_seconds or 0.0)
        project_ids.append(p.id)
    await settle_credits(user.get('id'), total_cost)
    return {"project_ids": project_ids, "project_id": project_ids[0], "shots": shots, "credits_charged": total_cost}


# ================= MULTI-SHOT TIMELINE =================
# Generate N sequential shots with per-shot prompt/duration/audio/SFX and stitch them into one final video via ffmpeg concat.

class MultiShotShot(BaseModel):
    prompt: str
    duration: Optional[int] = 5        # 2..15 (≤15)
    start_image_path: Optional[str] = None  # if set → image_to_video; else → text_to_video
    dialogue: Optional[str] = None     # TTS text (overridden if dialogue_audio_path set)
    dialogue_audio_path: Optional[str] = None  # uploaded/recorded dialogue audio
    voice_id: Optional[str] = "hi-IN-SwaraNeural"
    sound_effect: Optional[str] = None  # SFX id from /api/sound-effects
    quality_mode: Optional[str] = "studio"  # "quick" | "studio"
    transition_out: Optional[str] = "cut"  # "cut" | "fade" | "crossfade" — transition INTO the next shot (ignored on last)
    voice_style: Optional[str] = None  # Sprint 2: audio emotion preset (per-shot)
    voice_rate: Optional[str] = None   # Sprint 2 Phase B: explicit rate override per shot
    voice_pitch: Optional[str] = None  # Sprint 2 Phase B: explicit pitch override per shot
    motion: Optional[str] = None       # Sprint 3 Phase A: ffmpeg motion preset (bypasses MH when set + start_image_path)


class CreateMultiShotRequest(BaseModel):
    shots: List[MultiShotShot]
    aspect_ratio: Optional[str] = "9:16"
    resolution: Optional[str] = "720p"  # "480p" | "720p"
    name: Optional[str] = None
    parent_id: Optional[str] = None
    voice_style: Optional[str] = None   # Sprint 2: timeline-wide style (overrides per-shot if present)
    voice_rate: Optional[str] = None    # Sprint 2 Phase B: timeline-wide rate override
    voice_pitch: Optional[str] = None   # Sprint 2 Phase B: timeline-wide pitch override


async def _generate_single_shot_clip(mh, shot: MultiShotShot, aspect_ratio: str, shot_idx: int) -> Optional[Path]:
    """Generate a single shot video via MH (text_to_video or image_to_video),
    then locally overlay voice (TTS or uploaded) + SFX. Returns local Path or None.

    Sprint 3 Phase A: If `shot.motion` is set (a valid preset) AND `shot.start_image_path` exists,
    we BYPASS Magic Hour entirely and use ffmpeg zoompan locally — zero credit cost."""
    ar = aspect_ratio if aspect_ratio in ["16:9", "9:16", "1:1"] else "9:16"
    end_s = max(5.0, float(shot.duration or 5))

    # Sprint 3 Phase A — Motion short-circuit (ffmpeg zoompan, no MH call)
    mh_local = None
    motion_preset = _core_motion_preset_by_id(shot.motion) if shot.motion else None
    if motion_preset and shot.start_image_path and os.path.exists(shot.start_image_path):
        # Portrait/landscape resolution mapping based on aspect ratio
        res_w_h = {
            "9:16": ("480p", 480, 854),
            "16:9": ("480p", 854, 480),
            "1:1":  ("480p", 640, 640),
        }
        _res_id, tw, th = res_w_h.get(ar, ("480p", 854, 480))
        motion_out = UPLOAD_DIR / f"ms_{shot_idx}_motion_{uuid.uuid4().hex}.mp4"
        preset_expr = motion_preset["zoompan_expr"]
        fps = 25
        total_frames = int(round(end_s * fps))
        z = preset_expr["z"]
        x = preset_expr["x"].replace("{D}", str(total_frames))
        y = preset_expr["y"].replace("{D}", str(total_frames))
        scale_w, scale_h = int(tw * 1.5), int(th * 1.5)
        vf = (
            f"scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,"
            f"crop={scale_w}:{scale_h},"
            f"zoompan=z='{z}':x='{x}':y='{y}':d={total_frames}:s={tw}x{th}:fps={fps},"
            f"format=yuv420p"
        )
        cmd = [
            "/usr/bin/ffmpeg", "-y",
            "-loop", "1", "-i", str(shot.start_image_path),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-r", str(fps),
            "-frames:v", str(total_frames),
            str(motion_out),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=max(60, int(end_s * 15)))
            if res.returncode == 0 and motion_out.exists() and motion_out.stat().st_size > 1000:
                mh_local = motion_out
                logger.info(f"MS shot {shot_idx}: motion({shot.motion}) bypass MH → {motion_out.name}")
        except Exception as e:
            logger.warning(f"MS shot {shot_idx}: motion bypass failed ({e}) — falling back to MH")

    if mh_local is None:
        # Magic Hour path — pass shot prompt AS-IS (user feedback).
        enriched = shot.prompt

        if shot.start_image_path and os.path.exists(shot.start_image_path):
            # image_to_video — note: current magic_hour SDK no longer accepts `orientation`
            norm_img = normalize_image_for_mh(shot.start_image_path)
            mh_img = upload_to_magic_hour(mh, norm_img, "image")
            try:
                r = mh.v1.image_to_video.create(
                    name=f"MultiShot_{shot_idx}",
                    end_seconds=end_s,
                    assets={"image_file_path": mh_img},
                    style={"prompt": enriched, "high_quality": True, "quality_mode": "studio"},
                )
            except TypeError as te:
                # If SDK signature changed again, retry with minimal args
                logger.warning(f"MS shot {shot_idx}: image_to_video TypeError {te} — retrying minimal")
                r = mh.v1.image_to_video.create(
                    name=f"MultiShot_{shot_idx}",
                    assets={"image_file_path": mh_img},
                    style={"prompt": enriched},
                )
        else:
            # text_to_video
            r = mh.v1.text_to_video.create(
                name=f"MultiShot_{shot_idx}",
                end_seconds=end_s,
                aspect_ratio=ar,
                style={"prompt": enriched, "quality_mode": "studio"},
            )
        mh_video_url = await mh_poll_video(mh, r.id, max_wait=1200)
        if not mh_video_url:
            return None

        # Download MH result
        mh_local = UPLOAD_DIR / f"ms_{shot_idx}_mh_{uuid.uuid4().hex}.mp4"
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), follow_redirects=True) as c:
            resp = await c.get(mh_video_url)
            with open(mh_local, "wb") as f: f.write(resp.content)

    # Per-shot voice + SFX overlay
    voice_audio_file = None
    if shot.dialogue_audio_path and os.path.exists(shot.dialogue_audio_path):
        voice_audio_file = Path(shot.dialogue_audio_path)
    elif shot.dialogue and shot.dialogue.strip():
        voice_audio_file = UPLOAD_DIR / f"ms_{shot_idx}_tts_{uuid.uuid4().hex}.mp3"
        try:
            await generate_tts_audio(shot.dialogue.strip(), shot.voice_id or "hi-IN-SwaraNeural", voice_audio_file, min_duration=1.5, voice_style=shot.voice_style, voice_rate=shot.voice_rate, voice_pitch=shot.voice_pitch)
        except Exception as e:
            logger.warning(f"MS shot {shot_idx}: TTS failed: {e}")
            voice_audio_file = None

    # Sprint 2 Phase B — Auto-attach preset's suggested BGM when no sound_effect is set
    effective_sfx = shot.sound_effect
    style_preset = _core_voice_style_by_id(shot.voice_style) if shot.voice_style else None
    if (not effective_sfx or effective_sfx == "none") and style_preset and style_preset.get("bgm_suggest") and style_preset.get("bgm_suggest") != "none":
        effective_sfx = style_preset["bgm_suggest"]
        logger.info(f"MS shot {shot_idx}: auto-BGM '{effective_sfx}' from voice_style '{shot.voice_style}'")

    sfx_file = await _download_sfx(effective_sfx) if effective_sfx else None
    final = mh_local
    if (voice_audio_file and voice_audio_file.exists()) or (sfx_file and sfx_file.exists()):
        mixed = UPLOAD_DIR / f"ms_{shot_idx}_mix_{uuid.uuid4().hex}.mp4"
        # Detect if MH video has an audio track (MH T2V typically doesn't)
        probe = subprocess.run(
            ["/usr/bin/ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(mh_local)],
            capture_output=True, timeout=10,
        )
        mh_has_audio = bool(probe.stdout and b"audio" in probe.stdout)

        if voice_audio_file and voice_audio_file.exists() and sfx_file and sfx_file.exists():
            # 3-way mix WITH sidechain ducking (SFX/BGM dips when voice plays)
            if mh_has_audio:
                filt = "[0:a]volume=0.22[bg];[1:a]volume=1.2,asplit=2[vo][vo_dup];[2:a]volume=0.7,apad[sfx];[sfx][vo_dup]sidechaincompress=threshold=0.03:ratio=9:attack=5:release=300[sfx_duck];[bg][vo][sfx_duck]amix=inputs=3:duration=first:dropout_transition=2[a]"
            else:
                filt = "[1:a]volume=1.2,asplit=2[vo][vo_dup];[2:a]volume=0.7,apad[sfx];[sfx][vo_dup]sidechaincompress=threshold=0.03:ratio=9:attack=5:release=300[sfx_duck];[vo][sfx_duck]amix=inputs=2:duration=first:dropout_transition=2[a]"
            cmd = [
                "/usr/bin/ffmpeg", "-y",
                "-i", str(mh_local), "-i", str(voice_audio_file), "-stream_loop", "-1", "-i", str(sfx_file),
                "-filter_complex", filt,
                "-map", "0:v:0", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", str(mixed),
            ]
        elif voice_audio_file and voice_audio_file.exists():
            if mh_has_audio:
                filt = "[0:a]volume=0.35[bg];[1:a]volume=1.2[vo];[bg][vo]amix=inputs=2:duration=first:dropout_transition=2[a]"
                cmd = [
                    "/usr/bin/ffmpeg", "-y",
                    "-i", str(mh_local), "-i", str(voice_audio_file),
                    "-filter_complex", filt,
                    "-map", "0:v:0", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", str(mixed),
                ]
            else:
                # MH has no audio — just attach voice directly
                cmd = [
                    "/usr/bin/ffmpeg", "-y",
                    "-i", str(mh_local), "-i", str(voice_audio_file),
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", str(mixed),
                ]
        else:
            # SFX only (no voice)
            if mh_has_audio:
                filt = "[0:a]volume=0.5[bg];[1:a]volume=0.65,apad[sfx];[bg][sfx]amix=inputs=2:duration=first:dropout_transition=2[a]"
                cmd = [
                    "/usr/bin/ffmpeg", "-y",
                    "-i", str(mh_local), "-stream_loop", "-1", "-i", str(sfx_file),
                    "-filter_complex", filt,
                    "-map", "0:v:0", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", str(mixed),
                ]
            else:
                cmd = [
                    "/usr/bin/ffmpeg", "-y",
                    "-i", str(mh_local), "-stream_loop", "-1", "-i", str(sfx_file),
                    "-filter_complex", "[1:a]volume=0.7,apad[a]",
                    "-map", "0:v:0", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", str(mixed),
                ]
        res = subprocess.run(cmd, capture_output=True, timeout=180)
        if res.returncode == 0 and mixed.exists() and mixed.stat().st_size > 1000:
            final = mixed
            logger.info(f"MS shot {shot_idx}: mix OK (mh_audio={mh_has_audio}, voice={bool(voice_audio_file)}, sfx={bool(sfx_file)})")
        else:
            logger.warning(f"MS shot {shot_idx} mix failed (mh_audio={mh_has_audio}): {res.stderr[-300:] if res.stderr else ''}")
    return final


async def process_multishot_bg(project_id: str, shots: List[dict], aspect_ratio: str):
    """Generate N sequential shots + stitch via ffmpeg concat into one final mp4."""
    try:
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "processing", "progress": 3, "updated_at": datetime.now(timezone.utc).isoformat()}})
        mh = MagicHourClient(token=MAGIC_HOUR_API_KEY)
        total = len(shots)
        if total == 0:
            raise Exception("No shots provided")

        # Target resolution/fps based on aspect
        target_wh = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (1080, 1080)}.get(aspect_ratio, (720, 1280))
        W, H = target_wh
        TARGET_FPS = 30

        shot_clips: List[Path] = []
        for idx, raw in enumerate(shots):
            s = MultiShotShot(**raw)
            logger.info(f"MS project={project_id} shot {idx+1}/{total} prompt='{s.prompt[:50]}' dur={s.duration}s")
            clip = await _generate_single_shot_clip(mh, s, aspect_ratio, idx)
            if not clip:
                raise Exception(f"Shot {idx+1} failed to generate")
            # Normalize to target WxH + fps + codec for clean concat
            norm = UPLOAD_DIR / f"ms_{idx}_norm_{uuid.uuid4().hex}.mp4"
            norm_cmd = [
                "/usr/bin/ffmpeg", "-y", "-i", str(clip),
                "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1",
                "-r", str(TARGET_FPS),
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
                str(norm),
            ]
            res = subprocess.run(norm_cmd, capture_output=True, timeout=300)
            if res.returncode != 0 or not norm.exists() or norm.stat().st_size < 1000:
                logger.warning(f"MS normalize shot {idx} failed: {res.stderr[-300:] if res.stderr else ''}; falling back to raw clip")
                shot_clips.append(clip)
            else:
                shot_clips.append(norm)
            # Progress: shot i done → (i+1)/total * 85%
            prog = int(((idx + 1) / total) * 85)
            await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": prog, "updated_at": datetime.now(timezone.utc).isoformat()}})

        # Stitching: use per-shot transition_out. Options: "cut" (default) | "fade" | "crossfade"
        # Fast path: all cuts → ffmpeg concat demuxer.
        # Otherwise: build xfade filter_complex chain for proper crossfades.
        transitions = [ (s.get("transition_out") or "cut").lower() for s in shots ]
        # The last shot's transition doesn't matter (nothing after it)
        transitions_between = transitions[:-1] if len(transitions) > 1 else []
        XFADE_DUR = 0.5  # seconds — 500ms
        all_cuts = all(t == "cut" for t in transitions_between)

        final_fn = f"multishot_{uuid.uuid4().hex}.mp4"
        final_path = UPLOAD_DIR / final_fn

        if all_cuts or len(shot_clips) == 1:
            # Fast path — concat demuxer
            list_path = UPLOAD_DIR / f"ms_concat_{uuid.uuid4().hex}.txt"
            with open(list_path, "w") as f:
                for p in shot_clips:
                    f.write(f"file '{p}'\n")
            concat_cmd = [
                "/usr/bin/ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path),
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k",
                str(final_path),
            ]
            res = subprocess.run(concat_cmd, capture_output=True, timeout=600)
            if res.returncode != 0 or not final_path.exists() or final_path.stat().st_size < 1000:
                concat_cmd2 = [
                    "/usr/bin/ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path),
                    "-c", "copy", str(final_path),
                ]
                res2 = subprocess.run(concat_cmd2, capture_output=True, timeout=300)
                if res2.returncode != 0 or not final_path.exists() or final_path.stat().st_size < 1000:
                    raise Exception(f"Concat failed: {res.stderr[-400:] if res.stderr else ''}")
            try:
                if list_path.exists(): list_path.unlink()
            except Exception: pass
            logger.info(f"MS concat(cut) OK → {final_path.name} ({final_path.stat().st_size}b)")
        else:
            # Build xfade / fade chain via filter_complex
            durations = [ get_video_duration(str(p)) or 5.0 for p in shot_clips ]
            # Build input flags
            inputs = []
            for p in shot_clips:
                inputs.extend(["-i", str(p)])

            # Video filter chain
            # For each clip i (1..n-1), apply xfade with clip i-1 at offset = cumulative(i-1) - XFADE_DUR
            filter_v_parts = []
            filter_a_parts = []
            last_v = "[0:v]"
            last_a = "[0:a]"
            cumulative = durations[0]
            for i in range(1, len(shot_clips)):
                trans = transitions_between[i - 1] if i - 1 < len(transitions_between) else "cut"
                # Map our names to ffmpeg xfade transition values:
                # "fade"/"crossfade" → ffmpeg "fade" (crossfade-like cross dissolve)
                # "cut" inside this branch still behaves like crossfade short (should not happen since fast path handles it)
                xfade_type = "fade"  # both "fade" and "crossfade" become ffmpeg cross-dissolve "fade"
                offset = max(0.0, cumulative - XFADE_DUR)
                vlabel = f"v{i}"
                alabel = f"a{i}"
                # Video xfade
                filter_v_parts.append(
                    f"{last_v}[{i}:v]xfade=transition={xfade_type}:duration={XFADE_DUR}:offset={offset:.3f}[{vlabel}]"
                )
                # Audio crossfade (acrossfade requires both streams to contain audio; safe assumption since we added aac above)
                filter_a_parts.append(
                    f"{last_a}[{i}:a]acrossfade=d={XFADE_DUR}:c1=tri:c2=tri[{alabel}]"
                )
                last_v = f"[{vlabel}]"
                last_a = f"[{alabel}]"
                # New cumulative dur = cumulative + clip_i_dur - XFADE_DUR
                cumulative += durations[i] - XFADE_DUR

            filter_complex = ";".join(filter_v_parts + filter_a_parts)
            xfade_cmd = [
                "/usr/bin/ffmpeg", "-y",
                *inputs,
                "-filter_complex", filter_complex,
                "-map", last_v, "-map", last_a,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k",
                str(final_path),
            ]
            logger.info(f"MS xfade stitching {len(shot_clips)} clips, transitions={transitions_between}, total_est={cumulative:.1f}s")
            res = subprocess.run(xfade_cmd, capture_output=True, timeout=600)
            if res.returncode != 0 or not final_path.exists() or final_path.stat().st_size < 1000:
                # Fallback to hard-cut concat if xfade fails
                logger.warning(f"MS xfade failed: {res.stderr[-400:] if res.stderr else ''} — falling back to hard cuts")
                list_path = UPLOAD_DIR / f"ms_concat_{uuid.uuid4().hex}.txt"
                with open(list_path, "w") as f:
                    for p in shot_clips: f.write(f"file '{p}'\n")
                concat_cmd = [
                    "/usr/bin/ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                    "-c:a", "aac", "-b:a", "192k",
                    str(final_path),
                ]
                res_fb = subprocess.run(concat_cmd, capture_output=True, timeout=600)
                try:
                    if list_path.exists(): list_path.unlink()
                except Exception: pass
                if res_fb.returncode != 0 or not final_path.exists() or final_path.stat().st_size < 1000:
                    raise Exception(f"Xfade + concat fallback both failed: {res.stderr[-300:] if res.stderr else ''}")
            logger.info(f"MS xfade stitch OK → {final_path.name} ({final_path.stat().st_size}b)")

        result_url = f"/api/serve-file/{final_fn}"
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "completed", "result_url": result_url, "progress": 100, "updated_at": datetime.now(timezone.utc).isoformat()}})
        logger.info(f"MS project={project_id} complete → {result_url} ({final_path.stat().st_size} bytes)")

        # Cleanup intermediate files
        try:
            for p in shot_clips:
                try:
                    if p.exists() and p != final_path: p.unlink()
                except Exception: pass
        except Exception: pass
    except Exception as e:
        logger.error(f"MultiShot failed: {e}")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "failed", "error_message": str(e)[:500], "updated_at": datetime.now(timezone.utc).isoformat()}})


@api_router.post("/create-multishot")
async def create_multishot(req: CreateMultiShotRequest, background_tasks: BackgroundTasks, request: Request = None):
    if not req.shots or len(req.shots) == 0:
        raise HTTPException(status_code=400, detail="Provide at least 1 shot")
    if len(req.shots) > 6:
        raise HTTPException(status_code=400, detail="Maximum 6 shots per timeline")
    for i, s in enumerate(req.shots):
        if not s.prompt or not s.prompt.strip():
            raise HTTPException(status_code=400, detail=f"Shot {i+1}: prompt required")
    # Multi-shot: feature=multishot enforces tier (Free tier blocked past 2 shots).
    # Cost grows with shot count.
    total_duration = sum(int(s.duration or 5) for s in req.shots)
    max_shot_duration = max((int(s.duration or 5) for s in req.shots), default=5)
    user, cost = await preflight_and_reserve(
        request,
        job_type='multishot',
        feature='multishot',
        duration=total_duration,
        shots=len(req.shots),
    )
    # Session 27e — also enforce ai_video per-shot duration (Creator=3s, Pro=5s)
    from core.pricing import check_feature_access
    ok_av, msg_av = check_feature_access(user, feature='ai_video', duration=max_shot_duration)
    if not ok_av:
        raise HTTPException(status_code=402, detail=msg_av)
    name = req.name or f"MultiShot_{datetime.now(timezone.utc).strftime('%H%M%S')}"
    p = VideoProject(name=name, type="multishot", user_id=user["user_id"], aspect_ratio=req.aspect_ratio or "9:16", input_payload=req.dict(), endpoint="/api/create-multishot")
    await db.video_projects.insert_one(p.dict())
    await _link_as_version(p.id, req.parent_id)
    # Convert pydantic models to dicts (background task serializes cleanly)
    shots_raw = [s.dict() for s in req.shots]
    # Sprint 2 — apply timeline-wide voice_style/rate/pitch as default for any shot without its own
    if req.voice_style:
        for sr in shots_raw:
            if not sr.get("voice_style"):
                sr["voice_style"] = req.voice_style
    if req.voice_rate:
        for sr in shots_raw:
            if not sr.get("voice_rate"):
                sr["voice_rate"] = req.voice_rate
    if req.voice_pitch:
        for sr in shots_raw:
            if not sr.get("voice_pitch"):
                sr["voice_pitch"] = req.voice_pitch
    background_tasks.add_task(process_multishot_bg, p.id, shots_raw, req.aspect_ratio or "9:16")
    await settle_credits(user.get('id'), cost, user_tier=user.get('subscription_tier'), project_id=p.id, asset_kind='video', background_tasks=background_tasks)
    return {"project_id": p.id, "status": "processing", "shot_count": len(req.shots), "credits_charged": cost}


# ================= SCENE SUGGESTIONS (Gemini) =================

@api_router.post("/suggest-scenes")
async def suggest_scenes(req: SuggestScenesRequest):
    """Generate scene/background prompt suggestions for AI video gen.
    Uses Gemini 2.5 Flash via emergentintegrations. Optionally analyses a ref video frame.
    Returns { suggestions: [{title, prompt}, ...] }"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"scene_{uuid.uuid4().hex[:8]}",
            system_message="You are a creative AI director for short-form Indian video content.",
        ).with_model("gemini", "gemini-2.5-flash")
        count = max(2, min(int(req.count or 4), 8))
        hint = (req.user_hint or "").strip()
        hint_line = f"The creator gave this hint/topic: '{hint}'." if hint else ""
        ref_line = ""
        if req.ref_video_path and os.path.exists(req.ref_video_path):
            # Extract first frame as reference
            try:
                fp = UPLOAD_DIR / f"scene_ref_{uuid.uuid4().hex[:8]}.jpg"
                subprocess.run(["/usr/bin/ffmpeg", "-y", "-i", req.ref_video_path, "-vframes", "1", "-q:v", "3", str(fp)], capture_output=True, timeout=30)
                if fp.exists() and fp.stat().st_size > 100:
                    ref_line = f"Reference: base new scenes loosely on the style/tone of the uploaded video. Key visual style: cinematic, bright, emotive."
            except Exception: pass
        prompt = f"""Generate {count} distinct creative scene prompts for an AI text-to-video generator targeting Indian mobile reels creators.
{hint_line}
{ref_line}
Output JSON array ONLY, no markdown. Each item MUST have:
- title: short 2-4 word scene title (e.g. "Krishna in Vrindavan")
- prompt: 20-40 word detailed prompt including style, mood, camera, lighting, subject, action. Should be directly usable by MagicHour text-to-video.
Example format:
[{{"title": "Divine Dance", "prompt": "Lord Krishna dancing in Vrindavan garden, peacock feather, golden glow, cinematic slow-mo, divine atmosphere, soft warm lighting, close-up angle"}}, ...]
Topics can span: mythology, devotional, festival, cinematic, nature, dance, heroic. Make them diverse."""
        response = await chat.send_message(UserMessage(text=prompt))
        import json as _json, re as _re
        txt = response.strip()
        # Strip markdown fences
        txt = _re.sub(r"^```(?:json)?\s*|\s*```$", "", txt, flags=_re.IGNORECASE | _re.MULTILINE)
        try:
            data = _json.loads(txt)
        except Exception:
            # Try to locate JSON array substring
            m = _re.search(r"\[\s*\{.*\}\s*\]", txt, _re.DOTALL)
            data = _json.loads(m.group(0)) if m else []
        # Normalise
        out = []
        for it in data[:count]:
            if isinstance(it, dict) and it.get("prompt"):
                out.append({"title": str(it.get("title", "Scene"))[:60], "prompt": str(it["prompt"])[:600]})
        if not out:
            out = [
                {"title": "Divine Dance", "prompt": "Lord Krishna playing flute in Vrindavan garden, peacock feather crown, golden divine glow, cinematic slow motion, soft warm lighting"},
                {"title": "Mountain Meditation", "prompt": "Lord Shiva meditating on snowy Mount Kailash, third eye glowing, sacred aura, cinematic wide shot, cold blue and gold tones"},
                {"title": "Festival of Lights", "prompt": "Diwali celebration in Indian village, diyas lighting up night sky, fireworks, joyful family gathering, warm orange glow, festive mood"},
                {"title": "Royal Procession", "prompt": "Grand royal procession in ancient Indian palace, elephants, royal musicians, ornate decorations, golden hour lighting, cinematic grandeur"},
            ][:count]
        return {"suggestions": out}
    except Exception as e:
        logger.error(f"suggest-scenes failed: {e}")
        # Return fallback presets on error
        return {"suggestions": [
            {"title": "Divine Dance", "prompt": "Lord Krishna playing flute in Vrindavan garden, peacock feather, golden divine glow, cinematic slow motion, warm lighting"},
            {"title": "Mountain Meditation", "prompt": "Lord Shiva meditating on Mount Kailash, third eye glowing, serene aura, cinematic wide shot"},
            {"title": "Festival of Lights", "prompt": "Diwali celebration, diyas lighting the night, fireworks, joyful family, warm orange glow"},
            {"title": "Royal Procession", "prompt": "Grand royal procession, elephants and musicians, ornate palace, golden hour, cinematic grandeur"},
        ][: int(req.count or 4)], "error": str(e)[:120]}


# ================= AI BACKGROUND LIP SYNC =================

async def process_ai_bg_lipsync(project_id: str, character_image_path: str, scene_prompt: str, dialogue_text: str, voice_id: str, audio_path: Optional[str], duration: int, aspect_ratio: str):
    """Generates a brand-new AI scene with the character, then lip-syncs dialogue audio onto it.
    Pipeline: (1) image_to_video(character_image + scene_prompt) → animated scene (2) TTS dialogue → audio
    (3) lip_sync(animated_scene, audio) → final output."""
    try:
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "processing", "progress": 5}})
        mh = MagicHourClient(token=MAGIC_HOUR_API_KEY)

        # Step 1: TTS audio (if not provided)
        audio_file = Path(audio_path) if audio_path and os.path.exists(audio_path) else None
        if not audio_file:
            tts_fn = UPLOAD_DIR / f"bg_tts_{uuid.uuid4().hex}.mp3"
            await generate_tts_audio(dialogue_text, voice_id or "hi-IN-SwaraNeural", tts_fn, min_duration=2.0)
            audio_file = tts_fn
        # Measure audio duration
        probe = subprocess.run(["/usr/bin/ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(audio_file)], capture_output=True, text=True)
        audio_duration = float(probe.stdout.strip() or duration or 5)
        end_s = max(5.0, audio_duration + 0.5, float(duration or 5))
        await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 15}})

        # Step 2: Generate animated character scene via image_to_video
        combined_prompt = f"{scene_prompt}. The character is speaking naturally, expressive lip movements, facing camera."
        norm_char = normalize_image_for_mh(character_image_path)
        mh_image = upload_to_magic_hour(mh, norm_char, "image")
        logger.info(f"BG-LS: img2vid prompt='{combined_prompt[:80]}' end_s={end_s}")
        r1 = mh.v1.image_to_video.create(
            name=f"BGLS_i2v_{project_id}",
            assets={"image_file_path": mh_image},
            end_seconds=end_s,
            style={"prompt": combined_prompt, "high_quality": True, "quality_mode": "quick"},
        )
        async def _prog_stage1(p):
            scaled = 15 + int((p / 100) * 50)  # 15..65
            await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": min(scaled, 65)}})
        stage1_url = await mh_poll_video(mh, r1.id, max_wait=900, on_progress=_prog_stage1)
        if not stage1_url: raise Exception("Stage 1 (image_to_video) timed out")

        # Download stage 1 video locally
        stage1_local = UPLOAD_DIR / f"bg_stage1_{uuid.uuid4().hex}.mp4"
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), follow_redirects=True) as c:
            resp = await c.get(stage1_url)
            with open(stage1_local, "wb") as f: f.write(resp.content)
        logger.info(f"BG-LS: stage1 local={stage1_local.stat().st_size}b")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": 70}})

        # Step 3: Lip sync on the generated video
        mh_video2 = upload_to_magic_hour(mh, str(stage1_local), "video")
        mh_audio = upload_to_magic_hour(mh, str(audio_file), "audio")
        r2 = await mh_create_lipsync_with_retry(mh, f"BGLS_ls_{project_id}", {"video_source": "file", "video_file_path": mh_video2, "audio_file_path": mh_audio}, 0.0, min(end_s, audio_duration))
        async def _prog_stage2(p):
            scaled = 70 + int((p / 100) * 25)  # 70..95
            await db.video_projects.update_one({"id": project_id}, {"$set": {"progress": min(scaled, 95)}})
        async def _on_done(s): await _capture_credits(project_id, s)
        final_url = await mh_poll_video(mh, r2.id, max_wait=900, on_progress=_prog_stage2, on_complete=_on_done)
        if not final_url: raise Exception("Stage 2 (lip sync) timed out")

        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "completed", "progress": 100, "result_url": final_url, "updated_at": datetime.now(timezone.utc).isoformat()}})
    except Exception as e:
        logger.error(f"BG-LS failed: {e}")
        await db.video_projects.update_one({"id": project_id}, {"$set": {"status": "failed", "error_message": str(e)[:500]}})


@api_router.post("/create-ai-bg-lipsync")
async def create_ai_bg_lipsync(req: AIBgLipSyncRequest, background_tasks: BackgroundTasks, request: Request = None):
    if not os.path.exists(req.character_image_path):
        raise HTTPException(status_code=400, detail=f"Character image not found: {req.character_image_path}")
    if not req.scene_prompt.strip():
        raise HTTPException(status_code=400, detail="Scene prompt required")
    if not req.dialogue_text.strip() and not req.audio_path:
        raise HTTPException(status_code=400, detail="Dialogue text or audio required")
    user, cost = await preflight_and_reserve(request, job_type='lipsync', feature='lip_sync', duration=int(req.duration or 5))
    # Session 27e — AI BG LipSync generates an AI video scene, so also gate on ai_video
    from core.pricing import check_feature_access
    ok_av, msg_av = check_feature_access(user, feature='ai_video', duration=int(req.duration or 5))
    if not ok_av:
        raise HTTPException(status_code=402, detail=msg_av)
    p = VideoProject(name=f"BGLS_{datetime.now(timezone.utc).strftime('%H%M%S')}", type="ai_bg_lipsync", user_id=user["user_id"], aspect_ratio=req.aspect_ratio or "9:16")
    pd = p.dict()
    pd["created_at"] = pd["created_at"].isoformat() if isinstance(pd["created_at"], datetime) else pd["created_at"]
    pd["updated_at"] = pd["updated_at"].isoformat() if isinstance(pd["updated_at"], datetime) else pd["updated_at"]
    await db.video_projects.insert_one(pd)
    background_tasks.add_task(process_ai_bg_lipsync, p.id, req.character_image_path, req.scene_prompt, req.dialogue_text, req.voice_id or "hi-IN-SwaraNeural", req.audio_path, req.duration or 5, req.aspect_ratio or "9:16")
    await settle_credits(user.get('id'), cost, user_tier=user.get('subscription_tier'), project_id=p.id, asset_kind='video', background_tasks=background_tasks)
    return {"project_id": p.id, "credits_charged": cost}

app.include_router(api_router)
# Phase-B refactor (Session 22): extracted upload endpoints
from routes.uploads import router as _uploads_router
app.include_router(_uploads_router)
# Phase-B refactor (Session 23): extracted media endpoints (audio/video utilities)
from routes.media import router as _media_router
app.include_router(_media_router)
# Sprint 6 — Content Intelligence: templates router (Batch 2 refactor seed)
from routes.templates import router as _templates_router
app.include_router(_templates_router)
# Sprint 4 — Auth, Subscription, Admin (BETA mode)
from routes.auth import router as _auth_router
from routes.subscription import router as _sub_router
from routes.admin import router as _admin_router
from routes.divine import router as _divine_router
from routes.story import router as _story_router
app.include_router(_auth_router)
app.include_router(_sub_router)
app.include_router(_admin_router)
app.include_router(_divine_router)
app.include_router(_story_router)
# Session 27d — catalog endpoints migrated out of server.py
from routes.catalog import router as _catalog_router
app.include_router(_catalog_router)
# Session 27e — in-app notifications (trial reminders etc.)
from routes.notifications import router as _notif_router
app.include_router(_notif_router)
# Creator Wizard — 0-MH Instant Reel + MH upsell
from routes.wizard import router as _wizard_router
app.include_router(_wizard_router)
# Phase-2 Marketplace — curated quick-reel template marketplace
from routes.marketplace import router as _marketplace_router, db as _mp_db
from core.marketplace_seed import ensure_seeded as _mp_seed
app.include_router(_marketplace_router)
# Phase-3 Payments — Razorpay (orders + verify)
from routes.payments import router as _payments_router
app.include_router(_payments_router)
# Phase-4B Dialogues — viral one-liners catalog
from routes.dialogues import router as _dialogues_router
app.include_router(_dialogues_router)
# Phase-4A Avatar — cartoon avatar generator (Nano Banana)
from routes.avatar import router as _avatar_router
app.include_router(_avatar_router)
# Creative Plan Engine — POST /api/creative-plan (GPT-4o-mini structured plan)
from routes.creative_plan import router as _creative_plan_router
app.include_router(_creative_plan_router)

# V2.0 — ChatGPT-style Prompt Selection (POST /api/generate-prompts)
from routes.prompts import router as _prompts_router
app.include_router(_prompts_router)

# Sprint 4 — BETA MODE metadata endpoint
from core.config import ENV as _ENV, IS_BETA as _IS_BETA, IS_DEV as _IS_DEV, IS_PROD as _IS_PROD
@app.get("/api/mode")
async def get_mode():
    return {"env": _ENV, "is_beta": _IS_BETA, "is_dev": _IS_DEV, "is_prod": _IS_PROD, "version": "v1.0-beta" if _IS_BETA else ("v1.0-dev" if _IS_DEV else "v1.0-prod")}

app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def _startup_scheduler():
    """Phase 3 — start nightly trending recompute loop."""
    try:
        # V1.0 — auto-seed admin/demo/beta users on first boot in any
        # non-DEV env (BETA / PROD). Safe: only runs if users collection
        # is empty. This removes the need to SSH into the deployed pod
        # and manually run scripts/seed_beta_users.py.
        try:
            from core.config import IS_DEV as _IS_DEV_STARTUP
            if not _IS_DEV_STARTUP:
                _user_count = await _mp_db.users.count_documents({}, limit=1)
                if _user_count == 0:
                    logger.info("auto-seed: empty users collection detected — seeding beta accounts")
                    import subprocess as _subp
                    import sys as _sys
                    _env = os.environ.copy()
                    _env['ENV'] = os.environ.get('ENV', 'BETA') or 'BETA'
                    _r = _subp.run(
                        [_sys.executable, '/app/backend/scripts/seed_beta_users.py'],
                        env=_env, capture_output=True, text=True, timeout=60,
                    )
                    logger.info("auto-seed stdout: %s", (_r.stdout or '')[:400])
                    if _r.returncode != 0:
                        logger.warning("auto-seed stderr: %s", (_r.stderr or '')[:400])
                else:
                    logger.info("auto-seed: users already present (count>=1) — skipping")
        except Exception as _e:
            logger.warning("auto-seed skipped: %s", _e)
        # Phase-2 — idempotent marketplace seed
        try:
            res = await _mp_seed(_mp_db)
            logger.info("marketplace startup seed: %s", res)
        except Exception as e:
            logger.warning("marketplace startup seed skipped: %s", e)
        # Phase-2 polish — enrich Pixabay thumbnails in background (fire-and-forget)
        try:
            from core.marketplace_seed import enrich_thumbnails as _mp_enrich
            asyncio.create_task(_mp_enrich(_mp_db, force=False))
        except Exception as e:
            logger.warning("marketplace thumbnail enrich skipped: %s", e)
        # Phase-4B+4C — seed viral dialogues + funny avatar templates (idempotent)
        try:
            from core.dialogues_seed import (
                ensure_dialogues_seeded as _dlg_seed,
                ensure_funny_avatar_templates_seeded as _funny_seed,
            )
            r1 = await _dlg_seed(_mp_db)
            r2 = await _funny_seed(_mp_db)
            logger.info("dialogues seed: %s | funny templates: %s", r1, r2)
            # Enrich thumbnails for any newly inserted funny templates
            if r2.get("inserted"):
                from core.marketplace_seed import enrich_thumbnails as _mp_enrich2
                asyncio.create_task(_mp_enrich2(_mp_db, force=False))
        except Exception as e:
            logger.warning("dialogues/funny templates seed skipped: %s", e)
        from core.scheduler import start_scheduler
        # Use the templates router's db which respects ENV-based routing.
        from routes.templates import db as _tmpl_db
        start_scheduler(_tmpl_db)
    except Exception as e:
        logger.error(f"startup scheduler wire failed: {e}")


@app.on_event("shutdown")
async def shutdown_db_client():
    try:
        from core.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass
    client.close()
