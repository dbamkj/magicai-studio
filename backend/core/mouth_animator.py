"""Procedural cartoon mouth animator.

Why this exists:
  MagicHour's ``v1.lip_sync`` is trained on real photographs and
  injects photoreal facial features (eyes, mouth, teeth) onto the
  source frame. When the source is a stylised cartoon avatar this
  produces the uncanny "realistic human eye pasted onto the cartoon"
  artifact that users have complained about.

  This module takes a cartoon still image + TTS audio and produces a
  talking-video MP4 *without* MagicHour. The cartoon's face is
  preserved byte-for-byte except for a small elliptical region around
  the mouth that is animated based on the audio amplitude envelope.

Public entry point:
  animate_talking_cartoon(image_path, audio_path, output_path,
                          fps=25, preferred_mouth_bbox=None) -> bool

Pipeline:
  1. Detect the face box with OpenCV's haar-frontalface cascade.
     Cascades work surprisingly well on Pixar/Disney/anime-style faces
     because those faces have the same proportional eye/nose/mouth
     structure as humans. If detection fails, we fall back to a
     "centered portrait" assumption (face ≈ middle 60% of frame).
  2. Derive a mouth rectangle from the face box:
        cx = face.x + face.w/2
        cy = face.y + face.h * 0.72   # mouth sits ~72% down the face
        mw = face.w * 0.35
        mh = face.h * 0.12
  3. Decode the audio to raw PCM mono @ 16 kHz via ffmpeg and compute
     per-frame RMS amplitude (window = 1/fps seconds), normalise to
     [0, 1] with a gentle noise floor so silence stays closed.
  4. For each frame:
        - start from the original cartoon pixels
        - inside the mouth rectangle, apply a vertical squash/stretch
          whose strength = amplitude * max_open (~0.22).
        - add a darker "inner mouth" ellipse whose alpha = amplitude
          so an open mouth shows a tiny cavity (sells the motion).
  5. Pipe frames to ffmpeg as a rawvideo stream, mux with the TTS
     audio, output H.264 yuv420p MP4 sized to the source resolution.

Performance:
  A 10-second clip at 25fps = 250 frames. On a single CPU this takes
  ~1.5-3 seconds total (PIL+numpy slicing is fast). Much cheaper than
  a MagicHour round-trip (45-90s + credits).

Dependencies: opencv-python-headless, numpy, Pillow, ffmpeg on PATH.
"""
from __future__ import annotations

import logging
import math
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image

log = logging.getLogger("core.mouth_animator")

# Lazy cv2 import so the module can be imported on boxes without opencv
# (unit-tests, linter runs). We raise only when an actual animation is
# requested without opencv installed.
try:
    import cv2  # type: ignore
    _HAAR = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    _HAS_CV2 = not _HAAR.empty()
except Exception as _cv2_err:  # pragma: no cover
    cv2 = None
    _HAAR = None
    _HAS_CV2 = False
    log.warning("mouth_animator: opencv unavailable (%s)", _cv2_err)


FFMPEG = "/usr/bin/ffmpeg"
FFPROBE = "/usr/bin/ffprobe"


# ──────────────────────────── Face detection ────────────────────────────

def _detect_face_bbox(img_rgb: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """Return the largest frontal face bbox (x, y, w, h) or None."""
    if not _HAS_CV2:
        return None
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    # Cartoons often have high contrast — equalising helps cascade fire.
    gray = cv2.equalizeHist(gray)
    faces = _HAAR.detectMultiScale(
        gray,
        scaleFactor=1.15,
        minNeighbors=3,
        minSize=(int(gray.shape[0] * 0.12), int(gray.shape[0] * 0.12)),
    )
    if len(faces) == 0:
        # Relaxed second pass for very small faces
        faces = _HAAR.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=2, minSize=(48, 48))
    if len(faces) == 0:
        return None
    # Pick the largest face (most likely the subject)
    x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
    return int(x), int(y), int(w), int(h)


