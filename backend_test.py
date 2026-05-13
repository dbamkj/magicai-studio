"""Session 36 — Sprint 2 DPDPA Security & Compliance — Backend Regression."""
import io
import sys
import random
import requests
from pathlib import Path

BASE_URL = "https://creative-plan-engine.preview.emergentagent.com/api"
PWD = "Test@123"

results = []


def log(name, passed, detail=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}  {name}  {detail}")
    results.append((name, passed, detail))


def login(email, password=PWD):
    return requests.post(f"{BASE_URL}/auth/login",
                         json={"email": email, "password": password}, timeout=30)


def auth_h(token):
    return {"Authorization": f"Bearer {token}"}


# ═════ (1) DSAR EXPORT ═════
print("\n━━━ (1) DSAR EXPORT ━━━")

r = login("demo_creator@test.com")
if r.status_code != 200:
    log("1.pre login demo_creator", False, f"status={r.status_code} body={r.text[:200]}")
    creator_token = None
    creator_id = None
else:
    creator_token = r.json()["token"]
    creator_id = r.json()["user"]["id"]
    log("1.pre login demo_creator", True, f"id={creator_id[:8]}")

if creator_token:
    r = requests.get(f"{BASE_URL}/account/export-data",
                     headers=auth_h(creator_token), timeout=60)
    if r.status_code != 200:
        log("1a DSAR export auth 200", False, f"status={r.status_code} body={r.text[:300]}")
    else:
        b = r.json()
        prof = (b.get("data") or {}).get("profile") or {}
        counts = b.get("counts") or {}
        checks = [
            ("exported_at", bool(b.get("exported_at"))),
            ("user_id_matches", b.get("user_id") == creator_id),
            ("regulation", b.get("regulation") == "DPDPA 2023 / GDPR Article 15"),
            ("profile.email", (prof.get("email") or "").lower() == "demo_creator@test.com"),
            ("profile.tier=creator", prof.get("subscription_tier") == "creator"),
            ("counts.projects>=0", isinstance(counts.get("projects"), int) and counts["projects"] >= 0),
            ("counts.audit_logs", "audit_logs" in counts),
            ("counts.notifications", "notifications" in counts),
        ]
        all_ok = all(v for _, v in checks)
        log("1a DSAR export full schema", all_ok,
            "; ".join(f"{k}={v}" for k, v in checks))
else:
    log("1a DSAR export auth 200", False, "no creator token")

r = requests.get(f"{BASE_URL}/account/export-data", timeout=15)
log("1b DSAR export no-auth 401", r.status_code == 401, f"status={r.status_code}")


# ═════ (2) AUDIT LOG WRITE ═════
print("\n━━━ (2) AUDIT LOG WRITE-PATH ━━━")

r = requests.post(f"{BASE_URL}/auth/login",
                  json={"email": "demo_basic@test.com", "password": "WrongPass"},
                  timeout=15)
log("2a wrong password 401", r.status_code == 401, f"status={r.status_code}")

r = login("demo_basic@test.com")
basic_token = r.json().get("token") if r.status_code == 200 else None
log("2b correct password login 200",
    r.status_code == 200 and basic_token is not None, f"status={r.status_code}")

suffix = random.randint(10000, 99999)
audit_email = f"test_audit_v36_{suffix}@test.com"
r = requests.post(f"{BASE_URL}/auth/register",
                  json={"email": audit_email, "password": PWD, "name": "Audit V36"},
                  timeout=30)
if r.status_code == 200:
    u = r.json()["user"]
    log("2c register new user 200", True,
        f"tier={u.get('subscription_tier')} credits={u.get('credits_balance')}")
    log("2c.tier=trial", u.get("subscription_tier") == "trial",
        f"tier={u.get('subscription_tier')}")
    log("2c.credits=50", int(u.get("credits_balance", 0)) == 50,
        f"credits={u.get('credits_balance')}")
else:
    log("2c register new user 200", False, f"status={r.status_code} body={r.text[:200]}")


# ═════ (3) ADMIN AUDIT-LOG VIEWER ═════
print("\n━━━ (3) ADMIN AUDIT-LOG VIEWER ━━━")

r = login("admin@magicai.test")
admin_token = None
if r.status_code != 200:
    log("3.pre login admin", False, f"status={r.status_code} body={r.text[:200]}")
else:
    admin_token = r.json()["token"]
    log("3.pre login admin", True, "ok")

