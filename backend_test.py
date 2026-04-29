"""V1.0 hardening sweep for MagiCAi Studio backend."""
import os
import time
import json
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL") or "https://creative-plan-engine.preview.emergentagent.com"
API = BASE.rstrip("/") + "/api"

results = []
def rec(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name} :: {detail}")
    results.append({"name": name, "ok": ok, "detail": detail})

# ---------- 1. Auth ----------
def test_auth():
    creds = [
        ("demo_free@test.com", "Test@123", "free", 300),
        ("demo_creator@test.com", "Test@123", "creator", 3000),
    ]
    tokens = {}
    for email, pw, exp_tier, exp_credits in creds:
        try:
            r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
            ok = r.status_code == 200
            data = r.json() if ok else {}
            token = data.get("token") or data.get("access_token") or data.get("session_token")
            user = data.get("user") or {}
            tier = user.get("subscription_tier")
            credits = user.get("credits_balance")
            ok2 = ok and bool(token) and tier == exp_tier and credits == exp_credits
            rec(f"Auth login {email}", ok2,
                f"status={r.status_code} tier={tier} credits={credits} expected_tier={exp_tier} expected_credits={exp_credits}")
            if token:
                tokens[email] = token
        except Exception as e:
            rec(f"Auth login {email}", False, f"exc={e}")
    # negative
    r = requests.post(f"{API}/auth/login", json={"email": "demo_free@test.com", "password": "wrong"}, timeout=10)
    rec("Auth login wrong password -> 401", r.status_code == 401, f"got {r.status_code}")
    return tokens

# ---------- 2. Creative Plan ----------
def test_creative_plan():
    plan_id = None
    body = {"idea": "Krishna bhajan", "language": "hindi", "duration": 20, "scene_count": 4}
    try:
        r = requests.post(f"{API}/creative-plan", json=body, timeout=60)
        ok = r.status_code == 200
        d = r.json() if ok else {}
        keys_ok = all(k in d for k in ["creative_plan_id", "hook", "script", "scene_keywords", "voice_style", "bgm_style", "mood"])
        types_ok = isinstance(d.get("hook"), str) and isinstance(d.get("script"), list) and isinstance(d.get("scene_keywords"), list)
        plan_id = d.get("creative_plan_id")
        rec("Creative-plan basic", ok and keys_ok and types_ok,
            f"status={r.status_code} plan_id={plan_id} keys_ok={keys_ok} src={d.get('source')}")
    except Exception as e:
        rec("Creative-plan basic", False, f"exc={e}")

    # cache hit
    try:
        r2 = requests.post(f"{API}/creative-plan", json=body, timeout=60)
        d2 = r2.json() if r2.status_code == 200 else {}
        same = d2.get("creative_plan_id") == plan_id
        is_cache = d2.get("source") == "cache"
        rec("Creative-plan cache hit", same and is_cache,
            f"plan_id_match={same} source={d2.get('source')}")
    except Exception as e:
        rec("Creative-plan cache hit", False, f"exc={e}")

    # template_id variant
    try:
        r3 = requests.post(f"{API}/creative-plan", json={"template_id": "mp_bhajan_01"}, timeout=60)
        ok3 = r3.status_code == 200
        d3 = r3.json() if ok3 else {}
        keys_ok3 = all(k in d3 for k in ["creative_plan_id", "hook", "script", "scene_keywords"])
        rec("Creative-plan template_id=mp_bhajan_01", ok3 and keys_ok3,
            f"status={r3.status_code} src={d3.get('source')} body={r3.text[:160] if not ok3 else ''}")
    except Exception as e:
        rec("Creative-plan template_id=mp_bhajan_01", False, f"exc={e}")

    # negative: empty idea no template_id
    try:
        r4 = requests.post(f"{API}/creative-plan", json={"language": "english"}, timeout=15)
        rec("Creative-plan empty idea -> 400/422", r4.status_code in (400, 422),
            f"got {r4.status_code} body={r4.text[:120]}")
    except Exception as e:
        rec("Creative-plan empty idea -> 400/422", False, f"exc={e}")

    return plan_id

# ---------- 3. Marketplace ----------
def test_marketplace():
    try:
        r = requests.get(f"{API}/marketplace/templates?limit=200", timeout=20)
        ok = r.status_code == 200
        d = r.json() if ok else {}
        items = d.get("templates", [])
        cnt = len(items)
        rec("Marketplace list count ~42", 35 <= cnt <= 60, f"count={cnt}")

        missing = []
        for t in items:
            for k in ("id", "title", "thumbnail", "preview_url", "plan_tier"):
                if not t.get(k):
                    missing.append((t.get("id"), k))
        rec("Marketplace required fields present", len(missing) == 0,
            f"missing_count={len(missing)} sample={missing[:5]}")

        by_id = {t["id"]: t for t in items if t.get("id")}
        ids_to_check = ["mp_funny_03", "mp_bhajan_04", "mp_emotional_04", "mp_aesthetic_01"]
        present = {i: i in by_id for i in ids_to_check}
        rec("Marketplace required ids present", all(present.values()), f"presence={present}")

        funny03 = by_id.get("mp_funny_03", {})
        title = funny03.get("title", "")
        is_baba = "AI Baba" in title and "Aunty" not in title
        rec("Marketplace mp_funny_03 title is 'AI Baba' (not 'Aunty Roast')", is_baba, f"title='{title}'")
    except Exception as e:
        rec("Marketplace tests", False, f"exc={e}")

