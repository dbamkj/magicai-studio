"""Session-34 Phase-B verification — routes/account.py extraction + templates path-order fix.

Tests:
  A) GET /api/credits-info, /api/mh-models, /api/usage (auth + no-auth)
  B) GET /api/templates/preview-stats + POST /api/templates/backfill-previews (with/without force)
  C) Regression — /api/, login, creative-plan, marketplace/templates, /api/mode, /api/cinematic-presets
"""
import time
import requests

BASE = "https://creative-plan-engine.preview.emergentagent.com"
EMAIL = "demo_creator@test.com"
PASSWORD = "Test@123"

results = []


def log(name, ok, detail=""):
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name} :: {detail}")
    results.append((name, ok, detail))


def jget(path, headers=None, timeout=30):
    return requests.get(f"{BASE}{path}", headers=headers or {}, timeout=timeout)


def jpost(path, json_body=None, headers=None, timeout=60):
    return requests.post(f"{BASE}{path}", json=json_body, headers=headers or {}, timeout=timeout)


# ---------- LOGIN (also serves as C2 regression) ----------
print("\n========= LOGIN (precondition) =========")
r = jpost("/api/auth/login", {"email": EMAIL, "password": PASSWORD})
TOKEN = None
if r.status_code == 200:
    data = r.json()
    TOKEN = data.get("token") or data.get("access_token")
    user = data.get("user") or {}
    tier = user.get("subscription_tier")
    cb = user.get("credits_balance")
    ok = bool(TOKEN) and tier == "creator" and cb == 3000
    log("C2 POST /api/auth/login (demo_creator)", ok,
        f"token={'set' if TOKEN else 'MISSING'} tier={tier} credits={cb}")
else:
    log("C2 POST /api/auth/login (demo_creator)", False,
        f"status={r.status_code} body={r.text[:300]}")

AUTH = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}


# ---------- A1 ----------
print("\n========= A1 GET /api/credits-info =========")
r = jget("/api/credits-info")
if r.status_code != 200:
    log("A1 /api/credits-info status=200", False, f"got {r.status_code} body={r.text[:200]}")
else:
    body = r.json()
    print(f"  KEYS: {sorted(body.keys())}")
    required = {"credits_used_total", "completed_jobs", "cost_table", "pricing",
                "quality_tiers", "resolutions", "resolutions_enabled", "note"}
    missing = required - set(body.keys())
    log("A1 required keys present", not missing, f"missing={missing}")
    int_ok = isinstance(body.get("credits_used_total"), int) and isinstance(body.get("completed_jobs"), int)
    log("A1 credits_used_total + completed_jobs are int (not str)", int_ok,
        f"types={type(body.get('credits_used_total')).__name__},{type(body.get('completed_jobs')).__name__}")
    ct = body.get("cost_table") or {}
    print(f"  cost_table KEYS: {sorted(ct.keys())}")
    sub_ok = (ct.get("lip_sync_per_sec") == 7
              and ct.get("face_swap_per_sec") == 3
              and ct.get("ai_image_generator") == 5
              and ct.get("head_swap") == 10)
    log("A1 cost_table contains lip_sync_per_sec=7 face_swap_per_sec=3 ai_image_generator=5 head_swap=10",
        sub_ok,
        f"lip_sync_per_sec={ct.get('lip_sync_per_sec')} face_swap_per_sec={ct.get('face_swap_per_sec')} "
        f"ai_image_generator={ct.get('ai_image_generator')} head_swap={ct.get('head_swap')}")


# ---------- A2 ----------
print("\n========= A2 GET /api/mh-models =========")
r = jget("/api/mh-models")
if r.status_code != 200:
    log("A2 /api/mh-models status=200", False, f"got {r.status_code} body={r.text[:200]}")
else:
    body = r.json()
    feats = body.get("features") or {}
    print(f"  features KEYS: {sorted(feats.keys())}")
    expected_feats = {"text_to_video", "image_to_video", "video_to_video",
                      "ai_image_generator", "face_swap_photo", "face_swap_video",
                      "lip_sync", "talking_avatar"}
    missing = expected_feats - set(feats.keys())
    log("A2 features dict has all 8 required keys", not missing, f"missing={missing}")
    qt = body.get("quality_tiers") or []
    qt_ids = [x.get("id") if isinstance(x, dict) else x for x in qt]
    print(f"  quality_tiers IDS: {qt_ids}")
    qt_ok = (len(qt) == 3 and set(qt_ids) == {"quick", "studio", "cinematic"})
    log("A2 quality_tiers has 3 entries [quick, studio, cinematic]", qt_ok,
        f"count={len(qt)} ids={qt_ids}")


# ---------- A3 ----------
print("\n========= A3 GET /api/usage =========")
r = jget("/api/usage")
log("A3 /api/usage WITHOUT auth -> 401", r.status_code == 401,
    f"status={r.status_code} body={r.text[:200]}")
if TOKEN:
    r = jget("/api/usage", headers=AUTH)
    if r.status_code != 200:
        log("A3 /api/usage WITH auth -> 200", False, f"status={r.status_code} body={r.text[:200]}")
    else:
        body = r.json()
        print(f"  usage KEYS: {sorted(body.keys())}  body={body}")
        required = {"lipsync", "faceswap", "headswap", "bodyswap", "total_projects", "total_completed"}
        missing = required - set(body.keys())
        log("A3 usage has all required keys", not missing, f"missing={missing}")
        ls = body.get("lipsync") or {}
        ls_ok = ("total" in ls and "completed" in ls)
        log("A3 lipsync sub-keys total+completed", ls_ok, f"lipsync={ls}")
