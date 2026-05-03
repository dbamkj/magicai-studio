"""Session 33 r2 — verify BGM mood matching fix end-to-end.

Tests:
  A) Direct import smoke-test for random_for_mood
  B) /api/create-talking-avatar with bgm_style='cinematic_epic' →
     log line "talking: BGM mixed (cinematic_score) under voice"
  C) Same with bgm_style='devotional' → "talking: BGM mixed (ambient_calm)..."
  D) Regression sweep
"""
from __future__ import annotations
import json, pathlib, subprocess, sys, time
from typing import Optional

import httpx
from PIL import Image, ImageDraw

BACKEND_URL = "https://creative-plan-engine.preview.emergentagent.com"
API = f"{BACKEND_URL}/api"
EMAIL = "demo_creator@test.com"
PASSWORD = "Test@123"
LOG_FILE = "/var/log/supervisor/backend.err.log"


def ok(msg: str): print(f"\033[92m[PASS]\033[0m {msg}")
def fail(msg: str): print(f"\033[91m[FAIL]\033[0m {msg}")
def info(msg: str): print(f"\033[94m[INFO]\033[0m {msg}")


def make_cartoon_png(path: pathlib.Path, w: int = 512, h: int = 768) -> None:
    img = Image.new("RGB", (w, h), (250, 230, 210))
    d = ImageDraw.Draw(img)
    fx0, fy0, fx1, fy1 = w*0.18, h*0.20, w*0.82, h*0.78
    d.ellipse([fx0, fy0, fx1, fy1], fill=(255, 220, 190), outline=(120, 80, 60), width=4)
    eye_y = h*0.42
    d.ellipse([w*0.32, eye_y-20, w*0.42, eye_y+20], fill=(255,255,255), outline=(0,0,0), width=3)
    d.ellipse([w*0.58, eye_y-20, w*0.68, eye_y+20], fill=(255,255,255), outline=(0,0,0), width=3)
    d.ellipse([w*0.355, eye_y-8, w*0.395, eye_y+8], fill=(0,0,0))
    d.ellipse([w*0.615, eye_y-8, w*0.655, eye_y+8], fill=(0,0,0))
    d.line([(w*0.50, h*0.50), (w*0.50, h*0.58)], fill=(120,80,60), width=4)
    d.arc([w*0.36, h*0.58, w*0.64, h*0.70], start=0, end=180, fill=(160,40,40), width=6)
    img.save(path, "PNG")


def login() -> str:
    r = httpx.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    r.raise_for_status()
    j = r.json()
    return j.get("token") or j.get("access_token")


def upload_image(token: str, path: pathlib.Path) -> str:
    with open(path, "rb") as fh:
        files = {"file": (path.name, fh, "image/png")}
        r = httpx.post(f"{API}/upload-image", files=files,
                       headers={"Authorization": f"Bearer {token}"}, timeout=60)
    r.raise_for_status()
    return r.json()["file_path"]


def create_talking(token: str, image_path: str, bgm_style: str) -> str:
    body = {
        "image_path": image_path,
        "script": "Namaste doston, yeh ek epic cinematic avatar hai. Hari Om.",
        "voice_id": "hi-IN-SwaraNeural",
        "motion": "ken_burns",
        "aspect_ratio": "9:16",
        "resolution": "480p",
        "bgm_style": bgm_style,
        "use_procedural_lipsync": True,
    }
    r = httpx.post(f"{API}/create-talking-avatar", json=body,
                   headers={"Authorization": f"Bearer {token}"}, timeout=60)
    if r.status_code != 200:
        raise SystemExit(f"create-talking-avatar {r.status_code}: {r.text[:300]}")
    return r.json()["project_id"]


def poll_project(token: str, pid: str, max_s: int = 180) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    deadline = time.time() + max_s
    last = None
    while time.time() < deadline:
        r = httpx.get(f"{API}/project/{pid}", headers=headers, timeout=30)
        if r.status_code == 200:
            j = r.json()
            last = j
            st = j.get("status")
            if st in ("completed", "failed"):
                return j
        time.sleep(3)
    return last or {}


def grep_log_recent(pattern: str, since_lines: int = 6000) -> Optional[str]:
    try:
        out = subprocess.check_output(
            ["tail", "-n", str(since_lines), LOG_FILE], text=True, timeout=10,
        )
    except Exception:
        return None
    for line in out.splitlines()[::-1]:
        if pattern in line:
            return line
    return None


def test_a_smoke():
    print("\n=== A) random_for_mood smoke test ===")
    sys.path.insert(0, "/app/backend")
    from core.bgm_catalog import random_for_mood, get_catalog
    cat_ids = [t["id"] for t in get_catalog()]
    info(f"catalog ids: {cat_ids}")
    expectations = {
        "cinematic_epic": "cinematic_score",
        "cinematic": "cinematic_score",
        "devotional": "ambient_calm",
        "playful": "playful_pulse",
        "motivational": "motivational_pulse",
    }
    failures = 0
    for m, want in expectations.items():
        t = random_for_mood(m)
        got = (t or {}).get("id")
        if got == want:
            ok(f"random_for_mood({m!r}) -> {got}")
        else:
            fail(f"random_for_mood({m!r}) -> {got}, want {want}")
            failures += 1
    t_unk = random_for_mood("unknown_tag")
    if t_unk and t_unk.get("id") in cat_ids:
        ok(f"random_for_mood('unknown_tag') -> {t_unk.get('id')} (any non-None fallback)")
    else:
        fail(f"random_for_mood('unknown_tag') -> {t_unk}")
        failures += 1
    t_empty = random_for_mood("")
    info(f"random_for_mood('') -> {t_empty}  (None is current designed behaviour)")
    return failures == 0


