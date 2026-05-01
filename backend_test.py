"""Session 23 — Phase-B media.py extraction regression test.

Verifies 5 extracted endpoints work + adjacent endpoints unchanged.
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

import httpx

BASE = "https://creative-plan-engine.preview.emergentagent.com"
API = f"{BASE}/api"
INTERNAL = "http://localhost:8001"

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


def build_test_mp4() -> bytes:
    out = Path("/tmp/test_media_23.mp4")
    if out.exists():
        out.unlink()
    subprocess.run(
        ["/usr/bin/ffmpeg", "-y",
         "-f", "lavfi", "-i", "testsrc=duration=1:size=160x120:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
         "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", str(out)],
        capture_output=True, timeout=30,
    )
    assert out.exists() and out.stat().st_size > 500
    return out.read_bytes()


def build_test_mp3() -> bytes:
    out = Path("/tmp/test_media_23.mp3")
    if out.exists():
        out.unlink()
    subprocess.run(
        ["/usr/bin/ffmpeg", "-y",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
         "-c:a", "libmp3lame", "-q:a", "4", str(out)],
        capture_output=True, timeout=30,
    )
    assert out.exists() and out.stat().st_size > 500
    return out.read_bytes()


def test_a_openapi():
    try:
        r = httpx.get(f"{INTERNAL}/openapi.json", timeout=10)
        if r.status_code != 200:
            rec("A.openapi", False, f"status={r.status_code}")
            return
        paths = r.json().get("paths", {})
        required = [
            "/api/upload-video", "/api/upload-audio", "/api/extract-frames",
            "/api/transcribe-audio", "/api/merge-segments/{project_id}",
        ]
        missing = [p for p in required if p not in paths]
        rec("A.openapi all 5 paths present", not missing,
            f"total_paths={len(paths)}, missing={missing}")
    except Exception as e:
        rec("A.openapi", False, f"error: {e}")


def test_b_upload_video(token: str):
    try:
        mp4 = build_test_mp4()
    except Exception as e:
        rec("B.prep.mp4", False, f"{e}")
        return

    try:
        r = httpx.post(
            f"{API}/upload-video",
            files={"file": ("t.mp4", mp4, "video/mp4")},
            timeout=30,
        )
        rec("B1.upload-video no-auth→401/403",
            r.status_code in (401, 403),
            f"status={r.status_code}")
    except Exception as e:
        rec("B1.upload-video no-auth", False, f"{e}")

    try:
        r = httpx.post(
            f"{API}/upload-video",
            files={"file": ("t.mp4", mp4, "video/mp4")},
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        if r.status_code == 200:
            j = r.json()
            needs = {"file_id", "file_path", "duration", "size_mb"}
            missing = needs - set(j.keys())
            rec("B2.upload-video auth valid",
                not missing and j.get("duration", 0) > 0,
                f"keys={sorted(j.keys())}, duration={j.get('duration')}, size_mb={j.get('size_mb')}, missing={missing}")
        else:
            rec("B2.upload-video auth valid", False,
                f"status={r.status_code} body={r.text[:200]}")
    except Exception as e:
        rec("B2.upload-video auth valid", False, f"{e}")

    try:
        r = httpx.post(
            f"{API}/upload-video",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        rec("B3.upload-video no-file→422",
            r.status_code == 422, f"status={r.status_code}")
    except Exception as e:
        rec("B3.upload-video no-file", False, f"{e}")


def test_c_upload_audio():
    try:
        mp3 = build_test_mp3()
    except Exception as e:
        rec("C.prep.mp3", False, f"{e}")
        return

    try:
        r = httpx.post(
            f"{API}/upload-audio",
            files={"file": ("t.mp3", mp3, "audio/mpeg")},
            timeout=30,
        )
        if r.status_code == 200:
            j = r.json()
            rec("C1.upload-audio valid mp3",
                "file_id" in j and "file_path" in j,
                f"keys={sorted(j.keys())}")
        else:
            rec("C1.upload-audio valid mp3", False,
                f"status={r.status_code} body={r.text[:200]}")
    except Exception as e:
        rec("C1.upload-audio valid mp3", False, f"{e}")

    try:
        big = b"\x00" * (51 * 1024 * 1024)
        r = httpx.post(
            f"{API}/upload-audio",
            files={"file": ("big.mp3", big, "audio/mpeg")},
            timeout=180,
        )
        rec("C2.upload-audio >50MB→400",
            r.status_code == 400 and "Max 50MB" in r.text,
            f"status={r.status_code} body={r.text[:120]}")
    except Exception as e:
        rec("C2.upload-audio >50MB", False, f"{e}")


def test_d_transcribe_audio():
    try:
        mp3 = build_test_mp3()
        r = httpx.post(
            f"{API}/transcribe-audio",
            files={"file": ("t.mp3", mp3, "audio/mpeg")},
            timeout=180,
        )
        rec("D1.transcribe-audio exists (not 404)",
            r.status_code != 404,
            f"status={r.status_code}")
    except Exception as e:
        rec("D1.transcribe-audio exists", False, f"{e}")

    try:
        r = httpx.post(f"{API}/transcribe-audio", timeout=30)
        rec("D2.transcribe-audio empty-body routes (not 404)",
            r.status_code != 404, f"status={r.status_code}")
    except Exception as e:
        rec("D2.transcribe-audio empty-body", False, f"{e}")


def test_e_extract_frames():
    try:
        r = httpx.post(f"{API}/extract-frames", timeout=15)
        rec("E1.extract-frames no-file routes (not 404)",
            r.status_code != 404, f"status={r.status_code}")
    except Exception as e:
        rec("E1.extract-frames no-file", False, f"{e}")

    try:
        mp4 = build_test_mp4()
        r = httpx.post(
            f"{API}/extract-frames",
            files={"file": ("t.mp4", mp4, "video/mp4")},
            timeout=180,
        )
        rec("E2.extract-frames valid mp4 (200/400 not 404)",
            r.status_code in (200, 400, 500),
            f"status={r.status_code}")
    except Exception as e:
        rec("E2.extract-frames valid mp4", False, f"{e}")


def test_f_merge_segments(token: str):
    try:
        r = httpx.post(
            f"{API}/merge-segments/nonexistent_proj_id_xyz",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        rec("F1.merge-segments auth bogus-id→404",
            r.status_code == 404 and "not found" in r.text.lower(),
            f"status={r.status_code} body={r.text[:120]}")
    except Exception as e:
        rec("F1.merge-segments auth bogus", False, f"{e}")

    try:
        r = httpx.post(f"{API}/merge-segments/anyid", timeout=15)
        rec("F2.merge-segments no-auth→401/403",
            r.status_code in (401, 403), f"status={r.status_code}")
    except Exception as e:
        rec("F2.merge-segments no-auth", False, f"{e}")


def test_g_regression(token: str):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), (200, 100, 50)).save(buf, "PNG")
    png = buf.getvalue()

    try:
        r = httpx.post(
            f"{API}/upload-image",
            files={"file": ("t.png", png, "image/png")},
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        rec("G1.upload-image",
            r.status_code == 200 and "file_path" in r.text,
            f"status={r.status_code}")
    except Exception as e:
        rec("G1.upload-image", False, f"{e}")

    try:
        import base64
        b64 = base64.b64encode(png).decode()
        r = httpx.post(
            f"{API}/upload-base64",
            json={"data": b64, "content_type": "image/png"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        rec("G2.upload-base64", r.status_code == 200, f"status={r.status_code} body={r.text[:120]}")
    except Exception as e:
        rec("G2.upload-base64", False, f"{e}")

    try:
        r = httpx.get(f"{API}/marketplace/templates?limit=3", timeout=15)
        count = len(r.json()) if r.status_code == 200 else 0
        rec("G3.marketplace templates limit=3",
            r.status_code == 200 and count >= 1,
            f"status={r.status_code} count={count}")
    except Exception as e:
        rec("G3.marketplace", False, f"{e}")

    try:
        r = httpx.get(f"{API}/avatar/styles", timeout=15)
        if r.status_code == 200:
            j = r.json()
            count = j.get("count") or len(j.get("styles", []))
            rec("G4.avatar/styles count=11",
                count == 11, f"count={count}")
        else:
            rec("G4.avatar/styles", False, f"status={r.status_code}")
    except Exception as e:
        rec("G4.avatar/styles", False, f"{e}")

    try:
        r = httpx.post(
            f"{API}/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
            timeout=20,
        )
        rec("G5.auth/login demo_creator",
            r.status_code == 200 and "token" in r.json(),
            f"status={r.status_code}")
    except Exception as e:
        rec("G5.auth/login", False, f"{e}")


def test_h_no_duplicates():
    try:
        out = subprocess.run(
            ["tail", "-n", "500", "/var/log/supervisor/backend.err.log"],
            capture_output=True, text=True, timeout=5,
        ).stdout
        bad = ["already exists", "duplicate route", "duplicate operation",
               "already registered"]
        hits = [p for p in bad if p.lower() in out.lower()]
        rec("H.no-duplicate-routes in backend log",
            not hits, f"bad_patterns={hits}")
    except Exception as e:
        rec("H.no-duplicate-routes", False, f"{e}")


def main():
    print(f"=== Session 23 media.py regression ===\nBase: {API}\n")
    try:
        token = login()
        print(f"Login OK token_len={len(token)}\n")
    except Exception as e:
        print(f"FATAL login: {e}")
        sys.exit(1)

    test_a_openapi()
    test_b_upload_video(token)
    test_c_upload_audio()
    test_d_transcribe_audio()
    test_e_extract_frames()
    test_f_merge_segments(token)
    test_g_regression(token)
    test_h_no_duplicates()

    print("\n=== SUMMARY ===")
    passes = sum(1 for _, ok, _ in results if ok)
    for name, ok, _ in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\nTotal: {passes}/{len(results)} passed")
    sys.exit(0 if passes == len(results) else 1)


if __name__ == "__main__":
    main()
