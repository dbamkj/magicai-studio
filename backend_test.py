"""V2.0 Prompt Generator + Phase-A Regression Backend Tests.

Validates the new POST /api/generate-prompts endpoint and confirms zero
regressions from the Phase-A refactor against the public preview ingress URL.
"""
from __future__ import annotations

import json
import time
import sys
import requests

PREVIEW_BASE = "https://creative-plan-engine.preview.emergentagent.com"
PROD_BASE = "https://creative-plan-engine.emergent.host"
API = f"{PREVIEW_BASE}/api"

DEMO_EMAIL = "demo_creator@test.com"
DEMO_PASSWORD = "Test@123"

results = []


def record(name: str, passed: bool, detail: str = "") -> None:
    icon = "PASS" if passed else "FAIL"
    print(f"[{icon}] {name}  -  {detail[:300]}")
    results.append((name, passed, detail))


def post(path: str, body: dict, timeout: float = 60, base: str = API):
    return requests.post(f"{base}{path}", json=body, timeout=timeout)


def get(path: str, timeout: float = 30, base: str = API, **kw):
    return requests.get(f"{base}{path}", timeout=timeout, **kw)


# ─── 1. Generate Prompts: Happy path English ────────────────────────────
def t1_english_happy():
    body = {"idea": "Monday motivation for busy professionals", "language": "english"}
    r = post("/generate-prompts", body, timeout=60)
    if r.status_code != 200:
        return record("T1 English happy path", False, f"status={r.status_code} body={r.text[:200]}")
    j = r.json()
    prompts = j.get("prompts", [])
    det = j.get("detected", {})
    src = j.get("source")
    tok = j.get("tokens_used", 0)
    ok = (
        len(prompts) == 3
        and all(det.get(k) for k in ["category", "mood", "suggested_voice"])
        and isinstance(det.get("scene_keywords"), list) and len(det["scene_keywords"]) >= 1
        and src in ("llm", "cache", "fallback")
        and (tok > 0 or src == "cache")
    )
    return record(
        "T1 English happy path",
        ok,
        f"src={src} tok={tok} cat={det.get('category')} mood={det.get('mood')} kw={det.get('scene_keywords')} titles={[p.get('title') for p in prompts]}",
    )


# ─── 2. Hindi: hindi titles + english tech fields ────────────────────────
def t2_hindi():
    body = {"idea": "Krishna bhajan devotional reel", "language": "hindi"}
    r = post("/generate-prompts", body, timeout=60)
    if r.status_code != 200:
        return record("T2 Hindi", False, f"status={r.status_code} body={r.text[:200]}")
    j = r.json()
    prompts = j.get("prompts", [])
    det = j.get("detected", {})

    # Check titles+hooks contain Devanagari OR are non-empty
    def has_devanagari(s):
        return any("\u0900" <= ch <= "\u097f" for ch in (s or ""))

    titles_dev = sum(1 for p in prompts if has_devanagari(p.get("title", "")))
    hooks_dev = sum(1 for p in prompts if has_devanagari(p.get("hook", "")))
    cta_dev = sum(1 for p in prompts if has_devanagari(p.get("cta", "")))

    # Tech fields should be ASCII English (not Devanagari)
    tech_english = all(
        not has_devanagari(p.get("voice_type", "")) and
        not has_devanagari(p.get("music_type", "")) and
        not has_devanagari(p.get("style_tag", "")) and
        not has_devanagari(p.get("mood", ""))
        for p in prompts
    )
    cat_eng = not has_devanagari(det.get("category", ""))
    kw_eng = all(not has_devanagari(k) for k in det.get("scene_keywords", []))

    ok = len(prompts) == 3 and (titles_dev + hooks_dev + cta_dev) >= 3 and tech_english and cat_eng and kw_eng
    return record(
        "T2 Hindi titles+hooks devanagari, tech fields English",
        ok,
        f"titles_dev={titles_dev}/3 hooks_dev={hooks_dev}/3 cta_dev={cta_dev}/3 tech_english={tech_english} cat_eng={cat_eng} kw_eng={kw_eng} sample_title={prompts[0].get('title') if prompts else ''}",
    )