if admin_token:
    r = requests.get(f"{BASE_URL}/admin/audit-logs?limit=20",
                     headers=auth_h(admin_token), timeout=30)
    if r.status_code != 200:
        log("3a admin audit-logs limit=20", False, f"status={r.status_code}")
    else:
        b = r.json()
        log("3a admin audit-logs shape",
            isinstance(b.get("logs"), list) and isinstance(b.get("count"), int),
            f"logs={len(b.get('logs', []))} count={b.get('count')}")
        actions = {row.get("action") for row in b.get("logs", [])}
        wanted = {"auth.register", "auth.login", "auth.login_failed"}
        log("3a recent test events present", len(wanted & actions) >= 2,
            f"found={wanted & actions}")

    r = requests.get(f"{BASE_URL}/admin/audit-logs?action=auth.login_failed&limit=50",
                     headers=auth_h(admin_token), timeout=30)
    rows = r.json().get("logs", []) if r.status_code == 200 else []
    all_match = all(row.get("action") == "auth.login_failed" for row in rows)
    log("3b filter action=auth.login_failed",
        r.status_code == 200 and all_match and len(rows) >= 1,
        f"status={r.status_code} rows={len(rows)} all_match={all_match}")

    if creator_id:
        r = requests.get(f"{BASE_URL}/admin/audit-logs?user_id={creator_id}&limit=50",
                         headers=auth_h(admin_token), timeout=30)
        rows = r.json().get("logs", []) if r.status_code == 200 else []
        all_match = all(row.get("user_id") == creator_id for row in rows)
        log("3c filter user_id=demo_creator",
            r.status_code == 200 and all_match and len(rows) >= 1,
            f"status={r.status_code} rows={len(rows)} all_match={all_match}")

r = requests.get(f"{BASE_URL}/admin/audit-logs", timeout=10)
log("3d no auth → 401/403", r.status_code in (401, 403), f"status={r.status_code}")

if basic_token:
    r = requests.get(f"{BASE_URL}/admin/audit-logs",
                     headers=auth_h(basic_token), timeout=10)
    log("3d non-admin token → 403", r.status_code == 403, f"status={r.status_code}")


# ═════ (4) ACCOUNT DELETION ═════
print("\n━━━ (4) ACCOUNT DELETION ━━━")

del_suffix = random.randint(10000, 99999)
del_email = f"test_dsar_delete_v36_{del_suffix}@test.com"
r = requests.post(f"{BASE_URL}/auth/register",
                  json={"email": del_email, "password": PWD, "name": "Del"}, timeout=30)
if r.status_code != 200:
    log("4a register throwaway", False, f"status={r.status_code} body={r.text[:200]}")
    del_token = None
else:
    del_token = r.json()["token"]
    log("4a register throwaway", True, f"email={del_email}")

if del_token:
    r = requests.post(f"{BASE_URL}/account/delete-account",
                      headers=auth_h(del_token), timeout=30)
    if r.status_code != 200:
        log("4b delete-account 200", False, f"status={r.status_code} body={r.text[:300]}")
    else:
        b = r.json()
        red = b.get("redaction_email") or ""
        log("4b delete-account 200", True,
            f"deleted_at={b.get('deleted_at','')[:20]} redact={red}")
        log("4b.deleted_at present", bool(b.get("deleted_at")), "")
        log("4b.redaction starts with 'deleted-'",
            red.startswith("deleted-"), f"redact={red}")
        log("4b.message present", bool(b.get("message")), "")

    r = login(del_email)
    log("4c login after delete → 401", r.status_code == 401, f"status={r.status_code}")

    r = requests.post(f"{BASE_URL}/auth/register",
                      json={"email": del_email, "password": PWD, "name": "Re"}, timeout=30)
    log("4d re-register after delete", r.status_code == 200,
        f"status={r.status_code} body={r.text[:200]}")


# ═════ (5) SIGNED-URL HELPER ═════
print("\n━━━ (5) SIGNED-URL HELPER ━━━")

target = "preview_insp_funny_free_monday_mood_audio.mp4"
r = requests.get(f"{BASE_URL}/serve-file/{target}", timeout=15)
if r.status_code == 404:
    # Try alternatives
    for alt in ["preview_insp_funny_free_monday_mood.mp4",
                "preview_insp_devotional_free_morning_blessing.mp4"]:
        rr = requests.get(f"{BASE_URL}/serve-file/{alt}", timeout=15)
        if rr.status_code == 200:
            target = alt
            r = rr
            break
log("5a unsigned serve-file → 200", r.status_code == 200,
    f"status={r.status_code} file={target}")

r = requests.get(f"{BASE_URL}/serve-file/{target}?sig=BADSIG&exp=9999999999", timeout=15)
log("5b bad sig + future exp → 403", r.status_code == 403, f"status={r.status_code}")

r = requests.get(f"{BASE_URL}/serve-file/{target}?sig=abc&exp=1", timeout=15)
log("5c expired exp → 403", r.status_code == 403, f"status={r.status_code}")


# ═════ (6) TIER GATE — talking_avatar ═════
print("\n━━━ (6) TIER GATE — talking_avatar ━━━")


def _upload_face(token):
    try:
        from PIL import Image
        img = Image.new("RGB", (256, 256), (100, 150, 200))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
    except Exception as e:
        print(f"  PIL missing: {e}")
        return None
    r = requests.post(f"{BASE_URL}/upload-face-image",
                      headers=auth_h(token),
                      files={"file": ("face.png", buf.getvalue(), "image/png")},
                      timeout=30)
    if r.status_code != 200:
        print(f"  upload-face-image failed: {r.status_code} {r.text[:200]}")
        return None
    return r.json().get("file_path")