def _derive_mouth_box(
    face_bbox: Optional[Tuple[int, int, int, int]],
    img_w: int,
    img_h: int,
) -> Tuple[int, int, int, int]:
    """Return (x, y, w, h) of the mouth rectangle in image pixel coords."""
    if face_bbox is not None:
        fx, fy, fw, fh = face_bbox
        cx = fx + fw // 2
        cy = fy + int(fh * 0.72)
        mw = max(24, int(fw * 0.42))
        mh = max(14, int(fh * 0.14))
    else:
        # Portrait fallback — assume centered 9:16 composition with face
        # occupying the top-half. Mouth sits ~48% down the full image,
        # centered horizontally.
        cx = img_w // 2
        cy = int(img_h * 0.48)
        mw = max(36, int(img_w * 0.22))
        mh = max(18, int(img_h * 0.05))
    x = max(0, cx - mw // 2)
    y = max(0, cy - mh // 2)
    w = min(mw, img_w - x)
    h = min(mh, img_h - y)
    return x, y, w, h


# ──────────────────────────── Audio envelope ────────────────────────────

def _audio_rms_envelope(audio_path: Path, fps: int) -> np.ndarray:
    """Decode audio to mono PCM16 @ 16 kHz and return per-frame RMS."""
    # Use ffmpeg to pipe raw pcm_s16le into numpy. Keeps dep list small.
    cmd = [
        FFMPEG, "-loglevel", "error", "-y",
        "-i", str(audio_path),
        "-f", "s16le", "-ac", "1", "-ar", "16000",
        "pipe:1",
    ]
    res = subprocess.run(cmd, capture_output=True, timeout=60)
    if res.returncode != 0 or not res.stdout:
        log.warning("mouth_animator: ffmpeg decode failed %s", res.stderr[-200:].decode(errors="ignore"))
        return np.zeros(1, dtype=np.float32)
    pcm = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    if pcm.size == 0:
        return np.zeros(1, dtype=np.float32)
    samples_per_frame = max(1, int(round(16000 / fps)))
    n_frames = int(math.ceil(pcm.size / samples_per_frame))
    env = np.zeros(n_frames, dtype=np.float32)
    for i in range(n_frames):
        seg = pcm[i * samples_per_frame : (i + 1) * samples_per_frame]
        if seg.size == 0:
            env[i] = 0.0
        else:
            env[i] = float(np.sqrt(np.mean(seg * seg)))
    # Normalise with gentle noise floor so silence stays closed.
    max_rms = float(env.max()) if env.size else 0.0
    if max_rms < 1e-4:
        return env
    # Soft compand: pow(x, 0.6) pushes mid-levels up for more visible motion.
    norm = np.clip(env / (max_rms * 0.85), 0.0, 1.0)
    norm = np.power(norm, 0.65)
    # Small smoothing so the mouth doesn't flicker
    if norm.size >= 3:
        kernel = np.array([0.25, 0.5, 0.25], dtype=np.float32)
        norm = np.convolve(norm, kernel, mode="same")
    return norm.astype(np.float32)


def _audio_duration_sec(audio_path: Path) -> float:
    try:
        r = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
            capture_output=True, timeout=10,
        )
        return float((r.stdout.decode() or "0").strip() or 0.0)
    except Exception:
        return 0.0


# ──────────────────────────── Frame rendering ────────────────────────────

def _render_frame(
    base_rgb: np.ndarray,
    mouth_box: Tuple[int, int, int, int],
    openness: float,
    inner_color: Tuple[int, int, int] = (45, 20, 25),
) -> np.ndarray:
    """Return a copy of base_rgb with the mouth area animated.

    openness ∈ [0, 1].
      0 → original pixels unchanged.
      1 → maximum vertical squash + visible inner-mouth ellipse.
    """
    if openness <= 0.02:
        return base_rgb  # no visible change → reuse reference to save memory

    x, y, w, h = mouth_box
    if w <= 4 or h <= 4:
        return base_rgb

    out = base_rgb.copy()

    # Work on an expanded vertical zone so we can "push" the lower half
    # down without tearing. Zone = 1.4× taller, centred on the mouth.
    zone_h = int(h * 1.6)
    zone_y = max(0, y - (zone_h - h) // 2)
    zone_y_end = min(out.shape[0], zone_y + zone_h)
    zone_h = zone_y_end - zone_y

    zone_orig = out[zone_y:zone_y_end, x:x + w].copy()
    zone = zone_orig.copy()
    if zone.size == 0:
        return out

    # Split zone horizontally at its midline — the upper half is kept in
    # place, the lower half is shifted DOWN by `shift` pixels. The gap
    # created at the midline is filled with a dark red/brown ellipse
    # (the inner mouth) so the motion reads as speaking.
    zh = zone.shape[0]
    mid = zh // 2
    max_shift = max(2, int(h * 0.60))  # how far the lower lip can drop
    shift = int(round(openness * max_shift))
    shift = min(shift, zh - mid - 1)
    if shift <= 0:
        return out

    upper = zone[:mid].copy()
    lower = zone[mid:mid + (zh - mid - shift)].copy()

    # Rebuild the zone: upper (unchanged), gap (dark mouth), then lower
    # shifted down. Gap height = `shift` px.
    new_zone = np.empty_like(zone)
    new_zone[:mid] = upper
    # Start the lower block at (mid + shift)
    lower_start = mid + shift
    lower_end = lower_start + lower.shape[0]
    if lower_end > zh:
        lower_end = zh
        lower = lower[: lower_end - lower_start]
    new_zone[lower_start:lower_end] = lower
    # If there's any trailing pixels not filled (e.g. lower too short),
    # copy from the original zone to keep things natural.
    if lower_end < zh:
        new_zone[lower_end:] = zone[lower_end:]

    # Inner mouth fill — a horizontal dark-red band with an ellipse
    # alpha to soften edges. Centred at (w/2, mid + shift/2).
    gap = new_zone[mid:mid + shift]
    if gap.size > 0:
        gh, gw = gap.shape[:2]
        yy, xx = np.mgrid[0:gh, 0:gw]
        # Ellipse: ((x - w/2)/(w/2*0.9))^2 + ((y - gh/2)/(gh/2*1.0))^2 <= 1
        ry = max(1.0, gh * 0.55)
        rx = max(1.0, gw * 0.42)
        dist = ((xx - gw / 2) / rx) ** 2 + ((yy - gh / 2) / ry) ** 2
        alpha = np.clip(1.0 - dist, 0.0, 1.0) ** 0.6  # soft edges
        alpha = alpha[..., None]
        fill = np.array(inner_color, dtype=np.uint8).reshape(1, 1, 3)
        gap[:] = (gap.astype(np.float32) * (1.0 - alpha) + fill.astype(np.float32) * alpha).astype(np.uint8)
        new_zone[mid:mid + shift] = gap

    # SOFT EDGE BLEND — taper the left/right and top/bottom edges of the
    # zone so the animated region fades smoothly back into the original
    # pixels. Without this the hard rectangular boundary of the zone
    # creates the "tearing / unnatural line" artifact users see.
    zh2, zw2 = new_zone.shape[:2]
    yy2, xx2 = np.mgrid[0:zh2, 0:zw2]
    fx = np.minimum(xx2, zw2 - 1 - xx2) / max(1.0, zw2 * 0.18)
    fy = np.minimum(yy2, zh2 - 1 - yy2) / max(1.0, zh2 * 0.18)
    mask = np.clip(np.minimum(fx, fy), 0.0, 1.0).astype(np.float32)
    # Emphasise the centre (where the mouth actually moves); tail off the
    # edges quickly.
    mask = mask ** 1.2
    mask3 = mask[..., None]
    blended = (new_zone.astype(np.float32) * mask3 +
               zone_orig.astype(np.float32) * (1.0 - mask3)).astype(np.uint8)

    out[zone_y:zone_y_end, x:x + w] = blended
    return out


# ──────────────────────────── Public API ────────────────────────────

def animate_talking_cartoon(
    image_path: Path | str,
    audio_path: Path | str,
    output_path: Path | str,
    fps: int = 25,
    max_duration: float = 60.0,
    preferred_mouth_bbox: Optional[Tuple[int, int, int, int]] = None,
    emotion: Optional[str] = None,
    emotion_intensity: float = 1.0,
) -> bool:
    """Produce a talking cartoon MP4 with procedural mouth animation.

    `emotion` (Phase-2): when set to one of happy/sad/calm/playful/
    confident/excited/motivational/fierce/devotional, applies a
    subtle full-frame RGB tint at low alpha (~10%) so the mood reads
    on screen without altering the cartoon's identity. Tint is
    pre-baked into base_rgb ONCE before the render loop so the cost
    is negligible.

    Returns True on success, False otherwise (caller should fall back
    to MagicHour's ``v1.lip_sync`` or raise).
    """
    image_path = Path(image_path)
    audio_path = Path(audio_path)
    output_path = Path(output_path)
    if not image_path.exists():
        log.warning("mouth_animator: image missing %s", image_path)
        return False
    if not audio_path.exists():
        log.warning("mouth_animator: audio missing %s", audio_path)
        return False

    try:
        base_img = Image.open(image_path).convert("RGB")
    except Exception as e:
        log.warning("mouth_animator: PIL open failed %s", e)
        return False

    # Enforce even dimensions for H.264
    w0, h0 = base_img.size
    w = w0 - (w0 % 2)
    h = h0 - (h0 % 2)
    if (w, h) != (w0, h0):
        base_img = base_img.resize((w, h), Image.LANCZOS)
    base_rgb = np.asarray(base_img, dtype=np.uint8)
    img_h, img_w = base_rgb.shape[:2]

    # Phase-2 — Pre-bake an emotion tint over the whole frame at low
    # alpha so the mood reads on screen without changing the cartoon's
    # identity. Done ONCE here (not per-frame) so the render loop is
    # not slowed down. Keeps the per-frame cost identical to a no-tint
    # render.
    if emotion:
        try:
            from core.emotion_detector import emotion_to_tint
            (tr, tg, tb), tint_alpha = emotion_to_tint(emotion, emotion_intensity)
            if tint_alpha > 0.005:
                tint_rgb = np.array([tr, tg, tb], dtype=np.float32).reshape(1, 1, 3)
                base_rgb = (
                    base_rgb.astype(np.float32) * (1.0 - tint_alpha)
                    + tint_rgb * tint_alpha
                ).clip(0, 255).astype(np.uint8)
                log.info(
                    "mouth_animator: emotion tint applied (%s, intensity=%.2f, alpha=%.3f)",
                    emotion, emotion_intensity, tint_alpha,
                )
        except Exception as _tint_err:
            log.debug("mouth_animator: tint skipped: %s", _tint_err)

    # Face + mouth detection
    face_bbox = _detect_face_bbox(base_rgb)
    mouth_box = preferred_mouth_bbox or _derive_mouth_box(face_bbox, img_w, img_h)
    log.info("mouth_animator: face=%s mouth=%s (img=%dx%d)", face_bbox, mouth_box, img_w, img_h)

    # Audio envelope
    dur = _audio_duration_sec(audio_path)
    if dur <= 0:
        log.warning("mouth_animator: could not read audio duration")
        return False
    dur = min(dur, max_duration)
    env = _audio_rms_envelope(audio_path, fps)
    total_frames = max(1, int(round(dur * fps)))
    if env.size < total_frames:
        pad = np.zeros(total_frames - env.size, dtype=np.float32)
        env = np.concatenate([env, pad])
    else:
        env = env[:total_frames]

    # Encode frames → ffmpeg via stdin (rawvideo). Stream raw BGR bytes
    # (ffmpeg -f rawvideo expects BGR by default when we say -pix_fmt bgr24).
    ffmpeg_cmd = [
        FFMPEG, "-loglevel", "error", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{img_w}x{img_h}",
        "-pix_fmt", "rgb24",
        "-r", str(fps),
        "-i", "pipe:0",
        "-i", str(audio_path),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
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
        log.exception("mouth_animator: could not spawn ffmpeg: %s", e)
        return False

    try:
        assert proc.stdin is not None
        for i in range(total_frames):
            amp = float(env[i]) if i < env.size else 0.0
            frame = _render_frame(base_rgb, mouth_box, amp)
            proc.stdin.write(frame.tobytes())
        try:
            proc.stdin.flush()
        except Exception:
            pass
        try:
            proc.stdin.close()
        except Exception:
            pass
        # Do NOT call communicate() here — it tries to flush the
        # already-closed stdin. Just wait + read stderr directly.
        try:
            proc.wait(timeout=180)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            log.warning("mouth_animator: ffmpeg timed out")
            return False
        err_bytes = proc.stderr.read() if proc.stderr else b""
        if proc.returncode != 0:
            log.warning("mouth_animator: ffmpeg non-zero (%d) %s",
                        proc.returncode, err_bytes[-200:].decode(errors="ignore"))
            return False
    except Exception as e:
        log.exception("mouth_animator: render loop failed: %s", e)
        try:
            proc.kill()
        except Exception:
            pass
        return False

    if not output_path.exists() or output_path.stat().st_size < 2048:
        log.warning("mouth_animator: output missing or too small")
        return False

    log.info("mouth_animator: OK %s (frames=%d dur=%.2fs)", output_path.name, total_frames, dur)
    return True


# CLI smoke-test: `python -m core.mouth_animator <img> <audio> <out>`
if __name__ == "__main__":  # pragma: no cover
    if len(sys.argv) < 4:
        print("usage: python -m core.mouth_animator <img> <audio> <out> [fps]")
        sys.exit(1)
    ok = animate_talking_cartoon(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3],
        fps=int(sys.argv[4]) if len(sys.argv) > 4 else 25,
    )
    sys.exit(0 if ok else 2)
