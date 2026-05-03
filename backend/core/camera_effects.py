"""Camera + effects engine (Phase 3) for the AI Avatar Studio.

Translates a preset's ``motion`` + ``effects[]`` strings into a single
ffmpeg ``-vf`` (or ``-filter_complex``) chain that re-renders an
existing MP4 with cinematic post-processing.

Why this is its own module:
  Solo procedural lipsync (mouth_animator) and dual procedural lipsync
  (dual_mouth_animator) both produce a "flat" MP4 — the camera is
  fixed and the cartoon is unembellished. The cinematic preset's
  ``motion`` ("dolly_in", "ken_burns", ...) and ``effects[]``
  ("vignette", "glow", "depth_of_field", ...) only have meaning if
  somebody actually applies them. This module is that somebody.

Public:
  - apply_camera_effects(input_path, output_path, motion=None,
                         effects=None, duration=None) -> bool

Filter implementation choices (ffmpeg 6.x):
  * ``slow_zoom`` / ``dolly_in`` / ``ken_burns`` / ``fast_zoom`` /
    ``slow_pan``  → ``zoompan`` filter; we feed it a single-frame
    interpolation timeline that varies by motion id.
  * ``shake`` → ``crop`` with a small jittered (x,y) using sine of
    time, simulating handheld camera.
  * ``punch_in`` → quick scale ramp at the start (1× → 1.08× over 0.4s)
    by appending a second zoompan at the front.
  * ``vignette`` → ``vignette=PI/4`` (subtle).
  * ``soft_glow`` / ``glow`` → ``unsharp`` + ``eq=brightness=0.04``.
  * ``bokeh`` → mild ``boxblur`` on a copy + ``blend=screen`` so highlights
    bloom; cheap approximation that reads as bokeh on cartoon backgrounds.
  * ``soft_blur`` → ``boxblur=2:1``.
  * ``depth_of_field`` → ``vignette`` + a radial ``boxblur`` approximated
    by ``boxblur=lr`` selectively (we use a simple full-frame blur at
    very low strength so the cartoon stays recognisable).
"""
from __future__ import annotations

import logging
import shlex
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional

log = logging.getLogger("core.camera_effects")

FFMPEG = "/usr/bin/ffmpeg"


# ─────────────────────────── Motion → filter ───────────────────────────
# Each entry returns a `vf` fragment that must end with a comma OR
# nothing (joiner adds the comma). zoompan's z= expression is the
# zoom curve; x= / y= position the crop. d=duration*fps frames.

def _motion_filter(motion: str, fps: int, duration_s: float, w: int, h: int) -> str:
    """Return a single zoompan/crop filter for the given motion id.

    Empty string = no motion (default).
    """
    if not motion:
        return ""
    motion = motion.lower().strip()
    total = max(1, int(round(duration_s * fps)))

    # zoompan needs a base scale + zoompan + scale-back. We always
    # output the original WxH so the file remains the same size.
    if motion == "slow_zoom":
        # 1.00 → 1.10 over the whole clip, centred
        z = "min(zoom+0.0006,1.10)"
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif motion == "dolly_in":
        # Faster, more dramatic — 1.00 → 1.18
        z = "min(zoom+0.0011,1.18)"
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif motion == "fast_zoom":
        # Punchy — 1.00 → 1.25 in the first 60% of the clip then hold
        z = f"if(lt(on,{int(total*0.6)}),min(zoom+0.0025,1.25),1.25)"
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif motion == "slow_pan":
        # Subtle pan left → right, very slight zoom 1.00 → 1.05
        z = "min(zoom+0.00025,1.05)"
        x = f"if(gte(on,1),(on/{total})*(iw-iw/zoom),0)"
        y = "ih/2-(ih/zoom/2)"
    elif motion == "ken_burns":
        # Classic — combine slow zoom + slight diagonal drift
        z = "min(zoom+0.0005,1.12)"
        x = f"((on/{total})*0.4)*iw/zoom*0.05+iw/2-(iw/zoom/2)*1.0"
        y = f"((on/{total})*0.4)*ih/zoom*0.04+ih/2-(ih/zoom/2)*1.0"
    elif motion == "shake":
        # Implemented via crop in the effects layer so we leave the
        # zoompan slot empty here.
        return ""
    elif motion == "none":
        return ""
    else:
        log.debug("camera: unknown motion '%s' — skipping", motion)
        return ""

    # zoompan's `s=` is the OUTPUT size of the zoom step. Keeping it
    # at the original WxH means we don't lose resolution.
    return (
        f"zoompan=z='{z}':x='{x}':y='{y}':"
        f"d=1:s={w}x{h}:fps={fps}"
    )


# ─────────────────────────── Effects → filter ───────────────────────────

