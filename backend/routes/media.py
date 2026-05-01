"""Media endpoints — Phase-B server.py refactor (Session 23 slice).

Consolidates audio/video utility endpoints that used to live inline in
server.py. All operate on uploaded files and return paths, durations,
extracted frames or transcripts.

Extracted endpoints:
  • POST /api/upload-video                 — multipart video upload + duration
  • POST /api/upload-audio                 — multipart audio upload (50MB cap)
  • POST /api/extract-frames               — 4 keyframes + Gemini diarization
  • POST /api/transcribe-audio             — Whisper-1 (Hindi default)
  • POST /api/merge-segments/{project_id}  — ffmpeg concat of result_segments

Internal helpers used (still in server.py):
  • core.auth.get_current_user
  • core.upload_safety.validate_video_upload
  • core.db.db, core.db.MONGO_URL
  • get_video_duration
  • EMERGENT_LLM_KEY env

This is the second slice of the Phase-B refactor. server.py shrinks
~140 LOC after this module is registered.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from core.auth import get_current_user
from core.db import db

load_dotenv()
log = logging.getLogger("routes.media")
router = APIRouter(prefix="/api", tags=["media"])

# Shared with server.py — same upload directories.
ROOT_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
VIDEO_DIR = ROOT_DIR / "videos"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

EMERGENT_LLM_KEY = (os.environ.get("EMERGENT_LLM_KEY") or "").strip()


def _ffprobe_duration(path: str) -> float:
    """Return seconds (float) of a media file, 0.0 on failure."""
    try:
        r = subprocess.run(
            ["/usr/bin/ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=10,
        )
        return float((r.stdout or "0").strip() or 0.0)
    except Exception:
        return 0.0


# ─────────────────────────── Routes ────────────────────────────────────────

@router.post("/upload-video")
async def upload_video(file: UploadFile = File(...), request: Request = None):
    """Multipart video upload (auth required). Returns file_path + duration."""
    from core.upload_safety import validate_video_upload
    await get_current_user(request)
    fid = str(uuid.uuid4())
    ext = Path(file.filename or "vid.mp4").suffix or ".mp4"
    sp = VIDEO_DIR / f"{fid}{ext}"
    content = await file.read()
    validate_video_upload(content, content_type=file.content_type, filename=file.filename)
    with open(sp, "wb") as f:
        f.write(content)
    dur = _ffprobe_duration(str(sp))
    return {
        "file_id": fid, "file_path": str(sp), "file_type": "video",
        "size_mb": round(len(content) / (1024 * 1024), 2),
        "duration": round(dur, 1),
    }


@router.post("/upload-audio")
async def upload_audio(file: UploadFile = File(...)):
    """Multipart audio upload (50MB cap)."""
    fid = uuid.uuid4().hex
    ext = Path(file.filename or "audio.mp3").suffix or ".mp3"
    sp = UPLOAD_DIR / f"audio_{fid}{ext}"
    content = await file.read()
    if len(content) / (1024 * 1024) > 50:
        raise HTTPException(status_code=400, detail="Max 50MB")
    with open(sp, "wb") as f:
        f.write(content)
    return {"file_id": fid, "file_path": str(sp)}


@router.post("/extract-frames")
async def extract_frames(file: UploadFile = File(...)):
    """Extract 4 keyframes + transcribe/diarize the audio of a reference
    video using Gemini 2.5 Flash. Returns frame URLs + transcript +
    diarized segments.
    """
    fid = uuid.uuid4().hex
    ext = Path(file.filename or "video.mp4").suffix or ".mp4"
    sp = UPLOAD_DIR / f"ref_{fid}{ext}"
    content = await file.read()
    with open(sp, "wb") as f:
        f.write(content)
    duration = _ffprobe_duration(str(sp)) or 10.0
    frames = []
    for i in range(4):
        ts = (duration / 5) * (i + 1)
        fn = f"frame_{fid}_{i}.jpg"
        fp = UPLOAD_DIR / fn
        subprocess.run(
            ["/usr/bin/ffmpeg", "-y", "-ss", str(ts), "-i", str(sp),
             "-vframes", "1", "-q:v", "3", str(fp)],
            capture_output=True, timeout=10,
        )
        if fp.exists():
            frames.append({
                "index": i,
                "url": f"/api/serve-file/{fn}",
                "timestamp": round(ts, 1),
            })

    transcript = ""
    diarized: list[dict] = []
    audio_path = UPLOAD_DIR / f"ref_audio_{fid}.mp3"
    subprocess.run(
        ["/usr/bin/ffmpeg", "-y", "-i", str(sp), "-vn",
         "-acodec", "libmp3lame", "-q:a", "4", str(audio_path)],
        capture_output=True, timeout=30,
    )
    if audio_path.exists() and audio_path.stat().st_size > 1000:
        try:
            from emergentintegrations.llm.chat import (
                FileContentWithMimeType, LlmChat, UserMessage,
            )
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"transcribe-{fid}",
                system_message=(
                    "You are an expert audio transcription + speaker diarization assistant. "
                    "Transcribe the given audio and detect DISTINCT speakers (voices). "
                    "IMPORTANT: REUSE speaker numbers when the SAME voice returns - do NOT give a new speaker number for every segment. "
                    "Cluster voices by pitch/timbre/gender; typical content has 1-4 unique speakers. DO NOT exceed 4 unique speakers unless absolutely necessary. "
                    "Output ONLY a valid JSON object (no markdown, no code fences, no prose) with this exact shape:\n"
                    '{"transcript":"full text","segments":[{"speaker":1,"start":0.0,"end":2.3,"text":"..."}]}'
                    "\nNumber speakers starting from 1. If only ONE voice is heard, use speaker:1 for all segments. "
                    "Keep timestamps accurate in seconds. Preserve original language."
                ),
            ).with_model("gemini", "gemini-2.5-flash")
            audio_attach = FileContentWithMimeType(
                file_path=str(audio_path), mime_type="audio/mpeg",
            )
            msg = UserMessage(
                text="Transcribe and diarize this audio as JSON only.",
                file_contents=[audio_attach],
            )
            raw = (await chat.send_message(msg) or "").strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
            import json as _json
            try:
                parsed = _json.loads(raw)
                transcript = (parsed.get("transcript") or "").strip()
                diarized = parsed.get("segments") or []
                log.info(
                    "Transcribed+diarized ref video (%db) -> %d chars, %d segs, speakers=%d",
                    audio_path.stat().st_size, len(transcript), len(diarized),
                    len({s.get("speaker", 1) for s in diarized}),
                )
            except Exception as je:
                transcript = raw
                log.warning(
                    "Diarization JSON parse failed (%s); using plain transcript (%d chars)",
                    je, len(transcript),
                )
        except Exception as e:
            log.warning("Transcription failed: %s", e)
    return {
        "video_path": str(sp),
        "duration": round(duration, 1),
        "frames": frames,
        "frame_count": len(frames),
        "transcript": transcript,
        "diarized_segments": diarized,
    }


@router.post("/transcribe-audio")
async def transcribe_audio(file: UploadFile = File(...)):
    """Whisper-1 transcription via OpenAI/Emergent LLM key. Defaults to Hindi."""
    fid = uuid.uuid4().hex
    ext = Path(file.filename or "audio.mp3").suffix or ".mp3"
    sp = UPLOAD_DIR / f"transcribe_{fid}{ext}"
    content = await file.read()
    with open(sp, "wb") as f:
        f.write(content)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as c:
            with open(sp, "rb") as fh:
                files = {"file": (file.filename or "audio.mp3", fh, "audio/mpeg")}
                data = {
                    "model": "whisper-1", "language": "hi",
                    "response_format": "verbose_json",
                }
                r = await c.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {EMERGENT_LLM_KEY}"},
                    files=files, data=data,
                )
            if r.status_code == 200:
                result = r.json()
                return {
                    "transcript": result.get("text", ""),
                    "segments": result.get("segments", []),
                    "file_path": str(sp),
                }
            return {
                "transcript": "", "segments": [], "file_path": str(sp),
                "error": "Transcription failed",
            }
    except Exception as e:
        log.error("Transcription failed: %s", e)
        return {
            "transcript": "", "segments": [], "file_path": str(sp),
            "error": str(e),
        }


@router.post("/merge-segments/{project_id}")
async def merge_segments(project_id: str, request: Request = None):
    """Concat all segments of a multi-segment project into one MP4 via ffmpeg."""
    user = await get_current_user(request)
    project = await db.video_projects.find_one(
        {"id": project_id, "user_id": user["user_id"]},
        {"_id": 0},
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    segments = project.get("result_segments", [])
    if len(segments) < 2:
        raise HTTPException(status_code=400, detail="Need 2+ segments to merge")
    try:
        merge_dir = UPLOAD_DIR / f"merge_{uuid.uuid4().hex}"
        merge_dir.mkdir(exist_ok=True)
        seg_files: list[Path] = []
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(120.0), follow_redirects=True,
        ) as c:
            for i, seg in enumerate(segments):
                url = seg.get("result_url")
                if not url:
                    continue
                resp = await c.get(url)
                if resp.status_code == 200:
                    fp = merge_dir / f"seg_{i:03d}.mp4"
                    with open(fp, "wb") as f:
                        f.write(resp.content)
                    seg_files.append(fp)
        if len(seg_files) < 2:
            raise Exception("Could not download enough segments")
        list_path = merge_dir / "list.txt"
        with open(list_path, "w") as f:
            for sf in seg_files:
                f.write(f"file '{sf}'\n")
        out_path = UPLOAD_DIR / f"merged_{uuid.uuid4().hex}.mp4"
        # Try copy first (fast, works if all segments use same codec)
        result = subprocess.run(
            ["/usr/bin/ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", str(list_path), "-c", "copy", str(out_path)],
            capture_output=True, timeout=120,
        )
        # Fallback: re-encode if codec mismatch
        if result.returncode != 0:
            result = subprocess.run(
                ["/usr/bin/ffmpeg", "-y", "-f", "concat", "-safe", "0",
                 "-i", str(list_path), "-c:v", "libx264",
                 "-c:a", "aac", str(out_path)],
                capture_output=True, timeout=120,
            )
        if not out_path.exists():
            raise Exception("FFmpeg merge failed")
        merged_url = f"/api/serve-file/{out_path.name}"
        await db.video_projects.update_one(
            {"id": project_id},
            {"$set": {
                "merged_url": merged_url,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        shutil.rmtree(merge_dir, ignore_errors=True)
        return {"merged_url": merged_url, "status": "completed"}
    except Exception as e:
        log.error("Merge failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
