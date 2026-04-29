"""Phase 1 — Divine Transformation route.

Wraps Magic Hour face-swap (image) + FFmpeg cinematic transition + SFX mix
into a single 'Divine Transform' pipeline that turns a user's portrait into
a cinematic divine reel.

Flow:
  1. MH face_swap: take human portrait + divine reference image,
     swap user's face onto divine form. Output: swapped_image.png
  2. ffmpeg zoompan: animate swapped_image with Ken-Burns motion
     over `duration` seconds. Output: motion.mp4
  3. ffmpeg concat: prepend coloured intro clip (transition) to motion.mp4.
     Output: with_intro.mp4
  4. ffmpeg amix: overlay divine SFX (om_chant / temple_bell / ...).
     Output: final.mp4
  5. Update project.result_url and mark completed.

Total cost: DIVINE_TRANSFORM_COST = 120 credits (settled on success).
"""
import os
import uuid
import asyncio
import logging
import subprocess
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient

from core.config import MONGO_URL, DB_NAME
from core.billing import preflight_and_reserve, settle_credits
from core.divine_transitions import (
    DIVINE_TRANSITIONS,
    DIVINE_SFX,
    DEITY_PRESETS,
    transition_by_id,
    deity_by_id,
    DIVINE_TRANSFORM_COST,
)
from core.constants import sfx_by_id as _main_sfx_by_id

logger = logging.getLogger("divine")
logger.setLevel(logging.INFO)

_client = AsyncIOMotorClient(MONGO_URL)
db = _client[DB_NAME]

router = APIRouter(prefix="/api", tags=["divine"])

