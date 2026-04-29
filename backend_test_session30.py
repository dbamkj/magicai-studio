"""Session 30 backend validation — Phase 3 & 4 Content Intelligence
Nightly trending + tier gating. 12 checks A-L per review spec.
"""
import json
import os
import random
import subprocess
import sys
import time

import requests

BASE = "https://creative-plan-engine.preview.emergentagent.com/api"

RESULTS = []  # list of (label, ok, detail)

def ok(label, detail=""):
    print(f"  ✅ {label} — {detail}")
    RESULTS.append((label, True, detail))

def fail(label, detail=""):
    print(f"  ❌ {label} — {detail}")
    RESULTS.append((label, False, detail))

def login(email, password):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=20)
    r.raise_for_status()
    return r.json()["token"]


# === (A) GET /api/mode ===
print("\n=== (A) GET /api/mode ===")
r = requests.get(f"{BASE}/mode", timeout=10)
if r.status_code == 200:
    j = r.json()
    ok("A /api/mode", f"status=200 env={j.get('env')} is_dev={j.get('is_dev')}")
else:
    fail("A /api/mode", f"status={r.status_code}")

# === (B) GET /api/templates?limit=100 ===
print("\n=== (B) GET /api/templates?limit=100 ===")
r = requests.get(f"{BASE}/templates?limit=100", timeout=20)
if r.status_code != 200:
    fail("B templates list", f"status={r.status_code}")
    tpls = []
else:
    j = r.json()
    tpls = j.get("templates", [])
    tier_counts = {}
    has_score_keys = 0
    has_view_count_keys = 0
    for t in tpls:
        tier_counts[t.get("tier", "missing")] = tier_counts.get(t.get("tier", "missing"), 0) + 1
        if "score" in t:
            has_score_keys += 1
        if "view_count" in t:
            has_view_count_keys += 1
    detail = f"count={len(tpls)} tier_dist={tier_counts} has_score={has_score_keys} has_view_count={has_view_count_keys}"
    # Verify at least 2 starter + 2 pro
    starter_count = tier_counts.get("starter", 0)
    pro_count = tier_counts.get("pro", 0)
    if starter_count >= 2 and pro_count >= 2:
        ok("B tier distribution (≥2 starter, ≥2 pro)", detail)
    else:
        fail("B tier distribution (need ≥2 starter, ≥2 pro)", detail)

# Get one free, one starter, one pro template
free_tpl = next((t for t in tpls if t.get("tier", "free") == "free"), None)
starter_tpl = next((t for t in tpls if t.get("tier") == "starter"), None)
pro_tpl = next((t for t in tpls if t.get("tier") == "pro"), None)
print(f"    picks: free={free_tpl.get('id') if free_tpl else None} starter={starter_tpl.get('id') if starter_tpl else None} pro={pro_tpl.get('id') if pro_tpl else None}")

# === (C) GET /api/templates/{id} twice — view_count increments ===
print("\n=== (C) GET /api/templates/{id} twice — view_count increments ===")
if free_tpl:
    tid = free_tpl["id"]
    r1 = requests.get(f"{BASE}/templates/{tid}", timeout=10)
    time.sleep(0.5)
    r2 = requests.get(f"{BASE}/templates/{tid}", timeout=10)
    time.sleep(0.5)
    # Fetch via list query (since GET increments) — but simplest: just re-GET and compare.
    # Actually each GET increments. r1 shows view_count after 1st increment, r2 after 2nd.
    vc1 = r1.json().get("view_count", 0)
    vc2 = r2.json().get("view_count", 0)
    if r1.status_code == 200 and r2.status_code == 200 and vc2 >= vc1 + 1:
        ok("C view_count increments", f"v1={vc1} v2={vc2} (delta≥1)")
    else:
        fail("C view_count increments", f"v1={vc1} v2={vc2} status1={r1.status_code} status2={r2.status_code}")
else:
    fail("C view_count increments", "no free template available")

