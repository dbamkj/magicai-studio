"""
Session 21 RETEST — FFmpeg Motion Engine (bugs just fixed).
Retest ONLY the previously-failing tests:
  (B1) POST /api/animate-image
  (C1) POST /api/create-multishot with motion bypass
  (C2) Backward compat — POST /api/create-multishot WITHOUT motion field
"""
import json
import os
import time
from pathlib import Path
import requests

BACKEND = "https://creative-plan-engine.preview.emergentagent.com"
API = f"{BACKEND}/api"

# Pick an existing image from uploads
UPLOAD_DIR = Path("/app/backend/uploads")
EXISTING_PNG = "04b7fb09-dea9-47bf-9732-040ad94d425a.png"
IMG_FULL = str(UPLOAD_DIR / EXISTING_PNG)
assert (UPLOAD_DIR / EXISTING_PNG).exists(), f"Test image missing at {IMG_FULL}"


def _poll(pid, timeout=30, interval=2):
    waited = 0
    last = None
    while waited <= timeout:
        r = requests.get(f"{API}/project/{pid}", timeout=15)
        if r.status_code == 200:
            last = r.json()
            if last.get("status") in ("completed", "failed"):
                return last, waited
        time.sleep(interval)
        waited += interval
    return last, waited


def test_B1_animate_image_zoom_in():
    print("\n=== (B1) POST /api/animate-image  zoom_in 3s 480p ===")
    body = {
        "image_path": f"/uploads/{EXISTING_PNG}",
        "motion": "zoom_in",
        "duration": 3,
        "resolution": "480p",
    }
    r = requests.post(f"{API}/animate-image", json=body, timeout=30)
    print("POST status:", r.status_code)
    assert r.status_code == 200, r.text
    j = r.json()
    pid = j.get("project_id")
    print("project_id:", pid, "status:", j.get("status"))
    assert pid

    final, waited = _poll(pid, timeout=30, interval=2)
    print(f"final after {waited}s: status={final.get('status')} result_url={final.get('result_url')} error={final.get('error')}")

    assert final.get("status") == "completed", f"Expected completed, got {final.get('status')} err={final.get('error')}"
    ru = final.get("result_url")
    assert ru and ru.startswith("/api/serve-file/motion_") and ru.endswith(".mp4"), f"Bad result_url: {ru}"

    # Download and verify > 1KB
    dl = requests.get(f"{BACKEND}{ru}", timeout=30)
    print("download status:", dl.status_code, "bytes:", len(dl.content))
    assert dl.status_code == 200 and len(dl.content) > 1024
    print("B1 zoom_in PASS")
    return pid


def test_B1_ken_burns():
    print("\n=== (B1 extra) POST /api/animate-image  ken_burns 2s 480p ===")
    body = {
        "image_path": f"/uploads/{EXISTING_PNG}",
        "motion": "ken_burns",
        "duration": 2,
        "resolution": "480p",
    }
    r = requests.post(f"{API}/animate-image", json=body, timeout=30)
    print("POST status:", r.status_code)
    assert r.status_code == 200, r.text
    pid = r.json()["project_id"]
    final, waited = _poll(pid, timeout=30, interval=2)
    print(f"final after {waited}s: status={final.get('status')} result_url={final.get('result_url')} error={final.get('error')}")
    assert final.get("status") == "completed"
    ru = final.get("result_url")
    assert ru and "motion_" in ru
    dl = requests.get(f"{BACKEND}{ru}", timeout=30)
    assert dl.status_code == 200 and len(dl.content) > 1024
    print("B1 ken_burns PASS")
    return pid


def test_C1_multishot_motion_bypass():
    print("\n=== (C1) POST /api/create-multishot with motion (bypass MH) ===")
    body = {
        "shots": [
            {
                "prompt": "Portrait zoom",
                "duration": 3,
                "start_image_path": IMG_FULL,
                "motion": "zoom_in",
                "voice_id": "hi-IN-SwaraNeural",
            }
        ],
        "aspect_ratio": "9:16",
        "resolution": "480p",
    }
    r = requests.post(f"{API}/create-multishot", json=body, timeout=30)
    print("POST status:", r.status_code)
    assert r.status_code == 200, r.text
    j = r.json()
    pid = j.get("project_id")
    print("project_id:", pid, "shot_count:", j.get("shot_count"))
    assert pid

    final, waited = _poll(pid, timeout=45, interval=2)
    print(f"final after {waited}s: status={final.get('status')} result_url={final.get('result_url')} error={final.get('error')}")
    assert final.get("status") == "completed", f"Expected completed, got {final.get('status')} err={final.get('error')}"
    ru = final.get("result_url")
    assert ru, f"result_url missing"
    print("C1 PASS pid=", pid)
    return pid


def test_C2_multishot_backward_compat():
    print("\n=== (C2) POST /api/create-multishot WITHOUT motion field (backward compat) ===")
    body = {
        "shots": [{"prompt": "A calm river at sunset", "duration": 3}],
        "aspect_ratio": "9:16",
        "resolution": "480p",
    }
    r = requests.post(f"{API}/create-multishot", json=body, timeout=30)
    print("POST status:", r.status_code)
    assert r.status_code == 200, r.text
    j = r.json()
    pid = j.get("project_id")
    print("project_id:", pid, "shot_count:", j.get("shot_count"))
    assert pid
    print("C2 PASS (endpoint accepts no-motion payload)")
    return pid


def scan_logs_for(pid_list, markers):
    """Scan backend log for markers associated with given project ids."""
    import subprocess
    out = subprocess.run(["tail", "-n", "2000", "/var/log/supervisor/backend.err.log"],
                         capture_output=True, text=True).stdout
    hits = {}
    for m in markers:
        hits[m] = [ln for ln in out.splitlines() if m in ln]
    return hits


if __name__ == "__main__":
    results = {}
    try:
        results["B1_zoom_in"] = ("PASS", test_B1_animate_image_zoom_in())
    except Exception as e:
        results["B1_zoom_in"] = ("FAIL", str(e))

    try:
        results["B1_ken_burns"] = ("PASS", test_B1_ken_burns())
    except Exception as e:
        results["B1_ken_burns"] = ("FAIL", str(e))

    try:
        results["C1_motion_bypass"] = ("PASS", test_C1_multishot_motion_bypass())
    except Exception as e:
        results["C1_motion_bypass"] = ("FAIL", str(e))

    try:
        results["C2_backward_compat"] = ("PASS", test_C2_multishot_backward_compat())
    except Exception as e:
        results["C2_backward_compat"] = ("FAIL", str(e))

    print("\n\n======== RESULTS ========")
    for k, v in results.items():
        print(f"{k}: {v[0]}  -> {v[1]}")

    # Log scan
    print("\n======== LOG SCAN ========")
    hits = scan_logs_for([], ["motion(zoom_in): OK", "motion(ken_burns): OK",
                              "MS shot 0: motion(zoom_in) bypass MH", "MS shot 0: motion",
                              "orientation"])
    for k, lines in hits.items():
        print(f"\n[{k}]: {len(lines)} line(s)")
        for ln in lines[-6:]:
            print("  ", ln)
