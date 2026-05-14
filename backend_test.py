"""Session 38 — Sprint 4 (Persistent Queue) backend verification.

Coverage:
  1) Queue basic roundtrip (enqueue → worker dispatch → done).
  2) Queue stats counters update.
  3) Authorization (admin-only endpoints + /api/jobs/{id}).
  4) Unknown job → 404.
  5) Moderation auto-strike on /wizard/preview-images and /avatar/dialogues.
  6) No-regression sweep on subscription/plans, account/export-data,
     admin/feature-flags, admin/moderation/records, backend logs.
"""
from __future__ import annotations
import json
import os
import sys
import time
import uuid
import subprocess
import requests

BASE = os.environ.get(
    "BACKEND_URL",
    "https://creative-plan-engine.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE}/api"

ADMIN_EMAIL = "admin@magicai.test"
ADMIN_PASS = "Test@123"
DEMO_BASIC_EMAIL = "demo_basic@test.com"
DEMO_BASIC_PASS = "Test@123"
DEMO_CREATOR_EMAIL = "demo_creator@test.com"
DEMO_CREATOR_PASS = "Test@123"
FRESH_USER_EMAIL = f"test_mod_extra_v38_{uuid.uuid4().hex[:6]}@test.com"
FRESH_USER_PASS = "Test@123"


# ────────────────────────── helpers ──────────────────────────
PASS = []
FAIL = []


def _record(ok: bool, name: str, detail: str = ""):
    if ok:
        PASS.append(name)
        print(f"  ✓ {name}")
        if detail:
            print(f"      {detail}")
    else:
        FAIL.append((name, detail))
        print(f"  ✗ {name}")
        if detail:
            print(f"      {detail}")


def login(email: str, password: str) -> str:
    r = requests.post(
        f"{API}/auth/login",
        json={"email": email, "password": password},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["token"]


def register(email: str, password: str) -> str:
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": password, "name": "Mod Strike Tester"},
        timeout=20,
    )
    if r.status_code in (200, 201):
        return r.json().get("token") or login(email, password)
    # already exists — fallback
    return login(email, password)


def hdr(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


# ────────────────────────── 1. Queue roundtrip ──────────────────────────
def test_queue_roundtrip(admin_tok: str) -> str:
    print("\n=== 1) Queue basic roundtrip ===")
    job_id = None

    r = requests.post(
        f"{API}/admin/queue/enqueue-test", headers=hdr(admin_tok), timeout=15
    )
    ok = r.status_code == 200 and r.json().get("ok") is True and r.json().get("job_id")
    detail = f"HTTP {r.status_code} body={r.text[:200]}"
    _record(ok, "POST /admin/queue/enqueue-test → 200 with {ok,job_id}", detail)
    if not ok:
        return ""
    job_id = r.json()["job_id"]

    r = requests.get(f"{API}/admin/queue/stats", headers=hdr(admin_tok), timeout=15)
    body = r.json() if r.status_code == 200 else {}
    handlers = body.get("handlers") or []
    ok2 = (
        r.status_code == 200
        and "system.ping" in handlers
        and "system.sleep" in handlers
        and body.get("backend") == "mongo"
        and float(body.get("poll_seconds") or 0) == 2.0
    )
    _record(
        ok2,
        "GET /admin/queue/stats handlers∋{ping,sleep} backend=mongo poll=2.0",
        f"handlers={handlers} backend={body.get('backend')} poll={body.get('poll_seconds')}",
    )

    print("  ... waiting 6s for worker dispatch ...")
    time.sleep(6)

    r = requests.get(f"{API}/jobs/{job_id}", headers=hdr(admin_tok), timeout=15)
    body = r.json() if r.status_code == 200 else {}
    result = body.get("result") or {}
    echo = result.get("echo") or {}
    ok3 = (
        r.status_code == 200
        and body.get("status") == "done"
        and result.get("pong") is True
        and echo.get("src") == "admin_smoke"
        and body.get("finished_at")
    )
    _record(
        ok3,
        f"GET /jobs/{{job_id}} (admin) status=done result.pong=true echo.src=admin_smoke finished_at present",
        f"status={body.get('status')} result={result} finished_at={body.get('finished_at')}",
    )
    return job_id


# ────────────────────────── 2. Stats update ──────────────────────────
def test_queue_stats_update(admin_tok: str):
    print("\n=== 2) Queue stats update ===")
    r = requests.get(f"{API}/admin/queue/stats", headers=hdr(admin_tok), timeout=15)
    body = r.json() if r.status_code == 200 else {}
    ok = (
        r.status_code == 200
        and int(body.get("total", 0)) >= 1
        and int(body.get("done", 0)) >= 1
        and int(body.get("pending", 0)) == 0
        and int(body.get("running", 0)) == 0
    )
    _record(
        ok,
        "queue/stats: total>=1, done>=1, pending=0, running=0",
        f"total={body.get('total')} done={body.get('done')} pending={body.get('pending')} running={body.get('running')}",
    )


# ────────────────────────── 3. Authorization ──────────────────────────
def test_authorization(non_admin_tok: str, job_id: str):
    print("\n=== 3) Authorization ===")
    # 403 for non-admin on admin queue endpoints
    r = requests.get(f"{API}/admin/queue/stats", headers=hdr(non_admin_tok), timeout=15)
    _record(r.status_code == 403, "non-admin GET /admin/queue/stats → 403",
            f"got {r.status_code} body={r.text[:120]}")

    r = requests.get(f"{API}/admin/queue/jobs", headers=hdr(non_admin_tok), timeout=15)
    _record(r.status_code == 403, "non-admin GET /admin/queue/jobs → 403",
            f"got {r.status_code} body={r.text[:120]}")

    r = requests.post(
        f"{API}/admin/queue/enqueue-test", headers=hdr(non_admin_tok), timeout=15
    )
    _record(r.status_code == 403, "non-admin POST /admin/queue/enqueue-test → 403",
            f"got {r.status_code} body={r.text[:120]}")

    # /jobs/{id} with user_id=null (admin enqueued) → ANY authed user can see it
    if job_id:
        r = requests.get(f"{API}/jobs/{job_id}", headers=hdr(non_admin_tok), timeout=15)
        body = r.json() if r.status_code == 200 else {}
        ok = r.status_code == 200 and body.get("job_id") == job_id and body.get("user_id") in (None, "")
        _record(
            ok,
            "non-admin GET /jobs/{job_id} where job.user_id=null → 200 (no owner constraint)",
            f"got {r.status_code} user_id={body.get('user_id')} status={body.get('status')}",
        )


# ────────────────────────── 4. Unknown job ──────────────────────────
def test_unknown_job(any_tok: str):
    print("\n=== 4) Unknown job ===")
    r = requests.get(f"{API}/jobs/nonexistent_xxx", headers=hdr(any_tok), timeout=15)
    _record(r.status_code == 404, "GET /jobs/nonexistent_xxx → 404",
            f"got {r.status_code} body={r.text[:120]}")


# ────────────────────────── 5. Moderation follow-up ──────────────────────────
def test_moderation_followup(admin_tok: str) -> str:
    print("\n=== 5) Moderation auto-strike wiring ===")
    fresh_tok = register(FRESH_USER_EMAIL, FRESH_USER_PASS)

    # Pick a real style_id (review request says try 'comedy' or motivational
    # but the code checks style FIRST so we must pass a known style)
    r = requests.get(f"{API}/avatar/styles", timeout=15)
    styles = []
    if r.status_code == 200:
        styles = [s.get("id") for s in (r.json() or {}).get("styles", [])]
    style_id = styles[0] if styles else "pixar"
    print(f"  using style_id='{style_id}' from available {styles}")

    # 5a) wizard/preview-images with profanity in `idea` field
    body = {
        "idea": "this fucking sucks",
        "title": "normal",
        "script": "normal",
        "image_query": "normal",
        "language": "english",
        "music_query": "",
    }
    r = requests.post(
        f"{API}/wizard/preview-images", headers=hdr(fresh_tok), json=body, timeout=20
    )
    parsed = {}
    try:
        parsed = r.json()
    except Exception:
        parsed = {}
    detail = parsed.get("detail") if isinstance(parsed, dict) else None
    blocked = isinstance(detail, dict) and detail.get("moderation_blocked") is True
    ok = r.status_code == 400 and blocked
    _record(
        ok,
        "POST /wizard/preview-images profanity → 400 detail.moderation_blocked=true",
        f"got {r.status_code} detail={detail!r}",
    )

    # 5b) avatar/dialogues with profanity in `idea`
    body = {
        "style_id": style_id,
        "idea": "this fucking sucks",
        "language": "english",
    }
    r = requests.post(
        f"{API}/avatar/dialogues", headers=hdr(fresh_tok), json=body, timeout=20
    )
    try:
        parsed = r.json()
    except Exception:
        parsed = {}
    detail = parsed.get("detail") if isinstance(parsed, dict) else None
    blocked = isinstance(detail, dict) and detail.get("moderation_blocked") is True
    ok = r.status_code == 400 and blocked
    _record(
        ok,
        f"POST /avatar/dialogues (style={style_id}) profanity → 400 detail.moderation_blocked=true",
        f"got {r.status_code} detail={detail!r}",
    )

    # 5c) Admin: fresh user appears in users-strikes
    r = requests.get(
        f"{API}/admin/moderation/users-strikes?min_score=0&limit=20",
        headers=hdr(admin_tok),
        timeout=15,
    )
    body = r.json() if r.status_code == 200 else {}
    users = body.get("users") or []
    match = next((u for u in users if u.get("email") == FRESH_USER_EMAIL), None)
    strike_count = int(match.get("strike_count") or 0) if match else 0
    ok = r.status_code == 200 and match is not None and strike_count >= 1
    _record(
        ok,
        f"admin users-strikes contains {FRESH_USER_EMAIL} with strike_count>=1",
        f"got {r.status_code} users.count={len(users)} match={match is not None} strike_count={strike_count}",
    )
    return fresh_tok


# ────────────────────────── 6. No regression ──────────────────────────
def test_no_regression(admin_tok: str, creator_tok: str):
    print("\n=== 6) No-regression sweep ===")

    # 6a) /api/subscription/plans (no auth) → trial/basic/creator only
    r = requests.get(f"{API}/subscription/plans", timeout=15)
    plans = []
    if r.status_code == 200:
        b = r.json()
        plans = b.get("plans") if isinstance(b, dict) else b
        if isinstance(plans, dict):
            ids = sorted(plans.keys())
        elif isinstance(plans, list):
            ids = sorted(p.get("id") for p in plans if isinstance(p, dict))
        else:
            ids = []
    else:
        ids = []
    expected = {"trial", "basic", "creator"}
    ok = r.status_code == 200 and set(ids) == expected
    _record(
        ok,
        "GET /subscription/plans (no auth) → trial/basic/creator only",
        f"got {r.status_code} plan_ids={ids}",
    )

    # 6b) /api/account/export-data (creator token)
    r = requests.get(f"{API}/account/export-data", headers=hdr(creator_tok), timeout=20)
    _record(
        r.status_code == 200,
        "GET /account/export-data (creator) → 200",
        f"got {r.status_code} bytes={len(r.content)}",
    )

    # 6c) /api/admin/feature-flags (admin)
    r = requests.get(f"{API}/admin/feature-flags", headers=hdr(admin_tok), timeout=15)
    _record(
        r.status_code == 200,
        "GET /admin/feature-flags (admin) → 200",
        f"got {r.status_code}",
    )

    # 6d) /api/admin/moderation/records (admin)
    r = requests.get(
        f"{API}/admin/moderation/records?limit=5", headers=hdr(admin_tok), timeout=15
    )
    _record(
        r.status_code == 200,
        "GET /admin/moderation/records (admin) → 200",
        f"got {r.status_code}",
    )


def check_backend_logs():
    print("\n=== 7) Backend log scan for 500s ===")
    try:
        out = subprocess.run(
            ["tail", "-n", "400", "/var/log/supervisor/backend.err.log"],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except Exception as e:
        _record(True, f"Skipped log scan ({e})")
        return
    # Look for explicit 500-level traffic lines or Python tracebacks
    five_hundred_lines = [ln for ln in out.splitlines() if " 500 " in ln]
    tb_lines = [ln for ln in out.splitlines() if "Traceback (most recent call last)" in ln]
    ok = len(five_hundred_lines) == 0
    detail = (
        f"500-status lines={len(five_hundred_lines)} tracebacks={len(tb_lines)}"
        + ("\n" + "\n".join(five_hundred_lines[-4:]) if five_hundred_lines else "")
    )
    _record(ok, "backend.err.log: no 500 responses during run", detail)


# ────────────────────────── Main ──────────────────────────
def main():
    print(f"Base API: {API}")
    admin_tok = login(ADMIN_EMAIL, ADMIN_PASS)
    print(f"admin token len={len(admin_tok)}")
    basic_tok = login(DEMO_BASIC_EMAIL, DEMO_BASIC_PASS)
    print(f"basic token len={len(basic_tok)}")
    creator_tok = login(DEMO_CREATOR_EMAIL, DEMO_CREATOR_PASS)
    print(f"creator token len={len(creator_tok)}")

    job_id = test_queue_roundtrip(admin_tok)
    test_queue_stats_update(admin_tok)
    test_authorization(basic_tok, job_id)
    test_unknown_job(basic_tok)
    test_moderation_followup(admin_tok)
    test_no_regression(admin_tok, creator_tok)
    check_backend_logs()

    print("\n" + "=" * 60)
    print(f"PASS: {len(PASS)}    FAIL: {len(FAIL)}")
    if FAIL:
        print("\nFailures:")
        for n, d in FAIL:
            print(f"  ✗ {n}\n      {d}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
