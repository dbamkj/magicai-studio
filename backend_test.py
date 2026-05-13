"""Sprint 1 (Phase-1 Pricing Live) — Session 35 backend regression.

Tests pricing catalog visibility, auto-trial enrollment on signup,
existing demo logins, admin Feature Flags endpoints + plan visibility
overrides, tier-gating regression, and a smoke pass.
"""
import os
import uuid
import requests
from datetime import datetime, timezone

BASE = os.environ.get(
    "BACKEND_URL",
    "https://creative-plan-engine.preview.emergentagent.com",
).rstrip("/") + "/api"

PASS = "Test@123"

results = []  # (label, ok, detail)


def rec(label, ok, detail=""):
    results.append((label, ok, detail))
    flag = "PASS" if ok else "FAIL"
    print(f"[{flag}] {label} — {detail}")


def post(path, json_body=None, headers=None, timeout=30):
    return requests.post(BASE + path, json=json_body, headers=headers or {}, timeout=timeout)


def get(path, headers=None, params=None, timeout=30):
    return requests.get(BASE + path, headers=headers or {}, params=params, timeout=timeout)


def delete(path, headers=None, timeout=30):
    return requests.delete(BASE + path, headers=headers or {}, timeout=timeout)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ============================================================
# 1) PRICING CATALOG
# ============================================================
print("\n=== 1) PRICING CATALOG ===")

r = get("/subscription/plans")
ok = r.status_code == 200
rec("GET /api/subscription/plans status 200", ok, f"status={r.status_code}")
if ok:
    body = r.json()
    plans = body.get("plans", [])
    ids = [p["id"] for p in plans]
    rec(
        "Default plans return EXACTLY [trial, basic, creator] in that order",
        ids == ["trial", "basic", "creator"],
        f"got={ids}",
    )

    visible_flags = [p.get("is_visible_in_pricing_page") for p in plans]
    rec(
        "Each public plan has is_visible_in_pricing_page=True",
        all(v is True for v in visible_flags),
        f"flags={visible_flags}",
    )

    by_id = {p["id"]: p for p in plans}

    c = by_id.get("creator", {})
    rec("Creator plan credits=1200 (was 3000)", c.get("credits") == 1200, f"credits={c.get('credits')}")
    rec(
        "Creator plan monthly_ai_videos_limit=4 (was 3)",
        c.get("monthly_ai_videos_limit") == 4,
        f"monthly_ai_videos_limit={c.get('monthly_ai_videos_limit')}",
    )

    b = by_id.get("basic", {})
    rec("Basic credits=100", b.get("credits") == 100, f"credits={b.get('credits')}")
    rec("Basic price_inr=99", b.get("price_inr") == 99, f"price_inr={b.get('price_inr')}")
    rec("Basic watermark=True", b.get("watermark") is True, f"watermark={b.get('watermark')}")
    rec("Basic allow_face_swap=False", b.get("allow_face_swap") is False, f"allow_face_swap={b.get('allow_face_swap')}")
    rec(
        "Basic allow_talking_avatar=False",
        b.get("allow_talking_avatar") is False,
        f"allow_talking_avatar={b.get('allow_talking_avatar')}",
    )

    t = by_id.get("trial", {})
    rec("Trial credits=50", t.get("credits") == 50, f"credits={t.get('credits')}")
    rec("Trial trial_days=7", t.get("trial_days") == 7, f"trial_days={t.get('trial_days')}")
    rec("Trial watermark=True", t.get("watermark") is True, f"watermark={t.get('watermark')}")
    rec(
        "Trial auto_downgrade_to=='basic'",
        t.get("auto_downgrade_to") == "basic",
        f"auto_downgrade_to={t.get('auto_downgrade_to')}",
    )

