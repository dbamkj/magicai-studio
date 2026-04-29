"""Session 24 backend tests — Admin ENV switcher + monetization regression.
Uses the external BETA backend URL per review spec.
"""
import os, sys, json, requests, time

BASE = "https://creative-plan-engine.preview.emergentagent.com/api"

ADMIN = ("admin@magicai.test", "Test@123")
FREE = ("demo_free@test.com", "Test@123")
PRO = ("demo_pro@test.com", "Test@123")

results = []  # (name, passed, detail)

def rec(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name} — {detail}")


def login(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=30)
    r.raise_for_status()
    d = r.json()
    return d.get("token"), d.get("user", {})


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


def main():
    # ========= (A) Core Auth Regression =========
    print("\n=== (A) Core Auth Regression ===")
    r = requests.get(f"{BASE}/mode", timeout=20)
    j = r.json() if r.ok else {}
    rec("A1 GET /mode 200 env=BETA", r.status_code == 200 and j.get("env") == "BETA", f"status={r.status_code} env={j.get('env')}")

    admin_tok, admin_user = None, {}
    try:
        r = requests.post(f"{BASE}/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]}, timeout=30)
        ok = r.status_code == 200
        j = r.json() if ok else {}
        admin_tok = j.get("token")
        admin_user = j.get("user", {})
        rec("A2 POST /auth/login admin", ok and admin_tok and admin_user.get("is_admin") is True,
            f"status={r.status_code} is_admin={admin_user.get('is_admin')} tier={admin_user.get('subscription_tier')}")
    except Exception as e:
        rec("A2 POST /auth/login admin", False, str(e))

    r = requests.get(f"{BASE}/auth/me", headers=H(admin_tok), timeout=20)
    j = r.json() if r.ok else {}
    user_obj = j.get("user", {}) if isinstance(j.get("user"), dict) else {}
    rec("A3 GET /auth/me admin", r.status_code == 200 and user_obj.get("is_admin") is True,
        f"status={r.status_code} keys={list(j.keys())[:5]}")

    # Login demos for later
    pro_tok, _ = login(*PRO)
    free_tok, _ = login(*FREE)

    # ========= (B) Admin ENV Info =========
    print("\n=== (B) Admin ENV Info ===")
    r = requests.get(f"{BASE}/admin/env", headers=H(admin_tok), timeout=20)
    j = r.json() if r.ok else {}
    rec("B1 GET /admin/env admin", r.status_code == 200 and j.get("env") == "BETA" and j.get("is_beta") is True,
        f"status={r.status_code} body={j}")

    r = requests.get(f"{BASE}/admin/env", timeout=20)
    rec("B2 GET /admin/env no auth → 401", r.status_code == 401, f"status={r.status_code} body={r.text[:120]}")

    r = requests.get(f"{BASE}/admin/env", headers=H(pro_tok), timeout=20)
    rec("B3 GET /admin/env non-admin (pro) → 403", r.status_code == 403, f"status={r.status_code} body={r.text[:120]}")

    # ========= (C) Admin ENV Switch no-op =========
    print("\n=== (C) Admin ENV Switch no-op ===")
    r = requests.post(f"{BASE}/admin/env/switch", headers=H(admin_tok), json={"env": "BETA"}, timeout=20)
    j = r.json() if r.ok else {}
    rec("C1 POST /admin/env/switch BETA (no-op)", r.status_code == 200 and j.get("ok") is True and j.get("unchanged") is True,
        f"status={r.status_code} body={j}")

    # ========= (D) Admin ENV Switch validation/negative =========
    print("\n=== (D) Admin ENV Switch negative cases ===")
    r = requests.post(f"{BASE}/admin/env/switch", headers=H(admin_tok), json={"env": "INVALID_XYZ"}, timeout=20)
    body = r.text
    detail = ""
    try:
        detail = r.json().get("detail", "")
    except Exception:
        pass
    rec("D1 POST /admin/env/switch INVALID_XYZ → 400",
        r.status_code == 400 and any(v in detail for v in ("DEV", "BETA", "PROD")),
        f"status={r.status_code} detail={detail}")

    r = requests.post(f"{BASE}/admin/env/switch", headers=H(pro_tok), json={"env": "DEV"}, timeout=20)
    rec("D2 POST /admin/env/switch non-admin (pro) → 403", r.status_code == 403, f"status={r.status_code}")

    r = requests.post(f"{BASE}/admin/env/switch", json={"env": "DEV"}, timeout=20)
    rec("D3 POST /admin/env/switch no auth → 401", r.status_code == 401, f"status={r.status_code}")

    # ========= (E) Monetization regression =========
    print("\n=== (E) Monetization Regression ===")
    # balance_before
    r = requests.get(f"{BASE}/subscription/balance", headers=H(admin_tok), timeout=20)
    j = r.json() if r.ok else {}
    balance_before = j.get("credits_balance")
    rec("E1 GET /subscription/balance admin", r.status_code == 200 and isinstance(balance_before, int),
        f"status={r.status_code} balance={balance_before}")

    # generate-image
    r = requests.post(f"{BASE}/generate-image", headers=H(admin_tok), json={"prompt": "test"}, timeout=60)
    j = r.json() if r.ok else {}
    credits_charged = j.get("credits_charged")
    rec("E2 POST /generate-image admin", r.status_code == 200 and isinstance(credits_charged, int) and credits_charged > 0,
        f"status={r.status_code} credits_charged={credits_charged} project={j.get('project_id')}")

    # balance_after
    time.sleep(1)
    r = requests.get(f"{BASE}/subscription/balance", headers=H(admin_tok), timeout=20)
    j = r.json() if r.ok else {}
    balance_after = j.get("credits_balance")
    expected = (balance_before or 0) - (credits_charged or 0)
    rec("E3 balance_after == balance_before - credits_charged",
        balance_after == expected, f"before={balance_before} after={balance_after} charged={credits_charged} expected={expected}")

    # generate-image no auth → 401
    r = requests.post(f"{BASE}/generate-image", json={"prompt": "x"}, timeout=20)
    rec("E4 POST /generate-image no auth → 401", r.status_code == 401, f"status={r.status_code}")

    # multishot free → 402
    r = requests.post(f"{BASE}/create-multishot", headers=H(free_tok),
                      json={"shots": [{"prompt": "a", "duration": 5}, {"prompt": "b", "duration": 5}, {"prompt": "c", "duration": 5}]},
                      timeout=30)
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text[:200]
    rec("E5 POST /create-multishot free → 402 Pro plan",
        r.status_code == 402 and "Pro" in detail, f"status={r.status_code} detail={detail}")

    # lipsync free → 402 tier error
    r = requests.post(f"{BASE}/create-lipsync", headers=H(free_tok),
                      json={"dialogue_lines": [{"character_index": 0, "text": "hi"}], "image_urls": ["x.jpg"]},
                      timeout=30)
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text[:200]
    # accept either "Starter" / "Pro" / "Lip Sync requires" wording
    is_tier_gate = r.status_code == 402 and ("Lip Sync" in detail or "Starter" in detail or "Pro" in detail or "tier" in detail.lower())
    rec("E6 POST /create-lipsync free → 402 tier error",
        is_tier_gate, f"status={r.status_code} detail={detail}")

    # multishot pro with 2 shots → 200
    r = requests.post(f"{BASE}/create-multishot", headers=H(pro_tok),
                      json={"shots": [{"prompt": "a", "duration": 5}, {"prompt": "b", "duration": 5}]},
                      timeout=60)
    j = r.json() if r.ok else {}
    rec("E7 POST /create-multishot pro 2 shots → 200",
        r.status_code == 200 and j.get("project_id"),
        f"status={r.status_code} project={j.get('project_id')} charged={j.get('credits_charged')}")

    # ========= (F) General regression endpoints =========
    print("\n=== (F) General regression endpoints ===")
    cases = [
        ("/subscription/plans", None),
        ("/admin/users", admin_tok),
        ("/admin/usage", admin_tok),
        ("/templates", None),
        ("/motion-presets", None),
        ("/voice-styles", None),
        ("/sound-effects", None),
        ("/mh-models", None),
        ("/credits-info", None),
    ]
    for path, tok in cases:
        hdr = H(tok) if tok else {}
        r = requests.get(f"{BASE}{path}", headers=hdr, timeout=30)
        extra = ""
        if r.ok:
            try:
                body = r.json()
                if path == "/motion-presets":
                    n = len(body.get("presets", []))
                    extra = f"len={n}"
                    rec(f"F {path} 200 (len==8)", r.status_code == 200 and n == 8, extra)
                    continue
                if path == "/voice-styles":
                    n = len(body.get("styles", []))
                    extra = f"len={n}"
                    rec(f"F {path} 200 (len==5)", r.status_code == 200 and n == 5, extra)
                    continue
            except Exception:
                pass
        rec(f"F {path} 200", r.status_code == 200, f"status={r.status_code} {extra}")

    # ========= (G) Cold-start sanity =========
    print("\n=== (G) Cold-start sanity (backend.err.log) ===")
    # Read log locally (test runs in same container)
    log_path = "/var/log/supervisor/backend.err.log"
    try:
        import subprocess
        out = subprocess.run(["tail", "-n", "80", log_path], capture_output=True, text=True, timeout=10)
        lines = out.stdout.splitlines()
        recent = lines[-80:]
        triggers = ("Traceback", "ImportError", "AttributeError", "ModuleNotFoundError", "NameError")
        hits = [ln for ln in recent if any(t in ln for t in triggers)]
        # Filter out historical ones by looking for mentions of watermark helper / billing
        relevant = [h for h in hits if ("apply_watermark_if_free" in h or "settle_credits" in h or "core.billing" in h or "get_mh_client" in h)]
        print(f"[info] backend.err.log tail scanned; total trigger lines: {len(hits)}")
        for h in hits[-10:]:
            print(f"   log> {h[-220:]}")
        rec("G1 No NEW startup errors for watermark/billing helpers in recent log",
            len(relevant) == 0, f"relevant_hits={len(relevant)} total_hits={len(hits)}")
    except Exception as e:
        rec("G1 backend.err.log scan", False, f"error={e}")

    # ========= SUMMARY =========
    print("\n=== SUMMARY ===")
    passed = sum(1 for _, ok, _ in results if ok)
    failed = [name for name, ok, _ in results if not ok]
    print(f"Total: {len(results)}  PASS: {passed}  FAIL: {len(failed)}")
    if failed:
        print("FAILED:")
        for f in failed:
            print(f"  - {f}")
    # Save
    with open("/app/backend_test_s24_results.json", "w") as f:
        json.dump([{"name": n, "passed": p, "detail": d} for n, p, d in results], f, indent=2)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
