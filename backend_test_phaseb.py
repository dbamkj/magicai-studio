"""Phase-B regression after uploads.py extraction (Session 22)."""
import base64 as _b64
import io
import sys
import time

import requests
from PIL import Image

BASE = "https://creative-plan-engine.preview.emergentagent.com"
API = f"{BASE}/api"

results = []
def rec(name, ok, note=""):
    results.append((name, ok, note))
    print(f"{'PASS' if ok else 'FAIL'}: {name} — {note}")


# ─── Login ───────────────────────────────────────────────────────────────
r = requests.post(f"{API}/auth/login", json={"email": "demo_creator@test.com", "password": "Test@123"}, timeout=20)
assert r.status_code == 200, r.text
TOKEN = r.json()["token"]
H = {"Authorization": f"Bearer {TOKEN}"}
print(f"Logged in. token_len={len(TOKEN)}")

# ─── A) OpenAPI sanity ────────────────────────────────────────────────────
r = requests.get(f"{BASE}/openapi.json", timeout=20)
if r.status_code != 200:
    rec("A.openapi_reachable", False, f"status={r.status_code}")
else:
    paths = set(r.json().get("paths", {}).keys())
    needed = [
        "/api/upload-image", "/api/upload-from-url", "/api/upload-base64",
        "/api/upload-face-image", "/api/upload-video", "/api/upload-audio",
    ]
    missing = [p for p in needed if p not in paths]
    rec("A.openapi_has_all_6_upload_paths", not missing,
        f"missing={missing}" if missing else "all 6 present")

# ─── Helpers ──────────────────────────────────────────────────────────────
def make_jpeg_b64(min_size=300):
    # Generate a JPEG >=200 bytes
    for dim in (32, 64, 96, 128, 192, 256):
        buf = io.BytesIO()
        img = Image.new("RGB", (dim, dim), color=(120, 90, 200))
        img.save(buf, format="JPEG", quality=85)
        data = buf.getvalue()
        if len(data) >= min_size:
            return _b64.b64encode(data).decode(), len(data)
    return _b64.b64encode(data).decode(), len(data)

def make_tiny_png_b64():
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), color=(255, 0, 0)).save(buf, format="PNG")
    data = buf.getvalue()
    return _b64.b64encode(data).decode(), len(data)

# ─── B.1) upload-base64 with auth ─────────────────────────────────────────
b64_str, raw_len = make_jpeg_b64()
print(f"Test JPEG raw_bytes={raw_len}")
r = requests.post(f"{API}/upload-base64", headers=H, json={"base64": b64_str, "filename": "t.jpg"}, timeout=30)
if r.status_code == 200:
    j = r.json()
    keys_ok = all(k in j for k in ("url", "file_id", "file_path", "file_type"))
    url_ok = isinstance(j.get("url"), str) and j["url"].startswith("/api/serve-file/")
    type_ok = j.get("file_type") == "image"
    rec("B.1a upload-base64 auth 200", keys_ok and url_ok and type_ok,
        f"url={j.get('url')}, type={j.get('file_type')}")
    # Serve file check
    sfu = f"{BASE}{j['url']}"
    r2 = requests.get(sfu, timeout=20)
    ct = r2.headers.get("content-type", "")
    rec("B.1b serve-file returns 200 image",
        r2.status_code == 200 and ("image" in ct or "jpeg" in ct or "png" in ct),
        f"status={r2.status_code} ct={ct} bytes={len(r2.content)}")
else:
    rec("B.1a upload-base64 auth 200", False, f"status={r.status_code} body={r.text[:200]}")
    rec("B.1b serve-file returns 200 image", False, "skipped (upload failed)")

# ─── B.2) upload-base64 WITHOUT auth ─────────────────────────────────────
r = requests.post(f"{API}/upload-base64", json={"base64": b64_str, "filename": "t.jpg"}, timeout=20)
rec("B.2 upload-base64 no-auth → 401/403", r.status_code in (401, 403), f"status={r.status_code}")

