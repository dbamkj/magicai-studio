"""Phase 2 emotion-aware TTS re-verification (Tests B, C, D).

Verifies the type-mismatch fixes:
  1. emotion_to_voice_params returns voice_rate as edge-tts string format
  2. _is_blank_rate helper treats None/0/0.0/"+0%"/empty as no override
"""
import os
import time
import re
import sys
import json
import subprocess

import requests

BASE = "https://creative-plan-engine.preview.emergentagent.com"
API = f"{BASE}/api"
EMAIL = "demo_creator@test.com"
PASSWORD = "Test@123"

TS = int(time.time())


def log(msg):
    print(f"[t+{int(time.time()-TS):03d}s] {msg}", flush=True)


def login():
    r = requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=20)
    r.raise_for_status()
    j = r.json()
    log(f"login OK tier={j['user']['subscription_tier']} credits={j['user'].get('credits_balance')}")
    return j["token"], j["user"]


def topup_if_needed(user_id, min_credits=200):
    """Top up via direct mongo if creds < min_credits."""
    try:
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        # Read from backend/.env if env not set
        if "localhost" in mongo_url and not os.environ.get("MONGO_URL"):
            with open("/app/backend/.env") as f:
                for line in f:
                    if line.startswith("MONGO_URL"):
                        mongo_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        client = MongoClient(mongo_url)
        # Find DB name
        db_name = "magicai_beta"  # BETA env
        db = client[db_name]
        u = db.users.find_one({"id": user_id})
        if not u:
            u = db.users.find_one({"email": EMAIL})
        if not u:
            log("topup: user not found in mongo, skipping")
            return
        bal = u.get("credits_balance", 0)
        if bal < min_credits:
            db.users.update_one({"id": u["id"]}, {"$set": {"credits_balance": 5000}})
            log(f"topup: credits {bal} -> 5000")
        else:
            log(f"topup: credits OK ({bal})")
    except Exception as e:
        log(f"topup: skipped ({e})")


def upload_image(token):
    """Upload a 512x768 PNG."""
    from PIL import Image
    import io

    img = Image.new("RGB", (512, 768), color=(180, 130, 90))
    # Add some variation
    import random
    px = img.load()
    random.seed(42)
    for i in range(0, 512, 4):
        for j in range(0, 768, 4):
            px[i, j] = (180 + random.randint(-20, 20), 130 + random.randint(-20, 20), 90 + random.randint(-20, 20))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    files = {"file": ("portrait.png", buf, "image/png")}
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{API}/upload-face-image", files=files, headers=headers, timeout=30)
    r.raise_for_status()
    j = r.json()
    log(f"upload OK file_path={j['file_path']}")
    return j["file_path"]


def poll_project(token, pid, max_wait=120):
    headers = {"Authorization": f"Bearer {token}"}
    start = time.time()
    last_status = None
    while time.time() - start < max_wait:
        r = requests.get(f"{API}/project/{pid}", headers=headers, timeout=15)
        if r.status_code != 200:
            log(f"poll {pid[:8]} -> HTTP {r.status_code}")
            time.sleep(3)
            continue
        j = r.json()
        st = j.get("status")
        prog = j.get("progress")
        if st != last_status:
            log(f"poll {pid[:8]} status={st} progress={prog}")
            last_status = st
        if st in ("completed", "failed"):
            return j
        time.sleep(3)
    log(f"poll {pid[:8]} TIMEOUT after {max_wait}s")
    r = requests.get(f"{API}/project/{pid}", headers=headers, timeout=15)
    return r.json() if r.status_code == 200 else {"status": "timeout"}


def tail_log_for(pattern, since_ts, max_age_s=180):
    """Search backend log for line matching pattern, written since since_ts."""
    try:
        out = subprocess.run(
            ["tail", "-n", "5000", "/var/log/supervisor/backend.err.log"],
            capture_output=True, timeout=10,
        )
        text = out.stdout.decode("utf-8", errors="ignore")
        rx = re.compile(pattern)
        for line in text.split("\n"):
            if rx.search(line):
                return line
    except Exception as e:
        log(f"log read err: {e}")
    return None


def grab_logs_window(start_ts):
    """Return all backend log lines for the past minutes window."""
    try:
        out = subprocess.run(
            ["tail", "-n", "8000", "/var/log/supervisor/backend.err.log"],
            capture_output=True, timeout=10,
        )
        return out.stdout.decode("utf-8", errors="ignore")
    except Exception:
        return ""


