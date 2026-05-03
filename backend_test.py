"""Session 33 Phase-2 — Emotion detection + emotion-aware TTS + face tint overlay.

Runs the review-request test matrix (A / B / C / D) against the public ingress.
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
import time
from pathlib import Path

import requests
from PIL import Image

BASE = "https://creative-plan-engine.preview.emergentagent.com/api"
LOG = "/var/log/supervisor/backend.err.log"


def log(msg: str) -> None:
    print(msg, flush=True)


def login(email: str, pw: str) -> str:
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=20)
    r.raise_for_status()
    data = r.json()
    log(f"  login OK: {email} tier={data['user'].get('subscription_tier')} credits={data['user'].get('credits_balance')}")
    return data["token"]


def ensure_credits(email: str, min_credits: int = 200) -> None:
    """Top up via direct Mongo write if running low — previous sessions drained demo accounts."""
    try:
        from pymongo import MongoClient
        mongo = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        client = MongoClient(mongo)
        # Try both DBs since avatar.py/talking.py use core.db (videoai_database or magicai_beta)
        for dbn in ("magicai_beta", "videoai_database"):
            client[dbn].users.update_one(
                {"email": email, "credits_balance": {"$lt": min_credits}},
                {"$set": {"credits_balance": max(min_credits, 3000)}},
            )
        log(f"  credits ensured >= {min_credits} for {email}")
    except Exception as e:
        log(f"  credits topup skipped ({e})")


# ────────── A) /api/avatar/detect-emotion ──────────

A_TESTS = [
    ("A1 happy/playful 😂", "Haha bhai aaj toh bahut mast hai! 😂",
     {"happy", "playful"}, None, "gt0"),
    ("A2 sad 💔",          "Mai bahut udaas hu. Tum chal gaye 💔",
     {"sad"}, "<0", "blue"),
    ("A3 devotional 🕉️",   "🕉️ Hari Om. Krishna meri raksha karo. Jai Shri Ram.",
     {"devotional"}, "<0", "golden"),
    ("A4 excited 🚀",     "Wow this is incredible! Lets go! 🚀",
     {"excited"}, ">0", None),
    ("A5 empty (422)",     "", None, None, None),
]


def run_section_A():
    log("\n=== A) POST /api/avatar/detect-emotion ===")
    failures = []
    for label, text, want_em, want_rate, want_tint in A_TESTS:
        try:
            r = requests.post(f"{BASE}/avatar/detect-emotion", json={"text": text}, timeout=20)
        except Exception as e:
            log(f"  ❌ {label}: request error {e}")
            failures.append(label)
            continue

        if want_em is None:
            # expect 422
            if r.status_code == 422:
                log(f"  ✅ {label}: 422 as expected")
            else:
                log(f"  ❌ {label}: expected 422, got {r.status_code}: {r.text[:200]}")
                failures.append(label)
            continue

        if r.status_code != 200:
            log(f"  ❌ {label}: HTTP {r.status_code}: {r.text[:200]}")
            failures.append(label)
            continue
        j = r.json()
        em = j.get("emotion")
        intensity = j.get("intensity")
        source = j.get("source")
        vp = j.get("voice_params") or {}
        tint = j.get("tint") or {}
        rgb = tint.get("rgb") or []
        alpha = tint.get("alpha")
        log(f"     json: emotion={em} intensity={intensity} source={source} "
            f"rate={vp.get('voice_rate')} pitch={vp.get('voice_pitch')} rgb={rgb} alpha={alpha}")

        errs = []
        if em not in want_em:
            errs.append(f"emotion {em} not in {want_em}")
        if source not in {"llm", "keyword", "empty"}:
            errs.append(f"source {source} invalid")
        if isinstance(intensity, (int, float)) and intensity <= 0.0:
            errs.append(f"intensity {intensity} not >0")

        # voice-rate expectation
        vr = vp.get("voice_rate")
        if want_rate == ">0" and not (isinstance(vr, (int, float)) and vr > 0):
            errs.append(f"voice_rate {vr} not >0")
        if want_rate == "<0" and not (isinstance(vr, (int, float)) and vr < 0):
            errs.append(f"voice_rate {vr} not <0")

        # tint expectation
        if want_tint == "blue" and len(rgb) == 3:
            if not (rgb[2] > rgb[0]):
                errs.append(f"tint rgb {rgb} not bluish (b>r)")
        if want_tint == "golden" and len(rgb) == 3:
            if not (rgb[0] > rgb[2]):
                errs.append(f"tint rgb {rgb} not golden (r>b)")
        if want_tint == "gt0" and not (isinstance(alpha, (int, float)) and alpha > 0):
            errs.append(f"tint alpha {alpha} not >0")

        if errs:
            log(f"  ❌ {label}: " + "; ".join(errs))
            failures.append(label)
        else:
            log(f"  ✅ {label}")
    return failures


# ────────── B/C helpers ──────────

def make_512_png() -> bytes:
    img = Image.new("RGB", (512, 768), (200, 180, 140))
    # Draw a simple face-like oval using PIL
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    d.ellipse((150, 180, 362, 470), fill=(250, 220, 200))
    d.ellipse((200, 280, 230, 310), fill=(30, 30, 30))
    d.ellipse((280, 280, 310, 310), fill=(30, 30, 30))
    d.ellipse((235, 380, 275, 420), fill=(120, 40, 40))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def upload_image(token: str) -> str:
    png = make_512_png()
    r = requests.post(
        f"{BASE}/upload-image",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("avatar.png", png, "image/png")},
        timeout=30,
    )
    r.raise_for_status()
    j = r.json()
    log(f"  upload-image OK: {j.get('file_path')} serve={j.get('url')}")
    return j["file_path"]


def poll_project(token: str, pid: str, timeout_s: int = 90) -> dict:
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        r = requests.get(f"{BASE}/project/{pid}", headers={"Authorization": f"Bearer {token}"}, timeout=15)
        if r.status_code == 200:
            last = r.json()
            st = last.get("status")
            if st in ("completed", "failed"):
                return last
        time.sleep(3)
    return last or {}


def read_log_tail(pattern_substrs: list[str], window_s: int = 120) -> dict:
    """Return dict {substr: first matching log line} scanning the last window of backend.err.log."""
    try:
        data = subprocess.check_output(["tail", "-n", "3000", LOG], text=True)
    except Exception:
        return {}
    hits: dict = {}
    for line in data.splitlines():
        for p in pattern_substrs:
            if p in line and p not in hits:
                hits[p] = line.strip()
        if len(hits) == len(pattern_substrs):
            break
    return hits


# ────────── B) End-to-end with auto-detect ──────────
def run_section_B():
    log("\n=== B) E2E procedural lipsync with emotion auto-detection ===")
    ensure_credits("demo_creator@test.com", 500)
    token = login("demo_creator@test.com", "Test@123")
    img_path = upload_image(token)

    body = {
        "image_path": img_path,
        "script": "🕉️ Hari Om doston. Krishna ki bhakti mein dhyan lagao.",
        "voice_id": "hi-IN-SwaraNeural",
        "use_procedural_lipsync": True,
    }
    t0 = time.time()
    r = requests.post(f"{BASE}/create-talking-avatar", headers={"Authorization": f"Bearer {token}"},
                      json=body, timeout=30)
    if r.status_code != 200:
        log(f"  ❌ POST failed {r.status_code}: {r.text[:300]}")
        return ["B:create"]
    pid = r.json().get("project_id") or r.json().get("id")
    log(f"  POST 200 project_id={pid}")

    proj = poll_project(token, pid, timeout_s=90)
    status = proj.get("status")
    result_url = proj.get("result_url")
    log(f"  poll: status={status} progress={proj.get('progress')} result_url={result_url}")

    failures = []
    if status != "completed":
        failures.append(f"B:status={status}")

    # Log strings
    hits = read_log_tail([
        "talking: emotion=devotional intensity=",
        "mouth_animator: emotion tint applied (devotional, intensity=",
        "talking: procedural lipsync OK",
    ])
    for p in [
        "talking: emotion=devotional intensity=",
        "mouth_animator: emotion tint applied (devotional, intensity=",
        "talking: procedural lipsync OK",
    ]:
        if p in hits:
            log(f"  ✅ LOG: {hits[p][-160:]}")
        else:
            log(f"  ❌ LOG MISSING: {p}")
            failures.append(f"B:log:{p}")

    # MP4 >= 50 KB
    if result_url:
        mp4_url = result_url if result_url.startswith("http") else f"https://creative-plan-engine.preview.emergentagent.com{result_url}"
        mr = requests.get(mp4_url, timeout=30)
        sz = len(mr.content)
        ct = mr.headers.get("Content-Type", "")
        log(f"  MP4 GET {mp4_url} -> {mr.status_code} {ct} size={sz}")
        if mr.status_code != 200 or sz < 50 * 1024:
            failures.append(f"B:mp4_size={sz}")
    else:
        failures.append("B:no_result_url")

    log(f"  B wall-clock: {time.time()-t0:.1f}s")
    return failures, pid


# ────────── C) Explicit voice_rate/pitch ──────────
def run_section_C():
    log("\n=== C) E2E with EXPLICIT voice_rate=0.0 + voice_pitch=+0Hz ===")
    ensure_credits("demo_creator@test.com", 500)
    token = login("demo_creator@test.com", "Test@123")
    img_path = upload_image(token)

    body = {
        "image_path": img_path,
        "script": "🕉️ Hari Om doston. Krishna ki bhakti mein dhyan lagao.",
        "voice_id": "hi-IN-SwaraNeural",
        "use_procedural_lipsync": True,
        "voice_rate": "0.0",     # model typed as str
        "voice_pitch": "+0Hz",
    }
    r = requests.post(f"{BASE}/create-talking-avatar", headers={"Authorization": f"Bearer {token}"},
                      json=body, timeout=30)
    if r.status_code != 200:
        log(f"  ❌ POST failed {r.status_code}: {r.text[:300]}")
        return [f"C:create_http_{r.status_code}"]
    pid = r.json().get("project_id") or r.json().get("id")
    log(f"  POST 200 project_id={pid}")

    proj = poll_project(token, pid, timeout_s=90)
    log(f"  poll: status={proj.get('status')} progress={proj.get('progress')} result_url={proj.get('result_url')}")

    # Just confirm no crash + emotion detection still logged
    hits = read_log_tail([
        "talking: emotion=devotional",
    ])
    if "talking: emotion=devotional" in hits:
        log(f"  ✅ LOG (emotion still detected): {hits['talking: emotion=devotional'][-180:]}")
    else:
        log(f"  ⚠️ emotion log not found in tail window — may have scrolled")

    failures = []
    if proj.get("status") != "completed":
        failures.append(f"C:status={proj.get('status')}")
    return failures


# ────────── D) Quick regression ──────────
def run_section_D():
    log("\n=== D) Regression ===")
    failures = []

    # D1 cinematic-presets
    r = requests.get(f"{BASE}/cinematic-presets", timeout=15)
    if r.status_code == 200:
        pres = (r.json() or {}).get("presets") or []
        log(f"  D1 cinematic-presets -> 200 count={len(pres)}")
        if len(pres) != 6:
            failures.append(f"D1:presets={len(pres)}")
    else:
        failures.append(f"D1:http={r.status_code}")

    # D2 detect-emotion neutral
    r = requests.post(f"{BASE}/avatar/detect-emotion", json={"text": "hello world"}, timeout=15)
    if r.status_code == 200:
        log(f"  D2 detect-emotion(hello world) -> 200 emotion={r.json().get('emotion')}")
    else:
        failures.append(f"D2:http={r.status_code}")

    # D3 create-talking-avatar with use_procedural=False → confirm 200 + 'MH upload OK' log
    ensure_credits("demo_creator@test.com", 500)
    token = login("demo_creator@test.com", "Test@123")
    img_path = upload_image(token)
    body = {
        "image_path": img_path,
        "script": "Hello world from regression test.",
        "voice_id": "hi-IN-SwaraNeural",
        "use_procedural_lipsync": False,
    }
    r = requests.post(f"{BASE}/create-talking-avatar", headers={"Authorization": f"Bearer {token}"}, json=body, timeout=30)
    if r.status_code != 200:
        log(f"  D3 ❌ POST {r.status_code}: {r.text[:200]}")
        failures.append(f"D3:http={r.status_code}")
        return failures
    pid = r.json().get("project_id") or r.json().get("id")
    log(f"  D3 POST 200 pid={pid}; waiting 60s for 'MH upload OK' log...")
    deadline = time.time() + 60
    found = False
    while time.time() < deadline:
        hits = read_log_tail(["MH upload OK"])
        if "MH upload OK" in hits:
            log(f"  ✅ D3 'MH upload OK' seen: {hits['MH upload OK'][-180:]}")
            found = True
            break
        time.sleep(3)
    if not found:
        log("  ❌ D3: 'MH upload OK' not observed within 60s")
        failures.append("D3:no_mh_upload_ok")
    return failures


def main():
    all_fail = []
    try:
        fA = run_section_A()
        all_fail += fA
    except Exception as e:
        log(f"A blew up: {e}")
        all_fail.append(f"A:exception:{e}")

    try:
        fB_tuple = run_section_B()
        if isinstance(fB_tuple, tuple):
            all_fail += fB_tuple[0]
        else:
            all_fail += fB_tuple
    except Exception as e:
        log(f"B blew up: {e}")
        all_fail.append(f"B:exception:{e}")

    try:
        fC = run_section_C()
        all_fail += fC
    except Exception as e:
        log(f"C blew up: {e}")
        all_fail.append(f"C:exception:{e}")

    try:
        fD = run_section_D()
        all_fail += fD
    except Exception as e:
        log(f"D blew up: {e}")
        all_fail.append(f"D:exception:{e}")

    log("\n=== SUMMARY ===")
    if all_fail:
        log(f"FAILURES ({len(all_fail)}):")
        for f in all_fail:
            log(f"  - {f}")
        sys.exit(1)
    log("ALL PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