else:
    log("A3 /api/usage WITH auth -> 200", False, "skipped (no token)")


# ---------- B1 ----------
print("\n========= B1 GET /api/templates/preview-stats =========")
r = jget("/api/templates/preview-stats")
if r.status_code != 200:
    log("B1 /api/templates/preview-stats status=200", False, f"status={r.status_code} body={r.text[:200]}")
else:
    body = r.json()
    print(f"  KEYS: {sorted(body.keys())}  body={body}")
    required = {"total", "with_thumbnail", "with_preview", "needs_preview", "coverage_pct"}
    missing = required - set(body.keys())
    log("B1 preview-stats has all required keys", not missing, f"missing={missing}")
    cp = body.get("coverage_pct")
    log("B1 coverage_pct is float", isinstance(cp, float), f"coverage_pct={cp} ({type(cp).__name__})")
    log("B1 total=26 coverage_pct=100.0",
        body.get("total") == 26 and cp == 100.0,
        f"total={body.get('total')} coverage_pct={cp}")


# ---------- B2 ----------
print("\n========= B2 POST /api/templates/backfill-previews =========")
r = jpost("/api/templates/backfill-previews", {})
if r.status_code != 200:
    log("B2 /api/templates/backfill-previews status=200", False, f"status={r.status_code} body={r.text[:300]}")
else:
    body = r.json()
    print(f"  body={body}")
    ok = (body.get("ok") is True and body.get("queued") == 0 and isinstance(body.get("message"), str))
    log("B2 ok=true queued=0 message=str", ok,
        f"ok={body.get('ok')} queued={body.get('queued')} message={body.get('message')!r}")


# ---------- B3 ----------
print("\n========= B3 POST /api/templates/backfill-previews?force=true&limit=2 =========")
r = requests.post(f"{BASE}/api/templates/backfill-previews?force=true&limit=2", timeout=30)
if r.status_code != 200:
    log("B3 /api/templates/backfill-previews?force=true&limit=2 status=200",
        False, f"status={r.status_code} body={r.text[:300]}")
else:
    body = r.json()
    print(f"  body={body}")
    log("B3 queued=2 (force re-renders existing)", body.get("queued") == 2,
        f"queued={body.get('queued')}")
    print("  waiting 10s for background ffmpeg job ...")
    time.sleep(10)
    r2 = jget("/api/templates/preview-stats")
    if r2.status_code == 200:
        body2 = r2.json()
        print(f"  post-backfill preview-stats: {body2}")
        log("B3 coverage_pct still 100.0 after force backfill",
            body2.get("coverage_pct") == 100.0,
            f"coverage_pct={body2.get('coverage_pct')} total={body2.get('total')}")
    else:
        log("B3 post-wait preview-stats", False, f"status={r2.status_code}")


# ---------- C1 ----------
print("\n========= C1 GET /api/ =========")
r = jget("/api/")
if r.status_code != 200:
    log("C1 /api/ status=200", False, f"status={r.status_code} body={r.text[:200]}")
else:
    body = r.json()
    print(f"  body={body}")
    log("C1 version=7.1.0", body.get("version") == "7.1.0", f"version={body.get('version')}")


# ---------- C3 ----------
print("\n========= C3 POST /api/creative-plan =========")
r = jpost("/api/creative-plan", {"idea": "quick test"}, timeout=120)
if r.status_code != 200:
    log("C3 /api/creative-plan status=200", False, f"status={r.status_code} body={r.text[:300]}")
else:
    body = r.json()
    print(f"  KEYS: {sorted(body.keys())}")
    required = {"creative_plan_id", "hook", "script", "scene_keywords", "voice_style", "bgm_style", "mood"}
    missing = required - set(body.keys())
    log("C3 creative-plan has all required keys", not missing, f"missing={missing}")


# ---------- C4 ----------
print("\n========= C4 GET /api/marketplace/templates?limit=5 =========")
r = jget("/api/marketplace/templates?limit=5")
if r.status_code != 200:
    log("C4 /api/marketplace/templates?limit=5 status=200", False, f"status={r.status_code} body={r.text[:300]}")
else:
    body = r.json()
    tpls = body.get("templates") or []
    print(f"  templates count={len(tpls)}")
    log("C4 templates length=5", len(tpls) == 5, f"got len={len(tpls)}")


# ---------- C5 ----------
print("\n========= C5 GET /api/mode =========")
r = jget("/api/mode")
if r.status_code != 200:
    log("C5 /api/mode status=200", False, f"status={r.status_code} body={r.text[:300]}")
else:
    body = r.json()
    print(f"  body={body}")
    ok = (body.get("env") == "BETA" and body.get("is_beta") is True and body.get("version") == "v1.0-beta")
    log("C5 env=BETA is_beta=true version=v1.0-beta", ok,
        f"env={body.get('env')} is_beta={body.get('is_beta')} version={body.get('version')}")


# ---------- C6 ----------
print("\n========= C6 GET /api/cinematic-presets =========")
r = jget("/api/cinematic-presets")
if r.status_code != 200:
    log("C6 /api/cinematic-presets status=200", False, f"status={r.status_code} body={r.text[:300]}")
else:
    body = r.json()
    if isinstance(body, list):
        presets = body
    else:
        presets = body.get("presets") or []
    print(f"  presets count={len(presets)}")
    log("C6 has 6 presets", len(presets) == 6, f"len={len(presets)}")


# ---------- SUMMARY ----------
print("\n========= SUMMARY =========")
total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
print(f"PASSED {passed}/{total}")
for name, ok, detail in results:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
print()
if passed != total:
    print("FAILED tests:")
    for name, ok, detail in results:
        if not ok:
            print(f"  - {name}: {detail}")
