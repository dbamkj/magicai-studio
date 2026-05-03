"""Procedural DUAL-speaker cartoon mouth animator (Session 33 r4).

Why this exists:
  MagicHour's ``v1.lip_sync`` for our split-screen flow costs ~600
  credits per generation AND injects photoreal facial features onto
  cartoon characters (uncanny "real human eye" artifact reported by
  the user multiple times). This module replaces that round-trip
  with a fully-local OpenCV + ffmpeg pipeline that animates each
  speaker's mouth ONLY when it's their turn, then composites both
  half-frames into a 1080×960 side-by-side MP4.

Public entry point:
  animate_dual_cartoon(
      image_a_path, image_b_path,
      segments,            # list of {"speaker": "A"|"B", "audio_path": Path,
                           #          "duration": float, "pre_pause": float}
      output_path,
      fps=25,
      half_size=(540, 960),
      bgm_audio_path=None, # optional pre-mixed combined-with-BGM audio
                           # to use for the final track (replaces the
                           # auto-concat of segment audios).
  ) -> bool

Per-frame logic:
  - For each speaker, build an envelope array in [0, 1] sampled at fps.
  - During segment K (speaker S, duration D), set env_S[start..start+D*fps]
    = audio RMS envelope of that segment's mp3. The OTHER speaker's
    envelope is held at 0 during that range — they're listening, not
    talking, so their mouth is closed.
  - Frame i: render half_a from image_a with mouth animated by env_a[i],
    render half_b from image_b with mouth animated by env_b[i],
    horizontally concat → 1080×960 BGR ndarray, push to ffmpeg stdin.

Audio track:
  - If bgm_audio_path is given, use that as the audio (already has BGM
    mixed under the combined voice). Otherwise concat the segment audios
    in order with `pre_pause` silence prepended per segment.
"""
from __future__ import annotations

import logging
import math
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple, TypedDict

import numpy as np
from PIL import Image

# Reuse the proven helpers from the solo animator to keep behavior
# identical for face/mouth detection + per-frame rendering.
from core.mouth_animator import (
    _detect_face_bbox,
    _derive_mouth_box,
    _audio_rms_envelope,
    _audio_duration_sec,
    _render_frame,
    FFMPEG,
)

log = logging.getLogger("core.dual_mouth_animator")


class DualSegment(TypedDict, total=False):
    speaker: str         # "A" or "B"
    audio_path: str      # mp3 path of just this turn's TTS
    duration: float      # decoded duration (seconds)
    pre_pause: float     # silence (s) to insert BEFORE this segment


# ──────────────────────────── Helpers ────────────────────────────

