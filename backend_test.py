#!/usr/bin/env python3
"""Session 33 backend tests."""
import asyncio
import base64
import io
import time
import subprocess

import httpx
from PIL import Image, ImageDraw

BASE = "https://creative-plan-engine.preview.emergentagent.com/api"
EMAIL = "demo_creator@test.com"
PASSWORD = "Test@123"


def log(msg):
    print(msg, flush=True)


def make_png_bytes(w=512, h=768):
    img = Image.new("RGB", (w, h), (240, 220, 200))
    d = ImageDraw.Draw(img)
    d.ellipse((w*0.20, h*0.18, w*0.80, h*0.65), fill=(245, 215, 180), outline=(80, 60, 50), width=4)
    d.ellipse((w*0.34, h*0.34, w*0.42, h*0.40), fill=(40, 40, 40))
    d.ellipse((w*0.58, h*0.34, w*0.66, h*0.40), fill=(40, 40, 40))
    d.rectangle((w*0.40, h*0.50, w*0.60, h*0.54), fill=(160, 60, 60))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def make_jpg_b64(size=384):
    img = Image.new("RGB", (size, size))
    for y in range(size):
        c = (int(40 + y * 0.5), int(80 + y * 0.3), max(0, int(180 - y * 0.3)))
        for x in range(size):
            img.putpixel((x, y), c)
    d = ImageDraw.Draw(img)
    d.ellipse((size*0.20, size*0.20, size*0.80, size*0.85), fill=(245, 215, 180))
    d.ellipse((size*0.32, size*0.40, size*0.42, size*0.48), fill=(20, 20, 20))
    d.ellipse((size*0.58, size*0.40, size*0.68, size*0.48), fill=(20, 20, 20))
    d.rectangle((size*0.40, size*0.62, size*0.60, size*0.68), fill=(150, 60, 60))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("ascii")


async def login(client):
    r = await client.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    r.raise_for_status()
    return r.json()["token"]


