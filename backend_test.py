"""Session 25 — Phase-B project CRUD refactor + b3 batch char-gen + dual-lipsync validation."""
import os, sys, time, json, hashlib, base64
import requests
from pathlib import Path

BASE = "https://creative-plan-engine.preview.emergentagent.com"
API = BASE + "/api"
CREDS = {"email": "demo_creator@test.com", "password": "Test@123"}
IMG_1X1 = "/app/backend/uploads/img_b7289365-32de-44ae-9499-c7d8f3caf62e.png"
EXISTING_PROJECT_ID = "df6a5d11-0c3b-4406-8316-0eaae7f04c81"

PASS=[]; FAIL=[]

def ok(name, detail=""):
    PASS.append(name); print(f"✅ {name}  {detail}")

def bad(name, detail=""):
    FAIL.append(name); print(f"❌ {name}  {detail}")

def login():
    r = requests.post(f"{API}/auth/login", json=CREDS, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    j = r.json()
    tok = j.get("token") or j.get("access_token") or j.get("session_token")
    assert tok, f"no token in login response: {j}"
    return tok, j

def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}

# ===================== A. Phase-B Projects CRUD =====================
def test_a_projects():
    tok, _ = login()
    H = hdr(tok)

    # A1 GET project valid
    r = requests.get(f"{API}/project/{EXISTING_PROJECT_ID}", headers=H, timeout=15)
    if r.status_code == 200 and r.json().get("id") == EXISTING_PROJECT_ID:
        ok("A1 GET /api/project/{valid}", f"status={r.json().get('status')}")
    else:
        bad("A1 GET /api/project/{valid}", f"{r.status_code} {r.text[:200]}")

    # A2 GET bogus
    r = requests.get(f"{API}/project/bogus-id-zzz-does-not-exist", headers=H, timeout=15)
    if r.status_code == 404:
        ok("A2 GET /api/project/{bogus}→404")
    else:
        bad("A2 GET /api/project/{bogus}", f"expected 404 got {r.status_code}")

    # A3 GET versions
    r = requests.get(f"{API}/project/{EXISTING_PROJECT_ID}/versions", headers=H, timeout=15)
    if r.status_code == 200:
        j = r.json()
        keys = set(j.keys())
        required = {"parent_id","count","versions"}
        if required.issubset(keys) and isinstance(j["versions"], list):
            ok("A3 GET versions", f"parent_id={j['parent_id']} count={j['count']} len={len(j['versions'])}")
        else:
            bad("A3 GET versions shape", f"keys={keys}")
    else:
        bad("A3 GET versions", f"{r.status_code} {r.text[:200]}")

    # A4 GET /api/projects (auth)
    r = requests.get(f"{API}/projects", headers=H, timeout=20)
    if r.status_code == 200 and isinstance(r.json(), list):
        ok("A4 GET /api/projects", f"n={len(r.json())}")
    else:
        bad("A4 GET /api/projects", f"{r.status_code} {r.text[:200]}")

    # A5 Create then delete
    # Use upload-image to create a project-less upload — but DELETE requires a project doc.
    # We'll insert a project by calling create-talking-avatar with bogus input OR use cartoonize which creates a project? 
    # Simpler: POST /api/avatar/dual-lipsync returns 400 before db insert. Use lipsync w/ dialogues.
    # Actually use something that creates a project doc quickly:
    # POST /api/create-image-to-video with uploaded PNG requires upload first.
    # Let's use upload + create-talking-avatar since we know it works + inserts a project.
    # Upload a valid image first
    try:
        # Use the existing 1x1 PNG — talking-avatar has own dimension guard maybe; easier: upload a bigger image
        # We can programmatically create a 128x128 PNG via Pillow
        try:
            from PIL import Image
            import io
            buf = io.BytesIO()
            Image.new("RGB", (128, 128), (200, 180, 150)).save(buf, "PNG")
            buf.seek(0)
            files = {"file": ("t.png", buf.getvalue(), "image/png")}
            ur = requests.post(f"{API}/upload-image", headers=H, files=files, timeout=30)
            up_path = ur.json().get("file_path") if ur.status_code == 200 else None
        except Exception as _e:
            up_path = None

        if up_path:
            cr = requests.post(f"{API}/create-talking-avatar", headers=H, timeout=30,
                               json={"image_path": up_path, "script": "Test delete flow", "voice_id": "hi-IN-SwaraNeural"})
            pid = cr.json().get("project_id") if cr.status_code == 200 else None
            if pid:
                dr = requests.delete(f"{API}/project/{pid}", headers=H, timeout=15)
                if dr.status_code == 200:
                    ok("A5 DELETE /api/project/{id}", f"created+deleted {pid[:8]}...")
                else:
                    bad("A5 DELETE", f"{dr.status_code} {dr.text[:200]}")
            else:
                bad("A5 create-talking-avatar", f"{cr.status_code} {cr.text[:200]}")
        else:
            bad("A5 upload-image", f"status={ur.status_code}")
    except Exception as e:
        bad("A5 create+delete flow", f"{e}")

    # Test DELETE of bogus id → 404
    dr = requests.delete(f"{API}/project/bogus-xxxxxxxxxxxxxxx", headers=H, timeout=15)
    if dr.status_code == 404:
        ok("A5b DELETE bogus→404")
    else:
        bad("A5b DELETE bogus", f"expected 404 got {dr.status_code}")

    # A6 download-video with fake url
    r = requests.get(f"{API}/download-video", params={"url":"https://example.com/test.mp4"}, timeout=30)
    if r.status_code in (502, 400, 404) and r.status_code != 500:
        ok("A6 /api/download-video fake url", f"status={r.status_code} (not 500)")
    else:
        bad("A6 /api/download-video", f"got {r.status_code}")

