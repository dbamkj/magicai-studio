"""Procedural BGM track generator — Session 25 round 11.

Generates 3 additional royalty-free ambient pads at startup if missing.
This lets us ship 4 distinct moods (cinematic, calm, playful,
motivational) without depending on external music APIs.

Tracks are generated once via ffmpeg synth filters and cached on disk.
They're simple but functional ambient pads — meant as a baseline that
the team can later replace with curated content.

Audio is pure synthesis (no copyrighted samples), so license is "MIT
generated" — safe for commercial use.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

BGM_DIR = Path("/app/backend/static/bgm")
BGM_DIR.mkdir(parents=True, exist_ok=True)


# Each track is a dict of (filename, ffmpeg lavfi expression, duration).
# Lavfi `aevalsrc` lets us layer simple sine waves to create an ambient pad.
_TRACKS = [
    {
        "filename": "ambient_calm.mp3",
        # Soft pad — root + fifth + octave low sine waves with slow LFO.
        # Devotional/spiritual mood, low energy.
        "filter": (
            "sine=frequency=110:duration=60[a];"
            "sine=frequency=164:duration=60[b];"
            "sine=frequency=220:duration=60[c];"
            "[a][b][c]amix=inputs=3:duration=longest:dropout_transition=2,"
            "tremolo=f=0.4:d=0.15,"
            "volume=0.18,"
            "afade=t=in:st=0:d=2,afade=t=out:st=58:d=2"
        ),
        "duration": 60,
    },
    {
        "filename": "playful_pulse.mp3",
        # Faster sine + small detune for "wobble" feel. Playful/funny mood.
        "filter": (
            "sine=frequency=261.6:duration=60[a];"
            "sine=frequency=329.6:duration=60[b];"
            "sine=frequency=392:duration=60[c];"
            "[a][b][c]amix=inputs=3:duration=longest:dropout_transition=2,"
            "tremolo=f=4.5:d=0.35,"
            "volume=0.16,"
            "afade=t=in:st=0:d=1,afade=t=out:st=59:d=1"
        ),
        "duration": 60,
    },
    {
        "filename": "motivational_pulse.mp3",
        # Big root + mediant + perfect fifth — driving major chord pad.
        # Motivational/inspirational mood, mid-energy.
        "filter": (
            "sine=frequency=130.8:duration=60[a];"
            "sine=frequency=164.8:duration=60[b];"
            "sine=frequency=196:duration=60[c];"
            "sine=frequency=261.6:duration=60[d];"
            "[a][b][c][d]amix=inputs=4:duration=longest:dropout_transition=2,"
            "tremolo=f=2.0:d=0.25,"
            "volume=0.20,"
            "afade=t=in:st=0:d=1.5,afade=t=out:st=58.5:d=1.5"
        ),
        "duration": 60,
    },
]


def ensure_procedural_bgm_tracks() -> dict:
    """Generate any missing procedural BGM tracks. Idempotent — skips
    files that already exist on disk. Returns {generated, skipped}."""
    generated = 0
    skipped = 0
    failures: list[str] = []
    for track in _TRACKS:
        out = BGM_DIR / track["filename"]
        if out.exists() and out.stat().st_size > 1024:
            skipped += 1
            continue
        try:
            r = subprocess.run(
                [
                    "/usr/bin/ffmpeg", "-y",
                    "-f", "lavfi", "-i", track["filter"],
                    "-t", str(track["duration"]),
                    "-ar", "44100", "-ac", "2",
                    "-c:a", "libmp3lame", "-b:a", "128k",
                    str(out),
                ],
                capture_output=True, timeout=60,
            )
            if r.returncode == 0 and out.exists() and out.stat().st_size > 1024:
                generated += 1
                log.info("bgm_procedural: generated %s", track["filename"])
            else:
                failures.append(track["filename"])
                log.warning(
                    "bgm_procedural: failed to generate %s: %s",
                    track["filename"], r.stderr.decode()[:300],
                )
        except Exception as e:
            failures.append(track["filename"])
            log.warning("bgm_procedural: %s exception: %s", track["filename"], e)
    return {"generated": generated, "skipped": skipped, "failures": failures}


__all__ = ["ensure_procedural_bgm_tracks"]
