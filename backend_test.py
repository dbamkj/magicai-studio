"""Phase-1 Cinematic Preset System — backend verification.

Tests:
  A) GET /api/cinematic-presets (anon, paid, free)
  B) POST /api/create-talking-avatar with preset_id (5 cases)
  C) Quick regression sweep
"""
import base64
import io
import os
import time
import json
import requests
from PIL import Image, ImageDraw

BASE = os.environ.get(
    "BACKEND_URL",
    "https://creative-plan-engine.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE}/api"

CREATOR_EMAIL = "demo_creator@test.com"
CREATOR_PW = "Test@123"

FREE_EMAIL = "phase1test@example.com"
FREE_PW = "Test@123"

EXPECTED_PRESETS = [
    ("funny", "free"),
    ("emotional", "free"),
    ("bhakti", "pro"),
    ("motivation", "pro"),
    ("influencer", "pro"),
    ("cinematic", "pro"),
]
REQUIRED_TOP_KEYS = {"id", "label", "emoji", "tagline", "plan_tier", "locked", "config"}
REQUIRED_CFG_KEYS = {
    "emotion", "intensity", "voice_style", "voice_rate", "voice_pitch",
    "motion", "camera", "lighting", "effects", "bgm",
}

results = []


def log(name, passed, detail=""):
    tag = "PASS" if passed else "FAIL"
    results.append((name, passed, detail))
    print(f"[{tag}] {name} :: {detail}"[:600])


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    if r.status_code != 200:
        return None, r
    return r.json().get("token"), r


def register_or_login(email, pw):
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": pw, "name": "Phase1 Test", "plan": "free"},
        timeout=30,
    )
    if r.status_code in (200, 201):
        return r.json().get("token"), r.json().get("user", {})
    if r.status_code == 409:
        tok, lr = login(email, pw)
        if tok:
            return tok, lr.json().get("user", {})
    return None, None


def make_test_png_512x768() -> bytes:
    img = Image.new("RGB", (512, 768), color=(220, 200, 180))
    d = ImageDraw.Draw(img)
    d.ellipse((150, 150, 380, 380), fill=(255, 220, 200), outline=(0, 0, 0))
    d.ellipse((200, 220, 230, 250), fill=(0, 0, 0))
    d.ellipse((300, 220, 330, 250), fill=(0, 0, 0))
    d.rectangle((230, 320, 300, 340), fill=(180, 50, 50))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def upload_image(token, png_bytes):
    files = {"file": ("face.png", png_bytes, "image/png")}
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{API}/upload-image", files=files, headers=headers, timeout=60)
    if r.status_code != 200:
        print("upload-image failed:", r.status_code, r.text[:300])
        return None
    return r.json().get("file_path")


# ── A) /api/cinematic-presets ──

def test_a1_anonymous():
    r = requests.get(f"{API}/cinematic-presets", timeout=20)
    if r.status_code != 200:
        log("A1 anonymous", False, f"HTTP {r.status_code}: {r.text[:200]}")
        return
    presets = (r.json() or {}).get("presets") or []
    if len(presets) != 6:
        log("A1 anonymous", False, f"expected 6 presets, got {len(presets)}")
        return
    expected_locks = {"funny": False, "emotional": False, "bhakti": True,
                      "motivation": True, "influencer": True, "cinematic": True}
    issues = []
    for (eid, etier) in EXPECTED_PRESETS:
        match = next((p for p in presets if p.get("id") == eid), None)
        if not match:
            issues.append(f"missing {eid}")
            continue
        if match.get("plan_tier") != etier:
            issues.append(f"{eid} tier {match.get('plan_tier')} != {etier}")
        if match.get("locked") != expected_locks[eid]:
            issues.append(f"{eid} locked={match.get('locked')} expected {expected_locks[eid]}")
        missing_top = REQUIRED_TOP_KEYS - set(match.keys())
        if missing_top:
            issues.append(f"{eid} missing top keys {missing_top}")
        cfg = match.get("config") or {}
        missing_cfg = REQUIRED_CFG_KEYS - set(cfg.keys())
        if missing_cfg:
            issues.append(f"{eid} missing cfg keys {missing_cfg}")
        if not isinstance(cfg.get("effects"), list):
            issues.append(f"{eid} effects not a list")
    if issues:
        log("A1 anonymous", False, "; ".join(issues[:6]))
    else:
        log("A1 anonymous", True, "6 presets, locks correct, all required keys present")


def test_a2_paid_creator(creator_tok):
    r = requests.get(
        f"{API}/cinematic-presets",
        headers={"Authorization": f"Bearer {creator_tok}"},
        timeout=20,
    )
    if r.status_code != 200:
        log("A2 creator (paid)", False, f"HTTP {r.status_code}: {r.text[:200]}")
        return
    presets = (r.json() or {}).get("presets") or []
    if len(presets) != 6:
        log("A2 creator (paid)", False, f"expected 6 got {len(presets)}")
        return
    locked_any = [p["id"] for p in presets if p.get("locked")]
    if locked_any:
        log("A2 creator (paid)", False, f"expected ALL unlocked, but locked={locked_any}")
    else:
        log("A2 creator (paid)", True, "all 6 unlocked for creator tier")


