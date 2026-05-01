"""Phase D backend tests — focused.

Covers:
  A) GET /api/avatar/styles  (11 buckets, new fields)
  B) POST /api/wizard/ai-images (gpt-image-1 generation, tier gate, cache, validation, health, serve-file)
  C) Regression sanity — generate-prompts/health, marketplace/templates
"""
from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, Optional

import httpx


# ───────────────────────── Config ──────────────────────────────────────
def _read_backend_url() -> str:
    with open("/app/frontend/.env", "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("Backend URL not found")


BACKEND_URL = _read_backend_url().rstrip("/")
API = f"{BACKEND_URL}/api"
print(f"[config] BACKEND_URL = {BACKEND_URL}")

CREATOR_EMAIL = "demo_creator@test.com"
STARTER_EMAIL = "demo_starter@test.com"
PASSWORD = "Test@123"

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, msg: str = ""):
    results.append((name, ok, msg))
    sym = "✅" if ok else "❌"
    print(f"{sym} {name}{(' — ' + msg) if msg else ''}")


def login(email: str) -> Optional[str]:
    try:
        r = httpx.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD}, timeout=20.0)
        if r.status_code != 200:
            print(f"  [login] {email} status={r.status_code} body={r.text[:200]}")
            return None
        data = r.json()
        return data.get("token") or data.get("access_token")
    except Exception as e:
        print(f"  [login] error: {e}")
        return None


# ════════════════════════ A) /api/avatar/styles ═══════════════════════
def test_avatar_styles():
    print("\n=== A) GET /api/avatar/styles ===")
    try:
        r = httpx.get(f"{API}/avatar/styles", timeout=15.0)
    except Exception as e:
        record("A1: avatar/styles reachable", False, f"network error {e}")
        return
    if r.status_code != 200:
        record("A1: avatar/styles 200", False, f"status={r.status_code} body={r.text[:200]}")
        return
    record("A1: avatar/styles 200", True)

    data = r.json()
    styles = data.get("styles", [])
    ids = [s.get("id") for s in styles]
    print(f"  total styles: {len(styles)} -> ids: {ids}")

    expected = [
        "pixar", "anime", "disney", "caricature", "comic",
        "desi_toon", "jungle_hero", "robo_pal",
        "mythological", "bollywood_poster", "cricket_champion",
    ]
    missing = [i for i in expected if i not in ids]
    if missing:
        record("A2: 11 expected style ids present", False, f"missing={missing}")
    else:
        record("A2: 11 expected style ids present", True, f"count={len(ids)}")

    # Check the new ones have label/icon/tagline/premium populated. NOTE: the
    # /styles endpoint serializer drops prompt_modifier from the response, so
    # we do not assert prompt_modifier presence here (it's an internal field).
    new_ids = ["desi_toon", "jungle_hero", "robo_pal", "mythological", "bollywood_poster", "cricket_champion"]
    by_id = {s.get("id"): s for s in styles}
    bad = []
    for nid in new_ids:
        s = by_id.get(nid)
        if not s:
            bad.append(f"{nid}:absent")
            continue
        if not s.get("label"): bad.append(f"{nid}:label")
        if not s.get("icon"): bad.append(f"{nid}:icon")
        if not s.get("tagline"): bad.append(f"{nid}:tagline")
        if not isinstance(s.get("premium"), bool): bad.append(f"{nid}:premium-not-bool")
    if bad:
        record("A3: new styles have label/icon/tagline/premium-bool", False, ", ".join(bad))
    else:
        record("A3: new styles have label/icon/tagline/premium-bool", True)