# ─── 3. Cache hit ─────────────────────────────────────────────────────
def t3_cache():
    body = {"idea": "Monday motivation for busy professionals", "language": "english"}
    # Already called in T1, now the second call should hit cache
    t0 = time.time()
    r = post("/generate-prompts", body, timeout=15)
    elapsed = time.time() - t0
    if r.status_code != 200:
        return record("T3 Cache hit", False, f"status={r.status_code}")
    j = r.json()
    ok = j.get("cached") is True and j.get("source") == "cache" and j.get("tokens_used", -1) == 0 and elapsed < 1.0
    return record(
        "T3 Cache hit",
        ok,
        f"cached={j.get('cached')} source={j.get('source')} tokens={j.get('tokens_used')} latency={elapsed:.3f}s",
    )


# ─── 4. force_refresh bypass ──────────────────────────────────────────
def t4_force_refresh():
    body = {"idea": "Monday motivation for busy professionals", "language": "english", "force_refresh": True}
    r = post("/generate-prompts", body, timeout=60)
    if r.status_code != 200:
        return record("T4 force_refresh", False, f"status={r.status_code}")
    j = r.json()
    ok = j.get("cached") is False and j.get("source") in ("llm", "fallback")
    return record("T4 force_refresh", ok, f"cached={j.get('cached')} source={j.get('source')} tok={j.get('tokens_used')}")


# ─── 5/6. Validation 422 ──────────────────────────────────────────────
def t5_too_short():
    r = post("/generate-prompts", {"idea": "ab"})
    ok = r.status_code == 422
    return record("T5 idea<3 chars → 422", ok, f"status={r.status_code} body={r.text[:150]}")


def t6_too_long():
    r = post("/generate-prompts", {"idea": "x" * 401})
    ok = r.status_code == 422
    return record("T6 idea>400 chars → 422", ok, f"status={r.status_code} body={r.text[:150]}")


# ─── 7. Health ────────────────────────────────────────────────────────
def t7_health():
    r = get("/generate-prompts/health")
    if r.status_code != 200:
        return record("T7 health", False, f"status={r.status_code}")
    j = r.json()
    ok = j.get("ok") is True and j.get("llm_key_configured") is True and isinstance(j.get("cache_size"), int)
    return record("T7 health", ok, json.dumps(j))


# ─── 8. Variance ──────────────────────────────────────────────────────
def t8_variance():
    body = {"idea": "Diwali festive reel for instagram", "language": "english"}
    r = post("/generate-prompts", body, timeout=60)
    if r.status_code != 200:
        return record("T8 variance", False, f"status={r.status_code}")
    j = r.json()
    prompts = j.get("prompts", [])
    if len(prompts) != 3:
        return record("T8 variance", False, f"got {len(prompts)} prompts")
    durations = {p.get("duration") for p in prompts}
    styles = {p.get("style_tag") for p in prompts}
    moods = {p.get("mood") for p in prompts}
    different = len(durations) >= 2 or len(styles) >= 2 or len(moods) >= 2
    detail = f"durations={durations} styles={styles} moods={moods}"
    if not different:
        # Don't fail per spec — log warning
        print(f"  WARN: 3 prompts identical on duration/style/mood — {detail}")
    return record("T8 variance (3 prompts differ on duration/style_tag/mood)", True, detail + (" (warn-pass)" if not different else ""))


# ─── 9. Schema correctness ────────────────────────────────────────────
def t9_schema():
    body = {"idea": "Quick coffee shop story reel", "language": "english"}
    r = post("/generate-prompts", body, timeout=60)
    if r.status_code != 200:
        return record("T9 schema", False, f"status={r.status_code}")
    j = r.json()
    prompts = j.get("prompts", [])
    if len(prompts) != 3:
        return record("T9 schema", False, f"len={len(prompts)}")
    ids = [p.get("id") for p in prompts]
    ok_ids = ids == ["p1", "p2", "p3"]
    ok_dur = all(isinstance(p.get("duration"), int) for p in prompts)
    sk = j.get("detected", {}).get("scene_keywords", [])
    ok_sk = isinstance(sk, list) and all(isinstance(x, str) for x in sk)
    ok = ok_ids and ok_dur and ok_sk
    return record(
        "T9 schema (ids p1/p2/p3, duration int, scene_keywords list[str])",
        ok,
        f"ids={ids} dur_types={[type(p.get('duration')).__name__ for p in prompts]} sk_types={[type(x).__name__ for x in sk]}",
    )


# ─── REGRESSION ───────────────────────────────────────────────────────
def reg1_root_api():
    r = get("/")
    ok = r.status_code == 200
    j = {}
    try:
        j = r.json()
        ok = ok and "MagiCAi" in j.get("message", "")
    except Exception:
        ok = False
    return record("REG1 GET /api/", ok, f"status={r.status_code} body={str(j)[:200]}")