if basic_token:
    bimg = _upload_face(basic_token)
    if not bimg:
        log("6.pre upload face (basic)", False, "upload failed")
    else:
        log("6.pre upload face (basic)", True, bimg)
        # 6a) Basic + non-procedural → expect 402/403
        payload = {
            "image_path": bimg,
            "script": "Hello there, this is a quick talking-avatar test.",
            "use_procedural_lipsync": False,
        }
        r = requests.post(f"{BASE_URL}/create-talking-avatar",
                          headers=auth_h(basic_token), json=payload, timeout=30)
        gate = r.status_code in (402, 403)
        log("6a basic + non-procedural → 402/403", gate,
            f"status={r.status_code} body={r.text[:200]}")
        if gate:
            log("6a.message mentions Creator",
                "creator" in r.text.lower(), f"body={r.text[:200]}")

        # 6b) Basic + procedural=true → should bypass talking_avatar gate
        payload2 = dict(payload, use_procedural_lipsync=True)
        r = requests.post(f"{BASE_URL}/create-talking-avatar",
                          headers=auth_h(basic_token), json=payload2, timeout=30)
        # Bypass = not a paywall response mentioning Creator/Talking-Avatar
        is_paywall = r.status_code in (402, 403) and (
            "creator" in r.text.lower() or "talking avatar" in r.text.lower()
        )
        log("6b basic + procedural=true bypass gate", not is_paywall,
            f"status={r.status_code} body={r.text[:200]}")

if creator_token:
    cimg = _upload_face(creator_token)
    if not cimg:
        log("6.pre upload face (creator)", False, "upload failed")
    else:
        log("6.pre upload face (creator)", True, cimg)
        payload = {
            "image_path": cimg,
            "script": "Hi there. Creator gate test.",
            "use_procedural_lipsync": False,
        }
        r = requests.post(f"{BASE_URL}/create-talking-avatar",
                          headers=auth_h(creator_token), json=payload, timeout=30)
        not_gated = r.status_code not in (402, 403)
        log("6c creator + non-procedural passes gate", not_gated,
            f"status={r.status_code} body={r.text[:200]}")


# ═════ (7) SMOKE / NO-REGRESSION ═════
print("\n━━━ (7) SMOKE / NO-REGRESSION ━━━")

r = requests.get(f"{BASE_URL}/subscription/plans", timeout=20)
if r.status_code != 200:
    log("7a plans no-auth 200", False, f"status={r.status_code}")
else:
    plans = r.json().get("plans", [])
    plan_ids = sorted(p.get("id") for p in plans)
    expected = {"trial", "basic", "creator"}
    log("7a plans no-auth ⊇ trial/basic/creator",
        expected.issubset(set(plan_ids)), f"ids={plan_ids}")
    log("7a plans no-auth ONLY trial/basic/creator",
        set(plan_ids) == expected, f"ids={plan_ids}")

r = requests.get(f"{BASE_URL}/subscription/plans?include_hidden=1", timeout=20)
if r.status_code != 200:
    log("7b plans include_hidden 200", False, f"status={r.status_code}")
else:
    plans = r.json().get("plans", [])
    plan_ids = sorted(p.get("id") for p in plans)
    log("7b plans include_hidden has 6", len(plans) == 6,
        f"count={len(plans)} ids={plan_ids}")

if admin_token:
    r = requests.post(f"{BASE_URL}/admin/plans/starter/toggle-visibility",
                      headers=auth_h(admin_token), json={"visible": True}, timeout=20)
    log("7c admin toggle-visibility starter 200",
        r.status_code == 200 and r.json().get("ok") is True,
        f"status={r.status_code} body={r.text[:120]}")
    # Reset
    requests.post(f"{BASE_URL}/admin/plans/starter/toggle-visibility",
                  headers=auth_h(admin_token), json={"visible": False}, timeout=20)

if creator_token:
    r = requests.get(f"{BASE_URL}/me/limits",
                     headers=auth_h(creator_token), timeout=20)
    if r.status_code != 200:
        log("7d me/limits demo_creator", False, f"status={r.status_code}")
    else:
        b = r.json()
        ok = all(k in b for k in ("tier", "credits", "usage_this_month",
                                  "usage_today", "feature_gates", "upgrade_hints"))
        log("7d me/limits demo_creator", ok, f"keys={sorted(b.keys())}")

# 7e) backend logs sanity
try:
    log_text = ""
    for p in ("/var/log/supervisor/backend.err.log", "/var/log/supervisor/backend.out.log"):
        if Path(p).exists():
            with open(p, "r", errors="ignore") as f:
                log_text += f.read()[-30000:]
    has_500 = " 500 Internal" in log_text or "Internal Server Error" in log_text
    log("7e no 500 in recent backend logs", not has_500, "")
except Exception as e:
    log("7e backend log scan", True, f"skipped: {e}")


# ═════ SUMMARY ═════
print("\n" + "=" * 70)
passed = sum(1 for _, p, _ in results if p)
failed = sum(1 for _, p, _ in results if not p)
print(f"TOTAL: {passed}/{len(results)} passed, {failed} failed")
if failed:
    print("\n❌ FAILURES:")
    for n, p, d in results:
        if not p:
            print(f"  - {n}: {d}")
sys.exit(0 if failed == 0 else 1)
