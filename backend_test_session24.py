"""Session 24 — Phase-B talking.py extraction regression test.

Verifies POST /api/create-talking-avatar (extracted to routes/talking.py)
behaves correctly + regression sweep + duplicate-route check.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import httpx
from PIL import Image

BASE = "https://creative-plan-engine.preview.emergentagent.com"
API = f"{BASE}/api"

EMAIL = "demo_creator@test.com"
PASSWORD = "Test@123"

results: list[tuple[str, bool, str]] = []


def rec(name: str, ok: bool, msg: str = "") -> None:
    results.append((name, ok, msg))
    flag = "PASS" if ok else "FAIL"
    print(f"[{flag}] {name} :: {msg}")


def login() -> str:
    r = httpx.post(
        f"{API}/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=30,
    )
    r.raise_for_status()
    tok = r.json().get("token")
    assert tok, "no token"
    return tok


def make_png_bytes() -> bytes:
    img = Image.new("RGB", (256, 256), color=(120, 80, 200))
    # add a simple pattern so it's >128B
    for x in range(0, 256, 16):
        for y in range(0, 256, 16):
            img.putpixel((x, y), (255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------- Test 1: /api/create-talking-avatar surface ----------

def test_1a_no_auth():
    """No Authorization header → 401 (BETA strict mode)."""
    payload = {"image_path": "/anything.png", "script": "Hello"}
    try:
        r = httpx.post(f"{API}/create-talking-avatar", json=payload, timeout=30)
    except Exception as e:
        rec("1a no-auth → 401", False, f"exception: {e}")
        return
    if r.status_code == 401:
        rec("1a no-auth → 401", True, f"status=401 body={r.text[:120]}")
    else:
        rec("1a no-auth → 401", False, f"got status={r.status_code} body={r.text[:200]}")


def test_1b_missing_image(token: str):
    """Valid auth + non-existent image_path → 400 'Image not found'."""
    payload = {
        "image_path": "/app/backend/uploads/nonexistent_xyz_123.png",
        "script": "Hello world",
    }
    headers = {"Authorization": f"Bearer {token}"}
    r = httpx.post(f"{API}/create-talking-avatar", json=payload, headers=headers, timeout=30)
    if r.status_code == 400 and "Image not found" in (r.json().get("detail") or ""):
        rec("1b missing image → 400", True, f"detail={r.json().get('detail')[:80]}")
    else:
        rec("1b missing image → 400", False, f"status={r.status_code} body={r.text[:200]}")


def upload_image(token: str) -> str | None:
    """Helper: upload an image and return its file_path."""
    png = make_png_bytes()
    files = {"file": ("test_talking.png", png, "image/png")}
    headers = {"Authorization": f"Bearer {token}"}
    r = httpx.post(f"{API}/upload-image", files=files, headers=headers, timeout=60)
    if r.status_code != 200:
        rec("upload-image (helper)", False, f"status={r.status_code} body={r.text[:200]}")
        return None
    fp = r.json().get("file_path") or r.json().get("path")
    rec("upload-image (helper)", True, f"file_path={fp}")
    return fp


def test_1c_empty_script(token: str, image_path: str):
    """Valid auth + valid image_path + empty script → 400 'Script is required'."""
    payload = {"image_path": image_path, "script": "   "}
    headers = {"Authorization": f"Bearer {token}"}
    r = httpx.post(f"{API}/create-talking-avatar", json=payload, headers=headers, timeout=30)
    if r.status_code == 400 and "Script is required" in (r.json().get("detail") or ""):
        rec("1c empty script → 400", True, f"detail={r.json().get('detail')[:80]}")
    else:
        rec("1c empty script → 400", False, f"status={r.status_code} body={r.text[:200]}")


def test_1d_happy_path(token: str, image_path: str):
    """Valid auth + valid image_path + valid short script → 200 with project_id/status/credits_charged."""
    payload = {
        "image_path": image_path,
        "script": "Hello, this is a quick test.",
        "voice_id": "hi-IN-SwaraNeural",
    }
    headers = {"Authorization": f"Bearer {token}"}
    r = httpx.post(f"{API}/create-talking-avatar", json=payload, headers=headers, timeout=30)
    if r.status_code != 200:
        rec("1d happy path → 200", False, f"status={r.status_code} body={r.text[:300]}")
        return
    body = r.json()
    pid = body.get("project_id")
    status = body.get("status")
    cc = body.get("credits_charged")
    if pid and status == "processing" and isinstance(cc, int):
        rec(
            "1d happy path → 200",
            True,
            f"project_id={pid[:12]}... status={status} credits_charged={cc}",
        )
    else:
        rec("1d happy path → 200", False, f"shape mismatch body={body}")


# ---------- Test 2: Regression sweep ----------

def test_2_regression(token: str):
    """Confirm core endpoints still respond."""
    headers = {"Authorization": f"Bearer {token}"}

    r = httpx.get(f"{API}/mode", timeout=20)
    rec("2.1 GET /api/mode", r.status_code == 200, f"status={r.status_code}")

    r = httpx.get(f"{API}/marketplace/templates?limit=3", timeout=30)
    rec(
        "2.2 GET /api/marketplace/templates",
        r.status_code == 200,
        f"status={r.status_code} count={len(r.json()) if isinstance(r.json(), list) else 'n/a'}",
    )

    r = httpx.get(f"{API}/avatar/styles", timeout=20)
    rec("2.3 GET /api/avatar/styles", r.status_code == 200, f"status={r.status_code}")

    # POST /api/upload-image already validated above as 'helper' — re-record
    png = make_png_bytes()
    files = {"file": ("regr.png", png, "image/png")}
    r = httpx.post(f"{API}/upload-image", files=files, headers=headers, timeout=60)
    rec(
        "2.4 POST /api/upload-image",
        r.status_code == 200 and bool(r.json().get("file_path")),
        f"status={r.status_code} file_path={r.json().get('file_path') if r.status_code==200 else 'n/a'}",
    )

    r = httpx.get(f"{API}/auth/me", headers=headers, timeout=20)
    rec(
        "2.5 GET /api/auth/me (auth)",
        r.status_code == 200 and bool(r.json().get("user")),
        f"status={r.status_code}",
    )

    r = httpx.get(f"{API}/projects", headers=headers, timeout=30)
    rec(
        "2.6 GET /api/projects (auth)",
        r.status_code == 200,
        f"status={r.status_code}",
    )


# ---------- Test 3: Duplicate registration check via openapi.json ----------

def test_3_no_duplicate():
    """Hit internal port for openapi (ingress doesn't proxy /openapi.json)."""
    INTERNAL = "http://localhost:8001"
    r = httpx.get(f"{INTERNAL}/openapi.json", timeout=20)
    if r.status_code != 200:
        rec("3 openapi.json fetch", False, f"status={r.status_code}")
        return
    spec = r.json()
    paths = spec.get("paths", {})
    target = "/api/create-talking-avatar"
    if target not in paths:
        rec("3 talking-avatar path present", False, f"missing {target} in {len(paths)} paths")
        return
    methods = list(paths[target].keys())
    # Count occurrences of 'post' (should be exactly 1)
    if methods == ["post"]:
        rec(
            "3 /api/create-talking-avatar registered EXACTLY once (post)",
            True,
            f"methods={methods}",
        )
    else:
        rec(
            "3 /api/create-talking-avatar registered EXACTLY once (post)",
            False,
            f"methods={methods}",
        )

    # Sanity: assert no other entry-key contains the substring (e.g., trailing slash variant)
    matches = [p for p in paths if "create-talking-avatar" in p]
    if len(matches) == 1:
        rec("3b unique path entry", True, f"matches={matches}")
    else:
        rec("3b unique path entry", False, f"matches={matches}")


# ---------- Main ----------

def main() -> int:
    print("=" * 70)
    print("Session 24 — POST /api/create-talking-avatar regression suite")
    print("=" * 70)

    # 1a (no auth)
    test_1a_no_auth()

    # auth bootstrap
    try:
        token = login()
        rec("auth login (demo_creator)", True, f"token len={len(token)}")
    except Exception as e:
        rec("auth login (demo_creator)", False, f"exception: {e}")
        return 1

    # 1b
    test_1b_missing_image(token)

    # upload an image (1c, 1d, 2.4 share helper)
    img_path = upload_image(token)
    if img_path:
        test_1c_empty_script(token, img_path)
        test_1d_happy_path(token, img_path)
    else:
        rec("1c/1d skipped", False, "no image uploaded")

    # 2 regression
    test_2_regression(token)

    # 3 dedup check
    test_3_no_duplicate()

    # summary
    print()
    print("=" * 70)
    pf = sum(1 for _, ok, _ in results if ok)
    tot = len(results)
    print(f"SUMMARY: {pf}/{tot} PASS")
    print("=" * 70)
    for name, ok, msg in results:
        flag = "PASS" if ok else "FAIL"
        print(f"  [{flag}] {name}")

    return 0 if pf == tot else 1


if __name__ == "__main__":
    sys.exit(main())