r = get("/subscription/plans", params={"include_hidden": "1"})
ok = r.status_code == 200
rec("GET /api/subscription/plans?include_hidden=1 status 200", ok)
if ok:
    plans = r.json().get("plans", [])
    ids = sorted([p["id"] for p in plans])
    expected = sorted(["trial", "basic", "creator", "starter", "pro", "free"])
    rec(
        "include_hidden=1 returns ALL 6 plans (trial, basic, creator, starter, pro, free)",
        ids == expected,
        f"got={ids}",
    )

# ============================================================
# 2) AUTO-ENROLL INTO TRIAL
# ============================================================
print("\n=== 2) AUTO-ENROLL INTO TRIAL ===")

signup_email = f"test_signup_v35_{uuid.uuid4().hex[:8]}@test.com"
r = post("/auth/register", {"email": signup_email, "password": PASS, "name": "Sprint1 Tester"})
ok = r.status_code == 200
rec(
    f"POST /api/auth/register {signup_email} returns 200",
    ok,
    f"status={r.status_code} body={r.text[:200]}",
)

if ok:
    body = r.json()
    u = body.get("user", {})
    rec(
        "New user subscription_tier=='trial'",
        u.get("subscription_tier") == "trial",
        f"tier={u.get('subscription_tier')}",
    )
    creds = u.get("credits_balance", u.get("credits"))
    rec("New user credits=50", creds == 50, f"credits={creds}")
    rec("New user has trial_started_at", bool(u.get("trial_started_at")), f"v={u.get('trial_started_at')}")

    exp = u.get("trial_expires_at")
    rec("New user has trial_expires_at", bool(exp), f"v={exp}")
    if exp:
        try:
            exp_dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            delta_days = (exp_dt - datetime.now(timezone.utc)).total_seconds() / 86400.0
            rec(
                "trial_expires_at is ~7 days in the future (6.5..7.5)",
                6.5 <= delta_days <= 7.5,
                f"delta_days={delta_days:.3f}",
            )
        except Exception as e:
            rec("trial_expires_at parseable", False, f"err={e}")

r = post("/auth/register", {"email": signup_email, "password": PASS, "name": "again"})
rec("Re-registering same email returns 409", r.status_code == 409, f"status={r.status_code}")

# ============================================================
# 3) EXISTING CREDENTIALS REGRESSION
# ============================================================
print("\n=== 3) EXISTING CREDENTIALS REGRESSION ===")

cred_cases = [
    ("demo_creator@test.com", "creator", 1200),
    ("demo_basic@test.com", "basic", 100),
    ("demo_trial@test.com", "trial", 50),
]

tokens = {}
for email, expected_tier, expected_credits in cred_cases:
    r = post("/auth/login", {"email": email, "password": PASS})
    ok = r.status_code == 200
    rec(f"Login {email} returns 200", ok, f"status={r.status_code}")
    if ok:
        body = r.json()
        u = body.get("user", {})
        rec(
            f"{email} subscription_tier=='{expected_tier}'",
            u.get("subscription_tier") == expected_tier,
            f"tier={u.get('subscription_tier')}",
        )
        rec(
            f"{email} credits_balance={expected_credits}",
            u.get("credits_balance") == expected_credits,
            f"credits={u.get('credits_balance')}",
        )
        tokens[email] = body["token"]

for email in ("demo_free@test.com", "admin@magicai.test"):
    r = post("/auth/login", {"email": email, "password": PASS})
    rec(f"Login {email} returns 200 (legacy/admin)", r.status_code == 200, f"status={r.status_code}")
    if r.status_code == 200:
        tokens[email] = r.json()["token"]

# ============================================================
# 4) FEATURE FLAGS ADMIN
# ============================================================
print("\n=== 4) FEATURE FLAGS ADMIN ===")

admin_token = tokens.get("admin@magicai.test")
if not admin_token:
    rec("Admin token available for admin tests", False, "admin login failed — skipping section 4")