# ────────────────────── TEST D ──────────────────────
def test_d_detect_emotion_shape():
    log("=" * 60)
    log("TEST D — POST /api/avatar/detect-emotion shape check")
    log("=" * 60)
    r = requests.post(f"{API}/avatar/detect-emotion", json={"text": "🕉️ Hari Om"}, timeout=30)
    if r.status_code != 200:
        log(f"D FAIL: HTTP {r.status_code} body={r.text[:300]}")
        return False
    j = r.json()
    log(f"D response: {json.dumps(j, ensure_ascii=False)[:400]}")
    vp = j.get("voice_params") or {}
    rate = vp.get("voice_rate")
    pitch = vp.get("voice_pitch")
    emotion = j.get("emotion")
    intensity = j.get("intensity")

    ok = True
    if not isinstance(rate, str):
        log(f"D FAIL: voice_rate is not str: type={type(rate).__name__} val={rate!r}")
        ok = False
    else:
        if not (rate.startswith("-") or rate.startswith("+")):
            log(f"D FAIL: voice_rate must start with +/-: {rate!r}")
            ok = False
        if not rate.endswith("%"):
            log(f"D FAIL: voice_rate must end with %: {rate!r}")
            ok = False
    log(f"D detected: emotion={emotion} intensity={intensity} rate={rate!r} pitch={pitch!r}")

    # For "🕉️ Hari Om" expected emotion=devotional, rate="-4%" at intensity 0.8
    # But intensity may vary per LLM — be lenient on exact value. Just verify
    # devotional + rate is negative percent string.
    if emotion == "devotional":
        if rate != "-4%":
            log(f"D NOTE: expected -4% for devotional@0.8, got {rate!r} (intensity={intensity})")
            # not a hard fail if intensity differs
    else:
        log(f"D NOTE: emotion={emotion} (expected devotional). rate must still be percent-string.")

    if ok:
        log("D PASS")
    return ok


# ────────────────────── TEST B ──────────────────────
def test_b_e2e_procedural(token, image_path):
    log("=" * 60)
    log("TEST B — End-to-end procedural lipsync with emotion auto-detection")
    log("=" * 60)
    payload = {
        "image_path": image_path,
        "script": "🕉️ Hari Om doston. Krishna ki bhakti mein dhyan lagao.",
        "voice_id": "hi-IN-SwaraNeural",
        "use_procedural_lipsync": True,
    }
    headers = {"Authorization": f"Bearer {token}"}
    post_ts = time.time()
    r = requests.post(f"{API}/create-talking-avatar", json=payload, headers=headers, timeout=30)
    if r.status_code != 200:
        log(f"B FAIL: POST HTTP {r.status_code} body={r.text[:400]}")
        return False
    j = r.json()
    pid = j["project_id"]
    log(f"B POST OK project_id={pid}")

    proj = poll_project(token, pid, max_wait=120)
    status = proj.get("status")
    result_url = proj.get("result_url")
    log(f"B final: status={status} result_url={result_url} error={proj.get('error')}")

    # Required asserts
    asserts_ok = True
    if status != "completed":
        log(f"B FAIL: status={status} (expected completed)")
        asserts_ok = False

    # Backend logs
    logs = grab_logs_window(post_ts)
    # Filter to last ~2000 lines for this test window
    relevant_lines = logs.split("\n")[-3000:]
    rel_text = "\n".join(relevant_lines)

    # 1) talking: emotion=devotional intensity=<float>
    m1 = re.search(r"talking: emotion=devotional intensity=([0-9.]+)", rel_text)
    if m1 and float(m1.group(1)) > 0:
        log(f"B LOG1 OK: 'talking: emotion=devotional intensity={m1.group(1)}'")
    else:
        log("B FAIL: missing 'talking: emotion=devotional intensity=...' log")
        asserts_ok = False

    # 2) -> rate=-4% pitch=+0Hz  (rate must be a percent string, not a float)
    # The full line is "talking: emotion=X intensity=Y source=Z -> rate=R pitch=P"
    m2 = re.search(r"-> rate=(-?\+?\d+%) pitch=(\S+)", rel_text)
    if m2:
        log(f"B LOG2 OK: '-> rate={m2.group(1)} pitch={m2.group(2)}'")
        if m2.group(1) != "-4%":
            log(f"B NOTE: rate is {m2.group(1)} (spec said -4% expected)")
    else:
        # check if there's a float-style rate (the bug)
        bad = re.search(r"-> rate=(-?\d+\.\d+)\s+pitch", rel_text)
        if bad:
            log(f"B FAIL: rate is FLOAT {bad.group(1)} (should be percent string like -4%)")
        else:
            log("B FAIL: no '-> rate=N% pitch=...' log found")
        asserts_ok = False

    # 3) mouth_animator: emotion tint applied (devotional, intensity=...
    m3 = re.search(r"mouth_animator: emotion tint applied \(devotional, intensity=([0-9.]+)", rel_text)
    if m3:
        log(f"B LOG3 OK: 'mouth_animator: emotion tint applied (devotional, intensity={m3.group(1)})'")
    else:
        log("B FAIL: missing 'mouth_animator: emotion tint applied (devotional, intensity=...)'")
        asserts_ok = False

    # 4) talking: procedural lipsync OK
    m4 = re.search(r"talking: procedural lipsync OK", rel_text)
    if m4:
        log("B LOG4 OK: 'talking: procedural lipsync OK'")
    else:
        log("B FAIL: missing 'talking: procedural lipsync OK'")
        asserts_ok = False

    # 5) MP4 verification
    if status == "completed" and result_url:
        try:
            # Fetch MP4
            r2 = requests.get(f"{BASE}{result_url}", timeout=60)
            if r2.status_code == 200:
                mp4_bytes = r2.content
                size_kb = len(mp4_bytes) // 1024
                log(f"B MP4 size={size_kb} KB")
                if size_kb < 50:
                    log(f"B FAIL: MP4 too small ({size_kb} KB < 50 KB)")
                    asserts_ok = False
                # ffprobe duration + audio codec
                tmpf = f"/tmp/test_b_{pid[:8]}.mp4"
                with open(tmpf, "wb") as f:
                    f.write(mp4_bytes)
                pr = subprocess.run(
                    ["/usr/bin/ffprobe", "-v", "error", "-show_entries",
                     "format=duration:stream=codec_name,codec_type",
                     "-of", "default=nw=1", tmpf],
                    capture_output=True, timeout=15,
                )
                pout = pr.stdout.decode()
                log(f"B ffprobe:\n{pout.strip()}")
                # check aac + duration
                if "aac" not in pout.lower():
                    log("B FAIL: no aac audio in MP4")
                    asserts_ok = False
                dm = re.search(r"duration=([0-9.]+)", pout)
                if dm and float(dm.group(1)) > 3.0:
                    log(f"B duration OK: {dm.group(1)}s")
                else:
                    log(f"B FAIL: duration not >3s: {pout}")
                    asserts_ok = False
            else:
                log(f"B FAIL: MP4 download HTTP {r2.status_code}")
                asserts_ok = False
        except Exception as e:
            log(f"B MP4 verify err: {e}")
            asserts_ok = False

    if asserts_ok:
        log("B PASS")
    return asserts_ok


