"""
Phase-1 Cinematic Preset paywall re-verification.
Tests B3, B6, B7 only.
"""
import io
import json
import time
import base64
import httpx
from PIL import Image

BASE = "https://creative-plan-engine.preview.emergentagent.com/api"
FREE_EMAIL = "phase1test@example.com"
FREE_PASS = "Test@123"


def make_png_bytes():
    img = Image.new("RGB", (512, 768), color=(220, 180, 160))
    # add a face-ish feature to maybe help detection
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def login_or_register(client):
    # Try login
    r = client.post(f"{BASE}/auth/login", json={"email": FREE_EMAIL, "password": FREE_PASS})
    if r.status_code == 200:
        return r.json()["token"]
    # Try register
    r2 = client.post(
        f"{BASE}/auth/register",
        json={"email": FREE_EMAIL, "password": FREE_PASS, "name": "Phase1 Free", "plan": "free"},
    )
    if r2.status_code in (200, 201):
        data = r2.json()
        return data.get("token")
    # Try login again
    r3 = client.post(f"{BASE}/auth/login", json={"email": FREE_EMAIL, "password": FREE_PASS})
    if r3.status_code == 200:
        return r3.json()["token"]
    raise RuntimeError(f"Login/register failed: {r.status_code} {r.text} / reg {r2.status_code} {r2.text}")


def upload_image(client, token, png):
    files = {"file": ("test.png", png, "image/png")}
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(f"{BASE}/upload-face-image", files=files, headers=headers)
    r.raise_for_status()
    return r.json()["file_path"]


def poll_project(client, token, pid, max_wait=90):
    headers = {"Authorization": f"Bearer {token}"}
    start = time.time()
    last_status = None
    while time.time() - start < max_wait:
        r = client.get(f"{BASE}/project/{pid}", headers=headers)
        if r.status_code == 200:
            js = r.json()
            last_status = js.get("status")
            if last_status in ("completed", "failed"):
                return js
        time.sleep(3)
    return {"status": last_status or "timeout"}


def main():
    results = {}
    with httpx.Client(timeout=60.0) as client:
        token = login_or_register(client)
        print(f"[AUTH] token={token[:30]}...")

        png = make_png_bytes()
        image_path = upload_image(client, token, png)
        print(f"[UPLOAD] image_path={image_path}")

        headers = {"Authorization": f"Bearer {token}"}

        # ============ B3: pro preset (cinematic) on free user → 402 preset_locked ============
        print("\n=== B3: cinematic preset on free user → expect 402 preset_locked ===")
        body_b3 = {
            "image_path": image_path,
            "script": "Test",
            "voice_id": "hi-IN-SwaraNeural",
            "use_procedural_lipsync": True,
            "preset_id": "cinematic",
        }
        r = client.post(f"{BASE}/create-talking-avatar", json=body_b3, headers=headers)
        print(f"B3 status={r.status_code}")
        try:
            js = r.json()
            print(f"B3 body={json.dumps(js, indent=2)}")
            results["B3"] = {
                "status": r.status_code,
                "body": js,
            }
        except Exception as e:
            print(f"B3 non-json body: {r.text}  err={e}")
            results["B3"] = {"status": r.status_code, "text": r.text}

        # ============ B6: funny preset (free) on free user → 200 + completes ============
        print("\n=== B6: funny preset on free user → expect 200 + completes ===")
        body_b6 = {
            "image_path": image_path,
            "script": "Test",
            "voice_id": "hi-IN-SwaraNeural",
            "use_procedural_lipsync": True,
            "preset_id": "funny",
        }
        r = client.post(f"{BASE}/create-talking-avatar", json=body_b6, headers=headers)
        print(f"B6 create status={r.status_code}")
        b6_result = {"create_status": r.status_code}
        if r.status_code == 200:
            pid = r.json().get("project_id")
            b6_result["project_id"] = pid
            print(f"B6 project_id={pid}  polling up to 90s...")
            final = poll_project(client, token, pid, max_wait=90)
            b6_result["final"] = {k: final.get(k) for k in ("status", "progress", "result_url", "error")}
            print(f"B6 final={b6_result['final']}")
        else:
            try:
                b6_result["body"] = r.json()
            except Exception:
                b6_result["text"] = r.text
            print(f"B6 body={b6_result.get('body') or b6_result.get('text')}")
        results["B6"] = b6_result

        # ============ B7: no preset_id on free user → 200 + completes ============
        print("\n=== B7: no preset_id on free user → expect 200 + completes ===")
        body_b7 = {
            "image_path": image_path,
            "script": "Test",
            "voice_id": "hi-IN-SwaraNeural",
            "use_procedural_lipsync": True,
        }
        r = client.post(f"{BASE}/create-talking-avatar", json=body_b7, headers=headers)
        print(f"B7 create status={r.status_code}")
        b7_result = {"create_status": r.status_code}
        if r.status_code == 200:
            pid = r.json().get("project_id")
            b7_result["project_id"] = pid
            print(f"B7 project_id={pid}  polling up to 90s...")
            final = poll_project(client, token, pid, max_wait=90)
            b7_result["final"] = {k: final.get(k) for k in ("status", "progress", "result_url", "error")}
            print(f"B7 final={b7_result['final']}")
        else:
            try:
                b7_result["body"] = r.json()
            except Exception:
                b7_result["text"] = r.text
        results["B7"] = b7_result

    print("\n\n=== SUMMARY ===")
    print(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    main()
