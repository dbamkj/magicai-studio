"""Focused re-test for Phase-3 Payments idempotency fix.

Bug: POST /api/payments/razorpay/verify previously raised KeyError 'summary' on a
2nd call (already-fulfilled order). The fix at /app/backend/routes/payments.py
should now short-circuit with {already: true} before touching summary.

This test runs the precise scenario described in the review request:
  1. Login (demo_pro)
  2. Create credit_pack order (credits_100, ₹99 = 9900 paise)
  3. Synthesize HMAC signature using local KEY_SECRET
  4. POST /api/payments/razorpay/verify  → expect 200 fulfilled w/ summary
  5. POST same payload again            → expect 200 already=true (NO 500)
  6. Confirm credits_balance unchanged  (no double credit)

Plus regressions:
  R1. GET /api/payments/credit-packs → 200
  R2. GET /api/payments/config       → 200, is_test=true
"""
from __future__ import annotations

import hmac
import hashlib
import json
import os
import sys
import time
import requests

BASE = "https://creative-plan-engine.preview.emergentagent.com"
API = f"{BASE}/api"

# Razorpay test secret (used for HMAC synthesis as the review specified)
RZP_KEY_SECRET = "c7p1XqphNlJYZL2PB5tmIM32"

EMAIL = "demo_pro@test.com"
PASSWORD = "Test@123"

results: list[tuple[str, bool, str]] = []


def step(name: str, ok: bool, msg: str = "") -> None:
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name}  {msg}")
    results.append((name, ok, msg))


def hmac_signature(order_id: str, payment_id: str, secret: str) -> str:
    body = f"{order_id}|{payment_id}".encode()
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def main() -> int:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})

    # ---- R1 ----
    r = s.get(f"{API}/payments/credit-packs", timeout=30)
    ok = r.status_code == 200 and "packs" in r.json()
    step("R1: GET /api/payments/credit-packs", ok, f"status={r.status_code}")

    # ---- R2 ----
    r = s.get(f"{API}/payments/config", timeout=30)
    cfg = r.json() if r.status_code == 200 else {}
    ok = r.status_code == 200 and cfg.get("is_test") is True
    step("R2: GET /api/payments/config (is_test=true)", ok, f"status={r.status_code} body={cfg}")

    # ---- 1. Login ----
    r = s.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    if r.status_code != 200:
        step("1: Login demo_pro", False, f"status={r.status_code} body={r.text[:200]}")
        return 1
    body = r.json()
    token = body.get("token") or body.get("access_token")
    if not token:
        step("1: Login demo_pro", False, f"no token in body keys={list(body.keys())}")
        return 1
    step("1: Login demo_pro", True, f"token len={len(token)}")
    s.headers["Authorization"] = f"Bearer {token}"

    # ---- get current credits balance ----
    r = s.get(f"{API}/auth/me", timeout=30)
    me_before = r.json().get("user", {}) if r.status_code == 200 else {}
    bal_initial = int(me_before.get("credits_balance", 0))
    user_id = me_before.get("id")
    print(f"  >> demo_pro user_id={user_id}, credits_balance BEFORE={bal_initial}")

    # ---- 2. Create credit_pack order (credits_100 = ₹99 = 9900 paise) ----
    r = s.post(
        f"{API}/payments/razorpay/create-order",
        json={"kind": "credit_pack", "item_id": "credits_100"},
        timeout=30,
    )
    if r.status_code != 200:
        step("2: Create credit_pack order (credits_100)", False, f"status={r.status_code} body={r.text[:300]}")
        return 1
    order_resp = r.json()
    order_id = order_resp.get("order_id")
    amount_paise = order_resp.get("amount_paise")
    ok = bool(order_id) and amount_paise == 9900
    step(
        "2: Create credit_pack order (credits_100, ₹99 = 9900 paise)",
        ok,
        f"order_id={order_id} amount_paise={amount_paise}",
    )
    if not ok:
        return 1

    # ---- 3. Synthesize HMAC signature ----
    fake_payment_id = "fake_pay_idem_test"
    sig = hmac_signature(order_id, fake_payment_id, RZP_KEY_SECRET)
    payload = {
        "razorpay_order_id": order_id,
        "razorpay_payment_id": fake_payment_id,
        "razorpay_signature": sig,
    }
    print(f"  >> synthesized HMAC: order={order_id} payment={fake_payment_id} sig={sig[:16]}…")

    # ---- 4. First verify call ----
    r = s.post(f"{API}/payments/razorpay/verify", json=payload, timeout=30)
    print(f"  >> first verify: status={r.status_code} body={r.text[:400]}")
    body1 = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    ok = (
        r.status_code == 200
        and body1.get("verified") is True
        and body1.get("fulfilled") is True
        and isinstance(body1.get("summary"), dict)
        and body1["summary"].get("credits_added") == 100
    )
    step(
        "4: First /razorpay/verify → 200 verified=true fulfilled=true summary.credits_added=100",
        ok,
        f"status={r.status_code} summary={body1.get('summary')}",
    )
    if not ok:
        return 1

    # Note credits_balance after step 4
    r = s.get(f"{API}/auth/me", timeout=30)
    me_after_first = r.json().get("user", {})
    bal_after_first = int(me_after_first.get("credits_balance", 0))
    print(f"  >> credits_balance AFTER FIRST verify = {bal_after_first} (delta={bal_after_first - bal_initial})")
    step(
        "4b: credits_balance increased by exactly 100 after first verify",
        bal_after_first - bal_initial == 100,
        f"before={bal_initial} after={bal_after_first}",
    )

    # ---- 5. Second verify (idempotent) ----
    r = s.post(f"{API}/payments/razorpay/verify", json=payload, timeout=30)
    print(f"  >> second verify: status={r.status_code} body={r.text[:400]}")
    body2 = {}
    try:
        body2 = r.json()
    except Exception:
        body2 = {}

    no_500 = r.status_code != 500
    step("5a: Second /razorpay/verify did NOT return 500", no_500, f"status={r.status_code}")

    is_200 = r.status_code == 200
    step("5b: Second /razorpay/verify returned 200", is_200, f"status={r.status_code}")

    has_already = body2.get("verified") is True and body2.get("fulfilled") is True and body2.get("already") is True
    step(
        "5c: Second /razorpay/verify body has verified=true fulfilled=true already=true",
        has_already,
        f"body={body2}",
    )

    no_keyerror = "KeyError" not in r.text and "summary" not in (body2.get("detail") or "") if not is_200 else True
    step("5d: Second response body did not throw KeyError 'summary'", no_keyerror, "")

    # ---- 6. credits_balance unchanged after second verify (no double-credit) ----
    r = s.get(f"{API}/auth/me", timeout=30)
    me_after_second = r.json().get("user", {})
    bal_after_second = int(me_after_second.get("credits_balance", 0))
    print(f"  >> credits_balance AFTER SECOND verify = {bal_after_second}")
    no_double = bal_after_second == bal_after_first
    step(
        "6: credits_balance unchanged from step 4 (no double-credit)",
        no_double,
        f"after_first={bal_after_first} after_second={bal_after_second}",
    )

    # ---- summary ----
    print("\n=========== SUMMARY ===========")
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, msg in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\n  {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