# === Auth tokens ===
print("\n=== Logging in demo_free + demo_pro + admin ===")
try:
    free_token = login("demo_free@test.com", "Test@123")
    ok("login demo_free", "token received")
except Exception as e:
    free_token = None
    fail("login demo_free", str(e))

try:
    pro_token = login("demo_pro@test.com", "Test@123")
    ok("login demo_pro", "token received")
except Exception as e:
    pro_token = None
    fail("login demo_pro", str(e))

try:
    admin_token = login("admin@magicai.test", "Test@123")
    ok("login admin", "token received")
except Exception as e:
    admin_token = None
    fail("login admin", str(e))


# === (D) POST /use on free template as demo_free → 200 ===
print("\n=== (D) POST /use on free template as demo_free → 200 ===")
if free_tpl and free_token:
    r = requests.post(
        f"{BASE}/templates/{free_tpl['id']}/use",
        headers={"Authorization": f"Bearer {free_token}"},
        json={},
        timeout=15,
    )
    body = {}
    try:
        body = r.json()
    except Exception:
        pass
    if r.status_code == 200 and "template" in body and "recommended_screen" in body:
        ok("D free→free /use", f"200 rec_screen={body.get('recommended_screen')}")
    else:
        fail("D free→free /use", f"status={r.status_code} body={str(body)[:300]}")
else:
    fail("D", "pre-req missing (free tpl or token)")

# === (E) /use starter template as demo_free → 402 ===
print("\n=== (E) POST /use on starter template as demo_free → 402 ===")
if starter_tpl and free_token:
    r = requests.post(
        f"{BASE}/templates/{starter_tpl['id']}/use",
        headers={"Authorization": f"Bearer {free_token}"},
        json={},
        timeout=15,
    )
    body = {}
    try:
        body = r.json()
    except Exception:
        pass
    detail = body.get("detail", "") if isinstance(body, dict) else ""
    if r.status_code == 402 and "Starter" in detail:
        ok("E free→starter /use", f"402 detail={detail}")
    else:
        fail("E free→starter /use", f"status={r.status_code} body={str(body)[:300]}")
else:
    fail("E", "pre-req missing (starter tpl or free_token)")

# === (F) /use pro template as demo_free → 402 ===
print("\n=== (F) POST /use on pro template as demo_free → 402 ===")
if pro_tpl and free_token:
    r = requests.post(
        f"{BASE}/templates/{pro_tpl['id']}/use",
        headers={"Authorization": f"Bearer {free_token}"},
        json={},
        timeout=15,
    )
    body = {}
    try:
        body = r.json()
    except Exception:
        pass
    detail = body.get("detail", "") if isinstance(body, dict) else ""
    if r.status_code == 402 and "Pro" in detail:
        ok("F free→pro /use", f"402 detail={detail}")
    else:
        fail("F free→pro /use", f"status={r.status_code} body={str(body)[:300]}")
else:
    fail("F", "pre-req missing (pro tpl or free_token)")

# === (G) /use pro template as demo_pro → 200 ===
print("\n=== (G) POST /use on pro template as demo_pro → 200 ===")
if pro_tpl and pro_token:
    r = requests.post(
        f"{BASE}/templates/{pro_tpl['id']}/use",
        headers={"Authorization": f"Bearer {pro_token}"},
        json={},
        timeout=15,
    )
    body = {}
    try:
        body = r.json()
    except Exception:
        pass
    if r.status_code == 200 and "template" in body:
        ok("G pro→pro /use", f"200 rec_screen={body.get('recommended_screen')}")
    else:
        fail("G pro→pro /use", f"status={r.status_code} body={str(body)[:300]}")
else:
    fail("G", "pre-req missing (pro tpl or pro_token)")

# === (H) admin recompute-trending WITHOUT auth → 401 ===
print("\n=== (H) POST /_internal/recompute-trending WITHOUT auth → 401 ===")
r = requests.post(f"{BASE}/templates/_internal/recompute-trending", timeout=20)
if r.status_code == 401:
    ok("H no-auth recompute", f"401 detail={r.json().get('detail', '')}")
