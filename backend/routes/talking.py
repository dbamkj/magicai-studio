"""Talking-Avatar endpoint — Phase-B server.py refactor (Session 24 slice).

Extracts the one-click "Talking Avatar" pipeline (image + script → MH
lip-sync + optional ffmpeg motion preset) from server.py into its own
self-contained route module.

Why lazy imports?
  Most heavy helpers (`generate_tts_audio`, `mh_create_lipsync_with_retry`,
  `mh_poll_video`, `apply_motion_to_video_clip`, `apply_resolution_to_project`,
  `_resolve_upload_path`, `_link_as_version`, `MagicHourClient`,
  `MAGIC_HOUR_API_KEY`, `UPLOAD_DIR`, `upload_to_magic_hour`) live in
  `server.py` at module scope. To avoid circular imports we import them
  *inside* the request handler — by the time a request arrives, server.py
  has fully loaded.

Extracted endpoints:
  • POST /api/create-talking-avatar — image + script → talking video

server.py shrinks ~95 LOC after this slice.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from core.billing import preflight_and_reserve, settle_credits
from core.db import db
from core.models import CreateTalkingAvatarRequest, VideoProject

log = logging.getLogger("routes.talking")
router = APIRouter(prefix="/api", tags=["talking-avatar"])


@router.post("/create-talking-avatar")
async def create_talking_avatar(
    req: CreateTalkingAvatarRequest,
    background_tasks: BackgroundTasks,
    request: Request = None,
):
    """One-click Talking Avatar: image + script → MH lip-sync + optional
    ffmpeg camera motion. Composes Sprint 2 (voice_style, pauses, rate/pitch)
    + Sprint 3 Phase A (motion) + MH lip-sync."""
    # Lazy-import helpers from server.py — avoids circular imports while
    # still reusing the proven implementations.
    from server import (
        MAGIC_HOUR_API_KEY,
        MagicHourClient,
        UPLOAD_DIR,
        _link_as_version,
        _resolve_upload_path,
        apply_motion_to_video_clip,
        apply_resolution_to_project,
        generate_tts_audio,
        mh_create_lipsync_with_retry,
        mh_poll_video,
        upload_to_magic_hour,
    )

    img_abs = _resolve_upload_path(req.image_path)
    if not img_abs.exists():
        raise HTTPException(status_code=400, detail=f"Image not found: {req.image_path}")
    if not (req.script or "").strip():
        raise HTTPException(status_code=400, detail="Script is required")

    # Phase-B: validate image dimensions early — a 1×1 placeholder PNG (which
    # can sneak through if upload was interrupted) crashes ffmpeg's scale
    # filter with "divisible by 2 (1x1)" and silently fails the whole job.
    # We bail out with a clear 400 instead of charging credits + burning MH.
    try:
        probe = subprocess.run(
            [
                "/usr/bin/ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "default=nw=1:nk=1",
                str(img_abs),
            ],
            capture_output=True, timeout=10,
        )
        dims = (probe.stdout.decode() or "").strip().split("\n")
        if len(dims) >= 2:
            w, h = int(dims[0] or "0"), int(dims[1] or "0")
            if w < 64 or h < 64:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Source image is too small ({w}x{h}). "
                        "Please upload a clearer photo (min 64x64)."
                    ),
                )
    except HTTPException:
        raise
    except Exception as _probe_err:
        # ffprobe failure shouldn't block the entire flow — just log it.
        log.warning("talking: ffprobe failed on %s: %s", img_abs, _probe_err)

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
            await db.video_projects.update_one(
                {"id": p.id}, {"$set": {"status": "processing", "progress": 10}}
            )
            mh = MagicHourClient(token=MAGIC_HOUR_API_KEY)

            # 1) Generate TTS audio (with style/pauses/rate/pitch)
            tts_path = UPLOAD_DIR / f"avatar_tts_{uuid.uuid4().hex}.mp3"
            await generate_tts_audio(
                req.script.strip(),
                req.voice_id or "hi-IN-SwaraNeural",
                tts_path,
                min_duration=2.5,
                voice_style=req.voice_style,
                voice_rate=req.voice_rate,
                voice_pitch=req.voice_pitch,
            )
            if not tts_path.exists() or tts_path.stat().st_size < 500:
                raise Exception("TTS synthesis failed")
            await db.video_projects.update_one({"id": p.id}, {"$set": {"progress": 30}})

            # 2) Probe TTS duration, pad if needed (MH requires >= 2.5s)
            dur_r = subprocess.run(
                [
                    "/usr/bin/ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(tts_path),
                ],
                capture_output=True, timeout=15,
            )
            audio_dur = float((dur_r.stdout.decode() or "3.0").strip() or "3.0")
            if audio_dur < 2.5:
                padded = UPLOAD_DIR / f"avatar_tts_pad_{uuid.uuid4().hex}.mp3"
                subprocess.run(
                    [
                        "/usr/bin/ffmpeg", "-y", "-i", str(tts_path),
                        "-af", "apad=pad_dur=2.5", "-t", "3.0", str(padded),
                    ],
                    capture_output=True, timeout=20,
                )
                if padded.exists():
                    tts_path = padded
                    audio_dur = 3.0

            # 3) Create still video from the image (duration matches audio+1)
            # Scale filter: ensure min 256px on shortest side and even dims —
            # `trunc(iw/2)*2:trunc(ih/2)*2` alone explodes on 1×1 placeholders.
            still_v = UPLOAD_DIR / f"avatar_still_{uuid.uuid4().hex}.mp4"
            r1 = subprocess.run(
                [
                    "/usr/bin/ffmpeg", "-y", "-loop", "1", "-i", str(img_abs),
                    "-c:v", "libx264", "-t", str(audio_dur + 1),
                    "-pix_fmt", "yuv420p", "-r", "25",
                    "-vf",
                    "scale='if(gt(iw,ih),max(iw,256),-2)':'if(gt(iw,ih),-2,max(ih,256))',"
                    "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                    str(still_v),
                ],
                capture_output=True, timeout=60,
            )
            if r1.returncode != 0 or not still_v.exists():
                raise Exception(
                    f"Still video creation failed: {r1.stderr[-200:].decode('utf-8', errors='ignore')}"
                )

            # 4) Upload to MH + lip-sync
            await db.video_projects.update_one({"id": p.id}, {"$set": {"progress": 45}})
            mh_video = upload_to_magic_hour(mh, str(still_v), "video")
            mh_audio = upload_to_magic_hour(mh, str(tts_path), "audio")
            ls = await mh_create_lipsync_with_retry(
                mh,
                f"TalkingAvatar_{p.id[:8]}",
                {"video_source": "file", "video_file_path": mh_video, "audio_file_path": mh_audio},
                0.0,
                audio_dur,
            )
            ls_url = await mh_poll_video(
                mh,
                ls.id,
                max_wait=600,
                on_progress=lambda pr: db.video_projects.update_one(
                    {"id": p.id}, {"$set": {"progress": 45 + int(pr / 100 * 40)}}
                ),
            )
            if not ls_url:
                raise Exception("Lip-sync timed out")

            # 5) Download MH lip-sync result
            await db.video_projects.update_one({"id": p.id}, {"$set": {"progress": 88}})
            ls_local = UPLOAD_DIR / f"avatar_ls_{uuid.uuid4().hex}.mp4"
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(120.0), follow_redirects=True,
            ) as c:
                resp = await c.get(ls_url)
                with open(ls_local, "wb") as f:
                    f.write(resp.content)

            # 6) Optionally apply motion (zoompan) on top of the talking video
            final = ls_local
            if req.motion and req.motion != "none":
                motioned = apply_motion_to_video_clip(ls_local, req.motion)
                if motioned and motioned.exists():
                    final = motioned

            # 7) Apply resolution downscale (reusing existing helper)
            result_url = f"/api/serve-file/{final.name}"
            await db.video_projects.update_one(
                {"id": p.id},
                {"$set": {
                    "status": "completed",
                    "progress": 100,
                    "result_url": result_url,
                    "completed_at": datetime.now(timezone.utc),
                }},
            )

            # Async resolution downscale (don't block)
            try:
                asyncio.create_task(
                    apply_resolution_to_project(p.id, req.resolution or "720p", "video")
                )
            except Exception:
                pass

            # Cleanup intermediate files
            for f_tmp in [tts_path, still_v]:
                try:
                    if f_tmp.exists() and f_tmp != final:
                        f_tmp.unlink()
                except Exception:
                    pass
        except Exception as e:
            log.error(f"TalkingAvatar failed: {e}")
            await db.video_projects.update_one(
                {"id": p.id},
                {"$set": {"status": "failed", "error": str(e)[:300]}},
            )

    background_tasks.add_task(_bg)
    await settle_credits(
        user.get('id'),
        cost,
        user_tier=user.get('subscription_tier'),
        project_id=p.id,
        asset_kind='video',
        background_tasks=background_tasks,
    )
    return {"project_id": p.id, "status": "processing", "credits_charged": cost}
