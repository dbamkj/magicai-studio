"""
Session 25 — Backend regression for the "Avatar Studio stuck @ 5%" fix.

Scope:
  TEST 1: /api/upload-image PIL dimension validation (>=64x64)
  TEST 2: /api/create-talking-avatar ffprobe pre-check
  TEST 3: GET /api/project/{id} sanity
  TEST 4: Smoke /api/avatar/styles + /api/avatar/suggestions

Auth: demo_creator@test.com / Test@123  (POST /api/auth/login -> token)
"""
from __future__ import annotations

import io
import os
import sys
import json
import uuid
import requests
from PIL import Image

BACKEND = (
    os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or os.environ.get("REACT_APP_BACKEND_URL")
    or "https://creative-plan-engine.preview.emergentagent.com"
).rstrip("/")
API = f"{BACKEND}/api"

EMAIL = "demo_creator@test.com"
PASSWORD = "Test@123"

PASS_LOG = []
FAIL_LOG = []


def _log(ok, name, detail=""):
    tag = "PASS" if ok else "FAIL"
    line = f"[{tag}] {name}"
    if detail:
        line += f"  -- {detail}"
    print(line)
    (PASS_LOG if ok else FAIL_LOG).append((name, detail))


def _short(text, n=200):
    if isinstance(text, (dict, list)):
        text = json.dumps(text)
    return (text or "")[:n]


def login():
    r = requests.post(
        f"{API}/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=30,
    )
    if r.status_code != 200:
        print("LOGIN FAIL:", r.status_code, r.text[:300])
        sys.exit(1)
    body = r.json()
    tok = body.get("token") or body.get("access_token")
    user = body.get("user", {})
    print(
        f"login OK -- tier={user.get('subscription_tier')} "
        f"creds={user.get('credits_balance')}"
    )
    return tok


def _png_bytes(w, h, color="red"):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


def _jpg_bytes(w, h, color="red"):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="JPEG")
    return buf.getvalue()


def test1_upload_image(token):
    print("\n=== TEST 1 -- /api/upload-image dim validation ===")
    H = {"Authorization": f"Bearer {token}"}

    r = requests.post(
        f"{API}/upload-image",
        headers=H,
        files={"file": ("ok.png", _png_bytes(256, 256), "image/png")},
        timeout=60,
    )
    body = {}
    try:
        body = r.json()
    except Exception:
        pass
    ok = r.status_code == 200 and "file_path" in body
    _log(ok, "1a 256x256 PNG -> 200 + file_path",
         f"status={r.status_code} body={_short(r.text, 150)}")

    r = requests.post(
        f"{API}/upload-image",
        headers=H,
        files={"file": ("tiny.png", _png_bytes(1, 1), "image/png")},
        timeout=60,
    )
    detail = ""
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text
    ok = r.status_code == 400 and (
        "too small" in (detail or "").lower()
        or "64x64" in (detail or "").lower()
    )
    _log(ok, "1b 1x1 PNG -> 400 'too small' / '64x64'",
         f"status={r.status_code} detail={_short(detail, 200)}")

    r = requests.post(
        f"{API}/upload-image",
        headers=H,
        files={"file": ("zero.png", b"", "image/png")},
        timeout=60,
    )
    detail = ""
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text
    ok = r.status_code == 400 and "empty" in (detail or "").lower()
    _log(ok, "1c 0-byte -> 400 'Empty file'",
         f"status={r.status_code} detail={_short(detail, 200)}")

    r = requests.post(
        f"{API}/upload-image",
        headers=H,
        files={"file": ("small.jpg", _jpg_bytes(32, 32), "image/jpeg")},
        timeout=60,
    )
    detail = ""
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text
    ok = r.status_code == 400 and (
        "too small" in (detail or "").lower()
        or "64x64" in (detail or "").lower()
    )
    _log(ok, "1d 32x32 JPG -> 400 'too small'",
         f"status={r.status_code} detail={_short(detail, 200)}")


