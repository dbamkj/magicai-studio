"""Session 33 r4 — DUAL procedural cartoon lipsync verification.

Tests:
  A — demo_creator dual procedural happy path
  B — free user can use dual procedural (no Pro gate)
  C — regression: dual without procedural still hits MagicHour
  D — quick regressions (cinematic-presets, avatar/styles, cartoonize text-only)
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests
from PIL import Image

BACKEND = "https://creative-plan-engine.preview.emergentagent.com"
API = f"{BACKEND}/api"

# ────────────────────────── helpers ──────────────────────────

def _login(email: str, password: str) -> str | None:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    if r.status_code != 200:
        print(f"login {email} → {r.status_code} {r.text[:200]}")
        return None
    return r.json().get("token")

def _register_free(email: str, password: str) -> str | None:
    body = {"email": email, "password": password, "full_name": "Phase1 Test User"}
    r = requests.post(f"{API}/auth/register", json=body, timeout=30)
    if r.status_code in (200, 201):
        return r.json().get("token")
    if r.status_code == 400 and "already" in r.text.lower():
        return _login(email, password)
    print(f"register {email} → {r.status_code} {r.text[:200]}")
    return None

def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}

def _cartoonize(token: str, prompt: str, emotion: str = "happy", style: str = "desi_toon") -> str | None:
    body = {"style": style, "emotion": emotion, "prompt": prompt}
    r = requests.post(f"{API}/avatar/cartoonize", json=body, headers=_auth(token), timeout=60)
    if r.status_code != 200:
        print(f"  cartoonize fail {r.status_code} {r.text[:200]}")
        return None
    return r.json().get("job_id")

def _poll_avatar_job(job_id: str, max_wait: int = 90) -> str | None:
    start = time.time()
    while time.time() - start < max_wait:
        r = requests.get(f"{API}/avatar/jobs/{job_id}", timeout=20)
        if r.status_code == 200:
            d = r.json()
            if d.get("status") == "completed":
                return d.get("image_url")
            if d.get("status") == "failed":
                print(f"  job {job_id} FAILED: {d.get('error')}")
                return None
        time.sleep(3)
    print(f"  job {job_id} timeout")
    return None

def _img_url_to_uploads(image_url: str) -> str:
    """Frontend logic: /api/serve-file/X.png → /api/uploads/X.png"""
    return image_url.replace("/api/serve-file/", "/api/uploads/")

def _poll_project(project_id: str, max_wait: int = 180, headers: dict | None = None) -> dict:
    start = time.time()
    last = {}
    while time.time() - start < max_wait:
        r = requests.get(f"{API}/project/{project_id}", headers=headers or {}, timeout=20)
        if r.status_code == 200:
            last = r.json()
            st = last.get("status")
            if st in ("completed", "failed"):
                return last
        time.sleep(5)
    return last


# ────────────────────────── tests ──────────────────────────

def test_D_regressions():
    print("\n" + "="*70 + "\n=== TEST D — regressions ===\n" + "="*70)
    out = {}

    # D1
    r = requests.get(f"{API}/cinematic-presets", timeout=20)
    print(f"D1 GET /cinematic-presets → {r.status_code}")
    if r.status_code == 200:
        presets = r.json().get("presets", [])
        print(f"   presets={len(presets)}")
        out["D1"] = (len(presets) == 6)
    else:
        out["D1"] = False
        print(f"   body={r.text[:200]}")

    # D2
    r = requests.get(f"{API}/avatar/styles", timeout=20)
    print(f"D2 GET /avatar/styles → {r.status_code}")
    out["D2"] = r.status_code == 200
    if out["D2"]:
        print(f"   styles_count={len(r.json().get('styles', []))} emotions={len(r.json().get('emotions', []))}")

    # D3 — cartoonize text-only
    tok = _login("demo_creator@test.com", "Test@123")
    if tok:
        body = {"style": "desi_toon", "emotion": "happy", "prompt": "young Indian man, happy, full body"}
        r = requests.post(f"{API}/avatar/cartoonize", json=body, headers=_auth(tok), timeout=30)
        print(f"D3 cartoonize text-only → {r.status_code}")
        if r.status_code == 200:
            jid = r.json().get("job_id")
            print(f"   job_id={jid}")
            out["D3"] = bool(jid)
        else:
            out["D3"] = False
            print(f"   body={r.text[:300]}")
    else:
        out["D3"] = False

    print(f"\n  D summary: {out}")
    return out


def _make_two_cartoon_images(token: str) -> tuple[str, str] | None:
    """Generate two cartoon source images and return their /api/uploads/ paths."""
    print("  → cartoonize image A (Indian man)...")
    jid_a = _cartoonize(token, "young Indian man in colourful clothes, full body", "happy", "desi_toon")
    print(f"    job_a={jid_a}")
    print("  → cartoonize image B (Indian woman in saree)...")
    jid_b = _cartoonize(token, "young Indian woman in saree, full body", "happy", "desi_toon")
    print(f"    job_b={jid_b}")
    if not (jid_a and jid_b):
        return None

    url_a = _poll_avatar_job(jid_a, 120)
    url_b = _poll_avatar_job(jid_b, 120)
    print(f"    image_a_url={url_a}")
    print(f"    image_b_url={url_b}")
    if not (url_a and url_b):
        return None
    return _img_url_to_uploads(url_a), _img_url_to_uploads(url_b)


def test_A_dual_procedural_paid():
    print("\n" + "="*70 + "\n=== TEST A — dual procedural (creator) ===\n" + "="*70)
    out = {}
    tok = _login("demo_creator@test.com", "Test@123")
    if not tok:
        return {"A_login": False}
    print(f"  ✓ creator token len={len(tok)}")

    pair = _make_two_cartoon_images(tok)
    if not pair:
        out["A_images"] = False
        return out
    out["A_images"] = True
    a_path, b_path = pair

    body = {
        "image_a_path": a_path,
        "image_b_path": b_path,
        "script": "A: Namaste doston, kaise ho?\nB: Bahut badhiya, aur tum?\nA: Sab theek hai, dhanyavaad.",
        "voice_a_id": "hi-IN-MadhurNeural",
        "voice_b_id": "hi-IN-SwaraNeural",
        "motion": "none",
        "aspect_ratio": "16:9",
        "resolution": "480p",
        "use_procedural_lipsync": True,
    }
    print(f"\n  → POST /api/avatar/dual-lipsync (procedural=True)")
    r = requests.post(f"{API}/avatar/dual-lipsync", json=body, headers=_auth(tok), timeout=60)
    print(f"     status={r.status_code}")
    if r.status_code != 200:
        out["A_dual_post"] = False
        print(f"     body={r.text[:500]}")
        return out
    pdata = r.json()
    pid = pdata.get("project_id")
    print(f"     project_id={pid} status={pdata.get('status')} credits_charged={pdata.get('credits_charged')}")
    out["A_dual_post"] = (pdata.get("status") == "processing" and bool(pid))
    out["A_project_id"] = pid

    # Poll
    print(f"\n  → polling project {pid} up to 180s...")
    final = _poll_project(pid, 180, headers=_auth(tok))
    print(f"     final status={final.get('status')}")
    print(f"     result_url={final.get('result_url')}")
    print(f"     error={final.get('error')}")

    out["A_completed"] = (final.get("status") == "completed")
    result_url = final.get("result_url") or ""
    out["A_proc_filename"] = "_proc.mp4" in result_url and "_ls.mp4" not in result_url

    if out["A_completed"] and result_url:
        # download
        full_url = BACKEND + result_url
        r2 = requests.get(full_url, timeout=120)
        ct = r2.headers.get("content-type", "")
        size = len(r2.content)
        print(f"     download {full_url} → {r2.status_code} ct={ct} size={size}")
        out["A_download"] = (r2.status_code == 200 and "video" in ct and size > 50000)

        # ffprobe
        local = Path(f"/tmp/dual_test_{pid[:8]}.mp4")
        local.write_bytes(r2.content)
        try:
            probe = subprocess.run([
                "ffprobe", "-v", "error", "-show_entries",
                "stream=codec_name,codec_type,width,height:format=duration",
                "-of", "json", str(local)
            ], capture_output=True, timeout=30)
            info = json.loads(probe.stdout.decode() or "{}")
            print(f"     ffprobe streams: {[(s.get('codec_type'),s.get('codec_name'),s.get('width'),s.get('height')) for s in info.get('streams',[])]}")
            print(f"     ffprobe duration={info.get('format',{}).get('duration')}")
            v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
            a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), {})
            out["A_codec_h264"] = v.get("codec_name") == "h264"
            out["A_codec_aac"] = a.get("codec_name") == "aac"
            out["A_dim_1080x960"] = (v.get("width") == 1080 and v.get("height") == 960)
            out["A_duration_s"] = float(info.get("format", {}).get("duration") or 0)
        except Exception as e:
            print(f"     ffprobe error: {e}")

    return out


def test_B_dual_procedural_free():
    print("\n" + "="*70 + "\n=== TEST B — dual procedural (free user, no Pro gate) ===\n" + "="*70)
    out = {}
    tok = _login("phase1test@example.com", "Test@123")
    if not tok:
        print("  → trying register…")
        tok = _register_free("phase1test@example.com", "Test@123")
    if not tok:
        return {"B_login": False}
    print(f"  ✓ free token len={len(tok)}")
    out["B_login"] = True

    pair = _make_two_cartoon_images(tok)
    if not pair:
        # Try with creator's images by re-using
        print("  ! free user could not generate cartoons (likely free credits limit). Reusing demo_creator images.")
        ctok = _login("demo_creator@test.com", "Test@123")
        pair = _make_two_cartoon_images(ctok) if ctok else None
        if not pair:
            out["B_images"] = False
            return out
    out["B_images"] = True
    a_path, b_path = pair

    body = {
        "image_a_path": a_path,
        "image_b_path": b_path,
        "script": "A: Namaste doston, kaise ho?\nB: Bahut badhiya, aur tum?\nA: Sab theek hai, dhanyavaad.",
        "voice_a_id": "hi-IN-MadhurNeural",
        "voice_b_id": "hi-IN-SwaraNeural",
        "motion": "none",
        "aspect_ratio": "16:9",
        "resolution": "480p",
        "use_procedural_lipsync": True,
    }
    r = requests.post(f"{API}/avatar/dual-lipsync", json=body, headers=_auth(tok), timeout=60)
    print(f"  POST /avatar/dual-lipsync → {r.status_code}")
    print(f"  body[:500]={r.text[:500]}")
    out["B_no_402"] = r.status_code != 402
    out["B_status_200"] = r.status_code == 200

    if r.status_code == 200:
        pid = r.json().get("project_id")
        out["B_project_id"] = pid
        print(f"  → polling free user project {pid} up to 180s...")
        final = _poll_project(pid, 180, headers=_auth(tok))
        print(f"     final status={final.get('status')} result_url={final.get('result_url')}")
        out["B_completed"] = final.get("status") == "completed"
        out["B_proc_filename"] = "_proc.mp4" in (final.get("result_url") or "")

    return out


def test_C_dual_mh_path():
    print("\n" + "="*70 + "\n=== TEST C — regression: dual WITHOUT procedural (MH path) ===\n" + "="*70)
    out = {}
    tok = _login("demo_creator@test.com", "Test@123")
    if not tok:
        return {"C_login": False}
    out["C_login"] = True

    pair = _make_two_cartoon_images(tok)
    if not pair:
        out["C_images"] = False
        return out
    out["C_images"] = True
    a_path, b_path = pair

    body = {
        "image_a_path": a_path,
        "image_b_path": b_path,
        "script": "A: Hello there, how are you today?\nB: I am doing very well, thank you.",
        "voice_a_id": "en-US-JennyNeural",
        "voice_b_id": "en-US-GuyNeural",
        "motion": "none",
        "aspect_ratio": "16:9",
        "resolution": "480p",
        "use_procedural_lipsync": False,
    }
    r = requests.post(f"{API}/avatar/dual-lipsync", json=body, headers=_auth(tok), timeout=60)
    print(f"  POST /avatar/dual-lipsync (procedural=False) → {r.status_code}")
    if r.status_code != 200:
        out["C_post_200"] = False
        print(f"     body={r.text[:400]}")
        return out
    out["C_post_200"] = True
    pid = r.json().get("project_id")
    out["C_project_id"] = pid
    print(f"     project_id={pid}")

    # Poll for ~60s, just confirm processing started
    print("  → polling for 60s to confirm MH path was taken...")
    for i in range(12):
        time.sleep(5)
        rr = requests.get(f"{API}/project/{pid}", headers=_auth(tok), timeout=15)
        if rr.status_code == 200:
            d = rr.json()
            print(f"     t={5*(i+1)}s status={d.get('status')} progress={d.get('progress')}")
            if d.get("status") in ("completed", "failed"):
                out["C_status_final"] = d.get("status")
                break
    return out


# ────────────────────────── log scan helpers ──────────────────────────

def scan_backend_log_for_project(pid: str, patterns: list[str]) -> dict[str, list[str]]:
    """Return matched log lines per pattern in last ~10000 lines of backend log."""
    found: dict[str, list[str]] = {p: [] for p in patterns}
    candidates = [
        "/var/log/supervisor/backend.err.log",
        "/var/log/supervisor/backend.out.log",
    ]
    text_blob = ""
    for path in candidates:
        if not Path(path).exists():
            continue
        try:
            r = subprocess.run(["tail", "-n", "20000", path], capture_output=True, timeout=10)
            text_blob += r.stdout.decode(errors="ignore")
        except Exception:
            pass
    for p in patterns:
        regex = re.compile(re.escape(p), re.IGNORECASE)
        for line in text_blob.splitlines():
            if regex.search(line):
                # Only keep relevant ones — also filter by pid if given
                found[p].append(line)
    return found


# ────────────────────────── main ──────────────────────────

if __name__ == "__main__":
    results = {}

    results["D"] = test_D_regressions()

    results["A"] = test_A_dual_procedural_paid()
    if results["A"].get("A_project_id"):
        pid_a = results["A"]["A_project_id"]
        scan = scan_backend_log_for_project(pid_a, [
            "dual: procedural lipsync OK",
            "_proc.mp4",
            "upload_to_magic_hour",
            "mh_create_lipsync",
            pid_a[:8],
        ])
        print("\n  --- TEST A backend log scan ---")
        for k, lines in scan.items():
            print(f"    pattern {k!r}: {len(lines)} matches")
            for ln in lines[-3:]:
                print(f"      • {ln[:240]}")
        # Filter MH lines to only those mentioning our project
        mh_lines = [ln for ln in scan.get("upload_to_magic_hour", []) if pid_a[:8] in ln]
        results["A"]["A_no_mh_for_project"] = (len(mh_lines) == 0)
        results["A"]["A_log_proc_ok"] = any("dual: procedural lipsync OK" in ln for ln in scan["dual: procedural lipsync OK"])

    results["B"] = test_B_dual_procedural_free()

    results["C"] = test_C_dual_mh_path()
    if results["C"].get("C_project_id"):
        pid_c = results["C"]["C_project_id"]
        scan_c = scan_backend_log_for_project(pid_c, ["upload_to_magic_hour", "mh_create_lipsync", pid_c[:8]])
        print("\n  --- TEST C backend log scan ---")
        for k, lines in scan_c.items():
            print(f"    pattern {k!r}: {len(lines)} matches")
            for ln in lines[-3:]:
                print(f"      • {ln[:240]}")
        # Look for MH activity within first 60s window — even if not project-specific
        results["C"]["C_log_mh_called"] = bool(scan_c.get("upload_to_magic_hour")) or bool(scan_c.get("mh_create_lipsync"))

    print("\n" + "="*70)
    print("=== FINAL RESULTS ===")
    print("="*70)
    print(json.dumps(results, indent=2, default=str))