else:
    A = auth(admin_token)

    r = get("/admin/feature-flags", headers=A)
    ok = r.status_code == 200
    rec("GET /api/admin/feature-flags 200", ok, f"status={r.status_code}")
    if ok:
        b = r.json()
        rec(
            "Response has 'flags' key (list)",
            isinstance(b.get("flags"), list),
            f"type={type(b.get('flags')).__name__}",
        )
        plans_arr = b.get("plans", [])
        rec(
            "Response has 'plans' key with 6 entries",
            isinstance(plans_arr, list) and len(plans_arr) == 6,
            f"plans_count={len(plans_arr) if isinstance(plans_arr, list) else 'NA'}",
        )
        if isinstance(plans_arr, list) and plans_arr:
            sample = plans_arr[0]
            need = {"id", "label", "default_visible", "override_visible", "effective_visible"}
            missing = need - set(sample.keys())
            rec(
                "Each plans[] item has id/label/default_visible/override_visible/effective_visible",
                not missing,
                f"missing={missing} sample_keys={list(sample.keys())}",
            )

    payload = {
        "key": "test_flag_v35",
        "enabled": True,
        "description": "sprint1 test",
        "rollout_pct": 50,
    }
    r = post("/admin/feature-flags", payload, headers=A)
    body = r.json() if r.status_code == 200 else {}
    rec(
        "POST /admin/feature-flags create returns ok:true + flag",
        r.status_code == 200 and body.get("ok") is True and "flag" in body,
        f"status={r.status_code} body={r.text[:200]}",
    )

    r = get("/admin/feature-flags", headers=A)
    if r.status_code == 200:
        keys = [f.get("key") for f in r.json().get("flags", [])]
        rec(
            "GET /admin/feature-flags now lists test_flag_v35",
            "test_flag_v35" in keys,
            f"keys={keys}",
        )

    r = post("/admin/plans/starter/toggle-visibility", {"visible": True}, headers=A)
    body = r.json() if r.status_code == 200 else {}
    rec(
        "toggle-visibility starter visible=true returns ok+plan_id+visible",
        r.status_code == 200
        and body.get("ok") is True
        and body.get("plan_id") == "starter"
        and body.get("visible") is True,
        f"status={r.status_code} body={r.text[:200]}",
    )

    r = get("/subscription/plans")
    if r.status_code == 200:
        ids = [p["id"] for p in r.json().get("plans", [])]
        rec(
            "After override, public /subscription/plans INCLUDES 'starter'",
            "starter" in ids,
            f"ids={ids}",
        )

    r = post("/admin/plans/starter/toggle-visibility", {"visible": False}, headers=A)
    body = r.json() if r.status_code == 200 else {}
    rec(
        "Revert starter visible=false",
        r.status_code == 200 and body.get("visible") is False,
        f"status={r.status_code}",
    )

    r = get("/subscription/plans")
    if r.status_code == 200:
        ids = [p["id"] for p in r.json().get("plans", [])]
        rec(
            "After revert, public /subscription/plans EXCLUDES 'starter'",
            "starter" not in ids,
            f"ids={ids}",
        )

    r = post("/admin/plans/nonexistent_plan/toggle-visibility", {"visible": True}, headers=A)
    rec("toggle-visibility for nonexistent plan returns 404", r.status_code == 404, f"status={r.status_code}")

    r = delete("/admin/feature-flags/test_flag_v35", headers=A)
    body = r.json() if r.status_code == 200 else {}
    rec(
        "DELETE /admin/feature-flags/test_flag_v35 returns ok:true + deleted:1",
        r.status_code == 200 and body.get("ok") is True and body.get("deleted") == 1,
        f"status={r.status_code} body={r.text[:200]}",
    )

    creator_tok = tokens.get("demo_creator@test.com")
    if creator_tok:
        r = get("/admin/feature-flags", headers=auth(creator_tok))
        rec("Non-admin GET /admin/feature-flags returns 403", r.status_code == 403, f"status={r.status_code}")
        r = post(
            "/admin/feature-flags",
            {"key": "should_not_create", "enabled": True, "rollout_pct": 10},
            headers=auth(creator_tok),
        )
        rec("Non-admin POST /admin/feature-flags returns 403", r.status_code == 403, f"status={r.status_code}")
        r = post(
            "/admin/plans/creator/toggle-visibility",
            {"visible": False},
            headers=auth(creator_tok),
        )
        rec(
            "Non-admin POST /admin/plans/.../toggle-visibility returns 403",
            r.status_code == 403,
            f"status={r.status_code}",
        )