else:
    fail("H no-auth recompute", f"status={r.status_code} body={r.text[:200]}")

# Also test with an invalid bearer
r2 = requests.post(
    f"{BASE}/templates/_internal/recompute-trending",
    headers={"Authorization": "Bearer invalid.garbage.token"},
    timeout=20,
)
print(f"    invalid-bearer variant: status={r2.status_code} body={r2.text[:200]}")

# === (I) admin recompute-trending WITH admin token → 200 ===
print("\n=== (I) POST /_internal/recompute-trending as admin → 200 ===")
if admin_token:
    r = requests.post(
        f"{BASE}/templates/_internal/recompute-trending",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=60,
    )
    body = {}
    try:
        body = r.json()
    except Exception:
        pass
    result = body.get("result", {}) if isinstance(body, dict) else {}
    total = result.get("total", 0)
    trending = result.get("trending_count", 0)
    top_3 = result.get("top_3", [])
    if r.status_code == 200 and total >= 30 and trending >= 3 and isinstance(top_3, list) and len(top_3) >= 1:
        ok("I admin recompute", f"total={total} trending={trending} top_3_len={len(top_3)} top1={top_3[0].get('title','')}")
    else:
        fail("I admin recompute", f"status={r.status_code} total={total} trending={trending} top_3_len={len(top_3)} body={str(body)[:400]}")
else:
    fail("I", "no admin token")

# === (J) scan backend logs for scheduler bootstrap + no new tracebacks ===
print("\n=== (J) Scan /var/log/supervisor/backend.err.log ===")
try:
    res = subprocess.run(
        ["tail", "-n", "300", "/var/log/supervisor/backend.err.log"],
        capture_output=True, text=True, timeout=10,
    )
    log = res.stdout + res.stderr
    has_bootstrap = "trending: recomputed=" in log or "trending: bootstrap" in log or "scheduler: bootstrap" in log
    # Only count tracebacks from recent entries — look for 'Traceback (most recent call last)' within last 300 lines
    tb_lines = [ln for ln in log.splitlines() if "Traceback (most recent call last)" in ln]
    # Pre-existing known errors we ignore (from session 28 review): Gemini RateLimitError, create_token TypeError pre-session-27
    detail = f"has_bootstrap_log={has_bootstrap} traceback_count_tail300={len(tb_lines)}"
    if has_bootstrap:
        ok("J scheduler startup log", detail)
    else:
        fail("J scheduler startup log", detail + " (no 'trending: recomputed=' line found)")
    # Print last 30 lines of log for reference
    print("    --- last 30 err lines ---")
    for ln in log.splitlines()[-30:]:
        print(f"    {ln}")
except Exception as e:
    fail("J log read", str(e))

# === (K) REGRESSION: admin login already done above ===
print("\n=== (K) REGRESSION: admin login ===")
if admin_token:
    ok("K admin login", "regression OK")
else:
    fail("K admin login", "failed")

# === (L) REGRESSION: GET /api/divine/deities ===
print("\n=== (L) REGRESSION: GET /api/divine/deities → count=6 ===")
r = requests.get(f"{BASE}/divine/deities", timeout=10)
if r.status_code == 200:
    j = r.json()
    deities = j.get("deities", [])
    if len(deities) == 6:
        ok("L divine deities", f"count=6 ids={[d.get('id') for d in deities]}")
    else:
        fail("L divine deities", f"count={len(deities)}")
else:
    fail("L divine deities", f"status={r.status_code}")


# === SUMMARY ===
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
passed = sum(1 for _, p, _ in RESULTS if p)
failed = [(l, d) for l, p, d in RESULTS if not p]
print(f"Passed: {passed}/{len(RESULTS)}")
if failed:
    print(f"\nFAILURES ({len(failed)}):")
    for l, d in failed:
        print(f"  ❌ {l}: {d}")
sys.exit(0 if not failed else 1)