# ════════════════════════ B) /api/wizard/ai-images ═══════════════════════
def test_wizard_ai_images():
    print("\n=== B) POST /api/wizard/ai-images ===")

    # B6: health (run early — independent)
    try:
        r = httpx.get(f"{API}/wizard/ai-images/health", timeout=10.0)
        if r.status_code == 200:
            d = r.json()
            ok = d.get("ok") is True and d.get("model") == "gpt-image-1" and d.get("tier_gate") == "creator+"
            record("B6: ai-images/health correct shape", ok, f"body={d}")
        else:
            record("B6: ai-images/health correct shape", False, f"status={r.status_code}")
    except Exception as e:
        record("B6: ai-images/health correct shape", False, f"err {e}")

    # B1: no auth → 403 tier_locked
    try:
        r = httpx.post(
            f"{API}/wizard/ai-images",
            json={"image_query": "Himalayan sunrise temple", "count": 1, "aspect": "9:16"},
            timeout=15.0,
        )
        body = {}
        try: body = r.json()
        except Exception: pass
        detail = body.get("detail") if isinstance(body, dict) else {}
        is_403 = r.status_code == 403
        is_tier = isinstance(detail, dict) and detail.get("code") == "tier_locked" and detail.get("required_tier") == "creator"
        record("B1: no-auth returns 403 tier_locked", is_403 and is_tier,
               f"status={r.status_code} detail={detail if isinstance(detail, dict) else body}")
    except Exception as e:
        record("B1: no-auth returns 403 tier_locked", False, f"err {e}")

    # B2: starter user → 403 tier_locked
    starter_token = login(STARTER_EMAIL)
    if not starter_token:
        record("B2: starter user 403 tier_locked", False, "could not login demo_starter (skipped)")
    else:
        try:
            r = httpx.post(
                f"{API}/wizard/ai-images",
                json={"image_query": "Himalayan sunrise temple", "count": 1, "aspect": "9:16"},
                headers={"Authorization": f"Bearer {starter_token}"},
                timeout=15.0,
            )
            body = {}
            try: body = r.json()
            except Exception: pass
            detail = body.get("detail") if isinstance(body, dict) else {}
            is_403 = r.status_code == 403
            is_tier = isinstance(detail, dict) and detail.get("code") == "tier_locked" and detail.get("required_tier") == "creator"
            record("B2: starter user 403 tier_locked", is_403 and is_tier,
                   f"status={r.status_code} detail={detail}")
        except Exception as e:
            record("B2: starter user 403 tier_locked", False, f"err {e}")

    # B5: validation — empty image_query (too short, min_length=3)
    creator_token = login(CREATOR_EMAIL)
    if not creator_token:
        record("B-login: creator login", False, "could NOT login demo_creator")
        return
    record("B-login: creator login", True)

    try:
        r = httpx.post(
            f"{API}/wizard/ai-images",
            json={"image_query": "", "count": 1, "aspect": "9:16"},
            headers={"Authorization": f"Bearer {creator_token}"},
            timeout=15.0,
        )
        record("B5: empty image_query → 422", r.status_code == 422,
               f"status={r.status_code}")
    except Exception as e:
        record("B5: empty image_query → 422", False, f"err {e}")

    # B3: creator generates a real image (~15s first call)
    payload = {
        "image_query": "Himalayan sunrise temple",
        "count": 1,
        "aspect": "9:16",
        "style_hint": "cinematic",
    }
    first_url: Optional[str] = None
    try:
        t0 = time.time()
        r = httpx.post(
            f"{API}/wizard/ai-images",
            json=payload,
            headers={"Authorization": f"Bearer {creator_token}"},
            timeout=120.0,
        )
        elapsed = time.time() - t0
        if r.status_code != 200:
            record("B3: creator AI image generation 200", False,
                   f"status={r.status_code} body={r.text[:300]} elapsed={elapsed:.1f}s")
        else:
            d = r.json()
            imgs = d.get("images") or []
            ok_shape = (
                d.get("source") == "ai"
                and d.get("tier") == "creator"
                and len(imgs) >= 1
                and imgs[0].get("ai_generated") is True
                and imgs[0].get("width") == 1024
                and imgs[0].get("height") == 1536
                and (imgs[0].get("url") or "").startswith("/api/serve-file/")
                and "img_" in (imgs[0].get("url") or "")
                and (imgs[0].get("url") or "").endswith(".png")
            )
            record("B3: creator AI image generation 200 (correct shape)",
                   ok_shape,
                   f"elapsed={elapsed:.1f}s source={d.get('source')} tier={d.get('tier')} cached={d.get('cached')} url={imgs[0].get('url') if imgs else None}")
            if imgs:
                first_url = imgs[0].get("url")
    except Exception as e:
        record("B3: creator AI image generation 200", False, f"err {e}")

    # B4: same request again → cached=true, fast
    try:
        t0 = time.time()
        r = httpx.post(
            f"{API}/wizard/ai-images",
            json=payload,
            headers={"Authorization": f"Bearer {creator_token}"},
            timeout=30.0,
        )
        elapsed = time.time() - t0
        if r.status_code != 200:
            record("B4: cache hit 200", False, f"status={r.status_code} body={r.text[:200]}")
        else:
            d = r.json()
            cached = d.get("cached") is True
            fast = elapsed < 3.0  # generous; goal was <1s but network adds latency
            record("B4: cache hit cached=true & fast",
                   cached and fast,
                   f"cached={d.get('cached')} elapsed={elapsed:.2f}s")
    except Exception as e:
        record("B4: cache hit cached=true & fast", False, f"err {e}")

    # B7: serve-file returns >1KB PNG
    if first_url:
        full = first_url if first_url.startswith("http") else f"{BACKEND_URL}{first_url}"
        try:
            r = httpx.get(full, timeout=20.0)
            ct = r.headers.get("content-type", "")
            size = len(r.content)
            ok = r.status_code == 200 and "image/png" in ct and size > 1024
            record("B7: serve-file returns >1KB PNG",
                   ok,
                   f"status={r.status_code} ct={ct} size={size}B url={full}")
        except Exception as e:
            record("B7: serve-file returns >1KB PNG", False, f"err {e}")
    else:
        record("B7: serve-file returns >1KB PNG", False, "no url from B3")


# ════════════════════════ C) Regression sanity ═══════════════════════
def test_regression_sanity():
    print("\n=== C) Regression sanity ===")
    try:
        r = httpx.get(f"{API}/generate-prompts/health", timeout=10.0)
        d = r.json() if r.status_code == 200 else {}
        record("C1: generate-prompts/health ok=true",
               r.status_code == 200 and d.get("ok") is True,
               f"status={r.status_code} body={d}")
    except Exception as e:
        record("C1: generate-prompts/health ok=true", False, f"err {e}")

    try:
        r = httpx.get(f"{API}/marketplace/templates", params={"limit": 5}, timeout=15.0)
        if r.status_code != 200:
            record("C2: marketplace/templates ≥5", False, f"status={r.status_code} body={r.text[:200]}")
        else:
            d = r.json()
            tpls = d.get("templates") if isinstance(d, dict) else None
            if tpls is None and isinstance(d, list):
                tpls = d
            cnt = len(tpls or [])
            record("C2: marketplace/templates ≥5", cnt >= 5, f"count={cnt}")
    except Exception as e:
        record("C2: marketplace/templates ≥5", False, f"err {e}")


def main():
    test_avatar_styles()
    test_wizard_ai_images()
    test_regression_sanity()

    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    n_pass = sum(1 for _, ok, _ in results if ok)
    n_fail = len(results) - n_pass
    for name, ok, msg in results:
        sym = "PASS" if ok else "FAIL"
        print(f"  [{sym}] {name}{(' — ' + msg) if (msg and not ok) else ''}")
    print(f"\nTotals: {n_pass} passed, {n_fail} failed (out of {len(results)})")
    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
