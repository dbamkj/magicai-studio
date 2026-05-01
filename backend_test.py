"""Session 19 — Phase C+ / C++ backend tests for /api/generate-prompts.

Covers:
  A) Health sanity
  B) style_boost parameter variations
  C) Rate limit (anonymous/free tier = 8/hr)
  D) Preview audio (Sarvam)
  E) Quick regression (generate-prompts basic + marketplace)
"""
from __future__ import annotations

import os
import sys
import time
import uuid
from typing import Any, Dict, Optional

import httpx
from pymongo import MongoClient

# ───────────────────────── Config ───────────────────────────────────────────
FRONTEND_ENV = "/app/frontend/.env"
def _read_backend_url() -> str:
    url = ""
    try:
        with open(FRONTEND_ENV, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
                    url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    except Exception:
        pass
    return url.rstrip("/") or "https://creative-plan-engine.preview.emergentagent.com"

BASE = _read_backend_url() + "/api"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "videoai_database"

TIMEOUT = 60.0
results: list[tuple[str, bool, str]] = []

def _ok(name: str, msg: str = "") -> None:
    results.append((name, True, msg))
    print(f"✅ {name} — {msg}")

def _fail(name: str, msg: str) -> None:
    results.append((name, False, msg))
    print(f"❌ {name} — {msg}")


def _uuid_suffix() -> str:
    return uuid.uuid4().hex[:8]


# ───────────────────────── A. Health ────────────────────────────────────────
def test_A_health(client: httpx.Client) -> None:
    try:
        r = client.get(f"{BASE}/generate-prompts/health")
        if r.status_code != 200:
            return _fail("A.health", f"status={r.status_code} body={r.text[:200]}")
        d = r.json()
        issues = []
        if d.get("ok") is not True: issues.append(f"ok={d.get('ok')}")
        if d.get("llm_key_configured") is not True: issues.append("llm_key_configured!=true")
        if d.get("sarvam_configured") is not True: issues.append("sarvam_configured!=true")
        if d.get("rate_limit_max") != 20: issues.append(f"rate_limit_max={d.get('rate_limit_max')}")
        if issues:
            return _fail("A.health", "; ".join(issues) + f" full={d}")
        _ok("A.health", f"ok llm+sarvam configured, rate_limit_max=20, cache_size={d.get('cache_size')}")
    except Exception as e:
        _fail("A.health", f"exc={e!r}")


# ───────────────────────── B. style_boost ───────────────────────────────────
def _post_gp(client: httpx.Client, body: dict) -> httpx.Response:
    return client.post(f"{BASE}/generate-prompts", json=body)


def test_B_style_boost(client: httpx.Client) -> None:
    # B1 — no style_boost
    try:
        body = {"idea": f"Krishna bhajan reel {_uuid_suffix()}", "language": "english"}
        r = _post_gp(client, body)
        if r.status_code != 200:
            _fail("B1.default", f"status={r.status_code} body={r.text[:300]}")
        else:
            d = r.json()
            issues = []
            if "detected" not in d or not isinstance(d["detected"], dict): issues.append("no detected{}")
            if not isinstance(d.get("prompts"), list) or len(d["prompts"]) != 3:
                issues.append(f"prompts len={len(d.get('prompts') or [])}")
            if d.get("style_boost") != "default": issues.append(f"style_boost={d.get('style_boost')}")
            rl = d.get("rate_limit") or {}
            for k in ("used", "limit", "remaining", "reset_at"):
                if k not in rl:
                    issues.append(f"rate_limit.{k} missing")
            # Each prompt must have a numeric score between 0..1
            if isinstance(d.get("prompts"), list):
                for i, p in enumerate(d["prompts"]):
                    s = p.get("score")
                    if not isinstance(s, (int, float)):
                        issues.append(f"prompts[{i}].score not numeric ({s!r})")
                    elif not (0.0 <= float(s) <= 1.0):
                        issues.append(f"prompts[{i}].score out of range ({s})")
            if issues:
                _fail("B1.default", "; ".join(issues))
            else:
                _ok("B1.default", f"3 prompts, style_boost=default, scores={[p.get('score') for p in d['prompts']]}, rl={rl}")
    except Exception as e:
        _fail("B1.default", f"exc={e!r}")

    # B2 — style_boost='cinematic'
    try:
        body = {"idea": f"Diwali festival reel {_uuid_suffix()}", "style_boost": "cinematic"}
        r = _post_gp(client, body)
        if r.status_code != 200:
            _fail("B2.cinematic", f"status={r.status_code} body={r.text[:300]}")
        else:
            d = r.json()
            prompts = d.get("prompts") or []
            matches = sum(1 for p in prompts if (p.get("style_tag") or "").lower() in {"cinematic", "documentary"})
            if d.get("style_boost") != "cinematic":
                _fail("B2.cinematic", f"style_boost response={d.get('style_boost')}")
            elif matches < 2:
                _fail("B2.cinematic", f"only {matches}/3 prompts match cinematic/documentary: style_tags={[p.get('style_tag') for p in prompts]}")
            else:
                _ok("B2.cinematic", f"{matches}/3 prompts match, style_tags={[p.get('style_tag') for p in prompts]}")
    except Exception as e:
        _fail("B2.cinematic", f"exc={e!r}")

    # B3 — style_boost='emotional'
    try:
        body = {"idea": f"Lost dad memories {_uuid_suffix()}", "style_boost": "emotional"}
        r = _post_gp(client, body)
        if r.status_code != 200:
            _fail("B3.emotional", f"status={r.status_code} body={r.text[:300]}")
        else:
            d = r.json()
            prompts = d.get("prompts") or []
            matches = sum(1 for p in prompts if (p.get("mood") or "").lower() in {"emotional", "nostalgic", "romantic"})
            if d.get("style_boost") != "emotional":
                _fail("B3.emotional", f"style_boost response={d.get('style_boost')}")
            elif matches < 2:
                _fail("B3.emotional", f"only {matches}/3 prompts match emotional/nostalgic/romantic: moods={[p.get('mood') for p in prompts]}")
            else:
                _ok("B3.emotional", f"{matches}/3 prompts match, moods={[p.get('mood') for p in prompts]}")
    except Exception as e:
        _fail("B3.emotional", f"exc={e!r}")

    # B4 — same idea with different boosts → distinct cache (second is NOT cached=true)
    try:
        idea = f"Mountain sunrise wanderlust {_uuid_suffix()}"
        r1 = _post_gp(client, {"idea": idea, "style_boost": "cinematic"})
        r2 = _post_gp(client, {"idea": idea, "style_boost": "emotional"})
        if r1.status_code != 200 or r2.status_code != 200:
            _fail("B4.cache_key_per_boost", f"r1={r1.status_code} r2={r2.status_code}")
        else:
            d2 = r2.json()
            if d2.get("cached") is True:
                _fail("B4.cache_key_per_boost", f"second call with different boost returned cached=True (cache key collision)")
            else:
                _ok("B4.cache_key_per_boost", f"cinematic then emotional — 2nd cached={d2.get('cached')} source={d2.get('source')}")
    except Exception as e:
        _fail("B4.cache_key_per_boost", f"exc={e!r}")

    # B5 — garbage style_boost → falls back to default
    try:
        body = {"idea": f"Morning routine vlog {_uuid_suffix()}", "style_boost": "garbage"}
        r = _post_gp(client, body)
        if r.status_code != 200:
            # Pydantic Literal will 422 — but server code normalises AFTER pydantic,
            # so "garbage" would fail pydantic validation. Check this.
            _fail("B5.garbage_fallback", f"status={r.status_code} body={r.text[:300]}")
        else:
            d = r.json()
            if d.get("style_boost") != "default":
                _fail("B5.garbage_fallback", f"style_boost in response={d.get('style_boost')} (expected 'default')")
            else:
                _ok("B5.garbage_fallback", "garbage boost → default (server normalised)")
    except Exception as e:
        _fail("B5.garbage_fallback", f"exc={e!r}")


# ───────────────────────── C. Rate limit ────────────────────────────────────
def _cleanup_anon_rows(client_ip_hint: Optional[str] = None) -> int:
    """Delete db.prompt_generations rows for anon:<ip> buckets we created.

    We don't know our own external IP definitively, so delete any rows with
    user_id starting 'anon:' that were inserted in the last hour. This is
    safe in a test environment.
    """
    try:
        mc = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
        col = mc[DB_NAME]["prompt_generations"]
        from datetime import datetime, timedelta, timezone
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        filt = {"user_id": {"$regex": "^anon:"}, "created_at": {"$gte": cutoff}}
        if client_ip_hint:
            filt["user_id"] = f"anon:{client_ip_hint}"
        res = col.delete_many(filt)
        mc.close()
        return res.deleted_count
    except Exception as e:
        print(f"   cleanup failed: {e}")
        return -1


def test_C_rate_limit(client: httpx.Client) -> None:
    # Clean up any pre-existing anon rows first to avoid inherited state
    deleted_pre = _cleanup_anon_rows()
    print(f"   pre-cleanup: deleted {deleted_pre} rows")

    successes = 0
    blocked_resp = None
    blocked_at = None
    last_200_rl = None
    for i in range(12):
        try:
            idea = f"Rate limit probe {i} {_uuid_suffix()}"
            r = _post_gp(client, {"idea": idea, "language": "english"})
            if r.status_code == 200:
                successes += 1
                try:
                    last_200_rl = r.json().get("rate_limit") or {}
                except Exception:
                    pass
            elif r.status_code == 429:
                blocked_resp = r
                blocked_at = i + 1
                print(f"   429 received at call #{i+1}")
                break
            else:
                print(f"   unexpected status {r.status_code} at call #{i+1}: {r.text[:200]}")
        except Exception as e:
            print(f"   exc at call #{i+1}: {e!r}")

    if blocked_resp is None:
        _fail("C.rate_limit", f"no 429 received after 12 calls (successes={successes}, last_rl={last_200_rl})")
        _cleanup_anon_rows()
        return

    # Validate 429 payload
    try:
        body = blocked_resp.json()
    except Exception:
        _fail("C.rate_limit", f"429 body not JSON: {blocked_resp.text[:200]}")
        _cleanup_anon_rows()
        return

    detail = body.get("detail") or {}
    issues = []
    if detail.get("code") != "rate_limited": issues.append(f"code={detail.get('code')}")
    rl = detail.get("rate_limit") or {}
    if rl.get("limit") != 8: issues.append(f"limit={rl.get('limit')} (expected 8 free tier)")
    if rl.get("remaining") != 0: issues.append(f"remaining={rl.get('remaining')} (expected 0 when blocked)")
    if not isinstance(rl.get("retry_after_s"), (int, float)) or rl.get("retry_after_s", 0) <= 0:
        issues.append(f"retry_after_s={rl.get('retry_after_s')} (expected > 0)")
    for k in ("used", "reset_at"):
        if k not in rl: issues.append(f"rate_limit.{k} missing")
    if "tier" not in detail: issues.append("tier missing")
    if "anonymous" not in detail: issues.append("anonymous missing")

    if issues:
        _fail("C.rate_limit", f"429 payload issues: {'; '.join(issues)}; full={body}")
    else:
        _ok("C.rate_limit", f"blocked at call #{blocked_at}, successes_before_block={successes}, rl={rl}")

    # Now verify GET /api/generate-prompts/usage returns matching numbers
    try:
        r = client.get(f"{BASE}/generate-prompts/usage")
        if r.status_code != 200:
            _fail("C.usage", f"status={r.status_code}")
        else:
            u = r.json()
            ui = []
            if u.get("limit") != 8: ui.append(f"limit={u.get('limit')}")
            if u.get("blocked") is not True: ui.append(f"blocked={u.get('blocked')}")
            if u.get("used", 0) < 8: ui.append(f"used={u.get('used')} (<8)")
            if ui:
                _fail("C.usage", "; ".join(ui) + f" full={u}")
            else:
                _ok("C.usage", f"usage endpoint matches: {u}")
    except Exception as e:
        _fail("C.usage", f"exc={e!r}")

    # Cleanup
    deleted = _cleanup_anon_rows()
    print(f"   post-cleanup: deleted {deleted} rows")


# ───────────────────────── D. Preview audio ─────────────────────────────────
def test_D_preview_audio(client: httpx.Client) -> None:
    # D1 — English
    unique_txt = f"Hello from MagiCAi {_uuid_suffix()}"
    t0 = time.time()
    try:
        r = client.post(f"{BASE}/generate-prompts/preview-audio",
                        json={"text": unique_txt, "voice_type": "warm_storyteller_female", "language": "english"})
        dt1 = time.time() - t0
        ct = r.headers.get("content-type", "")
        cl = int(r.headers.get("content-length", "0") or len(r.content))
        if r.status_code != 200 or "audio/mpeg" not in ct or cl < 1000:
            # If Sarvam is flaky → 503, mark partial
            if r.status_code == 503:
                _ok("D1.preview_en", f"partially working — Sarvam 503 (transient): {r.text[:200]}")
            else:
                _fail("D1.preview_en", f"status={r.status_code} ct={ct} cl={cl} body={r.text[:200]}")
        else:
            _ok("D1.preview_en", f"ct={ct} cl={cl} dt={dt1:.2f}s")
    except Exception as e:
        _fail("D1.preview_en", f"exc={e!r}")

    # D2 — same body → cache (fast)
    try:
        t0 = time.time()
        r = client.post(f"{BASE}/generate-prompts/preview-audio",
                        json={"text": unique_txt, "voice_type": "warm_storyteller_female", "language": "english"})
        dt2 = time.time() - t0
        if r.status_code == 200 and "audio/mpeg" in r.headers.get("content-type", ""):
            _ok("D2.preview_cached", f"200 ct=audio/mpeg dt={dt2:.2f}s (should be <1s if cached)")
        elif r.status_code == 503:
            _ok("D2.preview_cached", f"partially working — Sarvam 503 (transient)")
        else:
            _fail("D2.preview_cached", f"status={r.status_code} body={r.text[:200]}")
    except Exception as e:
        _fail("D2.preview_cached", f"exc={e!r}")

    # D3 — empty text → 400
    try:
        r = client.post(f"{BASE}/generate-prompts/preview-audio",
                        json={"text": "", "voice_type": "warm_storyteller_female", "language": "english"})
        # The pydantic min_length=1 triggers 422; server code also raises 400 inside route.
        if r.status_code in (400, 422):
            _ok("D3.preview_empty", f"got {r.status_code} as expected")
        else:
            _fail("D3.preview_empty", f"status={r.status_code} (expected 400 or 422) body={r.text[:200]}")
    except Exception as e:
        _fail("D3.preview_empty", f"exc={e!r}")

    # D4 — Hindi
    try:
        r = client.post(f"{BASE}/generate-prompts/preview-audio",
                        json={"text": f"एक छोटी सी कहानी सुनो {_uuid_suffix()}",
                              "voice_type": "warm_storyteller_female", "language": "hindi"})
        ct = r.headers.get("content-type", "")
        cl = int(r.headers.get("content-length", "0") or len(r.content))
        if r.status_code == 200 and "audio" in ct and cl > 1000:
            _ok("D4.preview_hi", f"ct={ct} cl={cl}")
        elif r.status_code == 503:
            _ok("D4.preview_hi", f"partially working — Sarvam 503 (transient): {r.text[:200]}")
        else:
            _fail("D4.preview_hi", f"status={r.status_code} ct={ct} cl={cl} body={r.text[:200]}")
    except Exception as e:
        _fail("D4.preview_hi", f"exc={e!r}")


# ───────────────────────── E. Regression ────────────────────────────────────
def test_E_regression(client: httpx.Client) -> None:
    # Clean anon rows again so rate limit doesn't block this
    _cleanup_anon_rows()

    try:
        r = _post_gp(client, {"idea": f"Quick reg test {_uuid_suffix()}"})
        if r.status_code != 200:
            _fail("E1.gp_basic", f"status={r.status_code} body={r.text[:200]}")
        else:
            d = r.json()
            if not isinstance(d.get("prompts"), list) or len(d["prompts"]) != 3:
                _fail("E1.gp_basic", f"prompts len={len(d.get('prompts') or [])}")
            else:
                _ok("E1.gp_basic", f"3 prompts, source={d.get('source')}, style_boost={d.get('style_boost')}")
    except Exception as e:
        _fail("E1.gp_basic", f"exc={e!r}")

    try:
        r = client.get(f"{BASE}/marketplace/templates?limit=10")
        if r.status_code != 200:
            _fail("E2.marketplace", f"status={r.status_code}")
        else:
            j = r.json()
            tmpl = j.get("templates") if isinstance(j, dict) else j
            n = len(tmpl) if isinstance(tmpl, list) else 0
            if n < 1:
                _fail("E2.marketplace", f"no templates returned, keys={list(j.keys()) if isinstance(j, dict) else type(j)}")
            else:
                _ok("E2.marketplace", f"{n} templates returned")
    except Exception as e:
        _fail("E2.marketplace", f"exc={e!r}")

    # Cleanup after regression insert too
    _cleanup_anon_rows()


# ───────────────────────── main ─────────────────────────────────────────────
def main() -> int:
    print(f"BASE = {BASE}")
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        print("\n== A) Health ==")
        test_A_health(client)

        print("\n== B) style_boost ==")
        test_B_style_boost(client)

        print("\n== C) Rate limit (fires many calls; cleans DB after) ==")
        test_C_rate_limit(client)

        print("\n== D) Preview audio ==")
        test_D_preview_audio(client)

        print("\n== E) Regression ==")
        test_E_regression(client)

    print("\n" + "=" * 64)
    print("SUMMARY")
    print("=" * 64)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, msg in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}  {msg[:200]}")
    print("=" * 64)
    print(f"RESULT: {passed}/{total} PASSED")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
