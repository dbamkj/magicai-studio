#!/usr/bin/env python3
"""
Session 37 — Sprint 3 (Content Moderation v2) Backend Regression
Tests:
  1) Moderation persistence
  2) Strike + auto-ban (severity-weighted, threshold 3)
  3) Admin override
  4) Manual ban/unban
  5) Negative tests (403 for non-admin)
  6) No regression (smoke)
"""
import json
import sys
import time
import uuid
import requests

BASE = "https://creative-plan-engine.preview.emergentagent.com/api"
TIMEOUT = 30

ADMIN = ("admin@magicai.test", "Test@123")
NONADMIN = ("demo_basic@test.com", "Test@123")

PASS = []
FAIL = []


def _log(ok, label, detail=""):
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {label}  {detail}")
    (PASS if ok else FAIL).append((label, detail))


def _post(path, json_body=None, headers=None, timeout=TIMEOUT):
    return requests.post(BASE + path, json=json_body, headers=headers or {}, timeout=timeout)


def _get(path, headers=None, params=None, timeout=TIMEOUT):
    return requests.get(BASE + path, headers=headers or {}, params=params or {}, timeout=timeout)


def login(email, password):
    r = _post("/auth/login", {"email": email, "password": password})
    if r.status_code != 200:
        raise RuntimeError(f"login failed for {email}: {r.status_code} {r.text[:200]}")
    j = r.json()
    return j["token"], j["user"]


def register(email, password):
    r = _post("/auth/register", {"email": email, "password": password, "name": "Mod Test"})
    return r


def bearer(tok):
    return {"Authorization": f"Bearer {tok}"}


# ────────────────────────────────────────────────────────────────────
# 0) Setup admin + non-admin + FRESH test user
# ────────────────────────────────────────────────────────────────────
print("\n=== 0. SETUP ===")
admin_tok, admin_u = login(*ADMIN)
_log(admin_u.get("is_admin") is True, "admin login + is_admin=true", f"id={admin_u.get('id')}")

nonadmin_tok, nonadmin_u = login(*NONADMIN)
_log(True, "non-admin login (demo_basic)", f"tier={nonadmin_u.get('subscription_tier')}")

# Fresh user — unique to avoid colliding with previous runs
fresh_email = f"test_mod_review_v37_{uuid.uuid4().hex[:8]}@test.com"
r = register(fresh_email, "Test@123")
if r.status_code != 200:
    _log(False, "fresh user register", f"{r.status_code} {r.text[:200]}")
    sys.exit(1)
fresh = r.json()
fresh_tok = fresh["token"]
fresh_uid = fresh["user"]["id"]
_log(True, "fresh user registered", f"email={fresh_email} uid={fresh_uid}")


# ────────────────────────────────────────────────────────────────────
# 1) MODERATION PERSISTENCE
# ────────────────────────────────────────────────────────────────────
print("\n=== 1. MODERATION PERSISTENCE ===")
r = _post("/wizard/prompts", {"idea": "this fucking sucks"}, headers=bearer(fresh_tok))
ok = r.status_code == 400
detail = {}
try:
    detail = r.json().get("detail", {})
except Exception:
    pass
_log(ok and detail.get("moderation_blocked") is True and "profanity" in (detail.get("categories") or []),
     "1a wizard/prompts 'this fucking sucks' → 400 moderation_blocked profanity",
     f"status={r.status_code} detail={json.dumps(detail)[:200]}")

# Admin list records
r = _get("/admin/moderation/records", headers=bearer(admin_tok), params={"limit": 10})
records_status = r.status_code
records_data = r.json() if r.ok else {}
recs = records_data.get("records", [])
# Find the most recent record for our user
user_recs = [x for x in recs if x.get("user_id") == fresh_uid]
top = user_recs[0] if user_recs else None
match = (top and top.get("source") == "wizard.idea" and int(top.get("severity") or 0) == 1
         and top.get("status") == "blocked")
_log(records_status == 200 and match,
     "1b admin/moderation/records — most recent for fresh user matches",
     f"status={records_status} top={json.dumps(top)[:280] if top else None}")