# ===================== B. b3 Hybrid batch char-gen =====================
def test_b_batch_chars():
    body_ok = {
        "style_id": "mythological",
        "slots": [
            {"role": "A", "gender": "male"},
            {"role": "A", "gender": "female"},
            {"role": "B", "gender": "male"},
            {"role": "B", "gender": "female"},
        ],
    }
    r = requests.post(f"{API}/avatar/generate-characters-batch", json=body_ok, timeout=30)
    jobs = None
    if r.status_code == 200:
        j = r.json()
        jobs = j.get("jobs") or []
        if len(jobs) == 4 and all("job_id" in x and "role" in x and "gender" in x for x in jobs):
            ok("B1 batch 4 slots → 200 jobs[4]", f"style={j.get('style')} count={j.get('count')}")
        else:
            bad("B1 batch shape", f"jobs={jobs}")
    else:
        bad("B1 batch 200", f"{r.status_code} {r.text[:200]}")

    # Unknown style
    r = requests.post(f"{API}/avatar/generate-characters-batch",
                      json={"style_id":"xyzunknown","slots":[{"role":"A","gender":"male"}]}, timeout=20)
    if r.status_code == 400:
        ok("B2 unknown style→400")
    else:
        bad("B2 unknown style", f"got {r.status_code}: {r.text[:150]}")

    # Empty slots
    r = requests.post(f"{API}/avatar/generate-characters-batch",
                      json={"style_id":"mythological","slots":[]}, timeout=20)
    if r.status_code == 400:
        ok("B3 empty slots→400")
    else:
        bad("B3 empty slots", f"got {r.status_code}: {r.text[:150]}")

    # 7 slots
    r = requests.post(f"{API}/avatar/generate-characters-batch",
                      json={"style_id":"mythological","slots":[{"role":"A","gender":"male"}]*7}, timeout=20)
    if r.status_code == 400:
        ok("B4 7 slots over limit→400")
    else:
        bad("B4 7 slots", f"got {r.status_code}: {r.text[:150]}")

    # Poll first job
    if jobs:
        jid = jobs[0]["job_id"]
        r = requests.get(f"{API}/avatar/jobs/{jid}", timeout=15)
        if r.status_code == 200:
            st = r.json().get("status")
            if st in ("queued","processing","completed","failed"):
                ok("B5a initial poll", f"job={jid} status={st}")
            else:
                bad("B5a poll status", f"status={st}")

            # Wait for completion up to ~90s
            deadline = time.time() + 120
            final = None
            while time.time() < deadline:
                r2 = requests.get(f"{API}/avatar/jobs/{jid}", timeout=15)
                if r2.status_code != 200:
                    break
                st2 = r2.json().get("status")
                if st2 in ("completed","failed"):
                    final = r2.json()
                    break
                time.sleep(4)
            if final and final.get("status") == "completed" and final.get("image_url"):
                ok("B5b poll → completed", f"image_url={final['image_url']}")
            elif final and final.get("status") == "failed":
                bad("B5b job failed", f"err={final.get('error','?')}")
            else:
                bad("B5b poll timeout", f"last={final}")
        else:
            bad("B5a poll", f"{r.status_code} {r.text[:200]}")

# ===================== C. Dual-lipsync validation =====================
def test_c_dual_lipsync():
    tok, _ = login()
    H = hdr(tok)
    # Must have image_b_path too → use same 1x1 PNG (it exists, small)
    base = {
        "image_a_path": IMG_1X1,
        "image_b_path": IMG_1X1,
        "script": "A: hello\nB: hi there",
        "voice_a_id": "en-US-JennyNeural",
        "voice_b_id": "en-US-GuyNeural",
    }

    # C1 Empty script → "Script is required"
    body = dict(base); body["script"] = ""
    r = requests.post(f"{API}/avatar/dual-lipsync", json=body, headers=H, timeout=15)
    if r.status_code == 400 and "script" in (r.text or "").lower():
        ok("C1 empty script→400", r.text[:120])
    elif r.status_code == 422:
        # pydantic min_length=6 catches this first → 422. Acceptable but flag
        ok("C1 empty script→422 (pydantic min_length)", r.text[:140])
    else:
        bad("C1 empty script", f"{r.status_code} {r.text[:200]}")

    # C2 Non-existent image_a
    body = dict(base); body["image_a_path"] = "/app/backend/uploads/does_not_exist_xyz.png"
    r = requests.post(f"{API}/avatar/dual-lipsync", json=body, headers=H, timeout=15)
    if r.status_code == 400 and "image a not found" in (r.text or "").lower():
        ok("C2 non-existent image_a→400 'Image A not found'")
    else:
        bad("C2 non-existent image_a", f"{r.status_code} {r.text[:200]}")

    # C3 1x1 PNG → dimension guard "too small"
    body = dict(base)  # both images are 1x1
    r = requests.post(f"{API}/avatar/dual-lipsync", json=body, headers=H, timeout=20)
    if r.status_code == 400 and "too small" in (r.text or "").lower():
        ok("C3 1x1 PNG dimension guard→400 'too small'", r.text[:140])
    else:
        bad("C3 1x1 PNG dimension guard", f"{r.status_code} {r.text[:200]}")