def _load_image_to_half(path: Path, half_w: int, half_h: int) -> np.ndarray:
    """Open `path` and return a (half_h, half_w, 3) RGB ndarray.

    We "scale-and-crop" (cover) so the character fills the half-frame
    without black bars, mimicking ffmpeg's
    ``scale=...:force_original_aspect_ratio=increase,crop=...``.
    """
    img = Image.open(path).convert("RGB")
    w0, h0 = img.size
    scale = max(half_w / w0, half_h / h0)
    nw, nh = int(round(w0 * scale)), int(round(h0 * scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    # Centre crop
    x0 = max(0, (nw - half_w) // 2)
    y0 = max(0, (nh - half_h) // 2)
    img = img.crop((x0, y0, x0 + half_w, y0 + half_h))
    return np.asarray(img, dtype=np.uint8)


def _build_envelopes(
    segments: List[DualSegment], fps: int, total_seconds: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return (env_a, env_b) — per-frame amplitude in [0,1].

    Only the active speaker's envelope is populated per segment; the
    other speaker's value stays 0 for that range (closed mouth).
    """
    total_frames = max(1, int(round(total_seconds * fps)))
    env_a = np.zeros(total_frames, dtype=np.float32)
    env_b = np.zeros(total_frames, dtype=np.float32)

    cursor = 0.0  # seconds
    for seg in segments:
        pre = float(seg.get("pre_pause") or 0.0)
        cursor += pre  # silence — both envelopes 0

        speaker = (seg.get("speaker") or "A").upper()
        ap = Path(seg["audio_path"])
        dur = float(seg.get("duration") or 0.0) or _audio_duration_sec(ap)
        if dur <= 0:
            continue

        seg_env = _audio_rms_envelope(ap, fps)
        n = max(1, int(round(dur * fps)))
        if seg_env.size < n:
            seg_env = np.concatenate([seg_env, np.zeros(n - seg_env.size, dtype=np.float32)])
        else:
            seg_env = seg_env[:n]

        start = int(round(cursor * fps))
        end = min(total_frames, start + n)
        if end <= start:
            cursor += dur
            continue
        chunk = seg_env[: end - start]
        if speaker == "A":
            env_a[start:end] = chunk
        else:
            env_b[start:end] = chunk
        cursor += dur

    return env_a, env_b


def _concat_audio_to_master(
    segments: List[DualSegment], output_mp3: Path,
) -> Optional[Path]:
    """Concat per-segment mp3s with pre-pause silences → single master mp3."""
    list_txt = output_mp3.with_suffix(".concat.txt")
    tmp_dir = output_mp3.parent
    cleanup: List[Path] = []
    try:
        with open(list_txt, "w") as lf:
            for i, seg in enumerate(segments):
                pre = float(seg.get("pre_pause") or 0.0)
                if pre > 0.05:
                    sil = tmp_dir / f"{output_mp3.stem}_sil_{i}.mp3"
                    res = subprocess.run([
                        FFMPEG, "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        f"anullsrc=r=44100:cl=stereo", "-t", f"{pre:.3f}",
                        "-q:a", "9", str(sil),
                    ], capture_output=True, timeout=20)
                    if res.returncode == 0 and sil.exists():
                        lf.write(f"file '{sil.resolve()}'\n")
                        cleanup.append(sil)
                ap = Path(seg["audio_path"])
                if ap.exists():
                    lf.write(f"file '{ap.resolve()}'\n")
        cleanup.append(list_txt)
        res = subprocess.run([
            FFMPEG, "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_txt), "-c:a", "libmp3lame", "-b:a", "160k",
            str(output_mp3),
        ], capture_output=True, timeout=120)
        if res.returncode != 0 or not output_mp3.exists():
            log.warning("dual_anim: concat failed %s", res.stderr[-200:].decode(errors="ignore"))
            return None
        return output_mp3
    finally:
        for p in cleanup:
            try: p.unlink(missing_ok=True)
            except Exception: pass


# ──────────────────────────── Public API ────────────────────────────

def animate_dual_cartoon(
    image_a_path: Path | str,
    image_b_path: Path | str,
    segments: List[DualSegment],
    output_path: Path | str,
    fps: int = 25,
    half_size: Tuple[int, int] = (540, 960),
    bgm_audio_path: Optional[Path | str] = None,
    max_duration: float = 90.0,
) -> bool:
    """Render a side-by-side dual-speaker cartoon talking video locally.

    Returns True on success; caller falls back to MagicHour on False.
    """
    image_a_path = Path(image_a_path)
    image_b_path = Path(image_b_path)
    output_path = Path(output_path)
    if not image_a_path.exists() or not image_b_path.exists():
        log.warning("dual_anim: missing image(s) a=%s b=%s", image_a_path, image_b_path)
        return False
    if not segments:
        log.warning("dual_anim: no segments provided")
        return False

    half_w, half_h = half_size
    # Even dims for H.264
    half_w -= half_w % 2
    half_h -= half_h % 2

    # 1) Load + scale-crop both characters into half-frame buffers.
    try:
        base_a = _load_image_to_half(image_a_path, half_w, half_h)
        base_b = _load_image_to_half(image_b_path, half_w, half_h)
    except Exception as e:
        log.warning("dual_anim: image prep failed: %s", e)
        return False

    # 2) Detect face + mouth box on each half (independently).
    face_a = _detect_face_bbox(base_a)
    face_b = _detect_face_bbox(base_b)
    mouth_a = _derive_mouth_box(face_a, half_w, half_h)
    mouth_b = _derive_mouth_box(face_b, half_w, half_h)
    log.info("dual_anim: A face=%s mouth=%s | B face=%s mouth=%s",
             face_a, mouth_a, face_b, mouth_b)

    # 3) Build / pick the master audio track.
    tmp_audio_owned: Optional[Path] = None
    if bgm_audio_path and Path(bgm_audio_path).exists():
        master_audio = Path(bgm_audio_path)
    else:
        master_audio = output_path.with_suffix(".master.mp3")
        if not _concat_audio_to_master(segments, master_audio):
            log.warning("dual_anim: master audio concat failed")
            return False
        tmp_audio_owned = master_audio

    total_seconds = _audio_duration_sec(master_audio)
    if total_seconds <= 0:
        log.warning("dual_anim: master audio has no duration")
        return False
    total_seconds = min(total_seconds, max_duration)

    # 4) Compute per-speaker envelopes.
    env_a, env_b = _build_envelopes(segments, fps, total_seconds)

    # 5) Render frames → ffmpeg via stdin (rgb24).
    full_w = half_w * 2
    full_h = half_h
    total_frames = int(round(total_seconds * fps))
    ffmpeg_cmd = [
        FFMPEG, "-loglevel", "error", "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{full_w}x{full_h}",
        "-pix_fmt", "rgb24",
        "-r", str(fps),
        "-i", "pipe:0",
        "-i", str(master_audio),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "160k",
        "-shortest",
        str(output_path),
    ]
    try:
        proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except Exception as e:
        log.exception("dual_anim: spawn ffmpeg failed: %s", e)
        return False

    try:
        assert proc.stdin is not None
        for i in range(total_frames):
            amp_a = float(env_a[i]) if i < env_a.size else 0.0
            amp_b = float(env_b[i]) if i < env_b.size else 0.0
            half_a = _render_frame(base_a, mouth_a, amp_a) if amp_a > 0.02 else base_a
            half_b = _render_frame(base_b, mouth_b, amp_b) if amp_b > 0.02 else base_b
            # numpy hstack — both halves have identical shape so this is O(n).
            frame = np.concatenate([half_a, half_b], axis=1)
            proc.stdin.write(frame.tobytes())
        try: proc.stdin.flush()
        except Exception: pass
        try: proc.stdin.close()
        except Exception: pass
        try: proc.wait(timeout=300)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait()
            log.warning("dual_anim: ffmpeg timed out")
            return False
        err_bytes = proc.stderr.read() if proc.stderr else b""
        if proc.returncode != 0:
            log.warning("dual_anim: ffmpeg non-zero (%d) %s",
                        proc.returncode, err_bytes[-200:].decode(errors="ignore"))
            return False
    except Exception as e:
        log.exception("dual_anim: render loop failed: %s", e)
        try: proc.kill()
        except Exception: pass
        return False
    finally:
        # If we allocated a temporary master mp3, only clean it up on
        # FAILURE. On success keep it around for debugging — caller
        # can mop up the upload dir with its existing janitor.
        if tmp_audio_owned and not output_path.exists():
            try: tmp_audio_owned.unlink(missing_ok=True)
            except Exception: pass

    if not output_path.exists() or output_path.stat().st_size < 4096:
        log.warning("dual_anim: output missing or too small")
        return False

    log.info("dual_anim: OK %s (frames=%d dur=%.2fs WxH=%dx%d)",
             output_path.name, total_frames, total_seconds, full_w, full_h)
    return True


__all__ = ["animate_dual_cartoon", "DualSegment"]


# CLI smoke-test:
#   python -m core.dual_mouth_animator imgA.png imgB.png segA.mp3 A segB.mp3 B out.mp4
if __name__ == "__main__":  # pragma: no cover
    if len(sys.argv) < 7:
        print("usage: python -m core.dual_mouth_animator imgA imgB segA.mp3 A segB.mp3 B out.mp4")
        sys.exit(1)
    segs: List[DualSegment] = [
        {"speaker": sys.argv[4], "audio_path": sys.argv[3],
         "duration": _audio_duration_sec(Path(sys.argv[3])), "pre_pause": 0.0},
        {"speaker": sys.argv[6], "audio_path": sys.argv[5],
         "duration": _audio_duration_sec(Path(sys.argv[5])), "pre_pause": 0.2},
    ]
    ok = animate_dual_cartoon(sys.argv[1], sys.argv[2], segs, sys.argv[7])
    sys.exit(0 if ok else 2)