# ────────────────────────────────────────────────────────────────────
# 2) STRIKE + AUTO-BAN
# ────────────────────────────────────────────────────────────────────
print("\n=== 2. STRIKE + AUTO-BAN ===")
# We already did one strike above (sev 1, score 1). Now do the next 2.
# Actually the review says 3 in sequence with the specific phrases. Let's do
# all three from scratch on a different fresh user to match the script exactly.

fresh2_email = f"test_mod_review_v37_{uuid.uuid4().hex[:8]}@test.com"
r = register(fresh2_email, "Test@123")
fresh2 = r.json()
fresh2_tok = fresh2["token"]
fresh2_uid = fresh2["user"]["id"]
_log(True, "fresh2 user registered", f"email={fresh2_email} uid={fresh2_uid}")

phrases = [
    ("this fucking sucks", 1, "sev1 profanity"),
    ("another bhencho moment", 1, "sev1 hindi-roman profanity"),
    ("deepfake of modi saying fake quote", 3, "sev3 real-person deepfake"),
]
for idea, exp_sev, lbl in phrases:
    r = _post("/wizard/prompts", {"idea": idea}, headers=bearer(fresh2_tok))
    try:
        d = r.json().get("detail", {})
    except Exception:
        d = {}
    _log(r.status_code == 400 and d.get("moderation_blocked") is True,
         f"2.strike: '{idea[:30]}…' → 400 moderation_blocked ({lbl})",
         f"status={r.status_code} cats={d.get('categories')}")

# Check users-strikes via admin
r = _get("/admin/moderation/users-strikes", headers=bearer(admin_tok), params={"min_score": 0})
us = r.json() if r.ok else {}
mine = next((u for u in (us.get("users") or []) if u.get("id") == fresh2_uid), None)
_log(r.status_code == 200 and mine is not None
     and int(mine.get("strike_count") or 0) == 3
     and int(mine.get("strike_score") or 0) == 5
     and mine.get("is_banned") is True,
     "2b users-strikes: fresh2 has strike_count=3 strike_score=5 is_banned=true",
     f"got={json.dumps({k: mine.get(k) for k in ('strike_count','strike_score','is_banned')}) if mine else None}")

# Banned user → /me/limits → 403
r = _get("/me/limits", headers=bearer(fresh2_tok))
det = {}
try:
    det = r.json().get("detail", {})
except Exception:
    pass
reason = (det.get("reason") or "") if isinstance(det, dict) else ""
_log(r.status_code == 403 and (isinstance(det, dict) and det.get("banned") is True) and ("strike score" in reason.lower()),
     "2c banned fresh2 token → GET /me/limits → 403 banned, reason mentions 'strike score'",
     f"status={r.status_code} detail={json.dumps(det)[:240]}")


# ────────────────────────────────────────────────────────────────────
# 3) ADMIN OVERRIDE
# ────────────────────────────────────────────────────────────────────
print("\n=== 3. ADMIN OVERRIDE ===")
# Get records for fresh2 user, find FIRST (most chronologically earliest)
r = _get("/admin/moderation/records", headers=bearer(admin_tok), params={"user_id": fresh2_uid, "limit": 100})
recs2 = (r.json() or {}).get("records") or []
# records are sorted by created_at desc; FIRST chronologically = last in list
first_rec = recs2[-1] if recs2 else None
first_rec_id = first_rec.get("id") if first_rec else None
_log(first_rec_id is not None,
     f"3.setup: located first moderation record for fresh2 user (records returned={len(recs2)})",
     f"first_rec_id={first_rec_id}")

# Override = overridden_allow
r = _post(f"/admin/moderation/records/{first_rec_id}/override",
          {"decision": "overridden_allow", "admin_note": "false positive on profanity"},
          headers=bearer(admin_tok))
body = r.json() if r.ok else {}
_log(r.status_code == 200 and body.get("ok") is True and body.get("status") == "overridden_allow",
     "3a override → 200 ok:true status='overridden_allow'",
     f"status={r.status_code} body={json.dumps(body)[:200]}")

