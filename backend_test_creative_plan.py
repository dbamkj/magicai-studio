"""Creative Plan Engine — full end-to-end pipeline test.

Tests:
1. POST /api/creative-plan — quality + caching (1a-1e)
2. GET /api/creative-plan/{plan_id} — fetch by id (2a-2b)
3. End-to-end: POST /api/wizard/create-reel WITH creative_plan_id (3a-3e)
4. /openapi.json route registration (4)
"""
import json
import re
import sys
import time
from typing import Any

import httpx

BASE = "https://creative-plan-engine.preview.emergentagent.com"
EMAIL = "demo_creator@test.com"
PASSWORD = "Test@123"

# Devanagari unicode block detector
DEVA_RE = re.compile(r"[\u0900-\u097F]")
LATIN_RE = re.compile(r"[A-Za-z]")


def is_devanagari(s: str) -> bool:
    return bool(DEVA_RE.search(s or ""))


def is_english_only(s: str) -> bool:
    s = s or ""
    return bool(LATIN_RE.search(s)) and not is_devanagari(s)


def pp(label: str, ok: bool, detail: str = "") -> None:
    mark = "✅" if ok else "❌"
    print(f"{mark} {label}{(' — ' + detail) if detail else ''}")


results: list[tuple[str, bool, str]] = []


def record(label: str, ok: bool, detail: str = "") -> None:
    results.append((label, ok, detail))
    pp(label, ok, detail)