def test2_talking_avatar(token):
    print("\n=== TEST 2 -- /api/create-talking-avatar pre-check ===")
    H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    body = {
        "image_path": "/app/backend/uploads/nope_does_not_exist_xyz123.png",
        "script": "Hello world",
        "voice_id": "hi-IN-SwaraNeural",
    }
    r = requests.post(f"{API}/create-talking-avatar", headers=H, json=body, timeout=30)
    detail = ""
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text
    ok = r.status_code == 400 and "image not found" in (detail or "").lower()
    _log(ok, "2a non-existent image -> 400 'Image not found'",
         f"status={r.status_code} detail={_short(detail, 200)}")

    body = {
        "image_path": "/app/backend/uploads/img_b7289365-32de-44ae-9499-c7d8f3caf62e.png",
        "script": "Hello world",
        "voice_id": "hi-IN-SwaraNeural",
    }
    r = requests.post(f"{API}/create-talking-avatar", headers=H, json=body, timeout=30)
    detail = ""
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text
    ok = r.status_code == 400 and (
        "too small" in (detail or "").lower()
        or "64x64" in (detail or "").lower()
    )
    _log(ok, "2b 1x1 placeholder -> 400 'too small' (CRITICAL)",
         f"status={r.status_code} detail={_short(detail, 250)}")

    # 2c needs a valid image to bypass image checks; upload 256x256 first
    H_mp = {"Authorization": f"Bearer {token}"}
    up = requests.post(
        f"{API}/upload-image",
        headers=H_mp,
        files={"file": ("ok2.png", _png_bytes(256, 256), "image/png")},
        timeout=60,
    )
    if up.status_code != 200:
        _log(False, "2c setup upload 256x256 png",
             f"status={up.status_code} body={_short(up.text, 200)}")
        return
    valid_path = up.json().get("file_path")
    body = {
        "image_path": valid_path,
        "script": "   ",
        "voice_id": "hi-IN-SwaraNeural",
    }
    r = requests.post(f"{API}/create-talking-avatar", headers=H, json=body, timeout=30)
    detail = ""
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text
    ok = (
        r.status_code == 400
        and "script" in (detail or "").lower()
        and "required" in (detail or "").lower()
    )
    _log(ok, "2c empty script -> 400 'Script is required'",
         f"status={r.status_code} detail={_short(detail, 200)}")


def test3_project_get(token):
    print("\n=== TEST 3 -- GET /api/project/{id} ===")
    H = {"Authorization": f"Bearer {token}"}

    pid = "df6a5d11-0c3b-4406-8316-0eaae7f04c81"
    r = requests.get(f"{API}/project/{pid}", headers=H, timeout=30)
    body = {}
    try:
        body = r.json()
    except Exception:
        pass
    ok = r.status_code == 200 and "status" in body
    _log(ok, "3a known project_id -> 200 with status/progress",
         f"status={r.status_code} keys={list(body.keys())[:10]} "
         f"status_field={body.get('status')} progress={body.get('progress')} "
         f"result_url={_short(body.get('result_url'), 80)}")

    rand = str(uuid.uuid4())
    r = requests.get(f"{API}/project/{rand}", headers=H, timeout=30)
    ok = r.status_code == 404
    _log(ok, "3b random uuid -> 404",
         f"status={r.status_code} body={_short(r.text, 150)}")

    r = requests.get(f"{API}/project/{pid}", timeout=30)
    ok = r.status_code in (200, 401, 404)
    _log(ok, "3c no auth -> not crash (200/401/404)",
         f"status={r.status_code} body={_short(r.text, 150)}")


def test4_avatar_smoke(token):
    print("\n=== TEST 4 -- Avatar smoke ===")
    H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    r = requests.get(f"{API}/avatar/styles", headers=H, timeout=30)
    body = {}
    try:
        body = r.json()
    except Exception:
        pass
    ok = r.status_code == 200 and ("styles" in body or "categories" in body)
    n_styles = len(body.get("styles") or [])
    _log(ok, "4a /avatar/styles -> 200 with styles[]",
         f"status={r.status_code} styles_count={n_styles} keys={list(body.keys())[:8]}")

    payload = {"style_id": "pixar", "emotion": "happy", "language": "english"}
    r = requests.post(f"{API}/avatar/suggestions", headers=H, json=payload, timeout=60)
    body = {}
    try:
        body = r.json()
    except Exception:
        pass
    ok = (
        r.status_code == 200
        and isinstance(body.get("suggestions"), list)
        and len(body["suggestions"]) > 0
    )
    _log(ok, "4b /avatar/suggestions -> 200 with suggestions[]",
         f"status={r.status_code} count={len(body.get('suggestions') or [])}")


def main():
    print(f"Backend = {BACKEND}")
    token = login()
    test1_upload_image(token)
    test2_talking_avatar(token)
    test3_project_get(token)
    test4_avatar_smoke(token)

    print("\n========================================")
    print(f"Pass: {len(PASS_LOG)}    Fail: {len(FAIL_LOG)}")
    if FAIL_LOG:
        print("\nFailures:")
        for n, d in FAIL_LOG:
            print(f"  FAIL {n}\n      {d}")
    print("========================================")


if __name__ == "__main__":
    main()