# Re-check users-strikes — strike_count should drop 3 → 2
r = _get("/admin/moderation/users-strikes", headers=bearer(admin_tok), params={"min_score": 0})
us2 = r.json() if r.ok else {}
mine2 = next((u for u in (us2.get("users") or []) if u.get("id") == fresh2_uid), None)
_log(mine2 is not None and int(mine2.get("strike_count") or 0) == 2,
     "3b users-strikes: fresh2 strike_count 3 → 2 after override",
     f"got_strike_count={mine2.get('strike_count') if mine2 else None} got_strike_score={mine2.get('strike_score') if mine2 else None}")

# Invalid decision → 400
r = _post(f"/admin/moderation/records/{first_rec_id}/override",
          {"decision": "invalid_decision"}, headers=bearer(admin_tok))
_log(r.status_code == 400,
     "3c invalid decision → 400",
     f"status={r.status_code} body={r.text[:200]}")

# Unknown record → 404
r = _post("/admin/moderation/records/00000000-deadbeef/override",
          {"decision": "overridden_allow"}, headers=bearer(admin_tok))
_log(r.status_code == 404,
     "3d unknown record id → 404",
     f"status={r.status_code} body={r.text[:200]}")


# ────────────────────────────────────────────────────────────────────
# 4) MANUAL BAN/UNBAN
# ────────────────────────────────────────────────────────────────────
print("\n=== 4. MANUAL BAN/UNBAN ===")
# 4a Unban first (user was auto-banned in step 2)
r = _post(f"/admin/users/{fresh2_uid}/unban", {}, headers=bearer(admin_tok))
body = r.json() if r.ok else {}
_log(r.status_code == 200 and body.get("ok") is True and bool(body.get("unbanned_at")),
     "4a admin/users/{id}/unban → ok:true, unbanned_at present",
     f"status={r.status_code} body={json.dumps(body)[:200]}")

# Verify strike_score reset to 0
r = _get("/admin/users", headers=bearer(admin_tok), params={"limit": 500})
users_all = (r.json() or {}).get("users") or []
me = next((u for u in users_all if u.get("id") == fresh2_uid), None)
_log(me is not None and int(me.get("strike_score") or 0) == 0,
     "4a.1 after unban: strike_score reset to 0",
     f"strike_score={me.get('strike_score') if me else None} is_banned={me.get('is_banned') if me else None}")

# 4b /me/limits 200 with user token
r = _get("/me/limits", headers=bearer(fresh2_tok))
_log(r.status_code == 200, "4b user regained access /me/limits → 200",
     f"status={r.status_code} body={r.text[:160]}")

# 4c Manual ban
r = _post(f"/admin/users/{fresh2_uid}/ban", {"reason": "manual ban test"}, headers=bearer(admin_tok))
body = r.json() if r.ok else {}
_log(r.status_code == 200 and body.get("ok") is True, "4c admin manual ban → ok:true",
     f"status={r.status_code} body={json.dumps(body)[:200]}")

# 4d /me/limits → 403 banned
r = _get("/me/limits", headers=bearer(fresh2_tok))
det = {}
try:
    det = r.json().get("detail", {})
except Exception:
    pass
_log(r.status_code == 403 and isinstance(det, dict) and det.get("banned") is True,
     "4d banned user /me/limits → 403 banned:true",
     f"status={r.status_code} detail={json.dumps(det)[:200]}")

# 4e Try to ban an admin → 400
r = _post(f"/admin/users/{admin_u['id']}/ban", {"reason": "x"}, headers=bearer(admin_tok))
err_msg = ""
try:
    err_msg = (r.json() or {}).get("detail", "")
except Exception:
    err_msg = r.text
_log(r.status_code == 400 and "cannot ban an admin" in (str(err_msg).lower()),
     "4e banning an admin → 400 'cannot ban an admin'",
     f"status={r.status_code} detail={err_msg}")

# Cleanup: final unban
r = _post(f"/admin/users/{fresh2_uid}/unban", {}, headers=bearer(admin_tok))
_log(r.status_code == 200, "4f cleanup unban", f"status={r.status_code}")