# ============================================================
# 5) TIER-GATING REGRESSION
# ============================================================
print("\n=== 5) TIER-GATING REGRESSION ===")

face_body = {
    "source_image_paths": ["/app/backend/uploads/nonexistent.png"],
    "target_video_path": "/app/backend/uploads/nonexistent.mp4",
    "target_type": "video",
    "video_duration": 5,
}

trial_tok = tokens.get("demo_trial@test.com")
if trial_tok:
    r = post("/create-faceswap", face_body, headers=auth(trial_tok))
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text[:200]
    rec(
        "Trial user face_swap blocked with tier-upgrade message",
        r.status_code == 402 and "face swap" in (detail or "").lower(),
        f"status={r.status_code} detail={detail}",
    )

basic_tok = tokens.get("demo_basic@test.com")
if basic_tok:
    r = post("/create-faceswap", face_body, headers=auth(basic_tok))
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text[:200]
    rec(
        "Basic user face_swap blocked with tier-upgrade message",
        r.status_code == 402 and "face swap" in (detail or "").lower(),
        f"status={r.status_code} detail={detail}",
    )

    r = get("/marketplace/templates", headers=auth(basic_tok), params={"limit": 3})
    rec("Basic user GET /marketplace/templates allowed", r.status_code == 200, f"status={r.status_code}")

creator_tok = tokens.get("demo_creator@test.com")
if creator_tok:
    r = post("/create-faceswap", face_body, headers=auth(creator_tok))
    blocked_by_gate = r.status_code == 402
    rec(
        "Creator user face_swap NOT blocked by tier gate (no 402)",
        not blocked_by_gate,
        f"status={r.status_code} body={r.text[:200]}",
    )

# ============================================================
# 6) SMOKE / OTHER
# ============================================================
print("\n=== 6) SMOKE / OTHER ===")

r = get("/marketplace/templates", params={"limit": 3})
ok = r.status_code == 200
rec("GET /api/marketplace/templates?limit=3 -> 200", ok, f"status={r.status_code}")
if ok:
    body = r.json()
    items = body if isinstance(body, list) else (body.get("templates") or body.get("items") or [])
    rec(
        "Marketplace templates returned a non-empty list",
        isinstance(items, list) and len(items) > 0,
        f"len={len(items) if isinstance(items, list) else 'NA'}",
    )

for email in ("demo_trial@test.com", "demo_basic@test.com", "demo_creator@test.com"):
    tok = tokens.get(email)
    if not tok:
        rec(f"GET /api/me/limits with {email} — skipped (no token)", False)
        continue
    r = get("/me/limits", headers=auth(tok))
    rec(f"GET /api/me/limits with {email} returns 200", r.status_code == 200, f"status={r.status_code}")

sched_ok = False
try:
    import subprocess
    txt = subprocess.run(
        ["bash", "-lc", "tail -n 400 /var/log/supervisor/backend.*.log 2>/dev/null"],
        capture_output=True, text=True, timeout=10,
    ).stdout
    sched_ok = "started 6h trial-expiry loop" in txt
except Exception:
    sched_ok = False
rec(
    "Backend log shows 'scheduler: started 6h trial-expiry loop' on startup",
    sched_ok,
    "found in /var/log/supervisor/backend.*.log" if sched_ok else "NOT FOUND",
)

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed
print(f"RESULTS: {passed}/{total} passed, {failed} failed")
print("=" * 60)
if failed:
    print("\nFAILED CASES:")
    for label, ok, detail in results:
        if not ok:
            print(f"  - {label}\n      {detail}")
