"""
Sprint 30e — Re-test after 2 critical fixes:
  Fix 1: server.py:647 — Sarvam branch returns str(output_path)
  Fix 2: creator_pipeline.py — _enforce_image_query_nouns uses \\b regex

Tests:
  A) Krishna Bhajan E2E with Creator tier — verify has_voice=True + voice present in MP4
  B) Shiv Tandav stotram — image_query must NOT start with 'ram '
  C) Free user Hindi — auto Hindi voice swap, Edge-TTS (not Sarvam)
"""
import os
import sys
import time
import json
import re
import subprocess
import requests
from pathlib import Path

BASE_URL = "https://creative-plan-engine.preview.emergentagent.com"
API = f"{BASE_URL}/api"

# Backend log file
BACKEND_LOG = "/var/log/supervisor/backend.err.log"

# Track results
results = {"pass": [], "fail": []}


def record(name, ok, msg=""):
    bucket = "pass" if ok else "fail"
    results[bucket].append((name, msg))
    sym = "✅" if ok else "❌"
    print(f"  {sym} {name}: {msg}")


def get_recent_log_tail(n=400):
    try:
        out = subprocess.run(["tail", "-n", str(n), BACKEND_LOG], capture_output=True, text=True, timeout=5)
        return out.stdout
    except Exception:
        return ""


def get_log_since(marker_offset_bytes):
    """Return log content after the given byte offset."""
    try:
        with open(BACKEND_LOG, "rb") as f:
            f.seek(marker_offset_bytes)
            return f.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def log_size():
    try:
        return os.path.getsize(BACKEND_LOG)
    except Exception:
        return 0


def ffprobe_audio_rms(mp4_path):
    """Return RMS dB of audio track using ffmpeg astats."""
    try:
        r = subprocess.run(
            ["/usr/bin/ffmpeg", "-i", str(mp4_path), "-af", "astats=metadata=1:reset=0", "-f", "null", "-"],
            capture_output=True, text=True, timeout=60,
        )
        # ffmpeg writes to stderr
        out = r.stderr
        # Look for "RMS level dB:" — there are per-channel and Overall lines
        # Pick the highest (least negative) "RMS level dB" value (overall)
        rms_values = []
        for line in out.splitlines():
            m = re.search(r"RMS level dB:\s*(-?\d+\.\d+|-inf)", line)
            if m:
                v = m.group(1)
                if v == "-inf":
                    continue
                rms_values.append(float(v))
        if not rms_values:
            return None
        # Report the maximum (overall) RMS
        return max(rms_values)
    except Exception as e:
        print(f"  ffprobe error: {e}")
        return None