# ────────────────────────────────────────────────────────────────────
# 5) NEGATIVE TESTS (non-admin auth)
# ────────────────────────────────────────────────────────────────────
print("\n=== 5. NEGATIVE TESTS (403 expected) ===")
r = _get("/admin/moderation/records", headers=bearer(nonadmin_tok))
_log(r.status_code == 403, "5a non-admin GET /admin/moderation/records → 403",
     f"status={r.status_code} body={r.text[:160]}")

# Need a valid record_id for the override 403 check
some_record_id = first_rec_id or "00000000-deadbeef"
r = _post(f"/admin/moderation/records/{some_record_id}/override",
          {"decision": "overridden_allow"}, headers=bearer(nonadmin_tok))
_log(r.status_code == 403, "5b non-admin POST override → 403",
     f"status={r.status_code} body={r.text[:160]}")

r = _post(f"/admin/users/{fresh2_uid}/ban", {"reason": "x"}, headers=bearer(nonadmin_tok))
_log(r.status_code == 403, "5c non-admin POST /admin/users/{id}/ban → 403",
     f"status={r.status_code} body={r.text[:160]}")


# ────────────────────────────────────────────────────────────────────
# 6) NO REGRESSION (smoke)
# ────────────────────────────────────────────────────────────────────
print("\n=== 6. NO REGRESSION (smoke) ===")
# /api/subscription/plans (no auth) — trial/basic/creator
r = _get("/subscription/plans")
plans = r.json() if r.ok else {}
plan_ids = set()
if isinstance(plans, dict) and isinstance(plans.get("plans"), list):
    plan_ids = {p.get("id") for p in plans["plans"]}
elif isinstance(plans, list):
    plan_ids = {p.get("id") for p in plans}
required_plans = {"trial", "basic", "creator"}
_log(r.status_code == 200 and required_plans.issubset(plan_ids),
     "6a /subscription/plans returns trial/basic/creator",
     f"status={r.status_code} got_plans={sorted(plan_ids)}")

# /api/account/export-data with creator token
try:
    creator_tok, _ = login("demo_creator@test.com", "Test@123")
    r = _get("/account/export-data", headers=bearer(creator_tok))
    _log(r.status_code == 200, "6b /account/export-data (creator) → 200",
         f"status={r.status_code} body_len={len(r.text)}")
except Exception as e:
    _log(False, "6b /account/export-data (creator)", f"err={e}")

# /api/admin/feature-flags
r = _get("/admin/feature-flags", headers=bearer(admin_tok))
_log(r.status_code == 200, "6c /admin/feature-flags (admin) → 200",
     f"status={r.status_code} body={r.text[:160]}")

# /api/admin/audit-logs?limit=10 — should contain moderation events
r = _get("/admin/audit-logs", headers=bearer(admin_tok), params={"limit": 200})
logs = (r.json() or {}).get("logs") or (r.json() or {}).get("items") or []
events = {e.get("action") or e.get("event") for e in logs}
has_strike = any(("moderation.strike" in (e or "")) for e in events)
has_banned = any(("moderation.banned" in (e or "")) for e in events)
has_override = any(("moderation.overridden_allow" in (e or "")) for e in events)
_log(r.status_code == 200,
     "6d /admin/audit-logs → 200",
     f"status={r.status_code} log_count={len(logs)} strike={has_strike} banned={has_banned} override={has_override}")
_log(has_strike and has_banned and has_override,
     "6d.1 audit logs contain moderation.strike + moderation.banned + moderation.overridden_allow",
     f"strike={has_strike} banned={has_banned} override={has_override}")


# ────────────────────────────────────────────────────────────────────
# SUMMARY
# ────────────────────────────────────────────────────────────────────
print("\n=== SUMMARY ===")
print(f"PASS: {len(PASS)}")
print(f"FAIL: {len(FAIL)}")
if FAIL:
    print("\nFailures:")
    for lbl, det in FAIL:
        print(f"  ❌ {lbl}  {det}")
sys.exit(0 if not FAIL else 1)