def test_a3_free_user(free_tok):
    r = requests.get(
        f"{API}/cinematic-presets",
        headers={"Authorization": f"Bearer {free_tok}"},
        timeout=20,
    )
    if r.status_code != 200:
        log("A3 free user", False, f"HTTP {r.status_code}: {r.text[:200]}")
        return
    presets = (r.json() or {}).get("presets") or []
    expected = {"funny": False, "emotional": False, "bhakti": True,
                "motivation": True, "influencer": True, "cinematic": True}
    issues = []
    for p in presets:
        e = expected.get(p["id"])
        if e is None:
            continue
        if p.get("locked") != e:
            issues.append(f"{p['id']} locked={p.get('locked')} expected {e}")
    if issues:
        log("A3 free user", False, "; ".join(issues))
    else:
        log("A3 free user", True, "free unlocked, pro locked")


# ── B) /api/create-talking-avatar with preset_id ──

def poll_project(token, project_id, max_wait=90):
    deadline = time.time() + max_wait
    last = None
    while time.time() < deadline:
        r = requests.get(
            f"{API}/project/{project_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
        if r.status_code == 200:
            last = r.json()
            st = last.get("status")
            if st in ("completed", "failed"):
                return last
        time.sleep(3)
    return last


def test_b1(creator_tok, image_path):
    body = {
        "image_path": image_path,
        "script": "Yeh ek funny test hai. Hari Om.",
        "voice_id": "hi-IN-SwaraNeural",
        "use_procedural_lipsync": True,
        "preset_id": "funny",
    }
    r = requests.post(
        f"{API}/create-talking-avatar",
        json=body,
        headers={"Authorization": f"Bearer {creator_tok}"},
        timeout=60,
    )
    if r.status_code != 200:
        log("B1 funny preset (free, paid user)", False, f"HTTP {r.status_code}: {r.text[:300]}")
        return
    pid = r.json().get("project_id")
    final = poll_project(creator_tok, pid, max_wait=120)
    st = final.get("status") if final else None
    if st == "completed":
        log("B1 funny preset (free, paid user)", True, f"project={pid} completed")
    else:
        log("B1 funny preset (free, paid user)", False,
            f"project={pid} status={st} err={(final or {}).get('error')}")


def test_b2(creator_tok, image_path):
    body = {
        "image_path": image_path,
        "script": "Yeh ek funny test hai. Hari Om.",
        "voice_id": "hi-IN-SwaraNeural",
        "use_procedural_lipsync": True,
        "preset_id": "cinematic",
    }
    r = requests.post(
        f"{API}/create-talking-avatar",
        json=body,
        headers={"Authorization": f"Bearer {creator_tok}"},
        timeout=60,
    )
    if r.status_code != 200:
        log("B2 cinematic preset (pro, paid user)", False, f"HTTP {r.status_code}: {r.text[:300]}")
        return
    pid = r.json().get("project_id")
    final = poll_project(creator_tok, pid, max_wait=120)
    st = final.get("status") if final else None
    if st == "completed":
        log("B2 cinematic preset (pro, paid user)", True, f"project={pid} completed")
    else:
        log("B2 cinematic preset (pro, paid user)", False,
            f"project={pid} status={st} err={(final or {}).get('error')}")


def test_b3(free_tok, image_path):
    body = {
        "image_path": image_path,
        "script": "Yeh ek funny test hai. Hari Om.",
        "voice_id": "hi-IN-SwaraNeural",
        "use_procedural_lipsync": True,
        "preset_id": "cinematic",
    }
    r = requests.post(
        f"{API}/create-talking-avatar",
        json=body,
        headers={"Authorization": f"Bearer {free_tok}"},
        timeout=60,
    )
    if r.status_code != 402:
        log("B3 cinematic preset (free user paywall)", False,
            f"expected 402, got {r.status_code}: {r.text[:400]}")
        return
    try:
        body_j = r.json()
        detail = body_j.get("detail") or {}
        ok = (
            detail.get("code") == "preset_locked"
            and detail.get("preset_id") == "cinematic"
            and "message" in detail
            and "cta" in detail
        )
        if ok:
            log("B3 cinematic preset (free user paywall)", True,
                f"402 detail.code=preset_locked cta='{detail.get('cta')}'")
        else:
            log("B3 cinematic preset (free user paywall)", False,
                f"detail shape wrong: {detail}")
    except Exception as e:
        log("B3 cinematic preset (free user paywall)", False, f"json parse failed: {e}")


def test_b4(creator_tok, image_path):
    body = {
        "image_path": image_path,
        "script": "Yeh ek funny test hai. Hari Om.",
        "voice_id": "hi-IN-SwaraNeural",
        "use_procedural_lipsync": True,
        "preset_id": "nonexistent_preset_xyz",
    }
    r = requests.post(
        f"{API}/create-talking-avatar",
        json=body,
        headers={"Authorization": f"Bearer {creator_tok}"},
        timeout=60,
    )
    if r.status_code != 400:
        log("B4 unknown preset_id", False, f"expected 400, got {r.status_code}: {r.text[:300]}")
        return
    detail_str = json.dumps(r.json())
    if "Unknown preset_id" in detail_str:
        log("B4 unknown preset_id", True, "400 mentions Unknown preset_id")
    else:
        log("B4 unknown preset_id", False, f"detail missing 'Unknown preset_id': {detail_str[:200]}")


def test_b5(creator_tok, image_path):
    body = {
        "image_path": image_path,
        "script": "Yeh regression test hai.",
        "voice_id": "hi-IN-SwaraNeural",
        "use_procedural_lipsync": True,
    }
    r = requests.post(
        f"{API}/create-talking-avatar",
        json=body,
        headers={"Authorization": f"Bearer {creator_tok}"},
        timeout=60,
    )
    if r.status_code != 200:
        log("B5 no preset (regression)", False, f"HTTP {r.status_code}: {r.text[:300]}")
        return
    pid = r.json().get("project_id")
    final = poll_project(creator_tok, pid, max_wait=120)
    st = final.get("status") if final else None
    if st == "completed":
        log("B5 no preset (regression)", True, f"project={pid} completed without preset_id")
    else:
        log("B5 no preset (regression)", False, f"status={st}")


# ── C) Regression sweep ──

def test_c1_health():
    r = requests.get(f"{API}/", timeout=15)
    v = r.json().get("version", "") if r.status_code == 200 else ""
    if r.status_code == 200 and v.startswith("7."):
        log("C1 GET /api/", True, f"version={v}")
    else:
        log("C1 GET /api/", False, f"HTTP {r.status_code} version={v}")


def test_c3_avatar_styles():
    r = requests.get(f"{API}/avatar/styles", timeout=20)
    if r.status_code != 200:
        log("C3 GET /api/avatar/styles", False, f"HTTP {r.status_code}")
        return
    body = r.json()
    emotions = body.get("emotions") or []
    if len(emotions) >= 12:
        log("C3 GET /api/avatar/styles", True, f"emotions={len(emotions)}")
    else:
        log("C3 GET /api/avatar/styles", False, f"emotions={len(emotions)} (need >=12)")


def test_c4_cartoonize(creator_tok, png_bytes):
    b64 = base64.b64encode(png_bytes).decode("ascii")
    body = {
        "style": "pixar",
        "emotion": "happy",
        "image_base64": b64,
        "prompt": "young Indian woman with long dark hair",
    }
    r = requests.post(
        f"{API}/avatar/cartoonize",
        json=body,
        headers={"Authorization": f"Bearer {creator_tok}"},
        timeout=60,
    )
    if r.status_code != 200:
        log("C4 POST /api/avatar/cartoonize", False, f"HTTP {r.status_code}: {r.text[:300]}")
        return
    job_id = r.json().get("job_id")
    if job_id:
        log("C4 POST /api/avatar/cartoonize", True, f"job_id={job_id}")
    else:
        log("C4 POST /api/avatar/cartoonize", False, "no job_id in response")


def main():
    print(f"BASE={BASE}")

    test_c1_health()

    creator_tok, r = login(CREATOR_EMAIL, CREATOR_PW)
    if not creator_tok:
        log("C2 login demo_creator", False, f"failed: {r.status_code if r else 'n/a'}")
        return
    log("C2 login demo_creator", True, "200 with token")

    free_tok, free_user = register_or_login(FREE_EMAIL, FREE_PW)
    if not free_tok:
        free_tok, lr = login("beta_user_3@test.com", "Test@123")
        free_user = (lr.json().get("user") if lr else {}) or {}
        print("free token via beta_user_3:", bool(free_tok), "tier:", free_user.get("subscription_tier"))
    else:
        print("free user tier:", free_user.get("subscription_tier"))

    test_a1_anonymous()
    test_a2_paid_creator(creator_tok)
    if free_tok:
        test_a3_free_user(free_tok)
    else:
        log("A3 free user", False, "no free user token")

    png_bytes = make_test_png_512x768()
    image_path = upload_image(creator_tok, png_bytes)
    if image_path:
        log("upload-image (creator)", True, f"path={image_path}")
        test_b1(creator_tok, image_path)
        test_b2(creator_tok, image_path)
        if free_tok:
            test_b3(free_tok, image_path)
        test_b4(creator_tok, image_path)
        test_b5(creator_tok, image_path)
    else:
        log("upload-image (creator)", False, "upload failed")

    test_c3_avatar_styles()
    test_c4_cartoonize(creator_tok, png_bytes)

    print("\n========== SUMMARY ==========")
    passed = sum(1 for _, p, _ in results if p)
    failed = sum(1 for _, p, _ in results if not p)
    for name, p, detail in results:
        print(f"  {'OK ' if p else 'FAIL'}  {name}  -- {detail[:200]}")
    print(f"TOTAL: {passed} passed, {failed} failed")


if __name__ == "__main__":
    main()