# ─── B.3) upload-base64 tiny payload → 400 "Image too small" ─────────────
tiny_b64, tiny_len = make_tiny_png_b64()
print(f"Tiny PNG raw_bytes={tiny_len}")
r = requests.post(f"{API}/upload-base64", headers=H, json={"base64": tiny_b64, "filename": "t.png"}, timeout=20)
ok = r.status_code == 400 and "too small" in (r.text or "").lower()
rec("B.3 upload-base64 tiny → 400 'Image too small'", ok, f"status={r.status_code} body={r.text[:200]}")

# ─── B.4) upload-base64 garbage → 400 "Invalid base64" ───────────────────
r = requests.post(f"{API}/upload-base64", headers=H, json={"base64": "!!!!not@@@base64###", "filename": "t.jpg"}, timeout=20)
# Note: python base64 with validate=False is permissive. Check either "Invalid base64"
# or "Image too small" since decoded output of short garbage is <128 bytes.
body_lower = (r.text or "").lower()
ok = r.status_code == 400 and ("invalid base64" in body_lower or "too small" in body_lower)
rec("B.4 upload-base64 garbage → 400",
    ok, f"status={r.status_code} body={r.text[:200]}")

# ─── B.5) upload-from-url valid ──────────────────────────────────────────
url = "https://images.unsplash.com/photo-1716504628105-bd76d91e85f2?w=200"
r = requests.post(f"{API}/upload-from-url", headers=H, json={"url": url}, timeout=40)
if r.status_code == 200:
    j = r.json()
    ok = j.get("file_type") == "image" and str(j.get("url", "")).startswith("/api/serve-file/")
    rec("B.5 upload-from-url valid → 200 image", ok, f"type={j.get('file_type')} url={j.get('url')}")
else:
    rec("B.5 upload-from-url valid → 200 image", False, f"status={r.status_code} body={r.text[:200]}")

# ─── B.6) upload-from-url url='' → 400 ───────────────────────────────────
r = requests.post(f"{API}/upload-from-url", headers=H, json={"url": ""}, timeout=20)
ok = r.status_code == 400 and "url must be http" in (r.text or "").lower()
rec("B.6 upload-from-url empty → 400 'url must be http(s)'", ok,
    f"status={r.status_code} body={r.text[:200]}")

# ─── C.1) upload-video & upload-audio still exist (no 404) ───────────────
r = requests.post(f"{API}/upload-video", headers=H, timeout=20)
rec("C.1a /upload-video not 404", r.status_code != 404, f"status={r.status_code}")
r = requests.post(f"{API}/upload-audio", headers=H, timeout=20)
rec("C.1b /upload-audio not 404", r.status_code != 404, f"status={r.status_code}")

# ─── C.2) marketplace templates ─────────────────────────────────────────
r = requests.get(f"{API}/marketplace/templates?limit=3", timeout=20)
rec("C.2 /marketplace/templates?limit=3 → 200", r.status_code == 200,
    f"status={r.status_code} count={len(r.json().get('templates', [])) if r.status_code==200 else '-'}")

# ─── C.3) avatar styles ─────────────────────────────────────────────────
r = requests.get(f"{API}/avatar/styles", timeout=20)
ok = r.status_code == 200 and r.json().get("count") == 11
rec("C.3 /avatar/styles → 200 count=11", ok,
    f"status={r.status_code} count={r.json().get('count') if r.status_code==200 else '-'}")

# ─── C.4) generate-prompts ──────────────────────────────────────────────
r = requests.post(f"{API}/generate-prompts", headers=H, json={"idea": "test"}, timeout=30)
rec("C.4 /generate-prompts → 200 or 429", r.status_code in (200, 429),
    f"status={r.status_code}")

# ─── C.5) wizard ai-images health ───────────────────────────────────────
r = requests.get(f"{API}/wizard/ai-images/health", timeout=20)
ok = r.status_code == 200 and r.json().get("ok") is True
rec("C.5 /wizard/ai-images/health → 200 ok=true", ok,
    f"status={r.status_code} body={r.text[:200]}")

# ─── Summary ─────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print(f"SUMMARY: {passed}/{total} PASSED")
for name, ok, note in results:
    mark = "✅" if ok else "❌"
    print(f"  {mark} {name} — {note}")
sys.exit(0 if passed == total else 1)