# ===================== Optional smoke tests =====================
def test_d_optional_smoke():
    # D1+D2 avatar/dialogues solo mode cache-busting nonce
    body1 = {"style_id":"mythological","idea":"Diwali greeting","mode":"solo","nonce":"ROUND9a","count":3,"language":"english"}
    r1 = requests.post(f"{API}/avatar/dialogues", json=body1, timeout=40)
    body2 = {**body1, "nonce":"ROUND9b"}
    r2 = requests.post(f"{API}/avatar/dialogues", json=body2, timeout=40)
    if r1.status_code == 200 and r2.status_code == 200:
        # Check monologue format: should be dialogues list
        d1 = r1.json(); d2 = r2.json()
        diff = json.dumps(d1.get("dialogues") or d1.get("suggestions") or d1) != json.dumps(d2.get("dialogues") or d2.get("suggestions") or d2)
        if diff:
            ok("D1/D2 dialogues solo ROUND9a vs ROUND9b differ", f"src1={d1.get('source')} src2={d2.get('source')}")
        else:
            bad("D1/D2 nonce cache-bust", "outputs identical")
    else:
        bad("D1/D2 dialogues", f"s1={r1.status_code} s2={r2.status_code}")

    # D3 preview-audio different voices
    def get_audio(voice_id):
        r = requests.post(f"{API}/generate-prompts/preview-audio",
                          json={"text":"Namaste testing", "voice_id": voice_id, "language":"english"}, timeout=30)
        if r.status_code == 200:
            return r.content
        return None
    a1 = get_audio("en-US-AriaNeural")
    a2 = get_audio("hi-IN-MadhurNeural")
    if a1 and a2:
        md1 = hashlib.md5(a1).hexdigest()
        md2 = hashlib.md5(a2).hexdigest()
        if md1 != md2:
            ok("D3 preview-audio voice switch differs", f"aria_md5={md1[:10]} madhur_md5={md2[:10]}")
        else:
            bad("D3 preview-audio same md5", f"{md1}")
    else:
        bad("D3 preview-audio", f"a1={bool(a1)} a2={bool(a2)}")

    # D4 avatar/suggestions Hindi in Devanagari not Marathi
    r = requests.post(f"{API}/avatar/suggestions",
                      json={"style_id":"mythological","emotion":"devotional","language":"hindi"}, timeout=30)
    if r.status_code == 200:
        sug = r.json().get("suggestions") or []
        # Check Devanagari presence + not Marathi-only markers (e.g., "आहे")
        has_dev = any(any("\u0900" <= c <= "\u097F" for c in s) for s in sug)
        marathi_markers = ("आहे", "मी", "तुम्ही", "होतो", "करतो")
        has_marathi = any(any(m in s for m in marathi_markers) for s in sug)
        if has_dev and not has_marathi:
            ok("D4 Hindi suggestions Devanagari not Marathi", f"samples={sug[:2]}")
        elif has_dev and has_marathi:
            bad("D4 Hindi suggestions look Marathi", f"samples={sug}")
        else:
            bad("D4 Hindi suggestions no Devanagari", f"samples={sug}")
    else:
        bad("D4 avatar/suggestions hindi", f"{r.status_code}")


if __name__ == "__main__":
    print(f"\n=== Base: {BASE} ===\n")
    print("\n--- A. Projects CRUD ---")
    try: test_a_projects()
    except Exception as e: bad("A exception", str(e))
    print("\n--- B. b3 Hybrid batch char-gen ---")
    try: test_b_batch_chars()
    except Exception as e: bad("B exception", str(e))
    print("\n--- C. Dual-lipsync validation ---")
    try: test_c_dual_lipsync()
    except Exception as e: bad("C exception", str(e))
    print("\n--- D. Optional smoke ---")
    try: test_d_optional_smoke()
    except Exception as e: bad("D exception", str(e))
    print(f"\n=== RESULT: PASS={len(PASS)}  FAIL={len(FAIL)} ===")
    if FAIL:
        print("\nFAIL cases:")
        for f in FAIL: print("  -", f)
    sys.exit(0 if not FAIL else 1)