def poll_job(job_id, timeout=180):
    """Poll wizard job until completed or failed."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{API}/wizard/job/{job_id}", timeout=15)
            if r.status_code == 200:
                j = r.json()
                if j.get("status") in ("completed", "failed"):
                    return j
        except Exception as e:
            print(f"  poll err: {e}")
        time.sleep(3)
    return None


def test_a_krishna_bhajan_creator():
    print("\n=== TEST A: Krishna Bhajan E2E — Creator tier (Sarvam voice fix) ===")

    # Step 1: get prompts
    r = requests.post(f"{API}/wizard/prompts", json={"idea": "Krishna bhajan", "lang": "hindi"}, timeout=60)
    if r.status_code != 200:
        record("A1 prompts", False, f"HTTP {r.status_code} {r.text[:200]}")
        return None
    data = r.json()
    opts = data.get("options", [])
    if len(opts) < 1:
        record("A1 prompts", False, f"no options returned")
        return None
    opt = opts[0]
    record("A1 prompts", True, f"got {len(opts)} options; opt1.title={opt.get('title')!r}")

    # Show opt1 details
    print(f"     opt1.script (first 80): {(opt.get('script') or '')[:80]}")
    print(f"     opt1.image_query: {opt.get('image_query')}")
    print(f"     opt1.voice_style: {opt.get('voice_style')}, music_mood: {opt.get('music_mood')}")

    # Step 2: snapshot log offset BEFORE creating reel
    log_offset = log_size()

    # Step 3: create reel
    payload = {
        "idea": "Krishna bhajan",
        "title": opt.get("title") or "Krishna Bhajan",
        "script": opt.get("script") or "",
        "image_query": opt.get("image_query") or "krishna flute",
        "mode": "video",
        "total_duration": 10,
        "voice_id": "en-US-JennyNeural",  # will be auto-switched to Hindi
        "voice_style": opt.get("voice_style") or "devotional",
        "music_mood": opt.get("music_mood") or "devotional_peaceful",
        "motion": "auto",
        "aspect_ratio": "9:16",
        "duration_per_shot": 2.5,
        "user_tier": "creator",
        "lang": "hindi",
    }
    r = requests.post(f"{API}/wizard/create-reel", json=payload, timeout=30)
    if r.status_code != 200:
        record("A2 create-reel", False, f"HTTP {r.status_code} {r.text[:300]}")
        return None
    job_id = r.json().get("job_id")
    record("A2 create-reel", True, f"job_id={job_id}")

    # Step 4: poll
    job = poll_job(job_id, timeout=240)
    if job is None:
        record("A3 poll", False, "timeout, no terminal status")
        return None
    print(f"     job.status={job.get('status')} stage={job.get('stage')} progress={job.get('progress')}")
    print(f"     job.error={job.get('error')}")
    print(f"     job.has_voice={job.get('has_voice')} has_bgm={job.get('has_bgm')}")
    print(f"     job.result_url={job.get('result_url')}")

    # Step 5: assertions
    record("A3 status=completed", job.get("status") == "completed", f"actual={job.get('status')}")
    record("A4 has_voice=True (FIX 1)", job.get("has_voice") is True, f"actual={job.get('has_voice')}")

    # Read the log between start and now
    log_chunk = get_log_since(log_offset)
    has_route_log = "tts voice routed: tier=creator" in log_chunk and "chosen=sarvam:vidya" in log_chunk
    record("A5 log: routed creator→sarvam:vidya", has_route_log,
           "found" if has_route_log else "not found in log")

    has_sarvam_ok = "Sarvam TTS OK: speaker=vidya" in log_chunk
    record("A6 log: Sarvam TTS OK speaker=vidya", has_sarvam_ok,
           "found" if has_sarvam_ok else "not found in log")

    # Step 6: ffprobe MP4 audio RMS
    if job.get("result_url"):
        # path is /api/serve-file/wz_reel_<job_id>.mp4 — direct disk path
        fname = job["result_url"].split("/")[-1]
        mp4_path = Path(f"/app/backend/uploads/{fname}")
        if mp4_path.exists():
            size = mp4_path.stat().st_size
            print(f"     mp4 file size: {size} bytes")
            record("A7 file size > 500KB", size > 500_000, f"actual={size}")
            rms = ffprobe_audio_rms(mp4_path)
            print(f"     mp4 audio RMS: {rms} dB")
            record("A8 audio RMS > -25 dB (voice present)", rms is not None and rms > -25,
                   f"actual={rms} dB")
            return {"job": job, "mp4_path": mp4_path, "size": size, "rms": rms}
        else:
            record("A7 mp4 file exists", False, f"not found at {mp4_path}")
    else:
        record("A7 result_url present", False, "no result_url")
    return {"job": job}


def test_b_shiv_tandav_word_boundary():
    print("\n=== TEST B: Shiv Tandav stotram — word-boundary fix ===")
    r = requests.post(f"{API}/wizard/prompts", json={"idea": "Shiv Tandav stotram", "lang": "hinglish"}, timeout=60)
    if r.status_code != 200:
        record("B1 prompts", False, f"HTTP {r.status_code}")
        return
    opts = r.json().get("options", [])
    record("B1 got 3 opts", len(opts) == 3, f"count={len(opts)}")

    for i, o in enumerate(opts):
        iq = (o.get("image_query") or "").lower()
        print(f"     opt{i+1}.image_query: {iq!r}")
        # Bug fix verification: should NOT start with "ram " (or contain bare " ram " token)
        starts_with_ram = iq.startswith("ram ")
        record(f"B2.{i+1} image_query NOT starting with 'ram '", not starts_with_ram,
               f"starts_with_ram={starts_with_ram}, q={iq!r}")
        # Should contain 'shiva' or 'shiv' or 'mahadev' (word-boundary)
        has_shiva = bool(re.search(r"\b(shiva|shiv|mahadev)\b", iq))
        record(f"B3.{i+1} image_query contains shiva/shiv/mahadev", has_shiva,
               f"found={has_shiva}, q={iq!r}")


def test_c_free_user_hindi():
    print("\n=== TEST C: Free user Hindi — auto Hindi voice swap, Edge-TTS only ===")

    # Get prompts first to get a valid Hindi script
    r = requests.post(f"{API}/wizard/prompts", json={"idea": "Krishna bhajan", "lang": "hindi"}, timeout=60)
    if r.status_code != 200:
        record("C1 prompts", False, f"HTTP {r.status_code}")
        return
    opt = r.json().get("options", [{}])[0]

    log_offset = log_size()

    payload = {
        "idea": "Krishna bhajan",
        "title": opt.get("title") or "Krishna Bhajan",
        "script": opt.get("script") or "",
        "image_query": opt.get("image_query") or "krishna flute",
        "mode": "video",
        "total_duration": 10,
        "voice_id": "en-US-JennyNeural",  # will auto-switch to Hindi
        "voice_style": opt.get("voice_style") or "devotional",
        "music_mood": opt.get("music_mood") or "devotional_peaceful",
        "motion": "auto",
        "aspect_ratio": "9:16",
        "duration_per_shot": 2.5,
        "user_tier": "free",
        "lang": "hindi",
    }
    r = requests.post(f"{API}/wizard/create-reel", json=payload, timeout=30)
    if r.status_code != 200:
        record("C2 create-reel", False, f"HTTP {r.status_code} {r.text[:200]}")
        return
    job_id = r.json().get("job_id")
    record("C2 create-reel", True, f"job_id={job_id}")

    job = poll_job(job_id, timeout=240)
    if job is None:
        record("C3 poll", False, "timeout")
        return
    print(f"     job.status={job.get('status')} has_voice={job.get('has_voice')} has_bgm={job.get('has_bgm')}")
    print(f"     job.result_url={job.get('result_url')} error={job.get('error')}")

    record("C3 status=completed", job.get("status") == "completed", f"actual={job.get('status')}")
    record("C4 has_voice=True", job.get("has_voice") is True, f"actual={job.get('has_voice')}")

    log_chunk = get_log_since(log_offset)

    has_auto_switch = "auto-switched voice to Hindi hi-IN-MadhurNeural for lang=hindi" in log_chunk
    record("C5 log: auto-switched voice → hi-IN-MadhurNeural", has_auto_switch,
           "found" if has_auto_switch else "not found")

    # Should see "tts voice routed: tier=free requested=hi-IN-MadhurNeural → chosen=hi-IN-Madhur*"
    has_free_route = bool(re.search(
        r"tts voice routed:\s*tier=free\s+requested=hi-IN-MadhurNeural\s*→\s*chosen=hi-IN-Madhur",
        log_chunk
    ))
    record("C6 log: routed free→hi-IN-Madhur* (Edge, NOT sarvam)", has_free_route,
           "found" if has_free_route else "not found")

    # Should NOT route to sarvam for free
    sarvam_in_route = bool(re.search(r"tts voice routed:\s*tier=free.*chosen=sarvam:", log_chunk))
    record("C7 free user NOT routed to Sarvam", not sarvam_in_route,
           f"sarvam_in_route={sarvam_in_route}")

    if job.get("result_url"):
        fname = job["result_url"].split("/")[-1]
        mp4_path = Path(f"/app/backend/uploads/{fname}")
        if mp4_path.exists():
            size = mp4_path.stat().st_size
            rms = ffprobe_audio_rms(mp4_path)
            print(f"     mp4 size={size}, RMS={rms} dB")
            record("C8 audio RMS > -25 dB (voice present)", rms is not None and rms > -25,
                   f"actual={rms} dB")
            return {"size": size, "rms": rms}
    return None


def main():
    print(f"BASE_URL = {BASE_URL}")
    # Health
    try:
        r = requests.get(f"{API}/", timeout=10)
        print(f"  /api/ → {r.status_code}")
    except Exception as e:
        print(f"  health err: {e}")
        sys.exit(1)

    a = test_a_krishna_bhajan_creator()
    test_b_shiv_tandav_word_boundary()
    c = test_c_free_user_hindi()

    print("\n" + "=" * 60)
    print(f"PASS: {len(results['pass'])}")
    print(f"FAIL: {len(results['fail'])}")
    if results["fail"]:
        print("\n❌ FAILURES:")
        for n, m in results["fail"]:
            print(f"  - {n}: {m}")
    print("\nKey ffprobe RMS values:")
    if a and "rms" in a:
        print(f"  Creator (A) RMS: {a['rms']} dB, size={a.get('size')}B")
    if c and "rms" in c:
        print(f"  Free    (C) RMS: {c['rms']} dB, size={c.get('size')}B")

    sys.exit(0 if not results["fail"] else 1)


if __name__ == "__main__":
    main()