# ---------- 4. Trending ----------
def test_trending():
    try:
        r = requests.get(f"{API}/templates", timeout=20)
        ok = r.status_code == 200
        d = r.json() if ok else {}
        items = d.get("templates") if isinstance(d, dict) and "templates" in d else (d if isinstance(d, list) else [])
        cnt = len(items)
        rec("Trending GET /api/templates count ~26", 20 <= cnt <= 40, f"count={cnt}")

        previews = [t.get("preview_url") for t in items if t.get("preview_url")]
        dupes = len(previews) - len(set(previews))
        rec("Trending unique preview_urls (no dupes)", dupes == 0,
            f"total_with_preview={len(previews)} unique={len(set(previews))} dupes={dupes}")
    except Exception as e:
        rec("Trending list", False, f"exc={e}")

    try:
        url = f"{API}/serve-file/preview_insp_mot_pro_ceo_mindset_audio.mp4"
        r2 = requests.get(url, timeout=30, stream=True)
        ct = r2.headers.get("content-type", "")
        ok = r2.status_code == 200 and "video" in ct.lower()
        rec("Serve-file CEO Mindset audio mp4", ok, f"status={r2.status_code} content-type={ct}")
        r2.close()
    except Exception as e:
        rec("Serve-file CEO Mindset audio mp4", False, f"exc={e}")

# ---------- 5. Wizard ----------
def test_wizard(token, creative_plan_id):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    body_user = {
        "idea": "krishna",
        "creative_plan_id": creative_plan_id or "",
        "mode": "video",
        "total_duration": 20,
        "voice_id": "meera",
        "aspect_ratio": "9:16",
        "duration_per_shot": 2.5,
        "lang": "hindi",
    }
    job_id = None
    try:
        r = requests.post(f"{API}/wizard/create-reel", json=body_user, headers=headers, timeout=20)
        first_status = r.status_code
        first_body = r.text[:200]
        if r.status_code == 422:
            body_user["script"] = "Krishna ki bhakti me khoye rahna hi sukh hai aur sukoon"
            body_user["image_query"] = "krishna devotional"
            r = requests.post(f"{API}/wizard/create-reel", json=body_user, headers=headers, timeout=20)
        ok = r.status_code == 200
        d = r.json() if ok else {}
        job_id = d.get("job_id")
        rec("Wizard create-reel POST", ok and bool(job_id),
            f"first_status={first_status} retry_status={r.status_code} job_id={job_id} first_body={first_body if first_status != 200 else ''}")
    except Exception as e:
        rec("Wizard create-reel POST", False, f"exc={e}")

    if not job_id:
        return

    # Try BOTH /wizard/jobs/{id} (spec) and /wizard/job/{id} (actual route)
    poll_ok = False
    for path in (f"/wizard/jobs/{job_id}", f"/wizard/job/{job_id}"):
        try:
            r2 = requests.get(f"{API}{path}", timeout=15)
            if r2.status_code == 200:
                d2 = r2.json()
                status = d2.get("status")
                ok = status in ("queued", "running", "processing", "completed", "failed")
                rec(f"Wizard GET {path}", ok, f"status_field={status} progress={d2.get('progress')}")
                if ok:
                    poll_ok = True
            else:
                rec(f"Wizard GET {path}", False, f"http={r2.status_code}")
        except Exception as e:
            rec(f"Wizard GET {path}", False, f"exc={e}")

    # negative
    try:
        r3 = requests.get(f"{API}/wizard/job/nonexistent_id_xyz_404test", timeout=10)
        rec("Wizard GET nonexistent job -> 404", r3.status_code == 404, f"got {r3.status_code}")
    except Exception as e:
        rec("Wizard GET nonexistent job -> 404", False, f"exc={e}")

