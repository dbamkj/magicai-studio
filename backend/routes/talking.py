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


# ──────────────────────── Cinematic Presets (Phase 1) ────────────────────────

@router.get("/cinematic-presets")
async def list_cinematic_presets(request: Request = None):
    """Return all cinematic presets. The `locked` flag is computed
    against the calling user's `subscription_tier` when authenticated;
    anonymous callers see free presets unlocked + pro presets locked.

    Response shape:
        {
          "presets": [
            {
              "id": "funny", "label": "Funny", "emoji": "😂",
              "tagline": "...", "plan_tier": "free", "locked": false,
              "config": { "emotion": "playful", "motion": "ken_burns",
                          "bgm": "playful", "voice_style": "playful",
                          "effects": [...], ... }
            }, ...
          ]
        }
    """
    from core.cinematic_presets import list_presets

    # Optional auth — we don't 401 here because the picker is shown
    # before login on some flows.
    user_tier: str | None = None
    try:
        from core.auth import get_current_user_optional
        u = await get_current_user_optional(request)
        if u:
            user_tier = u.get("subscription_tier")
    except Exception:
        # Some installs don't expose get_current_user_optional — fall
        # back to anonymous (everything-locked-pro behavior).
        try:
            auth = (request.headers.get("authorization") or "").strip() if request else ""
            if auth.lower().startswith("bearer "):
                # If a token was sent, try to decode via the standard helper.
                from core.auth import get_current_user  # type: ignore
                u = await get_current_user(request)
                if u:
                    user_tier = u.get("subscription_tier")
        except Exception:
            pass

    return {"presets": list_presets(user_tier)}


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

    # Procedural cartoon lipsync runs entirely locally (OpenCV + ffmpeg)
    # with no MagicHour cost, so it shouldn't trigger the lip_sync
    # feature gate (which requires Starter plan +). The cartoon-solo
    # flow on free tier MUST be able to render — that's literally the
    # main funnel. Premium upsell still happens via the Cinematic
    # preset paywall + watermark + 480p cap.
    is_procedural = bool(getattr(req, 'use_procedural_lipsync', False))
    user, cost = await preflight_and_reserve(
        request,
        job_type='lipsync',
        feature=None if is_procedural else 'lip_sync',
    )

    # Phase-1 — Cinematic preset resolution. If client sent preset_id,
    # apply its config bundle (voice_style / motion / bgm_style) BEFORE
    # we persist the project so the recorded payload reflects what
    # actually rendered. Free presets work for everyone; pro presets
    # require a paid tier or we 402.
    if req.preset_id:
        from core.cinematic_presets import apply_preset_to_request
        applied = apply_preset_to_request(
            req.preset_id,
            user.get("subscription_tier"),
            voice_style=req.voice_style,
            motion=req.motion,
            bgm_style=req.bgm_style,
        )
        if applied.get("_error") == "locked":
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "preset_locked",
                    "preset_id": applied.get("_preset_id"),
                    "message": "This cinematic preset requires a paid plan.",
                    "cta": "Unlock Cinematic Mode",
                },
            )
        if applied.get("_error") == "unknown_preset":
            raise HTTPException(status_code=400, detail=f"Unknown preset_id: {req.preset_id}")
        if applied:
            # Mutate the request in-place so the rest of _bg() picks up
            # the merged values without further refactor.
            if applied.get("voice_style"):
                req.voice_style = applied["voice_style"]
            if applied.get("motion"):
                req.motion = applied["motion"]
            if applied.get("bgm_style"):
                req.bgm_style = applied["bgm_style"]
            log.info(
                "talking: preset '%s' applied (voice_style=%s motion=%s bgm=%s)",
                applied.get("_preset_id"), req.voice_style, req.motion, req.bgm_style,
            )

    # Phase-2 — Emotion-aware TTS. Detect the dominant emotion from the
    # script (LLM with keyword fallback) and merge its rate/pitch
    # tweaks into the request UNLESS the user already set explicit
    # voice_rate / voice_pitch values. Also persist the detected
    # emotion on the project so the procedural mouth animator can
    # apply a matching subtle face tint later.
    detected_emotion = "neutral"
    detected_intensity = 0.0
    try:
        from core.emotion_detector import (
            detect_emotion as _detect_emotion,
            emotion_to_voice_params as _emo_voice,
        )
        emo_res = await _detect_emotion(req.script, language=None)
        detected_emotion = emo_res.get("emotion") or "neutral"
        detected_intensity = float(emo_res.get("intensity") or 0.0)
        if detected_emotion != "neutral" and detected_intensity > 0.0:
            vp = _emo_voice(detected_emotion, detected_intensity)
            if req.voice_rate is None or req.voice_rate == 0.0:
                req.voice_rate = vp["voice_rate"]
            if not req.voice_pitch:
                req.voice_pitch = vp["voice_pitch"]
            log.info(
                "talking: emotion=%s intensity=%.2f source=%s -> rate=%s pitch=%s",
                detected_emotion, detected_intensity, emo_res.get("source"),
                req.voice_rate, req.voice_pitch,
            )
    except Exception as _emo_err:
        log.debug("talking: emotion detect skipped: %s", _emo_err)

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

            # 2) Probe TTS duration, pad if needed (MH requires >= 2.5s).
            # Also pad a 0.75s silence tail so the LAST spoken line isn't
            # clipped by MH's lipsync (Session 25 round 6 — users
            # complained the last syllable was cut off).
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
            # Always add a 0.75s silent tail unless TTS needed full 2.5s minimum.
            padded = UPLOAD_DIR / f"avatar_tts_pad_{uuid.uuid4().hex}.mp3"
            if audio_dur < 2.5:
                # Short clip → pad to 3.0s minimum for MH + 0.75s tail = 3.75s cap
                subprocess.run(
                    [
                        "/usr/bin/ffmpeg", "-y", "-i", str(tts_path),
                        "-af", "apad=pad_dur=3.25", "-t", "3.75", str(padded),
                    ],
                    capture_output=True, timeout=20,
                )
                if padded.exists() and padded.stat().st_size > 500:
                    tts_path = padded
                    audio_dur = 3.75
            else:
                # Long clip → just append 0.75s of silence so the last
                # word has room to finish before MH cuts the video.
                subprocess.run(
                    [
                        "/usr/bin/ffmpeg", "-y", "-i", str(tts_path),
                        "-af", "apad=pad_dur=0.75", "-t", str(audio_dur + 0.75),
                        str(padded),
                    ],
                    capture_output=True, timeout=30,
                )
                if padded.exists() and padded.stat().st_size > 500:
                    tts_path = padded
                    audio_dur = audio_dur + 0.75

            # Round 11 — optional BGM mixing. If req.bgm_style is provided,
            # pick a track from the catalog and amix it under the voice
            # at -15dB. Voice clarity stays priority; BGM is atmospheric.
            if req.bgm_style:
                try:
                    from core.bgm_catalog import random_for_mood, BGM_DIR as _BGM_DIR
                    track = random_for_mood(req.bgm_style)
                    if track:
                        bgm_path = _BGM_DIR / track["filename"]
                        if bgm_path.exists():
                            mixed = UPLOAD_DIR / f"avatar_tts_bgm_{uuid.uuid4().hex}.mp3"
                            # ffmpeg amix with the voice channel weighted 1.0
                            # and BGM at 0.18 (~-15dB). `apad` ensures BGM
                            # is at least as long as voice; `-shortest` then
                            # crops to voice length so we don't overshoot.
                            mix_r = subprocess.run([
                                "/usr/bin/ffmpeg", "-y",
                                "-i", str(tts_path),
                                "-i", str(bgm_path),
                                "-filter_complex",
                                "[0:a]volume=1.0[a];"
                                "[1:a]aloop=loop=-1:size=2e9,volume=0.18[b];"
                                "[a][b]amix=inputs=2:duration=first:dropout_transition=0[out]",
                                "-map", "[out]", "-c:a", "libmp3lame", "-b:a", "128k",
                                str(mixed),
                            ], capture_output=True, timeout=45)
                            if mix_r.returncode == 0 and mixed.exists() and mixed.stat().st_size > 500:
                                tts_path = mixed
                                log.info("talking: BGM mixed (%s) under voice", track["id"])
                            else:
                                log.warning("talking: BGM mix failed; continuing without BGM. stderr=%s", mix_r.stderr.decode()[:200])
                        else:
                            log.warning("talking: BGM file missing on disk: %s", bgm_path)
                    else:
                        log.info("talking: bgm_style=%s — no track matched, skipping", req.bgm_style)
                except Exception as _bgm_e:
                    log.warning("talking: BGM mixing exception (continuing without BGM): %s", _bgm_e)

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

            # Session 33 — PROCEDURAL CARTOON LIPSYNC PATH.
            # When use_procedural_lipsync=True (set by Cartoon Solo mode
            # in avatar-studio), skip MagicHour's v1.lip_sync (which
            # injects photoreal features onto cartoons) and run our
            # OpenCV+ffmpeg procedural animator instead. This preserves
            # the cartoon face byte-for-byte except for the animated
            # mouth region.
            use_procedural = bool(getattr(req, "use_procedural_lipsync", False))
            if use_procedural:
                try:
                    from core.mouth_animator import animate_talking_cartoon
                    proc_out = UPLOAD_DIR / f"avatar_proc_{uuid.uuid4().hex}.mp4"
                    ok = await asyncio.to_thread(
                        animate_talking_cartoon,
                        img_abs,
                        tts_path,
                        proc_out,
                        25,                     # fps
                        60.0,                   # max_duration
                        None,                   # preferred_mouth_bbox
                        detected_emotion,       # Phase-2: tint
                        detected_intensity,
                    )
                    if ok and proc_out.exists() and proc_out.stat().st_size > 2048:
                        log.info("talking: procedural lipsync OK → %s", proc_out.name)
                        ls_local = proc_out
                        # Skip MH upload + poll entirely
                        await db.video_projects.update_one(
                            {"id": p.id}, {"$set": {"progress": 85}}
                        )
                    else:
                        log.warning("talking: procedural lipsync failed, falling back to MagicHour")
                        use_procedural = False
                except Exception as _proc_err:
                    log.warning("talking: procedural lipsync exception: %s — falling back to MH",
                                _proc_err)
                    use_procedural = False

            if not use_procedural:
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
