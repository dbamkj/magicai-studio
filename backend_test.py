"""Phase 3 verification — camera + effects engine end-to-end.

Tests A, B, C, D (procedural lipsync → camera+effects) + E regression.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests
from PIL import Image

BACKEND_URL = "https://creative-plan-engine.preview.emergentagent.com"
API = BACKEND_URL + "/api"

DEMO_CREATOR = {"email": "demo_creator@test.com", "password": "Test@123"}

LOG_PATH = "/var/log/supervisor/backend.err.log"

results: list[tuple[str, bool, str]] = []


def _log_size() -> int:
    try:
        return os.path.getsize(LOG_PATH)
    except Exception:
        return 0


def _read_log_tail(start_offset: int) -> str:
    try:
        with open(LOG_PATH, "rb") as f:
            f.seek(start_offset)
            return f.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return f"<log read failed: {e}>"


def login(creds: dict) -> tuple[str, dict]:
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    r.raise_for_status()
    j = r.json()
    return j["token"], j["user"]


def topup_if_needed(user_id: str, min_credits: int = 500) -> int:
    from pymongo import MongoClient
    for dbn in ("magicai_beta", "videoai_database"):
        try:
            c = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
            db = c[dbn]
            u = db.users.find_one({"id": user_id})
            if not u:
                continue
            bal = int(u.get("credits_balance") or 0)
            if bal < min_credits:
                db.users.update_one({"id": user_id},
                                    {"$set": {"credits_balance": 5000,
                                              "daily_usage": 0}})
                print(f"  [topup] {dbn}: {bal} -> 5000 credits on {user_id}")
                return 5000
            print(f"  [credits-ok] {dbn}: balance={bal}")
            return bal
        except Exception as e:
            print(f"  [topup err {dbn}]: {e}")
    return 0


def make_png(path: Path, w=512, h=768, color=(220, 180, 120)) -> Path:
    img = Image.new("RGB", (w, h), color)
    px = img.load()
    for (cx, cy) in [(int(w * 0.35), int(h * 0.35)), (int(w * 0.65), int(h * 0.35))]:
        for dy in range(-14, 15):
            for dx in range(-18, 19):
                if dx * dx + dy * dy * 2 < 300:
                    if 0 <= cy + dy < h and 0 <= cx + dx < w:
                        px[cx + dx, cy + dy] = (40, 40, 40)
    mx, my = int(w * 0.5), int(h * 0.62)
    for dy in range(-10, 11):
        for dx in range(-60, 61):
            if abs(dy) <= 6 and abs(dx) <= 50:
                if 0 <= my + dy < h and 0 <= mx + dx < w:
                    px[mx + dx, my + dy] = (150, 40, 40)
    img.save(path, "PNG")
    return path


def upload_image(token: str, path: Path) -> str:
    with open(path, "rb") as f:
        files = {"file": (path.name, f, "image/png")}
        r = requests.post(f"{API}/upload-image",
                          files=files,
                          headers={"Authorization": f"Bearer {token}"},
                          timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"upload-image failed {r.status_code}: {r.text[:200]}")
    j = r.json()
    return j.get("file_path") or j.get("url")


def poll_project(token: str, pid: str, timeout=120) -> dict:
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        r = requests.get(f"{API}/project/{pid}",
                         headers={"Authorization": f"Bearer {token}"},
                         timeout=20)
        if r.status_code == 200:
            j = r.json()
            last = j
            st = j.get("status")
            if st in ("completed", "failed"):
                return j
        time.sleep(2)
    return last or {"status": "timeout"}


def ffprobe_info(url_or_path: str) -> dict:
    if url_or_path.startswith("/api/") or url_or_path.startswith("http"):
        full = url_or_path if url_or_path.startswith("http") else BACKEND_URL + url_or_path
        r = requests.get(full, timeout=60)
        if r.status_code != 200:
            return {"err": f"download {r.status_code}"}
        tmp = Path("/tmp/_pcheck.mp4")
        tmp.write_bytes(r.content)
        size = len(r.content)
        p = tmp
    else:
        p = Path(url_or_path)
        size = p.stat().st_size if p.exists() else 0
    try:
        r = subprocess.run(
            ["/usr/bin/ffprobe", "-v", "error",
             "-select_streams", "v:0", "-show_entries",
             "stream=codec_name,width,height:format=duration",
             "-of", "json", str(p)],
            capture_output=True, timeout=15,
        )
        info = json.loads(r.stdout.decode() or "{}")
        s0 = (info.get("streams") or [{}])[0]
        dur = float((info.get("format") or {}).get("duration") or "0")
        vc = s0.get("codec_name")
        w = s0.get("width")
        h = s0.get("height")
    except Exception as e:
        return {"err": str(e), "size": size}
    try:
        r2 = subprocess.run(
            ["/usr/bin/ffprobe", "-v", "error",
             "-select_streams", "a:0", "-show_entries",
             "stream=codec_name", "-of", "default=nw=1:nk=1", str(p)],
            capture_output=True, timeout=10,
        )
        ac = (r2.stdout.decode() or "").strip() or None
    except Exception:
        ac = None
    return {"size": size, "vcodec": vc, "acodec": ac,
            "duration": dur, "width": w, "height": h}


def run_case_A(token: str, img_path: str) -> None:
    print("\n=== A) Solo procedural + cinematic preset ===")
    log0 = _log_size()
    body = {
        "image_path": img_path,
        "script": "🎬 Welcome to the cinematic test. Magic awaits.",
        "voice_id": "en-US-JennyNeural",
        "use_procedural_lipsync": True,
        "preset_id": "cinematic",
    }
    r = requests.post(f"{API}/create-talking-avatar",
                      headers={"Authorization": f"Bearer {token}"},
                      json=body, timeout=30)
    print(f"  POST status={r.status_code}")
    if r.status_code != 200:
        results.append(("A-create", False, f"{r.status_code}: {r.text[:200]}"))
        return
    pid = r.json().get("project_id")
    print(f"  project_id={pid}")
    res = poll_project(token, pid, timeout=120)
    st = res.get("status")
    result_url = res.get("result_url") or ""
    print(f"  final status={st}  result_url={result_url}")

    logs = _read_log_tail(log0)
    preset_applied = bool(re.search(
        r"talking: preset 'cinematic' applied \(voice_style=confident motion=ken_burns",
        logs))
    proc_ok = bool(re.search(r"talking: procedural lipsync OK → avatar_proc_[0-9a-f]+\.mp4",
                             logs))
    camera_line = bool(re.search(
        r"camera: motion=ken_burns effects=\['vignette', 'depth_of_field'\] duration=",
        logs))
    fx_applied = bool(re.search(
        r"talking: camera\+effects applied → avatar_proc_fx_[0-9a-f]+\.mp4 "
        r"\(motion=ken_burns effects=\['vignette', 'depth_of_field'\]\)",
        logs))
    print(f"  log: preset_applied={preset_applied} proc_ok={proc_ok} "
          f"camera={camera_line} fx_applied={fx_applied}")

    for patt, label in [
        (r"talking: preset 'cinematic' applied[^\n]*", "preset_applied"),
        (r"talking: procedural lipsync OK → avatar_proc_[0-9a-f]+\.mp4", "proc_ok"),
        (r"camera: motion=ken_burns effects=\['vignette', 'depth_of_field'\][^\n]*",
         "camera"),
        (r"talking: camera\+effects applied → avatar_proc_fx_[0-9a-f]+\.mp4[^\n]*",
         "fx"),
    ]:
        m = re.search(patt, logs)
        if m:
            print(f"    LOG[{label}]: {m.group(0)[:200]}")

    fx_in_url = "_fx_" in (result_url or "")
    probe = {}
    if result_url:
        probe = ffprobe_info(result_url)
        print(f"  ffprobe: {probe}")

    ok = (st == "completed"
          and preset_applied and proc_ok and camera_line and fx_applied
          and fx_in_url
          and probe.get("vcodec") == "h264"
          and probe.get("acodec") == "aac"
          and (probe.get("duration") or 0) > 3.0
          and (probe.get("size") or 0) > 50 * 1024)
    reason = (f"status={st} preset={preset_applied} proc={proc_ok} "
              f"cam={camera_line} fx={fx_applied} fx_in_url={fx_in_url} "
              f"probe={probe}")
    results.append(("A-cinematic-preset", ok, reason))


def run_case_B(token: str, img_path: str) -> None:
    print("\n=== B) Solo procedural + funny preset ===")
    log0 = _log_size()
    body = {
        "image_path": img_path,
        "script": "🎉 Haha this funny preset is wild! Let's go!",
        "voice_id": "en-US-JennyNeural",
        "use_procedural_lipsync": True,
        "preset_id": "funny",
    }
    r = requests.post(f"{API}/create-talking-avatar",
                      headers={"Authorization": f"Bearer {token}"},
                      json=body, timeout=30)
    if r.status_code != 200:
        results.append(("B-create", False, f"{r.status_code}: {r.text[:200]}"))
        return
    pid = r.json().get("project_id")
    print(f"  project_id={pid}")
    res = poll_project(token, pid, timeout=120)
    st = res.get("status")
    print(f"  final status={st}  result_url={res.get('result_url')}")
    logs = _read_log_tail(log0)

    camera_line = bool(re.search(
        r"camera: motion=ken_burns effects=\['shake', 'punch_in'\]", logs))
    fx_applied = bool(re.search(
        r"talking: camera\+effects applied → avatar_proc_fx_[0-9a-f]+\.mp4", logs))
    for patt, label in [
        (r"camera: motion=ken_burns effects=\['shake', 'punch_in'\][^\n]*", "camera"),
        (r"talking: camera\+effects applied → avatar_proc_fx_[0-9a-f]+\.mp4[^\n]*", "fx"),
    ]:
        m = re.search(patt, logs)
        if m:
            print(f"    LOG[{label}]: {m.group(0)[:200]}")
    print(f"  log: camera={camera_line} fx_applied={fx_applied}")
    ok = (st == "completed" and camera_line and fx_applied)
    results.append(("B-funny-preset", ok,
                    f"status={st} cam={camera_line} fx={fx_applied}"))


def run_case_C(token: str, img_path: str) -> None:
    print("\n=== C) Solo procedural — NO preset (no camera pass) ===")
    log0 = _log_size()
    body = {
        "image_path": img_path,
        "script": "Simple test without any preset.",
        "voice_id": "en-US-JennyNeural",
        "use_procedural_lipsync": True,
    }
    r = requests.post(f"{API}/create-talking-avatar",
                      headers={"Authorization": f"Bearer {token}"},
                      json=body, timeout=30)
    if r.status_code != 200:
        results.append(("C-create", False, f"{r.status_code}: {r.text[:200]}"))
        return
    pid = r.json().get("project_id")
    print(f"  project_id={pid}")
    res = poll_project(token, pid, timeout=120)
    st = res.get("status")
    result_url = res.get("result_url") or ""
    print(f"  final status={st}  result_url={result_url}")

    logs = _read_log_tail(log0)
    camera_present = bool(re.search(r"camera: motion=\w", logs))
    fx_in_url = "_fx_" in result_url
    base_proc_in_url = bool(re.search(r"avatar_proc_[0-9a-f]+\.mp4", result_url))
    print(f"  log: camera_present={camera_present} fx_in_url={fx_in_url} "
          f"base_proc_in_url={base_proc_in_url}")

    ok = (st == "completed" and not camera_present and not fx_in_url
          and base_proc_in_url)
    results.append(("C-no-preset", ok,
                    f"status={st} camera_present={camera_present} "
                    f"fx_in_url={fx_in_url} base_proc={base_proc_in_url}"))


def run_case_D(token: str) -> None:
    print("\n=== D) Dual procedural + cinematic preset ===")
    img_a = make_png(Path("/tmp/_speaker_a.png"), 512, 768, color=(210, 170, 130))
    img_b = make_png(Path("/tmp/_speaker_b.png"), 512, 768, color=(180, 140, 200))
    path_a = upload_image(token, img_a)
    path_b = upload_image(token, img_b)
    print(f"  img_a={path_a}\n  img_b={path_b}")

    log0 = _log_size()
    body = {
        "image_a_path": path_a,
        "image_b_path": path_b,
        "script": "A: Hello!\nB: Welcome!\nA: Let's go cinematic.",
        "voice_a_id": "hi-IN-MadhurNeural",
        "voice_b_id": "hi-IN-SwaraNeural",
        "motion": "none",
        "aspect_ratio": "16:9",
        "resolution": "480p",
        "use_procedural_lipsync": True,
        "preset_id": "cinematic",
    }
    r = requests.post(f"{API}/avatar/dual-lipsync",
                      headers={"Authorization": f"Bearer {token}"},
                      json=body, timeout=30)
    print(f"  POST status={r.status_code}")
    if r.status_code != 200:
        results.append(("D-dual-create", False,
                        f"{r.status_code}: {r.text[:300]}"))
        return
    pid = r.json().get("project_id")
    print(f"  project_id={pid}")
    res = poll_project(token, pid, timeout=180)
    st = res.get("status")
    result_url = res.get("result_url") or ""
    print(f"  final status={st}  result_url={result_url}")

    logs = _read_log_tail(log0)
    proc_ok = bool(re.search(r"dual: procedural lipsync OK", logs))
    camera_line = bool(re.search(
        r"camera: motion=ken_burns effects=\['vignette', 'depth_of_field'\]", logs))
    fx_applied = bool(re.search(
        r"dual: camera\+effects applied → dual_[0-9a-f]{8}_proc_fx\.mp4", logs))
    for patt, label in [
        (r"dual: procedural lipsync OK[^\n]*", "proc_ok"),
        (r"camera: motion=ken_burns effects=\['vignette', 'depth_of_field'\][^\n]*", "camera"),
        (r"dual: camera\+effects applied → dual_[0-9a-f]{8}_proc_fx\.mp4[^\n]*", "fx"),
    ]:
        m = re.search(patt, logs)
        if m:
            print(f"    LOG[{label}]: {m.group(0)[:200]}")
    print(f"  log: proc_ok={proc_ok} camera={camera_line} fx_applied={fx_applied}")
    ok = (st == "completed" and proc_ok and camera_line and fx_applied)
    results.append(("D-dual-cinematic", ok,
                    f"status={st} proc={proc_ok} cam={camera_line} fx={fx_applied}"))


def run_case_E(token: str) -> None:
    print("\n=== E) Quick regressions ===")
    r = requests.get(f"{API}/cinematic-presets",
                     headers={"Authorization": f"Bearer {token}"},
                     timeout=15)
    ok1 = r.status_code == 200
    presets = (r.json() or {}).get("presets", []) if ok1 else []
    ok1 = ok1 and len(presets) == 6
    print(f"  E1 cinematic-presets: {r.status_code} count={len(presets)}")
    results.append(("E1-cinematic-presets", ok1,
                    f"status={r.status_code} count={len(presets)}"))

    r2 = requests.post(f"{API}/avatar/detect-emotion",
                       headers={"Authorization": f"Bearer {token}"},
                       json={"text": "happy day! 😊"}, timeout=30)
    ok2 = r2.status_code == 200
    emo = (r2.json() or {}).get("emotion") if ok2 else None
    ok2 = ok2 and emo == "happy"
    print(f"  E2 detect-emotion: {r2.status_code} emotion={emo}")
    results.append(("E2-detect-emotion", ok2,
                    f"status={r2.status_code} emotion={emo}"))


def main():
    print("=== Phase 3 — Camera+Effects backend verification ===")
    print(f"Backend: {BACKEND_URL}")
    token, user = login(DEMO_CREATOR)
    print(f"Login: {user['email']} tier={user['subscription_tier']} "
          f"credits={user['credits_balance']}")
    topup_if_needed(user["id"], min_credits=500)

    img_local = make_png(Path("/tmp/_phase3_face.png"), 512, 768,
                         color=(230, 190, 140))
    img_path = upload_image(token, img_local)
    print(f"Uploaded image path: {img_path}")

    run_case_A(token, img_path)
    run_case_B(token, img_path)
    run_case_C(token, img_path)
    run_case_D(token)
    run_case_E(token)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, reason in results:
        mark = "✅" if ok else "❌"
        print(f"{mark} {name}: {reason}")
    print(f"\n{passed}/{total} passed")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
