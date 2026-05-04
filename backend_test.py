"""
Session-34B Tier Gating Verification — backend test.
Tests /api/me/limits, tier gate enforcement (402), preview-voice, regression.
"""
import sys
import requests

BASE = "https://creative-plan-engine.preview.emergentagent.com"
API = f"{BASE}/api"

ACCOUNTS = {
    "free":    {"email": "demo_free@test.com",    "tier": "free",    "credits": 300,  "price": 0,    "max_res": "480p"},
    "starter": {"email": "demo_starter@test.com", "tier": "starter", "credits": 1500, "price": 249,  "max_res": "720p"},
    "creator": {"email": "demo_creator@test.com", "tier": "creator", "credits": 3000, "price": 599,  "max_res": "720p"},
    "pro":     {"email": "demo_pro@test.com",     "tier": "pro",     "credits": 6000, "price": 1499, "max_res": "1080p"},
}
PASSWORD = "Test@123"

results = []
def rec(section, name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    results.append((section, name, ok, detail))
    print(f"[{status}] [{section}] {name}: {detail}")


def login(email, password=PASSWORD):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    if r.status_code != 200:
        return None, f"login {email} -> {r.status_code} {r.text[:200]}"
    data = r.json()
    return data.get("token") or data.get("access_token"), None


tokens = {}

# =========================
# Section A — /api/me/limits
# =========================
EXPECTED_GATES_FREE    = {k: False for k in ["face_swap","lip_sync","head_swap","body_swap","video_to_video","divine","ai_bg_lipsync","multishot","ai_video","video_studio","video_cinematic","image_cinematic"]}
EXPECTED_GATES_STARTER = {**EXPECTED_GATES_FREE, "face_swap": True, "lip_sync": True, "head_swap": True, "body_swap": True}
EXPECTED_GATES_CREATOR = {k: True for k in EXPECTED_GATES_FREE}
EXPECTED_GATES_CREATOR["video_cinematic"] = False
EXPECTED_GATES_PRO     = {k: True for k in EXPECTED_GATES_FREE}

EXPECTED_GATES = {
    "free": EXPECTED_GATES_FREE,
    "starter": EXPECTED_GATES_STARTER,
    "creator": EXPECTED_GATES_CREATOR,
    "pro": EXPECTED_GATES_PRO,
}

def section_a():
    print("\n=== Section A — /api/me/limits ===")
    for key, info in ACCOUNTS.items():
        tok, err = login(info["email"])
        if err:
            rec("A", f"login {key}", False, err)
            continue
        tokens[key] = tok
        r = requests.get(f"{API}/me/limits", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        if r.status_code != 200:
            rec("A", f"GET /me/limits {key}", False, f"status={r.status_code} body={r.text[:300]}")
            continue
        data = r.json()
        # Required keys
        required = {"tier","credits","usage_this_month","usage_today","feature_gates","upgrade_hints"}
        missing = required - set(data.keys())
        if missing:
            rec("A", f"keys {key}", False, f"missing: {missing}")
            continue
        rec("A", f"keys {key}", True, "all 6 top-level keys present")

        tier = data["tier"]
        # tier.id
        tier_id_ok = tier.get("id") == info["tier"]
        rec("A", f"tier.id {key}", tier_id_ok, f"got={tier.get('id')} expected={info['tier']}")
        # tier.price_inr - integer
        price = tier.get("price_inr")
        price_int_ok = isinstance(price, int) and not isinstance(price, bool)
        rec("A", f"tier.price_inr type {key}", price_int_ok, f"value={price} type={type(price).__name__}")
        rec("A", f"tier.price_inr value {key}", price == info["price"], f"got={price} expected={info['price']}")
        # tier.max_resolution
        rec("A", f"tier.max_resolution {key}", tier.get("max_resolution") == info["max_res"], f"got={tier.get('max_resolution')} expected={info['max_res']}")

        # feature_gates 12 keys
        gates = data["feature_gates"]
        expected_gates = EXPECTED_GATES[key]
        if set(gates.keys()) != set(expected_gates.keys()):
            rec("A", f"gates keys {key}", False, f"got={sorted(gates.keys())} expected={sorted(expected_gates.keys())}")
        else:
            rec("A", f"gates keys {key}", True, "12 keys present")
        # gates values
        mismatches = {k: (gates.get(k), expected_gates[k]) for k in expected_gates if gates.get(k) != expected_gates[k]}
        rec("A", f"gates values {key}", not mismatches, f"mismatches={mismatches}" if mismatches else "all match")

        # upgrade hints
        hints = data.get("upgrade_hints", [])
        if key == "pro":
            rec("A", "pro upgrade_hints empty", hints == [], f"got={hints}")
        elif key == "creator":
            text_blob = " ".join(h.get("text","") for h in hints).lower()
            ok = ("kling 3.0" in text_blob) or ("veo" in text_blob)
            rec("A", "creator upgrade_hints mentions Kling 3.0/Veo", ok, f"hints text='{text_blob}'")

        # usage_today.images.cap
        cap = data.get("usage_today", {}).get("images", {}).get("cap")
        expected_cap = 5 if key == "free" else 9999
        rec("A", f"usage_today.images.cap {key}", cap == expected_cap, f"got={cap} expected={expected_cap}")


# =========================
# Section B — Tier gate enforcement (402)
# =========================
def expect_402(section, name, resp, expected_substr):
    if resp.status_code != 402:
        rec(section, name, False, f"status={resp.status_code} body={resp.text[:300]}")
        return
    try:
        body = resp.json()
        detail = body.get("detail", "")
    except Exception:
        detail = resp.text
    if not isinstance(detail, str) or not detail.strip():
        rec(section, name, False, f"detail not human-readable: {detail!r}")
        return
    ok = expected_substr.lower() in detail.lower()
    rec(section, name, ok, f"detail='{detail}' (expected substring='{expected_substr}')")


def section_b():
    print("\n=== Section B — Tier gate enforcement ===")
    h_free    = {"Authorization": f"Bearer {tokens['free']}"}
    h_starter = {"Authorization": f"Bearer {tokens['starter']}"}
    h_creator = {"Authorization": f"Bearer {tokens['creator']}"}

    # B1: free /api/create-faceswap
    r = requests.post(f"{API}/create-faceswap", headers=h_free, json={"target_video_path":"/tmp/x.mp4","source_image_paths":["/tmp/y.png"]}, timeout=30)
    expect_402("B", "B1 free->faceswap", r, "Face Swap requires Starter plan or higher.")

    # B2: free /api/create-headswap
    r = requests.post(f"{API}/create-headswap", headers=h_free, json={"head_image_path":"/tmp/h.png","body_image_path":"/tmp/b.png"}, timeout=30)
    expect_402("B", "B2 free->headswap", r, "Head Swap requires Starter plan or higher.")

    # B3: free /api/create-bodyswap
    r = requests.post(f"{API}/create-bodyswap", headers=h_free, json={"person_image_path":"/tmp/p.png","garment_image_path":"/tmp/g.png","garment_type":"dress"}, timeout=30)
    expect_402("B", "B3 free->bodyswap", r, "Body Swap requires Starter plan or higher.")

    # B4: starter /api/create-video-to-video
    r = requests.post(f"{API}/create-video-to-video", headers=h_starter, json={"video_path":"/tmp/v.mp4","prompt":"x","art_style":"Anime","duration":5}, timeout=30)
    expect_402("B", "B4 starter->v2v", r, "Video-to-Video style transfer requires Creator plan or higher.")

    # B5: starter /api/generate-video studio
    r = requests.post(f"{API}/generate-video", headers=h_starter, json={"prompt":"x","duration":5,"quality_mode":"studio"}, timeout=30)
    expect_402("B", "B5 starter->generate-video studio", r, "AI Video requires Creator plan or higher")

    # B6: creator /api/generate-video cinematic
    r = requests.post(f"{API}/generate-video", headers=h_creator, json={"prompt":"x","duration":3,"quality_mode":"cinematic"}, timeout=30)
    expect_402("B", "B6 creator->generate-video cinematic", r, "Kling 3.0 Pro")

    # B7: starter /api/generate-image cinematic
    r = requests.post(f"{API}/generate-image", headers=h_starter, json={"prompt":"x","quality":"cinematic"}, timeout=30)
    expect_402("B", "B7 starter->generate-image cinematic", r, "FLUX Pro (cinematic) image quality requires Creator plan or higher.")


# =========================
# Section C — credits-info regression
# =========================
def section_c():
    print("\n=== Section C — /api/credits-info regression ===")
    r = requests.get(f"{API}/credits-info", timeout=30)
    if r.status_code != 200:
        rec("C", "GET /credits-info", False, f"status={r.status_code}")
        return
    data = r.json()
    cost = data.get("cost_table") or {}
    qt = data.get("quality_tiers") or []
    rec("C", "cost_table non-empty", bool(cost), f"keys={list(cost.keys())[:8]}")
    needed_costs = ["lip_sync_per_sec","face_swap_per_sec","head_swap","ai_image_generator","ai_clothes_changer"]
    rec("C", "cost_table required keys", all(k in cost for k in needed_costs), f"missing={[k for k in needed_costs if k not in cost]}")
    qt_ids = [t.get("id") for t in qt] if isinstance(qt, list) else (list(qt.keys()) if isinstance(qt, dict) else [])
    rec("C", "quality_tiers has quick/studio/cinematic", set(["quick","studio","cinematic"]).issubset(set(qt_ids)), f"got={qt_ids}")


# =========================
# Section D — preview-voice
# =========================
def section_d():
    print("\n=== Section D — /api/preview-voice ===")
    r = requests.get(f"{API}/preview-voice", params={"voice_id":"en-US-JennyNeural"}, timeout=60)
    ok = r.status_code == 200 and "audio/mpeg" in (r.headers.get("Content-Type") or "") and len(r.content) > 10*1024
    rec("D", "preview-voice valid", ok, f"status={r.status_code} ct={r.headers.get('Content-Type')} bytes={len(r.content)}")
    r2 = requests.get(f"{API}/preview-voice", params={"voice_id":"BOGUS_VOICE"}, timeout=60)
    detail = ""
    try:
        if r2.status_code == 500:
            detail = r2.json().get("detail","")
    except Exception:
        pass
    ok2 = (r2.status_code == 200) or (r2.status_code == 500 and isinstance(detail, str) and detail.strip())
    rec("D", "preview-voice bogus handled", ok2, f"status={r2.status_code} bytes={len(r2.content)} detail={detail!r}")


# =========================
# Section E — regression
# =========================
def section_e():
    print("\n=== Section E — Regression ===")
    r = requests.get(f"{API}/", timeout=15)
    rec("E", "GET /", r.status_code == 200 and r.json().get("version") == "7.1.0", f"status={r.status_code} body={r.text[:120]}")

    r = requests.get(f"{API}/credits-info", timeout=15)
    needed = {"credits_used_total","completed_jobs","cost_table","pricing","quality_tiers","resolutions","resolutions_enabled","note"}
    body = r.json() if r.status_code == 200 else {}
    rec("E", "credits-info keys", r.status_code == 200 and needed.issubset(set(body.keys())), f"missing={needed - set(body.keys())}")

    r = requests.get(f"{API}/mh-models", timeout=15)
    feats = (r.json().get("features") or {}) if r.status_code == 200 else {}
    rec("E", "mh-models 8 features", r.status_code == 200 and len(feats) == 8, f"len={len(feats)}")

    r = requests.get(f"{API}/usage", headers={"Authorization": f"Bearer {tokens['creator']}"}, timeout=15)
    rec("E", "usage with creator token", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")

    r = requests.get(f"{API}/templates/preview-stats", timeout=15)
    cov = r.json().get("coverage_pct") if r.status_code == 200 else None
    rec("E", "templates/preview-stats coverage_pct=100", r.status_code == 200 and cov == 100.0, f"cov={cov}")

    r = requests.post(f"{API}/creative-plan", json={"idea":"test"}, timeout=60)
    body = r.json() if r.status_code == 200 else {}
    rec("E", "creative-plan keys", r.status_code == 200 and all(k in body for k in ("hook","script","scene_keywords")), f"status={r.status_code} keys={list(body.keys())[:6]}")

    r = requests.get(f"{API}/cinematic-presets", timeout=15)
    body = r.json() if r.status_code == 200 else {}
    if isinstance(body, list):
        presets = body
    else:
        presets = body.get("presets") or []
    rec("E", "cinematic-presets 6", r.status_code == 200 and len(presets) == 6, f"status={r.status_code} count={len(presets) if presets else 0}")

    r = requests.get(f"{API}/marketplace/templates", params={"limit":5}, timeout=30)
    body = r.json() if r.status_code == 200 else {}
    items = body if isinstance(body, list) else (body.get("templates") or [])
    rec("E", "marketplace 5 items", r.status_code == 200 and len(items) == 5, f"count={len(items)}")


if __name__ == "__main__":
    section_a()
    section_b()
    section_c()
    section_d()
    section_e()

    print("\n=== SUMMARY ===")
    fails = [r for r in results if not r[2]]
    passes = [r for r in results if r[2]]
    print(f"PASS: {len(passes)}  FAIL: {len(fails)}")
    for s,n,ok,d in fails:
        print(f"  X [{s}] {n}: {d}")
    sys.exit(0 if not fails else 1)