def reg2_login():
    body = {"email": DEMO_EMAIL, "password": DEMO_PASSWORD}
    r = post("/auth/login", body, timeout=30)
    if r.status_code != 200:
        return record("REG2 demo_creator login", False, f"status={r.status_code} body={r.text[:200]}")
    j = r.json()
    user = j.get("user") or {}
    tier = user.get("subscription_tier") or user.get("tier")
    cred = user.get("credits_balance") or user.get("credits")
    token = j.get("token") or j.get("access_token")
    ok = bool(token) and tier == "creator" and cred == 3000
    return record("REG2 demo_creator login (creator/3000)", ok, f"tier={tier} credits={cred} token_set={bool(token)}")


def reg3_creative_plan():
    body = {"idea": "quick test"}
    r = post("/creative-plan", body, timeout=60)
    if r.status_code != 200:
        return record("REG3 creative-plan", False, f"status={r.status_code} body={r.text[:200]}")
    j = r.json()
    needed = ["hook", "script", "scene_keywords", "voice_style", "bgm_style", "mood"]
    missing = [k for k in needed if k not in j]
    ok = not missing
    return record("REG3 POST /api/creative-plan shape", ok, f"missing={missing} keys={list(j.keys())[:10]}")


def reg4_marketplace():
    r = get("/marketplace/templates", params={"limit": 5})
    if r.status_code != 200:
        return record("REG4 marketplace", False, f"status={r.status_code}")
    j = r.json()
    # may be {templates:[...]} or list directly
    templates = j.get("templates") if isinstance(j, dict) else j
    ok = isinstance(templates, list) and len(templates) >= 1
    return record("REG4 marketplace ?limit=5", ok, f"count={len(templates) if isinstance(templates, list) else 'N/A'}")


def reg5_mode():
    r = get("/mode")
    if r.status_code != 200:
        return record("REG5 mode", False, f"status={r.status_code}")
    j = r.json()
    ok = "env" in j or "is_beta" in j
    return record("REG5 GET /api/mode", ok, json.dumps(j)[:200])


# ─── LANDING PAGE ─────────────────────────────────────────────────────
def land1_preview_root():
    try:
        r = requests.get(f"{PREVIEW_BASE}/", timeout=20, allow_redirects=True)
        ok = r.status_code == 200
        return record("LAND1 preview / (Expo, HTML expected)", ok, f"status={r.status_code} ct={r.headers.get('Content-Type','')[:60]} bytes={len(r.content)}")
    except Exception as e:
        return record("LAND1 preview /", False, f"error={e}")


def land2_prod_root():
    try:
        r = requests.get(f"{PROD_BASE}/", timeout=30, allow_redirects=True)
        if r.status_code != 200:
            return record("LAND2 prod / landing HTML", False, f"status={r.status_code} body={r.text[:200]}")
        ok_title = "MagiCAi Studio" in r.text
        not_404 = "Not Found" not in r.text or '<title>' in r.text.lower()
        ok = ok_title and not_404
        return record("LAND2 prod / landing HTML (<title>MagiCAi Studio)", ok, f"status={r.status_code} title_match={ok_title} bytes={len(r.content)}")
    except Exception as e:
        return record("LAND2 prod /", False, f"error={e}")


def land3_prod_api_root():
    try:
        r = requests.get(f"{PROD_BASE}/api/", timeout=30)
        ok = r.status_code == 200
        return record("LAND3 prod /api/", ok, f"status={r.status_code} body={r.text[:200]}")
    except Exception as e:
        return record("LAND3 prod /api/", False, f"error={e}")


def main():
    print(f"=== V2 Prompt Generator + Phase-A Regression Tests ===")
    print(f"API: {API}")

    print("\n--- V2 NEW ENDPOINT ---")
    t1_english_happy()
    t2_hindi()
    t3_cache()
    t4_force_refresh()
    t5_too_short()
    t6_too_long()
    t7_health()
    t8_variance()
    t9_schema()

    print("\n--- REGRESSION ---")
    reg1_root_api()
    reg2_login()
    reg3_creative_plan()
    reg4_marketplace()
    reg5_mode()

    print("\n--- LANDING PAGES ---")
    land1_preview_root()
    land2_prod_root()
    land3_prod_api_root()

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n=== SUMMARY: {passed}/{total} passed ===")
    for n, ok, d in results:
        if not ok:
            print(f"  FAIL: {n} :: {d[:200]}")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