def test_full(token: str, image_path: str, bgm_style: str, expected_track: str) -> bool:
    print(f"\n=== {bgm_style} → expecting BGM mixed ({expected_track}) ===")
    pid = create_talking(token, image_path, bgm_style)
    info(f"project_id={pid}")

    j = poll_project(token, pid, max_s=180)
    st = j.get("status")
    if st != "completed":
        fail(f"project {pid} status={st} progress={j.get('progress')} err={j.get('error')}")
        return False
    ok(f"project {pid} completed")

    bgm_line = grep_log_recent(f"talking: BGM mixed ({expected_track})")
    if not bgm_line:
        any_bgm = grep_log_recent("talking: BGM mixed")
        fail(f"missing 'talking: BGM mixed ({expected_track})'. Most recent BGM line: {any_bgm}")
        return False
    ok(f"log: {bgm_line.strip()[-160:]}")

    proc_line = grep_log_recent("talking: procedural lipsync OK")
    if proc_line:
        ok(f"log: {proc_line.strip()[-140:]}")
    else:
        info("(no procedural-lipsync OK line found in tail)")

    result_url = j.get("result_url")
    if not result_url:
        fail(f"no result_url: {j}")
        return False
    full_url = result_url if result_url.startswith("http") else f"{BACKEND_URL}{result_url}"
    r = httpx.get(full_url, timeout=60)
    if r.status_code != 200:
        fail(f"GET {full_url} -> {r.status_code}")
        return False
    size_kb = len(r.content) / 1024
    ctype = r.headers.get("content-type", "")
    if size_kb < 100 or "video/mp4" not in ctype:
        fail(f"MP4 size={size_kb:.1f}KB ctype={ctype}")
        return False
    ok(f"MP4: {size_kb:.1f}KB ctype={ctype}")

    tmp = pathlib.Path(f"/tmp/talking_{pid[:8]}.mp4")
    tmp.write_bytes(r.content)
    pr = subprocess.run(
        ["/usr/bin/ffprobe", "-v", "error", "-show_streams", "-show_format",
         "-of", "json", str(tmp)],
        capture_output=True, timeout=20,
    )
    try:
        meta = json.loads(pr.stdout.decode())
    except Exception:
        fail(f"ffprobe failed: {pr.stderr.decode()[:200]}")
        return False
    streams = meta.get("streams", [])
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    audio_codec = next((s.get("codec_name") for s in streams if s.get("codec_type") == "audio"), None)
    duration = float(meta.get("format", {}).get("duration") or 0)
    if not has_audio:
        fail("MP4 has no audio stream")
        return False
    if duration < 3.0:
        fail(f"duration too short: {duration:.2f}s")
        return False
    ok(f"ffprobe: audio={audio_codec} duration={duration:.2f}s")
    return True


def test_d_regression(token: str) -> bool:
    print("\n=== D) Regression sweep ===")
    fails = 0
    r = httpx.get(f"{API}/", timeout=15)
    if r.status_code == 200:
        ok(f"GET /api/ -> 200 v={r.json().get('version')}")
    else:
        fail(f"GET /api/ -> {r.status_code}"); fails += 1
    r = httpx.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=15)
    if r.status_code == 200 and (r.json().get("token") or r.json().get("access_token")):
        ok("POST /api/auth/login -> 200")
    else:
        fail(f"login -> {r.status_code}"); fails += 1
    r = httpx.get(f"{API}/avatar/styles", timeout=15)
    if r.status_code == 200 and "styles" in r.json():
        ok(f"GET /api/avatar/styles -> 200 count={r.json().get('count')}")
    else:
        fail(f"GET /api/avatar/styles -> {r.status_code}"); fails += 1
    r = httpx.get(f"{API}/projects", headers={"Authorization": f"Bearer {token}"}, timeout=20)
    if r.status_code == 200:
        data = r.json()
        projs = data if isinstance(data, list) else data.get("projects", [])
        ta = [p for p in projs if p.get("type") == "talking_avatar"]
        ok(f"GET /api/projects -> 200 total={len(projs)} talking_avatar={len(ta)}")
        if not ta:
            fail("expected ≥1 talking_avatar project, got 0"); fails += 1
    else:
        fail(f"GET /api/projects -> {r.status_code}"); fails += 1
    return fails == 0


def main():
    print(f"Backend: {API}")
    a_ok = test_a_smoke()
    token = login()
    info(f"auth token: ***{token[-8:] if token else None}")
    img_path = pathlib.Path("/tmp/cartoon_512x768.png")
    make_cartoon_png(img_path)
    info(f"made cartoon {img_path} ({img_path.stat().st_size} B)")
    upload_path = upload_image(token, img_path)
    info(f"uploaded -> {upload_path}")
    b_ok = test_full(token, upload_path, "cinematic_epic", "cinematic_score")
    c_ok = test_full(token, upload_path, "devotional", "ambient_calm")
    d_ok = test_d_regression(token)
    print("\n=== SUMMARY ===")
    print(f"A (smoke):              {'PASS' if a_ok else 'FAIL'}")
    print(f"B (cinematic_epic mix): {'PASS' if b_ok else 'FAIL'}")
    print(f"C (devotional mix):     {'PASS' if c_ok else 'FAIL'}")
    print(f"D (regression):         {'PASS' if d_ok else 'FAIL'}")
    sys.exit(0 if all([a_ok, b_ok, c_ok, d_ok]) else 1)


if __name__ == "__main__":
    main()
