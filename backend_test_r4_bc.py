"""Session 33 r4 — Run Tests B & C with retry-resilient polling."""
from __future__ import annotations
import json, re, subprocess, time
from pathlib import Path
import requests

BACKEND = "https://creative-plan-engine.preview.emergentagent.com"
API = f"{BACKEND}/api"


def req_with_retry(method: str, url: str, **kw) -> requests.Response | None:
    for i in range(4):
        try:
            return requests.request(method, url, timeout=30, **kw)
        except (requests.Timeout, requests.ConnectionError) as e:
            print(f"   [retry {i+1}/4] {method} {url[-60:]} error: {type(e).__name__}")
            time.sleep(5)
    return None


def _login(email, password):
    r = req_with_retry("POST", f"{API}/auth/login", json={"email": email, "password": password})
    return r.json().get("token") if r and r.status_code == 200 else None


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def _cartoonize(token, prompt):
    r = req_with_retry("POST", f"{API}/avatar/cartoonize",
                       json={"style": "desi_toon", "emotion": "happy", "prompt": prompt},
                       headers=_auth(token))
    return r.json().get("job_id") if r and r.status_code == 200 else None


def _poll_job(jid, max_wait=120):
    start = time.time()
    while time.time() - start < max_wait:
        r = req_with_retry("GET", f"{API}/avatar/jobs/{jid}")
        if r and r.status_code == 200:
            d = r.json()
            if d.get("status") == "completed":
                return d.get("image_url")
            if d.get("status") == "failed":
                print(f"   job {jid} FAILED: {d.get('error')}")
                return None
        time.sleep(4)
    return None


def _img_url_to_uploads(u):
    return u.replace("/api/serve-file/", "/api/uploads/")


def _poll_project(pid, tok, max_wait=180):
    start = time.time()
    last = {}
    while time.time() - start < max_wait:
        r = req_with_retry("GET", f"{API}/project/{pid}", headers=_auth(tok))
        if r and r.status_code == 200:
            last = r.json()
            st = last.get("status")
            print(f"    t={int(time.time()-start)}s status={st} progress={last.get('progress')} url={last.get('result_url')}")
            if st in ("completed", "failed"):
                return last
        elif r:
            print(f"    t={int(time.time()-start)}s http={r.status_code}")
        time.sleep(5)
    return last


def make_images(tok):
    print("  → cartoonize image A...")
    ja = _cartoonize(tok, "young Indian man in colourful clothes, full body")
    print(f"    job_a={ja}")
    print("  → cartoonize image B...")
    jb = _cartoonize(tok, "young Indian woman in saree, full body")
    print(f"    job_b={jb}")
    ua = _poll_job(ja)
    ub = _poll_job(jb)
    print(f"    image_a={ua}")
    print(f"    image_b={ub}")
    if ua and ub:
        return _img_url_to_uploads(ua), _img_url_to_uploads(ub)
    return None


def test_B():
    print("\n" + "="*70 + "\n=== TEST B — dual procedural (free user) ===\n" + "="*70)
    out = {}
    tok = _login("phase1test@example.com", "Test@123")
    if not tok:
        return {"B_login": False}
    out["B_login"] = True
    pair = make_images(tok)
    if not pair:
        out["B_images"] = False
        return out
    out["B_images"] = True
    a, b = pair
    body = {
        "image_a_path": a, "image_b_path": b,
        "script": "A: Namaste doston, kaise ho?\nB: Bahut badhiya, aur tum?\nA: Sab theek hai, dhanyavaad.",
        "voice_a_id": "hi-IN-MadhurNeural",
        "voice_b_id": "hi-IN-SwaraNeural",
        "motion": "none",
        "aspect_ratio": "16:9",
        "resolution": "480p",
        "use_procedural_lipsync": True,
    }
    r = req_with_retry("POST", f"{API}/avatar/dual-lipsync", json=body, headers=_auth(tok))
    print(f"  POST /avatar/dual-lipsync → {r.status_code if r else 'ERR'}")
    if not r:
        out["B_post"] = False
        return out
    out["B_no_402"] = r.status_code != 402
    out["B_status_200"] = r.status_code == 200
    if r.status_code == 200:
        pid = r.json().get("project_id")
        out["B_project_id"] = pid
        print(f"  → polling free user project {pid}...")
        final = _poll_project(pid, tok, 200)
        out["B_final_status"] = final.get("status")
        out["B_completed"] = final.get("status") == "completed"
        result_url = final.get("result_url") or ""
        out["B_proc_filename"] = "_proc.mp4" in result_url or "pp_" in result_url
        out["B_result_url"] = result_url
        if out["B_completed"]:
            fu = BACKEND + result_url
            r2 = req_with_retry("GET", fu)
            if r2:
                out["B_dl_status"] = r2.status_code
                out["B_dl_size"] = len(r2.content)
                out["B_dl_ct"] = r2.headers.get("content-type", "")
                print(f"     download {r2.status_code} {out['B_dl_ct']} size={out['B_dl_size']}")
    else:
        print(f"  body={r.text[:300]}")
    return out


