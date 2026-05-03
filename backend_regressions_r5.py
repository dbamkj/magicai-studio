"""Phase-3 r5 extra regressions: bhakti-dual, no-preset-dual."""
from __future__ import annotations
import os, re, time
from pathlib import Path
import requests
from PIL import Image

BACKEND = "https://creative-plan-engine.preview.emergentagent.com"
API = BACKEND + "/api"
DEMO_CREATOR = {"email": "demo_creator@test.com", "password": "Test@123"}
LOG = "/var/log/supervisor/backend.err.log"


def log_size():
    try: return os.path.getsize(LOG)
    except: return 0

def log_tail(offset):
    with open(LOG, "rb") as f:
        f.seek(offset)
        return f.read().decode("utf-8", errors="ignore")

def login(c):
    r = requests.post(f"{API}/auth/login", json=c, timeout=30); r.raise_for_status()
    j = r.json(); return j["token"], j["user"]

def mkpng(path, color):
    Image.new("RGB", (512,768), color).save(path, "PNG")
    return path

def upload(tok, path):
    with open(path,"rb") as f:
        r = requests.post(f"{API}/upload-image",
                          files={"file":(path.name,f,"image/png")},
                          headers={"Authorization":f"Bearer {tok}"},
                          timeout=60)
    return r.json()["file_path"]

def poll(tok, pid, t=180):
    t0=time.time()
    while time.time()-t0<t:
        r=requests.get(f"{API}/project/{pid}",headers={"Authorization":f"Bearer {tok}"},timeout=20)
        if r.status_code==200:
            j=r.json()
            if j.get("status") in ("completed","failed"):
                return j
        time.sleep(2)
    return {"status":"timeout"}

def main():
    tok,u=login(DEMO_CREATOR)
    print(f"Login: {u['email']} credits={u['credits_balance']}")
    a=upload(tok,mkpng(Path("/tmp/_r5_a.png"),(210,170,130)))
    b=upload(tok,mkpng(Path("/tmp/_r5_b.png"),(180,140,200)))

    # R1: dual with preset_id="bhakti"
    print("\n-- R1 dual preset=bhakti --")
    off=log_size()
    body={
        "image_a_path":a,"image_b_path":b,
        "script":"A: Radhe Radhe.\nB: Jai Shri Krishna.\nA: Bhakti mein shakti.",
        "voice_a_id":"hi-IN-MadhurNeural","voice_b_id":"hi-IN-SwaraNeural",
        "motion":"none","aspect_ratio":"16:9","resolution":"480p",
        "use_procedural_lipsync":True,"preset_id":"bhakti",
    }
    r=requests.post(f"{API}/avatar/dual-lipsync",json=body,
                    headers={"Authorization":f"Bearer {tok}"},timeout=30)
    print(f"  POST status={r.status_code}")
    if r.status_code==200:
        pid=r.json()["project_id"]
        res=poll(tok,pid,t=180)
        print(f"  final status={res.get('status')} result_url={res.get('result_url')}")
        logs=log_tail(off)
        m=re.search(r"dual: preset 'bhakti' applied[^\n]*",logs)
        print(f"  LOG preset: {m.group(0) if m else '<not found>'}")
        m2=re.search(r"camera: motion=\w+[^\n]*",logs)
        print(f"  LOG camera: {m2.group(0) if m2 else '<not found>'}")
        print(f"  R1 expected: dual: preset 'bhakti' applied (motion=ken_burns bgm=devotional)")
    else:
        print(f"  ERR: {r.text[:300]}")

    # R2: dual WITHOUT preset_id, motion="none"
    print("\n-- R2 dual no-preset no-motion --")
    off=log_size()
    body2={
        "image_a_path":a,"image_b_path":b,
        "script":"A: Hi.\nB: Hello.\nA: Ok.",
        "voice_a_id":"en-US-GuyNeural","voice_b_id":"en-US-JennyNeural",
        "motion":"none","aspect_ratio":"16:9","resolution":"480p",
        "use_procedural_lipsync":True,
    }
    r=requests.post(f"{API}/avatar/dual-lipsync",json=body2,
                    headers={"Authorization":f"Bearer {tok}"},timeout=30)
    print(f"  POST status={r.status_code}")
    if r.status_code==200:
        pid=r.json()["project_id"]
        res=poll(tok,pid,t=180)
        print(f"  final status={res.get('status')} result_url={res.get('result_url')}")
        logs=log_tail(off)
        preset_line=re.search(r"dual: preset '[^']+' applied",logs)
        camera_line=re.search(r"camera: motion=\w+[^\n]*",logs)
        fx_line=re.search(r"dual: camera\+effects applied[^\n]*",logs)
        print(f"  preset_log_present: {bool(preset_line)} (expected False)")
        print(f"  camera_log_present: {bool(camera_line)} (expected False)")
        print(f"  fx_line_present: {bool(fx_line)} (expected False)")
        # these should ALL be absent
    else:
        print(f"  ERR: {r.text[:300]}")

if __name__=="__main__":
    main()