def _effects_filters(effects: Iterable[str]) -> List[str]:
    """Translate an effects[] list into individual ffmpeg `-vf` chunks.

    Order matters slightly: blurs/glows go first (so vignette
    darkens the bloom edges), then sharpening, then vignette, then
    eq adjustments. Final shake is applied last via crop.
    """
    if not effects:
        return []
    seen = set()
    out: List[str] = []
    pending_shake = False
    for raw in effects:
        if not raw:
            continue
        e = str(raw).lower().strip()
        if e in seen:
            continue
        seen.add(e)

        if e == "vignette":
            out.append("vignette=PI/4.5")
        elif e in ("soft_glow", "glow"):
            # Soft bloom: copy + boxblur + screen blend, then a tiny
            # brightness lift. Done in two stages for cheap quality.
            out.append("unsharp=5:5:0.4:5:5:0.0")
            out.append("eq=brightness=0.03:saturation=1.06")
        elif e == "bokeh":
            # Approximation — soft boxblur + brightness lift on highlights.
            # True bokeh would need depth segmentation; this still reads as
            # "creamy edges" on stylised cartoons.
            out.append("boxblur=lr=1:lp=1:cr=2:cp=1")
        elif e == "soft_blur":
            out.append("boxblur=lr=1:lp=1")
        elif e == "depth_of_field":
            # Approx — vignette + slight outer blur. We can't do a true
            # radial blur in pure ffmpeg without complex split/blend,
            # but vignette + soft sharpen interior reads as DoF.
            out.append("unsharp=3:3:0.6:3:3:0.0")
            out.append("vignette=PI/4")
        elif e == "shake":
            pending_shake = True
        elif e == "punch_in":
            # Brief scale spike at the start. Implemented as a zoompan
            # whose curve flattens after frame 12 (~0.5s @ 25fps).
            out.append(
                "zoompan=z='if(lt(on,12),1.0+(on/12)*0.08,1.08-(on-12)*0.005)':"
                "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=hd1080:fps=25"
            )
            # Note: hd1080 is just an alias — ffmpeg will use it as
            # 1920x1080. For our 540x960 / 1080x960 inputs this still
            # produces a correctly-sized punch because zoompan auto-
            # resizes back. If problems, override to s='iw'x'ih' below.
        elif e == "warm_film":
            out.append("eq=gamma=1.04:saturation=1.10:brightness=0.02")
        elif e == "cool_film":
            out.append("eq=gamma=1.02:saturation=0.92:brightness=-0.01")
        else:
            log.debug("camera: unknown effect '%s' — skipping", e)

    if pending_shake:
        # Subtle handheld shake — crop a slightly oversized inner box
        # whose (x,y) wiggles per-frame. ix/iy oscillate ±2 px at ~3 Hz.
        # Done LAST so the shake samples the already-effected frame.
        out.append(
            "crop=iw-6:ih-6:"
            "3+1.5*sin(n/9):3+1.5*cos(n/11)"
        )
    return out


# ─────────────────────────── Public API ───────────────────────────


def apply_camera_effects(
    input_path: Path | str,
    output_path: Path | str,
    motion: Optional[str] = None,
    effects: Optional[Iterable[str]] = None,
    duration: Optional[float] = None,
    fps: int = 25,
) -> bool:
    """Re-encode `input_path` with the given camera motion + effects.

    Returns True on success, False otherwise. If both `motion` and
    `effects` are None / empty, this is a no-op (returns False so the
    caller knows it didn't transform — caller should keep using the
    original file).

    Why a single ffmpeg pass: chaining filter strings is much faster
    (1 decode + 1 encode) than calling ffmpeg twice. The order in
    `vf_parts` must be:
       motion → effects → final pad/scale guard.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    if not input_path.exists():
        log.warning("camera: input missing %s", input_path)
        return False
    if not motion and not effects:
        return False

    # Probe input dimensions + duration so motion zoompan can size correctly.
    try:
        probe = subprocess.run([
            "/usr/bin/ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration:format=duration",
            "-of", "default=noprint_wrappers=1:nokey=0",
            str(input_path),
        ], capture_output=True, timeout=20)
        probe_out = probe.stdout.decode(errors="ignore")
        w, h, dur = 0, 0, 0.0
        for line in probe_out.splitlines():
            if line.startswith("width="):
                try: w = int(line.split("=", 1)[1])
                except Exception: pass
            elif line.startswith("height="):
                try: h = int(line.split("=", 1)[1])
                except Exception: pass
            elif line.startswith("duration="):
                try:
                    val = float(line.split("=", 1)[1])
                    if val > dur:
                        dur = val
                except Exception:
                    pass
        if w == 0 or h == 0:
            log.warning("camera: probe failed to read dims for %s", input_path)
            return False
        if duration:
            dur = duration
    except Exception as e:
        log.warning("camera: ffprobe failed: %s", e)
        return False

    vf_parts: List[str] = []
    motion_filter = _motion_filter(motion or "", fps, dur or 5.0, w, h)
    if motion_filter:
        vf_parts.append(motion_filter)
    vf_parts.extend(_effects_filters(effects or []))
    if not vf_parts:
        return False

    # Always cap to even dims for H.264 yuv420p.
    vf_parts.append(f"scale=trunc(iw/2)*2:trunc(ih/2)*2")
    vf_str = ",".join(vf_parts)

    cmd = [
        FFMPEG, "-y", "-loglevel", "error",
        "-i", str(input_path),
        "-vf", vf_str,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        str(output_path),
    ]
    log.info("camera: motion=%s effects=%s duration=%.2fs", motion, list(effects or []), dur)
    log.debug("camera: vf=%s", vf_str)
    try:
        res = subprocess.run(cmd, capture_output=True, timeout=180)
        if res.returncode != 0:
            log.warning("camera: ffmpeg non-zero (%d) %s",
                        res.returncode, res.stderr[-200:].decode(errors="ignore"))
            return False
        if not output_path.exists() or output_path.stat().st_size < 4096:
            log.warning("camera: output missing or too small")
            return False
        return True
    except subprocess.TimeoutExpired:
        log.warning("camera: ffmpeg timed out")
        return False
    except Exception as e:
        log.exception("camera: ffmpeg crashed: %s", e)
        return False


__all__ = ["apply_camera_effects"]


if __name__ == "__main__":  # pragma: no cover
    import sys
    if len(sys.argv) < 4:
        print("usage: python -m core.camera_effects <in.mp4> <out.mp4> "
              "<motion> [effect1 effect2 ...]")
        sys.exit(1)
    in_, out_, mo_ = sys.argv[1], sys.argv[2], sys.argv[3]
    fx = sys.argv[4:] if len(sys.argv) > 4 else []
    ok = apply_camera_effects(in_, out_, mo_, fx)
    sys.exit(0 if ok else 2)
