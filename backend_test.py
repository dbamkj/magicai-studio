"""Session 34-D verification suite — waitlist + plan_tier migration + regression sweep.

Tests against EXPO_PUBLIC_BACKEND_URL from frontend/.env (NOT localhost).
"""
from __future__ import annotations
import json
import os
import sys
import time
from typing import Any

import requests

BASE = "https://creative-plan-engine.preview.emergentagent.com"
API = f"{BASE}/api"
PWD = "Test@123"

results: list[tuple[str, bool, str]] = []


def rec(name: str, ok: bool, detail: str = ""):
    results.append((name, ok, detail))
    flag = "OK " if ok else "FAIL"
    print(f"[{flag}] {name}  {detail[:200]}")


def login(email: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": PWD}, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"login {email} failed: {r.status_code} {r.text}")
    return r.json()["token"]


def hdr(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


# ────────────────────────────────────────────────────────────────────
# A) NEW WAITLIST ENDPOINTS
# ────────────────────────────────────────────────────────────────────
def test_waitlist():
    print("\n=== A) WAITLIST ENDPOINTS ===")

    # Cleanup first (in case prior test runs left rows). We delete via Mongo direct
    # at the END (cleanup section). Here we run the actual tests.

    # A1 — first signup
    r = requests.post(f"{API}/waitlist-signup",
                      json={"email": "alice@example.com", "name": "Alice", "tier_interest": "creator"},
                      timeout=10)
    a1_pass = (r.status_code == 200)
    if a1_pass:
        j = r.json()
        a1_pass = (
            j.get("ok") is True
            and j.get("already_signed_up") is False
            and j.get("email") == "alice@example.com"
            and isinstance(j.get("position"), int)
            and "#" in (j.get("message") or "")
        )
        rec("A1 first signup alice", a1_pass, f"position={j.get('position')} msg={j.get('message')}")
    else:
        rec("A1 first signup alice", False, f"status={r.status_code} body={r.text[:200]}")

    # A2 — same email idempotency
    r = requests.post(f"{API}/waitlist-signup",
                      json={"email": "alice@example.com", "name": "Alice", "tier_interest": "creator"},
                      timeout=10)
    if r.status_code == 200:
        j = r.json()
        ok = (
            j.get("ok") is True
            and j.get("already_signed_up") is True
            and j.get("email") == "alice@example.com"
            and isinstance(j.get("position"), int)
            and "already" in (j.get("message") or "").lower()
        )
        rec("A2 idempotent re-signup", ok, f"already_signed_up={j.get('already_signed_up')} msg={j.get('message')}")
    else:
        rec("A2 idempotent re-signup", False, f"status={r.status_code}")

    # A3 — invalid email
    r = requests.post(f"{API}/waitlist-signup",
                      json={"email": "not-an-email", "name": "X"}, timeout=10)
    if r.status_code == 422:
        body = r.text.lower()
        rec("A3 invalid email -> 422", "email" in body, f"detail mentions email: {('email' in body)}")
    else:
        rec("A3 invalid email -> 422", False, f"status={r.status_code} body={r.text[:200]}")

    # A4 — UTM params
    r = requests.post(f"{API}/waitlist-signup",
                      json={"email": "bob@example.com", "utm_source": "twitter",
                            "utm_medium": "share", "utm_campaign": "launch"}, timeout=10)
    a4_pass = (r.status_code == 200 and r.json().get("ok") is True)
    rec("A4 UTM signup bob", a4_pass, f"status={r.status_code}")

    # A5 — malicious name
    r = requests.post(f"{API}/waitlist-signup",
                      json={"email": "hack@example.com", "name": "<script>alert(1)</script>"}, timeout=10)
    if r.status_code == 400:
        try:
            d = r.json().get("detail", "")
        except Exception:
            d = r.text
        rec("A5 malicious name -> 400", "invalid characters" in d.lower(), f"detail={d}")
    else:
        rec("A5 malicious name -> 400", False, f"status={r.status_code} body={r.text[:200]}")

    # A6 — public stats
    r = requests.get(f"{API}/waitlist-stats", timeout=10)
    if r.status_code == 200:
        j = r.json()
        total = j.get("total")
        invited = j.get("invited")
        seats = j.get("remaining_seats")
        ok = (
            isinstance(total, int) and isinstance(invited, int) and isinstance(seats, int)
            and seats == max(0, 20 - invited)
            and total >= 2  # alice + bob (hack rejected)
        )
        rec("A6 waitlist-stats", ok, f"total={total} invited={invited} seats={seats}")
    else:
        rec("A6 waitlist-stats", False, f"status={r.status_code}")

    # A7 — admin endpoint no auth
    r = requests.get(f"{API}/admin/waitlist", timeout=10)
    rec("A7 admin/waitlist no auth -> 401/403", r.status_code in (401, 403),
        f"status={r.status_code}")

    # A8 — non-admin
    try:
        tok = login("demo_creator@test.com")
        r = requests.get(f"{API}/admin/waitlist", headers=hdr(tok), timeout=10)
        if r.status_code == 403:
            try:
                d = r.json().get("detail", "")
            except Exception:
                d = r.text
            rec("A8 non-admin -> 403", "admin only" in d.lower(), f"detail={d}")
        else:
            rec("A8 non-admin -> 403", False, f"status={r.status_code} body={r.text[:200]}")
    except Exception as e:
        rec("A8 non-admin -> 403", False, f"login err: {e}")

    # A9 — admin listing
    try:
        admin_tok = login("admin@magicai.test")
        r = requests.get(f"{API}/admin/waitlist?limit=10", headers=hdr(admin_tok), timeout=10)
        if r.status_code == 200:
            j = r.json()
            items = j.get("items") or []
            # check sort ascending by created_at
            cas = [it.get("created_at") for it in items if it.get("created_at")]
            sorted_ok = (cas == sorted(cas))
            # verify meta stripped
            meta_stripped = all("meta" not in it for it in items)
            # check our 2 emails appear
            emails = {it.get("email") for it in items}
            has_alice = "alice@example.com" in emails
            has_bob = "bob@example.com" in emails
            ok = (
                isinstance(j.get("total"), int)
                and isinstance(items, list)
                and sorted_ok and meta_stripped
                and has_alice and has_bob
            )
            rec("A9 admin GET list", ok,
                f"total={j.get('total')} items={len(items)} sorted={sorted_ok} meta_stripped={meta_stripped} alice={has_alice} bob={has_bob}")
            # Verify A4 UTM persisted via the admin listing
            bob_doc = next((it for it in items if it.get("email") == "bob@example.com"), None)
            if bob_doc:
                utm = bob_doc.get("utm") or {}
                utm_ok = (
                    utm.get("source") == "twitter"
                    and utm.get("medium") == "share"
                    and utm.get("campaign") == "launch"
                )
                rec("A4b UTM persisted in DB doc", utm_ok, f"utm={utm}")
            else:
                rec("A4b UTM persisted in DB doc", False, "bob not found in admin listing")
            # Also verify alice had name persisted
            alice_doc = next((it for it in items if it.get("email") == "alice@example.com"), None)
            if alice_doc:
                rec("A1b name+tier persisted",
                    alice_doc.get("name") == "Alice" and alice_doc.get("tier_interest") == "creator",
                    f"name={alice_doc.get('name')} tier_interest={alice_doc.get('tier_interest')}")
        else:
            rec("A9 admin GET list", False, f"status={r.status_code} body={r.text[:200]}")

        # A10 — only_uninvited filter
        r = requests.get(f"{API}/admin/waitlist?only_uninvited=true", headers=hdr(admin_tok), timeout=10)
        if r.status_code == 200:
            items = r.json().get("items") or []
            ok = all((it.get("invited") is False) for it in items)
            rec("A10 only_uninvited filter", ok, f"items={len(items)} all uninvited={ok}")
        else:
            rec("A10 only_uninvited filter", False, f"status={r.status_code}")
        return admin_tok
    except Exception as e:
        rec("A9 admin GET list", False, f"login err: {e}")
        return None


# ────────────────────────────────────────────────────────────────────
# B) PLAN_TIER MIGRATION
# ────────────────────────────────────────────────────────────────────
def test_plan_tier():
    print("\n=== B) PLAN_TIER MIGRATION ===")
    r = requests.get(f"{API}/marketplace/templates?limit=100", timeout=15)
    if r.status_code != 200:
        rec("B1 marketplace/templates", False, f"status={r.status_code}")
        return
    j = r.json()
    items = j.get("templates") or []
    valid_tiers = {"free", "starter", "creator", "pro"}
    missing = [it.get("id") for it in items if it.get("plan_tier") not in valid_tiers]
    distrib = {"free": 0, "starter": 0, "creator": 0, "pro": 0}
    for it in items:
        pt = it.get("plan_tier")
        if pt in distrib:
            distrib[pt] += 1
    rec("B1 every template has plan_tier", len(missing) == 0,
        f"items={len(items)} missing={len(missing)} distribution={distrib}")
    # B2 spot check creator
    creator_items = [it for it in items if it.get("plan_tier") == "creator"]
    rec("B2 plan_tier=creator field set",
        len(creator_items) > 0 and creator_items[0].get("plan_tier") == "creator",
        f"creator_count={len(creator_items)}")


# ────────────────────────────────────────────────────────────────────
# C) REGRESSION SWEEP
# ────────────────────────────────────────────────────────────────────
def test_regression():
    print("\n=== C) REGRESSION SWEEP ===")

    # C1
    r = requests.get(f"{API}/", timeout=10)
    j = r.json() if r.status_code == 200 else {}
    rec("C1 / -> 200 v7.1.0", r.status_code == 200 and j.get("version") == "7.1.0",
        f"version={j.get('version')}")

    # C2
    r = requests.post(f"{API}/auth/login",
                      json={"email": "demo_creator@test.com", "password": PWD}, timeout=15)
    creator_tok = None
    if r.status_code == 200 and r.json().get("token"):
        creator_tok = r.json()["token"]
        rec("C2 demo_creator login", True, "token received")
    else:
        rec("C2 demo_creator login", False, f"status={r.status_code}")
        return

    # C3 /me/limits
    r = requests.get(f"{API}/me/limits", headers=hdr(creator_tok), timeout=10)
    if r.status_code == 200:
        j = r.json()
        keys = {"tier", "credits", "usage_this_month", "usage_today", "feature_gates", "upgrade_hints"}
        missing_keys = keys - set(j.keys())
        gates = j.get("feature_gates") or {}
        expected_gates = {"face_swap","lip_sync","head_swap","body_swap","video_to_video",
                          "divine","ai_bg_lipsync","multishot","ai_video","video_studio",
                          "video_cinematic","image_cinematic"}
        gate_match = (set(gates.keys()) == expected_gates)
        # creator hint mentions kling 3.0 / pro
        hints = j.get("upgrade_hints") or []
        hint_text = " ".join(str(h.get("text", "")) for h in hints).lower()
        kling_hint = ("kling" in hint_text and "pro" in hint_text)
        rec("C3 /me/limits creator", not missing_keys and gate_match and kling_hint and len(gates) == 12,
            f"missing={missing_keys} gates={len(gates)} gate_match={gate_match} kling_hint={kling_hint}")
    else:
        rec("C3 /me/limits creator", False, f"status={r.status_code}")

    # C4 demo_free faceswap
    free_tok = login("demo_free@test.com")
    r = requests.post(f"{API}/create-faceswap",
                      headers=hdr(free_tok),
                      json={"target_video_path": "/tmp/x.mp4",
                            "source_image_paths": ["/tmp/a.png"],
                            "video_duration": 5},
                      timeout=10)
    if r.status_code == 402:
        try:
            d = r.json().get("detail", "")
        except Exception:
            d = r.text
        rec("C4 free /create-faceswap -> 402", "Face Swap requires Starter" in d, f"detail={d}")
    else:
        rec("C4 free /create-faceswap -> 402", False, f"status={r.status_code} body={r.text[:200]}")

    # C5 demo_free headswap
    r = requests.post(f"{API}/create-headswap",
                      headers=hdr(free_tok),
                      json={"head_image_path": "/tmp/a.png", "body_image_path": "/tmp/b.png"},
                      timeout=10)
    if r.status_code == 402:
        try:
            d = r.json().get("detail", "")
        except Exception:
            d = r.text
        rec("C5 free /create-headswap -> 402", "Head Swap requires Starter" in d, f"detail={d}")
    else:
        rec("C5 free /create-headswap -> 402", False, f"status={r.status_code} body={r.text[:200]}")

    # C6 demo_starter generate-video studio
    starter_tok = login("demo_starter@test.com")
    r = requests.post(f"{API}/generate-video",
                      headers=hdr(starter_tok),
                      json={"prompt": "test", "duration": 5, "quality_mode": "studio",
                            "aspect_ratio": "9:16"},
                      timeout=10)
    if r.status_code == 402:
        try:
            d = r.json().get("detail", "")
        except Exception:
            d = r.text
        rec("C6 starter studio -> 402", "AI Video requires Creator" in d, f"detail={d}")
    else:
        rec("C6 starter studio -> 402", False, f"status={r.status_code} body={r.text[:200]}")

    # C7 demo_creator generate-video cinematic
    r = requests.post(f"{API}/generate-video",
                      headers=hdr(creator_tok),
                      json={"prompt": "test", "duration": 3, "quality_mode": "cinematic",
                            "aspect_ratio": "9:16"},
                      timeout=10)
    if r.status_code == 402:
        try:
            d = r.json().get("detail", "")
        except Exception:
            d = r.text
        rec("C7 creator cinematic -> 402",
            "Kling 3.0 Pro" in d or "cinematic" in d.lower() and "Pro plan" in d,
            f"detail={d}")
    else:
        rec("C7 creator cinematic -> 402", False, f"status={r.status_code} body={r.text[:200]}")

    # C8 credits-info
    r = requests.get(f"{API}/credits-info", timeout=10)
    if r.status_code == 200:
        j = r.json()
        ok = ("cost_table" in j and "pricing" in j and "quality_tiers" in j)
        rec("C8 /credits-info", ok, f"keys={list(j.keys())[:10]}")
    else:
        rec("C8 /credits-info", False, f"status={r.status_code}")

    # C9 mh-models
    r = requests.get(f"{API}/mh-models", timeout=10)
    if r.status_code == 200:
        j = r.json()
        feats = j.get("features") or {}
        rec("C9 /mh-models 8 features", len(feats) == 8, f"features={len(feats)}")
    else:
        rec("C9 /mh-models 8 features", False, f"status={r.status_code}")

    # C10 usage demo_creator
    r = requests.get(f"{API}/usage", headers=hdr(creator_tok), timeout=10)
    if r.status_code == 200:
        j = r.json()
        rec("C10 /usage", isinstance(j, dict) and len(j) > 0, f"keys={list(j.keys())[:10]}")
    else:
        rec("C10 /usage", False, f"status={r.status_code}")

    # C11 templates/preview-stats
    r = requests.get(f"{API}/templates/preview-stats", timeout=10)
    if r.status_code == 200:
        j = r.json()
        rec("C11 preview-stats coverage_pct=100",
            j.get("coverage_pct") in (100, 100.0), f"coverage_pct={j.get('coverage_pct')}")
    else:
        rec("C11 preview-stats coverage_pct=100", False, f"status={r.status_code}")

    # C12 creative-plan
    r = requests.post(f"{API}/creative-plan", json={"idea": "test"}, timeout=30)
    if r.status_code == 200:
        j = r.json()
        ok = all(k in j for k in ("hook", "script", "scene_keywords"))
        rec("C12 creative-plan", ok, f"keys: hook={bool(j.get('hook'))} script={bool(j.get('script'))} scene_keywords={bool(j.get('scene_keywords'))}")
    else:
        rec("C12 creative-plan", False, f"status={r.status_code}")

    # C13 cinematic-presets
    r = requests.get(f"{API}/cinematic-presets", timeout=10)
    if r.status_code == 200:
        j = r.json()
        # could be list or {presets:[...]}
        presets = j if isinstance(j, list) else j.get("presets", [])
        rec("C13 cinematic-presets 6", len(presets) == 6, f"presets={len(presets)}")
    else:
        rec("C13 cinematic-presets 6", False, f"status={r.status_code}")

    # C14 preview-voice
    t0 = time.time()
    r = requests.get(f"{API}/preview-voice?voice_id=en-US-JennyNeural", timeout=20)
    dt = time.time() - t0
    if r.status_code == 200:
        ct = r.headers.get("content-type", "")
        size = len(r.content)
        rec("C14 preview-voice JennyNeural",
            "audio/mpeg" in ct and size > 10000,
            f"content-type={ct} size={size}B time={dt:.2f}s")
    else:
        rec("C14 preview-voice JennyNeural", False, f"status={r.status_code} time={dt:.2f}s")

    # C15 voices 43
    r = requests.get(f"{API}/voices", timeout=10)
    if r.status_code == 200:
        j = r.json()
        v = j.get("voices") or []
        rec("C15 voices 43", len(v) == 43, f"count={len(v)}")
    else:
        rec("C15 voices 43", False, f"status={r.status_code}")

    # C16 mode
    r = requests.get(f"{API}/mode", timeout=10)
    if r.status_code == 200:
        j = r.json()
        ok = j.get("env") == "BETA" and j.get("is_beta") is True and j.get("version") == "v1.0-beta"
        rec("C16 /mode BETA v1.0-beta", ok, f"env={j.get('env')} is_beta={j.get('is_beta')} version={j.get('version')}")
    else:
        rec("C16 /mode BETA v1.0-beta", False, f"status={r.status_code}")


# ────────────────────────────────────────────────────────────────────
# D) CLEANUP
# ────────────────────────────────────────────────────────────────────
def cleanup():
    print("\n=== D) CLEANUP — delete test waitlist rows ===")
    try:
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient

        sys.path.insert(0, "/app/backend")
        os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
        from core.config import DB_NAME

        async def _del():
            cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
            d = cli[DB_NAME]
            res = await d.waitlist.delete_many({"email": {"$in": [
                "alice@example.com", "bob@example.com", "hack@example.com"
            ]}})
            return res.deleted_count

        deleted = asyncio.run(_del())
        rec("D cleanup waitlist", True, f"deleted {deleted} rows")
    except Exception as e:
        rec("D cleanup waitlist", False, f"err: {e}")


def main():
    cleanup()  # pre-cleanup so position counts are deterministic
    test_waitlist()
    test_plan_tier()
    test_regression()
    cleanup()

    print("\n" + "=" * 60)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"RESULTS: {passed}/{total} passed")
    failed = [(n, d) for n, ok, d in results if not ok]
    if failed:
        print("\nFailures:")
        for n, d in failed:
            print(f"  - {n}: {d}")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