# ---------- 6. Pricing/Subscription ----------
def test_pricing():
    found_path = None
    plans_data = None
    for path in ("/pricing", "/subscription/plans"):
        try:
            r = requests.get(f"{API}{path}", timeout=10)
            if r.status_code == 200:
                found_path = path
                plans_data = r.json()
                break
        except Exception:
            pass
    rec("Pricing endpoint reachable", plans_data is not None, f"path={found_path}")
    if plans_data is None:
        return

    plist = plans_data.get("plans") if isinstance(plans_data, dict) else plans_data
    by_tier = {}
    for p in plist:
        tier = (p.get("id") or p.get("tier") or p.get("plan_id") or p.get("name") or "").lower()
        credits = p.get("credits") or p.get("credits_balance") or p.get("monthly_credits")
        by_tier[tier] = credits
    free_credits = by_tier.get("free")
    rec("Pricing Free credits == 100 (per spec)", free_credits == 100,
        f"free_credits={free_credits} (note: test_credentials.md says 300)")
    rec("Pricing Starter credits == 1500", by_tier.get("starter") == 1500, f"starter={by_tier.get('starter')}")
    rec("Pricing Creator credits == 3000", by_tier.get("creator") == 3000, f"creator={by_tier.get('creator')}")
    rec("Pricing Pro credits == 6000", by_tier.get("pro") == 6000, f"pro={by_tier.get('pro')}")
    print(f"  >> all_tiers = {by_tier}")

# ---------- 7. MH models ----------
def test_mh_models():
    try:
        r = requests.get(f"{API}/mh-models", timeout=10)
        ok = r.status_code == 200
        d = r.json() if ok else {}
        # response shape: {quality_tiers, min_billed_seconds, resolutions, features:{text_to_video, image_to_video, ...}}
        features = d.get("features") if isinstance(d, dict) else {}
        # count distinct models across all features
        all_models = []
        if isinstance(features, dict):
            for fk, fv in features.items():
                ml = fv.get("models", []) if isinstance(fv, dict) else []
                all_models.extend(ml)
        rec("MH models endpoint >=1 model entry", ok and len(all_models) >= 1,
            f"status={r.status_code} feature_count={len(features) if isinstance(features, dict) else 0} total_models={len(all_models)}")
    except Exception as e:
        rec("MH models", False, f"exc={e}")

# ---------- 8. Healthchecks ----------
def test_misc(free_token):
    try:
        r = requests.get(f"{API}/mode", timeout=10)
        rec("GET /api/mode", r.status_code == 200, f"status={r.status_code} body={r.text[:120]}")
    except Exception as e:
        rec("GET /api/mode", False, f"exc={e}")

    try:
        h = {"Authorization": f"Bearer {free_token}"} if free_token else {}
        r = requests.get(f"{API}/notifications", headers=h, timeout=10)
        ok = r.status_code == 200
        rec("GET /api/notifications (auth=free)", ok, f"status={r.status_code} body={r.text[:120]}")
    except Exception as e:
        rec("GET /api/notifications", False, f"exc={e}")

    found = None
    for path in ("/stats", "/admin/stats", "/credits-info"):
        try:
            r = requests.get(f"{API}{path}", timeout=8)
            if r.status_code == 200:
                found = path
                break
        except Exception:
            pass
    rec("Stats-like endpoint reachable", found is not None, f"path={found}")

    try:
        r = requests.get(f"{API}/motion-presets", timeout=10)
        ok = r.status_code == 200
        rec("GET /api/motion-presets", ok, f"status={r.status_code} body={r.text[:120]}")
    except Exception as e:
        rec("GET /api/motion-presets", False, f"exc={e}")

# ---------- 9. Avatar serve-file ----------
def test_avatar_servefile():
    cand = None
    # /api/serve-file searches /app/backend/uploads, /app/backend/static/bgm, /app/backend/static/previews
    for root in ("/app/backend/uploads",):
        try:
            files = sorted(os.listdir(root))
            for f in files:
                if f.lower().endswith((".png", ".jpg", ".jpeg")):
                    cand = f
                    break
            if cand:
                break
        except Exception:
            pass
    if not cand:
        rec("Avatar serve-file", False, "no candidate image found in /app/backend/uploads")
        return
    try:
        r = requests.get(f"{API}/serve-file/{cand}", timeout=15)
        ct = r.headers.get("content-type", "")
        ok = r.status_code == 200 and "image" in ct.lower()
        rec(f"Serve-file image '{cand}'", ok, f"status={r.status_code} content-type={ct} size={len(r.content)}")
    except Exception as e:
        rec("Avatar serve-file", False, f"exc={e}")

if __name__ == "__main__":
    print(f"BASE={BASE}")
    print("=" * 70)
    tokens = test_auth()
    plan_id = test_creative_plan()
    test_marketplace()
    test_trending()
    creator_token = tokens.get("demo_creator@test.com")
    test_wizard(creator_token, plan_id)
    test_pricing()
    test_mh_models()
    free_token = tokens.get("demo_free@test.com")
    test_misc(free_token)
    test_avatar_servefile()

    print("\n" + "=" * 70)
    fails = [r for r in results if not r["ok"]]
    print(f"TOTAL: {len(results)} | PASS: {len(results)-len(fails)} | FAIL: {len(fails)}")
    if fails:
        print("\nFAILED ITEMS:")
        for r in fails:
            print(f"  - {r['name']} :: {r['detail']}")