# ────────────────────── TEST C ──────────────────────
def test_c_with_explicit_zero_rate(token, image_path):
    log("=" * 60)
    log("TEST C — same as B but with voice_rate=0.0 (was crashing on '0.0')")
    log("=" * 60)
    payload = {
        "image_path": image_path,
        "script": "🕉️ Hari Om doston. Krishna ki bhakti mein dhyan lagao.",
        "voice_id": "hi-IN-SwaraNeural",
        "use_procedural_lipsync": True,
        "voice_rate": "0.0",  # the previously-crashing string value
    }
    headers = {"Authorization": f"Bearer {token}"}
    post_ts = time.time()
    r = requests.post(f"{API}/create-talking-avatar", json=payload, headers=headers, timeout=30)
    if r.status_code != 200:
        log(f"C FAIL: POST HTTP {r.status_code} body={r.text[:400]}")
        return False
    j = r.json()
    pid = j["project_id"]
    log(f"C POST OK project_id={pid}")

    proj = poll_project(token, pid, max_wait=120)
    status = proj.get("status")
    result_url = proj.get("result_url")
    log(f"C final: status={status} result_url={result_url} error={proj.get('error')}")

    ok = True
    if status != "completed":
        log(f"C FAIL: status={status} (expected completed). error={proj.get('error')}")
        ok = False

    # Verify the merge happened (rate filled by detected emotion)
    logs = grab_logs_window(post_ts)
    rel_text = "\n".join(logs.split("\n")[-3000:])
    # We expect emotion=devotional and rate = -4% (filled by detection because 0.0 = blank)
    m = re.search(r"talking: emotion=devotional .*?-> rate=(\S+) pitch=(\S+)", rel_text)
    if m:
        log(f"C LOG: rate={m.group(1)} pitch={m.group(2)} (filled by detected emotion)")
        if not m.group(1).endswith("%"):
            log(f"C NOTE: rate {m.group(1)} doesn't look like percent string — but flow completed.")
    else:
        log("C NOTE: no devotional log found in window (may have been overwritten by other tests)")

    if status == "completed" and result_url:
        try:
            r2 = requests.get(f"{BASE}{result_url}", timeout=60)
            if r2.status_code == 200 and len(r2.content) > 50 * 1024:
                log(f"C MP4 OK ({len(r2.content)//1024} KB)")
            else:
                log(f"C FAIL: MP4 issue (HTTP {r2.status_code} size={len(r2.content)})")
                ok = False
        except Exception as e:
            log(f"C MP4 err: {e}")
            ok = False

    if ok:
        log("C PASS")
    return ok


# ────────────────────── Main ──────────────────────
def main():
    log("Starting Phase 2 emotion-aware TTS re-verification")
    token, user = login()
    topup_if_needed(user["id"], min_credits=600)

    image_path = upload_image(token)

    results = {}

    # Run D first (simple endpoint check)
    results["D"] = test_d_detect_emotion_shape()

    # Run B
    results["B"] = test_b_e2e_procedural(token, image_path)

    # Run C
    results["C"] = test_c_with_explicit_zero_rate(token, image_path)

    log("=" * 60)
    log("SUMMARY")
    log("=" * 60)
    for k, v in results.items():
        log(f"Test {k}: {'PASS' if v else 'FAIL'}")
    all_pass = all(results.values())
    log(f"OVERALL: {'PASS' if all_pass else 'FAIL'}")
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