def main() -> int:
    client = httpx.Client(timeout=httpx.Timeout(120.0), follow_redirects=True)

    # ============================================================
    # Login
    # ============================================================
    print("\n=== Auth ===")
    r = client.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    if r.status_code != 200:
        record("login demo_creator", False, f"status={r.status_code} body={r.text[:200]}")
        return 1
    token = r.json().get("token")
    if not token:
        record("login demo_creator", False, "no token in response")
        return 1
    record("login demo_creator", True, f"token len={len(token)}")
    auth_headers = {"Authorization": f"Bearer {token}"}

    # ============================================================
    # 1a. POST /api/creative-plan — Krishna Hindi
    # ============================================================
    print("\n=== 1a. POST /api/creative-plan — Krishna Hindi ===")
    body_1a = {
        "idea": "Krishna devotional bhajan",
        "language": "hindi",
        "duration": 15,
        "scene_count": 3,
    }
    t0 = time.time()
    r = client.post(f"{BASE}/api/creative-plan", json=body_1a)
    dt = time.time() - t0
    if r.status_code != 200:
        record("1a status 200", False, f"status={r.status_code} body={r.text[:300]}")
        return 1
    plan_1a = r.json()
    record("1a status 200", True, f"latency={dt:.2f}s source={plan_1a.get('source')}")

    required = ["creative_plan_id", "hook", "script", "scene_keywords", "voice_style", "bgm_style", "mood"]
    missing = [k for k in required if k not in plan_1a or plan_1a[k] in (None, "", [])]
    record("1a all required fields present", not missing, f"missing={missing}" if missing else f"id={plan_1a.get('creative_plan_id')}")

    record(
        "1a script has 3 entries",
        isinstance(plan_1a.get("script"), list) and len(plan_1a["script"]) == 3,
        f"len={len(plan_1a.get('script', []))}",
    )
    record(
        "1a scene_keywords has 3 entries",
        isinstance(plan_1a.get("scene_keywords"), list) and len(plan_1a["scene_keywords"]) == 3,
        f"len={len(plan_1a.get('scene_keywords', []))}",
    )

    # Devanagari check on script
    script_devanagari = all(is_devanagari(s) for s in plan_1a.get("script", []))
    record("1a script entries in Devanagari", script_devanagari, f"sample={plan_1a.get('script', [''])[0][:60]!r}")

    # English check on scene_keywords
    sk_english = all(is_english_only(k) for k in plan_1a.get("scene_keywords", []))
    record("1a scene_keywords in English", sk_english, f"keywords={plan_1a.get('scene_keywords')}")

    record(
        "1a source is llm or cache",
        plan_1a.get("source") in ("llm", "cache"),
        f"source={plan_1a.get('source')}",
    )

    plan_1a_id = plan_1a.get("creative_plan_id")
    print(f"   hook: {plan_1a.get('hook')!r}")
    print(f"   voice_style: {plan_1a.get('voice_style')!r}")
    print(f"   bgm_style: {plan_1a.get('bgm_style')!r}")
    print(f"   mood: {plan_1a.get('mood')!r}")

    # ============================================================
    # 1b. SAME request again → source="cache", same plan_id
    # ============================================================
    print("\n=== 1b. Same request again → cache ===")
    t0 = time.time()
    r = client.post(f"{BASE}/api/creative-plan", json=body_1a)
    dt = time.time() - t0
    if r.status_code != 200:
        record("1b status 200", False, f"status={r.status_code}")
    else:
        plan_1b = r.json()
        record("1b status 200", True, f"latency={dt:.2f}s")
        record("1b source=cache", plan_1b.get("source") == "cache", f"source={plan_1b.get('source')}")
        record(
            "1b same creative_plan_id",
            plan_1b.get("creative_plan_id") == plan_1a_id,
            f"old={plan_1a_id} new={plan_1b.get('creative_plan_id')}",
        )

    # ============================================================
    # 1c. Use template_id
    # ============================================================
    print("\n=== 1c. POST with template_id ===")
    r = client.get(f"{BASE}/api/marketplace/templates", params={"limit": 5})
    template_id = None
    if r.status_code == 200:
        items = r.json()
        # could be list or dict
        if isinstance(items, dict):
            items = items.get("templates") or items.get("items") or []
        if items:
            template_id = items[0].get("id") or items[0].get("_id") or items[0].get("template_id")
    record("1c fetched marketplace template_id", template_id is not None, f"template_id={template_id}")

    if template_id:
        body_1c = {"template_id": template_id, "language": "english", "duration": 15, "scene_count": 3}
        r = client.post(f"{BASE}/api/creative-plan", json=body_1c)
        if r.status_code != 200:
            record("1c status 200 (template_id)", False, f"status={r.status_code} body={r.text[:300]}")
        else:
            plan_1c = r.json()
            record("1c status 200 (template_id)", True, f"source={plan_1c.get('source')}")
            record(
                "1c plan derived from template (idea field set)",
                bool(plan_1c.get("idea")) and bool(plan_1c.get("hook")),
                f"idea_len={len(plan_1c.get('idea',''))}",
            )

    # ============================================================
    # 1d. Both idea and template_id missing → 400
    # ============================================================
    print("\n=== 1d. Empty body → 400 ===")
    r = client.post(f"{BASE}/api/creative-plan", json={"language": "english", "duration": 15, "scene_count": 3})
    record(
        "1d returns 400 when no idea/template_id",
        r.status_code == 400,
        f"status={r.status_code} body={r.text[:200]}",
    )

    # ============================================================
    # 1e. English motivational
    # ============================================================
    print("\n=== 1e. English motivational ===")
    body_1e = {
        "idea": "Energetic morning workout motivation",
        "language": "english",
        "duration": 20,
        "scene_count": 4,
    }
    r = client.post(f"{BASE}/api/creative-plan", json=body_1e)
    if r.status_code != 200:
        record("1e status 200", False, f"status={r.status_code}")
    else:
        plan_1e = r.json()
        record("1e status 200", True, f"source={plan_1e.get('source')}")
        record(
            "1e script has 4 entries",
            isinstance(plan_1e.get("script"), list) and len(plan_1e["script"]) == 4,
            f"len={len(plan_1e.get('script', []))}",
        )
        record(
            "1e scene_keywords has 4 entries",
            isinstance(plan_1e.get("scene_keywords"), list) and len(plan_1e["scene_keywords"]) == 4,
            f"len={len(plan_1e.get('scene_keywords', []))}",
        )
        # English script (no Devanagari)
        en_script = all(is_english_only(s) for s in plan_1e.get("script", []))
        record("1e script in English", en_script, f"sample={plan_1e.get('script', [''])[0][:60]!r}")
        en_sk = all(is_english_only(k) for k in plan_1e.get("scene_keywords", []))
        record("1e scene_keywords in English", en_sk, f"keywords={plan_1e.get('scene_keywords')}")
        # voice_style/mood reflect motivational
        vs = (plan_1e.get("voice_style") or "").lower()
        mood = (plan_1e.get("mood") or "").lower()
        bgm = (plan_1e.get("bgm_style") or "").lower()
        motiv_words = ("energetic", "powerful", "confident", "motivat", "upbeat", "epic", "dynamic", "intense", "energy")
        is_motiv = any(w in vs or w in mood or w in bgm for w in motiv_words)
        record(
            "1e voice/mood matches motivational vibe",
            is_motiv,
            f"voice_style={vs!r} mood={mood!r} bgm={bgm!r}",
        )

    # ============================================================
    # 2a/2b. GET /api/creative-plan/{plan_id}
    # ============================================================
    print("\n=== 2. GET /api/creative-plan/{id} ===")
    r = client.get(f"{BASE}/api/creative-plan/{plan_1a_id}")
    if r.status_code != 200:
        record("2a GET valid plan_id → 200", False, f"status={r.status_code}")
    else:
        gdoc = r.json()
        ok = all(k in gdoc for k in required)
        record("2a GET valid plan_id → 200 with full plan", ok, f"keys={list(gdoc.keys())[:8]}")

    r = client.get(f"{BASE}/api/creative-plan/cp_bogusxxxxxx")
    record("2b GET bogus plan_id → 404", r.status_code == 404, f"status={r.status_code}")

    # ============================================================
    # 4. /openapi.json route registration check (BEFORE wizard)
    # ============================================================
    print("\n=== 4. /openapi.json registration ===")
    # Try /openapi.json (note: ingress only proxies /api/*, so try /api/openapi.json too)
    paths_found: dict[str, int] = {}
    for url in (f"{BASE}/openapi.json", f"http://localhost:8001/openapi.json", f"{BASE}/api/openapi.json"):
        try:
            r = client.get(url, timeout=20.0)
            if r.status_code == 200:
                try:
                    spec = r.json()
                    if isinstance(spec, dict) and "paths" in spec:
                        for p in spec["paths"].keys():
                            if "creative-plan" in p:
                                paths_found[p] = paths_found.get(p, 0) + 1
                        if paths_found:
                            print(f"   openapi.json fetched from {url}")
                            break
                except Exception:
                    pass
        except Exception as e:
            print(f"   {url} -> {e}")
    record(
        "4 /api/creative-plan registered exactly once",
        paths_found.get("/api/creative-plan") == 1,
        f"count={paths_found.get('/api/creative-plan')}",
    )
    record(
        "4 /api/creative-plan/{plan_id} registered exactly once",
        paths_found.get("/api/creative-plan/{plan_id}") == 1,
        f"count={paths_found.get('/api/creative-plan/{plan_id}')}",
    )

    # ============================================================
    # 3. End-to-end: create-reel with creative_plan_id (Krishna Hindi)
    # ============================================================
    print("\n=== 3. End-to-end create-reel with creative_plan_id ===")
    # 3a — already have plan_1a_id (Krishna Hindi)
    record("3a Krishna Hindi plan available", bool(plan_1a_id), f"id={plan_1a_id}")

    # 3b — POST /api/wizard/create-reel
    # Note: CreateReelRequest still requires script + image_query (frontend sends
    # plan.hook and plan.scene_keywords[0] as placeholders). The worker will
    # overwrite both from the creative plan once it loads.
    reel_body = {
        "creative_plan_id": plan_1a_id,
        "script": plan_1a.get("hook") or "placeholder",
        "image_query": (plan_1a.get("scene_keywords") or ["krishna"])[0],
        "mode": "video",
        "total_duration": 10,
        "voice_id": "en-US-JennyNeural",
        "music_mood": "cinematic_epic",
        "user_tier": "creator",
        "lang": "hindi",
    }
    r = client.post(f"{BASE}/api/wizard/create-reel", json=reel_body, headers=auth_headers)
    if r.status_code != 200:
        record("3b create-reel returns 200", False, f"status={r.status_code} body={r.text[:300]}")
        job_id = None
    else:
        rj = r.json()
        job_id = rj.get("job_id")
        record("3b create-reel returns 200 with job_id", bool(job_id), f"job_id={job_id} status={rj.get('status')}")

    if not job_id:
        # bail on wizard tests
        return summarize()

    # 3c/3d — Poll for up to 90s
    print("\n=== 3c/3d. Poll wizard job (up to 90s) ===")
    final_status = "unknown"
    final_stage = "unknown"
    final_error = None
    final_progress = 0
    stages_seen: list[str] = []
    deadline = time.time() + 90.0
    while time.time() < deadline:
        r = client.get(f"{BASE}/api/wizard/job/{job_id}")
        if r.status_code == 200:
            j = r.json()
            stage = j.get("stage") or "unknown"
            status = j.get("status") or "unknown"
            progress = j.get("progress") or 0
            if not stages_seen or stages_seen[-1] != stage:
                stages_seen.append(stage)
                print(f"   t={time.time():.0f}: stage={stage} status={status} progress={progress}%")
            final_status = status
            final_stage = stage
            final_progress = progress
            final_error = j.get("error")
            if status in ("completed", "failed", "error"):
                break
        time.sleep(5)

    print(f"\n   FINAL: stage={final_stage} status={final_status} progress={final_progress}% error={final_error}")
    print(f"   stages traversed: {stages_seen}")
    # 3d is best-effort: if completed OR progress > 50% → pass
    is_3d_pass = final_status == "completed" or (final_status != "failed" and final_progress > 50) or final_status == "completed"
    record(
        "3d job progressed/completed (best-effort, >50% or completed)",
        is_3d_pass,
        f"status={final_status} progress={final_progress}% stages={stages_seen}",
    )

    # 3e — inspect backend logs
    print("\n=== 3e. Backend logs check ===")
    import subprocess
    log_paths = ["/var/log/supervisor/backend.err.log", "/var/log/supervisor/backend.out.log"]
    log_text = ""
    for p in log_paths:
        try:
            out = subprocess.run(["tail", "-n", "500", p], capture_output=True, text=True, timeout=5)
            log_text += out.stdout + out.stderr
        except Exception:
            pass

    applied_re = re.compile(rf"wizard: applied creative_plan {re.escape(plan_1a_id)}.*?voice_style=.*?music_mood=.*?scenes=\d+")
    voice_re = re.compile(r"wizard: auto-switched voice to Hindi hi-IN-\w+ for plan_lang=hindi")
    applied_match = applied_re.search(log_text)
    voice_match = voice_re.search(log_text)

    record(
        "3e log: 'wizard: applied creative_plan <id>' present",
        bool(applied_match),
        f"snippet={applied_match.group(0)[:200] if applied_match else 'NOT FOUND'}",
    )
    record(
        "3e log: 'wizard: auto-switched voice to Hindi ... plan_lang=hindi' present",
        bool(voice_match),
        f"snippet={voice_match.group(0)[:200] if voice_match else 'NOT FOUND'}",
    )

    return summarize()


def summarize() -> int:
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    n_pass = sum(1 for _, ok, _ in results if ok)
    n_total = len(results)
    for label, ok, detail in results:
        mark = "✅" if ok else "❌"
        print(f"{mark} {label}{(' — ' + detail) if detail and not ok else ''}")
    print(f"\n{n_pass}/{n_total} passed")
    return 0 if n_pass == n_total else 1


if __name__ == "__main__":
    sys.exit(main())