UPLOAD_DIR = Path("/app/backend/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

FFMPEG = "/usr/bin/ffmpeg"


# ========== Request model ==========
class DivineTransformRequest(BaseModel):
    human_image_path: str = Field(..., description="Absolute path to user's portrait upload")
    divine_image_path: Optional[str] = Field(None, description="Optional custom divine reference (overrides deity)")
    deity_id: Optional[str] = Field(None, description="Deity preset id (krishna/shiva/durga/ganesha/ram/hanuman)")
    transition: str = Field("divine_reveal", description="Transition id")
    sfx: str = Field("om_chant", description="Divine SFX id")
    duration: int = Field(5, ge=3, le=10, description="Output duration in seconds (3-10)")
    festival_pack: Optional[str] = None
    aspect_ratio: str = Field("9:16", description="9:16 | 1:1 | 16:9")


# ========== Read-only metadata endpoints ==========
@router.get("/divine/deities")
async def list_deities():
    return {"deities": DEITY_PRESETS}


@router.get("/divine/transitions")
async def list_transitions():
    # Strip internal color/fade args, return only user-facing metadata
    safe = [
        {"id": t["id"], "label": t["label"], "emoji": t["emoji"], "desc": t["desc"]}
        for t in DIVINE_TRANSITIONS
    ]
    return {"transitions": safe}


@router.get("/divine/sfx")
async def list_divine_sfx():
    # Do not leak raw urls
    safe = [{k: v for k, v in s.items() if k != "url"} for s in DIVINE_SFX]
    return {"sfx": safe}


# ========== Main transform endpoint ==========
@router.post("/divine-transform")
async def divine_transform(
    req: DivineTransformRequest,
    background_tasks: BackgroundTasks,
    request: Request = None,
):
    # Plan: face_swap feature access (Starter+)
    user, _ = await preflight_and_reserve(
        request,
        job_type="faceswap",  # tier gating reuses face_swap flag
        feature="face_swap",
        duration=req.duration,
    )
    cost = DIVINE_TRANSFORM_COST

    # Validate paths
    if not os.path.exists(req.human_image_path):
        raise HTTPException(status_code=400, detail="human_image_path does not exist on server")

    divine_path = req.divine_image_path
    if not divine_path and req.deity_id:
        # Fallback: if no custom divine image and user picked a deity, try
        # to find a previously-cached deity portrait under uploads/deity_{id}.*
        for ext in ("png", "jpg", "jpeg", "webp"):
            candidate = UPLOAD_DIR / f"deity_{req.deity_id}.{ext}"
            if candidate.exists():
                divine_path = str(candidate)
                break
    if not divine_path or not os.path.exists(divine_path):
        raise HTTPException(
            status_code=400,
            detail=(
                "No divine reference image available. Upload one via /api/upload "
                "(divine_image_path) OR first run /api/generate-idea-image with "
                "the deity prompt and reuse its file_path as divine_image_path."
            ),
        )

    t_meta = transition_by_id(req.transition)
    if not t_meta:
        raise HTTPException(status_code=400, detail=f"Unknown transition '{req.transition}'")

    # Create project doc (reuse VideoProject shape via a minimal dict)
    project_id = str(uuid.uuid4())
    proj = {
        "id": project_id,
        "name": f"DivineTransform_{datetime.now(timezone.utc).strftime('%H%M%S')}",
        "type": "divine_transform",
        "user_id": user.get("user_id") or user.get("id"),
        "status": "processing",
        "progress": 0,
        "aspect_ratio": req.aspect_ratio,
        "input_payload": req.dict(),
        "endpoint": "/api/divine-transform",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.video_projects.insert_one(proj)

    # Fire the background pipeline
    background_tasks.add_task(
        process_divine_transform_bg,
        project_id,
        req.human_image_path,
        divine_path,
        t_meta,
        req.sfx,
        req.duration,
        req.aspect_ratio,
    )

    # Settle credits (+ free-tier watermark)
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
        "transition": t_meta["id"],
        "sfx": req.sfx,
    }


# ========== Background pipeline ==========
async def process_divine_transform_bg(
    project_id: str,
    human_image_path: str,
    divine_image_path: str,
    transition: dict,
    sfx_id: Optional[str],
    duration: int,
    aspect_ratio: str,
):
    """Run the 4-step Divine Transformation pipeline."""
    async def _update(progress: int, **extra):
        patch = {
            "progress": progress,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **extra,
        }
        await db.video_projects.update_one({"id": project_id}, {"$set": patch})

    try:
        await _update(5, status="processing")

        # ----- Step 1: MH face-swap (image → image) -----
        try:
            # Lazy import to avoid circular at module load
            from server import process_faceswap_image_bg, MAGIC_HOUR_API_KEY  # type: ignore
            from magic_hour import Client as MagicHourClient
            from server import upload_to_magic_hour  # type: ignore

            mh = MagicHourClient(token=MAGIC_HOUR_API_KEY)
            mh_human = upload_to_magic_hour(mh, human_image_path, "image")
            mh_divine = upload_to_magic_hour(mh, divine_image_path, "image")

            r = mh.v1.face_swap_photo.create(
                assets={
                    "source_file_path": mh_human,
                    "target_file_path": mh_divine,
                },
                name=f"DT_{project_id}",
            )
            import time
            swapped_url = None
            start = time.time()
            while time.time() - start < 300:
                js = mh.v1.image_projects.get(id=r.id)
                if js.status == "complete":
                    swapped_url = js.downloads[0].url if js.downloads else None
                    break
                if js.status in ("error", "canceled"):
                    raise Exception(f"MH face_swap_photo {js.status}")
                p = 5 + int(((time.time() - start) / 300) * 40)
                await _update(min(p, 45))
                await asyncio.sleep(4)
            if not swapped_url:
                raise Exception("Face swap timed out")

            # Download swapped image locally
            import httpx
            swapped_local = UPLOAD_DIR / f"dt_swap_{uuid.uuid4().hex}.png"
            async with httpx.AsyncClient(timeout=60) as c:
                r2 = await c.get(swapped_url)
                swapped_local.write_bytes(r2.content)
        except Exception as e:
            logger.error(f"DT face-swap failed: {e}")
            await _update(100, status="failed", error_message=f"face_swap: {str(e)[:200]}")
            return
        await _update(50)

        # ----- Step 2: ffmpeg zoompan motion -----
        W, H = _resolve_dimensions(aspect_ratio)
        fps = 25
        frames = duration * fps
        motion_mp4 = UPLOAD_DIR / f"dt_motion_{uuid.uuid4().hex}.mp4"
        # Ken-Burns zoom-in expression
        zp = (
            f"zoompan=z='min(zoom+0.0015,1.35)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={W}x{H}:fps={fps}"
        )
        cmd1 = [
            FFMPEG, "-y", "-loop", "1", "-i", str(swapped_local),
            "-vf", zp,
            "-c:v", "libx264", "-t", str(duration),
            "-pix_fmt", "yuv420p", "-r", str(fps),
            str(motion_mp4),
        ]
        logger.info(f"DT motion ffmpeg: {' '.join(cmd1[:8])}...")
        res1 = subprocess.run(cmd1, capture_output=True, timeout=90)
        if res1.returncode != 0 or not motion_mp4.exists():
            logger.error(f"DT motion ffmpeg failed: {res1.stderr.decode()[:400]}")
            await _update(100, status="failed", error_message="motion render failed")
            return
        await _update(65)

        # ----- Step 3: Prepend colored intro clip (transition) -----
        intro_mp4 = UPLOAD_DIR / f"dt_intro_{uuid.uuid4().hex}.mp4"
        final_mp4 = UPLOAD_DIR / f"dt_final_{uuid.uuid4().hex}.mp4"
        intro_dur = float(transition.get("prefix_duration_sec", 0.8))
        color = transition.get("prefix_color", "white")
        cmd2 = [
            FFMPEG, "-y",
            "-f", "lavfi", "-i", f"color=c={color}:s={W}x{H}:r={fps}:d={intro_dur}",
            "-vf", f"fade=t=out:st=0:d={intro_dur}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
            str(intro_mp4),
        ]
        res2 = subprocess.run(cmd2, capture_output=True, timeout=30)
        if res2.returncode != 0:
            # If intro fails, skip it and just use motion
            logger.warning(f"DT intro skipped: {res2.stderr.decode()[:200]}")
            intro_mp4 = None

        # Concat demuxer (silent video) then add audio in step 4
        concat_mp4 = UPLOAD_DIR / f"dt_concat_{uuid.uuid4().hex}.mp4"
        if intro_mp4 and intro_mp4.exists():
            concat_list = UPLOAD_DIR / f"dt_list_{uuid.uuid4().hex}.txt"
            concat_list.write_text(f"file '{intro_mp4}'\nfile '{motion_mp4}'\n")
            cmd3 = [
                FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
                str(concat_mp4),
            ]
            res3 = subprocess.run(cmd3, capture_output=True, timeout=60)
            if res3.returncode != 0 or not concat_mp4.exists():
                logger.warning(f"DT concat fallback: {res3.stderr.decode()[:200]}")
                concat_mp4 = motion_mp4  # fallback
        else:
            concat_mp4 = motion_mp4
        await _update(80)

        # ----- Step 4: Mix SFX -----
        sfx_meta = _sfx_lookup(sfx_id)
        if sfx_meta and sfx_meta.get("url"):
            sfx_local = await _download_sfx(sfx_meta)
            if sfx_local and sfx_local.exists():
                cmd4 = [
                    FFMPEG, "-y",
                    "-i", str(concat_mp4),
                    "-i", str(sfx_local),
                    "-filter_complex",
                    "[1:a]volume=0.55,afade=t=out:st=4:d=1[a]",
                    "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-shortest",
                    str(final_mp4),
                ]
                res4 = subprocess.run(cmd4, capture_output=True, timeout=60)
                if res4.returncode != 0:
                    logger.warning(f"DT sfx mix failed, using silent: {res4.stderr.decode()[:200]}")
                    final_mp4 = concat_mp4
            else:
                final_mp4 = concat_mp4
        else:
            # No SFX requested — just use concatenated video
            final_mp4 = concat_mp4

        # ----- Publish result -----
        result_url = f"/api/serve-file/{final_mp4.name}"
        await _update(100, status="completed", result_url=result_url)
        logger.info(f"DT completed project={project_id} result={result_url}")
    except Exception as e:
        logger.exception(f"DT pipeline crash: {e}")
        await db.video_projects.update_one(
            {"id": project_id},
            {"$set": {
                "status": "failed",
                "error_message": str(e)[:300],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )


# ========== Helpers ==========
def _resolve_dimensions(aspect_ratio: str) -> tuple[int, int]:
    if aspect_ratio == "16:9":
        return 1280, 720
    if aspect_ratio == "1:1":
        return 720, 720
    # default 9:16 vertical
    return 720, 1280


def _sfx_lookup(sfx_id: Optional[str]):
    if not sfx_id or sfx_id == "none":
        return None
    for s in DIVINE_SFX:
        if s["id"] == sfx_id:
            return s
    return _main_sfx_by_id(sfx_id)


async def _download_sfx(sfx_meta: dict):
    """Download SFX to disk (cached by filename) and return local path."""
    import httpx
    url = sfx_meta.get("url")
    if not url:
        return None
    local = UPLOAD_DIR / f"sfx_cache_{sfx_meta['id']}.mp3"
    if local.exists() and local.stat().st_size > 1024:
        return local
    try:
        async with httpx.AsyncClient(
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "Referer": "https://pixabay.com/",
            },
        ) as c:
            r = await c.get(url, follow_redirects=True)
            if r.status_code == 200 and len(r.content) > 1024:
                local.write_bytes(r.content)
                return local
            logger.warning(f"SFX download {sfx_meta['id']} got HTTP {r.status_code} size={len(r.content)}")
    except Exception as e:
        logger.warning(f"SFX download failed {sfx_meta['id']}: {e}")
    return None