def test_C():
    print("\n" + "="*70 + "\n=== TEST C — regression: dual MH path ===\n" + "="*70)
    out = {}
    tok = _login("demo_creator@test.com", "Test@123")
    if not tok:
        return {"C_login": False}
    pair = make_images(tok)
    if not pair:
        out["C_images"] = False
        return out
    a, b = pair
    body = {
        "image_a_path": a, "image_b_path": b,
        "script": "A: Hello there, how are you today?\nB: I am doing well, thank you.",
        "voice_a_id": "en-US-JennyNeural",
        "voice_b_id": "en-US-GuyNeural",
        "motion": "none", "aspect_ratio": "16:9", "resolution": "480p",
        "use_procedural_lipsync": False,
    }
    r = req_with_retry("POST", f"{API}/avatar/dual-lipsync", json=body, headers=_auth(tok))
    print(f"  POST procedural=False → {r.status_code if r else 'ERR'}")
    if not r or r.status_code != 200:
        out["C_post_200"] = False
        if r:
            print(f"  body={r.text[:300]}")
        return out
    out["C_post_200"] = True
    pid = r.json().get("project_id")
    out["C_project_id"] = pid
    # Poll 60s — must return 200 (NOT 404)
    for i in range(12):
        time.sleep(5)
        rr = req_with_retry("GET", f"{API}/project/{pid}", headers=_auth(tok))
        if rr:
            print(f"    t={5*(i+1)}s http={rr.status_code} "
                  f"status={rr.json().get('status') if rr.status_code==200 else '-'}")
            if rr.status_code == 200:
                out["C_get_200"] = True
                out["C_last_status"] = rr.json().get("status")
    return out


def scan_log(pid, patterns):
    found = {}
    blob = subprocess.run(["tail", "-n", "30000", "/var/log/supervisor/backend.err.log"],
                          capture_output=True, timeout=10).stdout.decode(errors="ignore")
    for p in patterns:
        found[p] = [ln for ln in blob.splitlines() if p.lower() in ln.lower()]
    return found


if __name__ == "__main__":
    results = {}
    results["B"] = test_B()
    if results["B"].get("B_project_id"):
        pid = results["B"]["B_project_id"]
        s = scan_log(pid[:8], ["dual: procedural lipsync OK", "DualAvatar failed", "cannot access local variable"])
        print("\n  --- B log scan ---")
        for k, v in s.items():
            print(f"    {k!r}: {len(v)} matches")
            for ln in v[-2:]:
                print(f"      • {ln[:220]}")
        results["B"]["B_log_proc_ok"] = any(pid[:8] in ln for ln in s["dual: procedural lipsync OK"])
        results["B"]["B_log_no_unbound"] = not any(pid[:8] in ln for ln in s["cannot access local variable"])

    results["C"] = test_C()
    if results["C"].get("C_project_id"):
        pid = results["C"]["C_project_id"]
        s = scan_log(pid[:8], ["MH upload OK", "DualAvatar failed", "cannot access local variable"])
        print("\n  --- C log scan ---")
        for k, v in s.items():
            print(f"    {k!r}: {len(v)} matches")
            for ln in v[-2:]:
                print(f"      • {ln[:220]}")
        # MH upload may not be project-specific in log, check globally near that time
        mh_any = subprocess.run(["grep", "-c", "MH upload OK: type=video",
                                 "/var/log/supervisor/backend.err.log"],
                                capture_output=True).stdout.decode().strip()
        results["C"]["C_log_mh_video_total"] = mh_any
        results["C"]["C_log_no_unbound"] = not any(pid[:8] in ln for ln in s["cannot access local variable"])

    print("\n" + "="*70)
    print(json.dumps(results, indent=2, default=str))