async def upload_image(client, token):
    png_bytes = make_png_bytes(512, 768)
    files = {"file": ("avatar.png", png_bytes, "image/png")}
    r = await client.post(f"{BASE}/upload-image", files=files,
                          headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()


async def test_a_procedural(client, token):
    log("\n=== A) create-talking-avatar use_procedural_lipsync=true ===")
    up = await upload_image(client, token)
    img_path = up.get("file_path") or up.get("path")
    log(f"  uploaded: {img_path}")
    body = {
        "image_path": img_path,
        "script": "Namaste doston, aaj ham ek nayi kahani sunne wale hain. Yeh bahut interesting hai.",
        "voice_id": "hi-IN-SwaraNeural",
        "aspect_ratio": "9:16",
        "resolution": "480p",
        "use_procedural_lipsync": True,
    }
    t0 = time.time()
    r = await client.post(f"{BASE}/create-talking-avatar", json=body,
                          headers={"Authorization": f"Bearer {token}"}, timeout=60)
    log(f"  POST status={r.status_code} latency={time.time()-t0:.2f}s")
    if r.status_code != 200:
        log(f"  FAIL body: {r.text[:400]}")
        return False
    data = r.json()
    log(f"  resp project_id={data.get('project_id')} status={data.get('status')} credits={data.get('credits_charged')}")
    pid = data.get("project_id")
    if not pid or data.get("status") != "processing":
        return False

    poll_start = time.time()
    final = None
    while time.time() - poll_start < 120:
        await asyncio.sleep(5)
        rp = await client.get(f"{BASE}/project/{pid}", headers={"Authorization": f"Bearer {token}"})
        if rp.status_code == 200:
            pj = rp.json()
            log(f"  poll t={int(time.time()-poll_start)}s status={pj.get('status')} progress={pj.get('progress')}")
            if pj.get("status") in ("completed", "failed"):
                final = pj
                break
    if not final or final.get("status") != "completed":
        log(f"  FAIL: did not complete; final={final}")
        return False
    log(f"  COMPLETED in {time.time()-poll_start:.1f}s")
    result_url = final.get("result_url")
    log(f"  result_url={result_url}")
    if not result_url or ".mp4" not in result_url:
        return False

    full_url = result_url if result_url.startswith("http") else f"https://creative-plan-engine.preview.emergentagent.com{result_url}"
    rd = await client.get(full_url, timeout=60)
    log(f"  download status={rd.status_code} ct={rd.headers.get('content-type')} size={len(rd.content)}")
    if rd.status_code != 200 or len(rd.content) < 10240:
        return False

    # Logs
    for f in ("/var/log/supervisor/backend.err.log", "/var/log/supervisor/backend.out.log"):
        try:
            g = subprocess.run(["grep", "-c", "talking: procedural lipsync OK", f], capture_output=True, text=True)
            log(f"  log {f}: 'procedural lipsync OK' count={g.stdout.strip()}")
        except Exception:
            pass
    return True


async def test_a_reg(client, token):
    log("\n=== A-reg) create-talking-avatar use_procedural_lipsync=false ===")
    up = await upload_image(client, token)
    img_path = up.get("file_path") or up.get("path")
    body = {
        "image_path": img_path,
        "script": "Hello, this is a quick MagicHour regression test for talking avatar.",
        "voice_id": "en-US-JennyNeural",
        "aspect_ratio": "9:16",
        "resolution": "480p",
        "use_procedural_lipsync": False,
    }
    t0 = time.time()
    r = await client.post(f"{BASE}/create-talking-avatar", json=body,
                          headers={"Authorization": f"Bearer {token}"}, timeout=60)
    log(f"  POST status={r.status_code} latency={time.time()-t0:.2f}s")
    if r.status_code != 200:
        log(f"  FAIL: {r.text[:300]}")
        return False
    d = r.json()
    log(f"  resp project_id={d.get('project_id')} status={d.get('status')} credits={d.get('credits_charged')}")
    if d.get("status") != "processing":
        return False
    # Wait for MH upload step in background
    pid = d.get("project_id")
    await asyncio.sleep(15)
    rp = await client.get(f"{BASE}/project/{pid}", headers={"Authorization": f"Bearer {token}"})
    if rp.status_code == 200:
        pj = rp.json()
        log(f"  after 15s: status={pj.get('status')} progress={pj.get('progress')}")
    return True


async def test_b_cartoonize(client, token):
    log("\n=== B) cartoonize 5x concurrent ===")
    img_b64 = make_jpg_b64(384)
    emotions = ["happy", "excited", "confident", "playful", "peaceful"]

    async def fire(i, emo):
        try:
            r = await client.post(f"{BASE}/avatar/cartoonize",
                                  json={"image_b64": img_b64, "style": "pixar", "emotion": emo},
                                  headers={"Authorization": f"Bearer {token}"}, timeout=30)
            log(f"  [{i}] emo={emo} -> {r.status_code}")
            if r.status_code == 200:
                return r.json().get("job_id")
        except Exception as e:
            log(f"  [{i}] exc: {e}")
        return None

    job_ids = await asyncio.gather(*[fire(i, e) for i, e in enumerate(emotions)])
    job_ids = [j for j in job_ids if j]
    log(f"  jobs: {len(job_ids)}/5: {job_ids}")
    if len(job_ids) != 5:
        return False

    final = {}
    poll_start = time.time()
    while time.time() - poll_start < 150 and len(final) < 5:
        await asyncio.sleep(3)
        for jid in job_ids:
            if jid in final:
                continue
            try:
                r = await client.get(f"{BASE}/avatar/jobs/{jid}", timeout=20)
                if r.status_code == 200:
                    st = r.json().get("status")
                    if st in ("completed", "failed"):
                        final[jid] = st
                        log(f"  {jid}={st} t={int(time.time()-poll_start)}s")
            except Exception:
                pass

    completed = sum(1 for v in final.values() if v == "completed")
    failed = sum(1 for v in final.values() if v == "failed")
    pending = 5 - len(final)
    log(f"  Final: completed={completed} failed={failed} pending={pending}")

    # log markers
    for f in ("/var/log/supervisor/backend.err.log",):
        try:
            g1 = subprocess.run(["grep", "-c", "nano banana OK on attempt", f], capture_output=True, text=True)
            g2 = subprocess.run(["grep", "-c", "nano banana attempt", f], capture_output=True, text=True)
            g3 = subprocess.run(["grep", "-c", "nano banana ALL", f], capture_output=True, text=True)
            log(f"  log: OK_on_attempt={g1.stdout.strip()} attempt_warn={g2.stdout.strip()} ALL_failed={g3.stdout.strip()}")
        except Exception:
            pass

    return completed >= 4


async def test_c_preview(client):
    log("\n=== C) generate-prompts/preview-audio ===")
    cases = [
        {"text": "Namaste, aaj ka din bahut shubh hai. Hari Om.", "voice_id": "hi-IN-SwaraNeural", "language": "hindi"},
        {"text": "Hello world, welcome to MagiCAi Studio.", "voice_id": "en-US-JennyNeural", "language": "english"},
    ]
    ok = True
    for case in cases:
        t0 = time.time()
        try:
            r = await client.post(f"{BASE}/generate-prompts/preview-audio", json=case, timeout=60)
            ct = (r.headers.get("content-type") or "").lower()
            log(f"  voice={case['voice_id']} status={r.status_code} ct={ct} size={len(r.content)} latency={time.time()-t0:.2f}s")
            if r.status_code != 200 or "audio/mpeg" not in ct or len(r.content) < 10240:
                log(f"    FAIL")
                ok = False
        except Exception as e:
            log(f"    EXC: {e}"); ok = False
    return ok


async def test_d_reg(client, token):
    log("\n=== D) Regression sweep ===")
    ok = True

    r = await client.get(f"{BASE}/")
    j = r.json() if r.status_code == 200 else {}
    ver = j.get("version", "")
    log(f"  /api/ -> {r.status_code} version={ver}")
    if r.status_code != 200 or not ver.startswith("7."):
        ok = False

    r = await client.get(f"{BASE}/avatar/styles")
    if r.status_code == 200:
        emos = r.json().get("emotions", [])
        log(f"  /avatar/styles -> 200 emotions_len={len(emos)}")
        if len(emos) < 12:
            ok = False
    else:
        log(f"  /avatar/styles -> {r.status_code}"); ok = False

    r = await client.get(f"{BASE}/marketplace/templates?limit=3")
    log(f"  /marketplace/templates?limit=3 -> {r.status_code}")
    if r.status_code != 200:
        ok = False

    r = await client.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    has_t = "token" in (r.json() if r.status_code == 200 else {})
    log(f"  /auth/login -> {r.status_code} has_token={has_t}")
    if r.status_code != 200 or not has_t:
        ok = False

    r = await client.get(f"{BASE}/mode")
    if r.status_code == 200:
        env = r.json().get("env")
        log(f"  /mode -> 200 env={env}")
        if env != "BETA":
            ok = False
    else:
        log(f"  /mode -> {r.status_code}"); ok = False

    return ok


async def main():
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        token = await login(client)
        log(f"Logged in, token len={len(token)}")

        d_ok = await test_d_reg(client, token)
        c_ok = await test_c_preview(client)
        b_ok = await test_b_cartoonize(client, token)
        a_ok = await test_a_procedural(client, token)
        a_reg_ok = await test_a_reg(client, token)

    log("\n========== SUMMARY ==========")
    log(f"  A) procedural lipsync: {'PASS' if a_ok else 'FAIL'}")
    log(f"  A-reg) MH path request: {'PASS' if a_reg_ok else 'FAIL'}")
    log(f"  B) cartoonize 5x: {'PASS' if b_ok else 'FAIL'}")
    log(f"  C) preview-audio: {'PASS' if c_ok else 'FAIL'}")
    log(f"  D) regression: {'PASS' if d_ok else 'FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())
