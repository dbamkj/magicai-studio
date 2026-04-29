"""Session 27d bucket (C) retest after fix — buckets (A), (B), (C), (D)."""
import os
import sys
import glob
import requests
import subprocess

sys.path.insert(0, '/app/backend')

BASE_URL = None
with open('/app/frontend/.env') as f:
    for line in f:
        if line.startswith('EXPO_PUBLIC_BACKEND_URL='):
            BASE_URL = line.split('=', 1)[1].strip().strip('"')
            break
assert BASE_URL, 'Backend URL not found'
API = BASE_URL.rstrip('/') + '/api'
print(f'API base: {API}')

FREE = 'demo_free@test.com'
PW = 'Test@123'

results = []


def record(name, ok, detail=''):
    status = 'PASS' if ok else 'FAIL'
    line = f'[{status}] {name} — {detail}'
    print(line)
    results.append((name, ok, detail))


def login(email, pw=PW):
    r = requests.post(f'{API}/auth/login', json={'email': email, 'password': pw}, timeout=30)
    r.raise_for_status()
    return r.json()['token']


def get_sample_image():
    paths = sorted(glob.glob('/app/backend/uploads/*.jpg') + glob.glob('/app/backend/uploads/*.png'))
    for p in paths:
        if os.path.getsize(p) > 500:
            return p
    return paths[0] if paths else None


def reset_free_user():
    """Ensure demo_free is in clean state (free tier, 300 credits) in magicai_beta."""
    script = '''
import asyncio, os, sys
sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient
async def main():
    c = AsyncIOMotorClient("mongodb://localhost:27017")
    db = c["magicai_beta"]
    res = await db.users.update_one({"email":"demo_free@test.com"}, {
        "$set": {"subscription_tier":"free","credits_balance":300,"trial_active":False,
                 "trial_used":False,"addon_ai_videos_remaining":0,"addon_ai_video_max_seconds":0},
        "$unset": {"subscription_cycle":"","subscription_price_inr":"","subscription_renews_at":"",
                   "trial_end":"","trial_plan":"","trial_started_at":"","trial_expired_at":""}
    })
    u = await db.users.find_one({"email":"demo_free@test.com"},
        {"subscription_tier":1,"credits_balance":1,"trial_active":1,"trial_used":1,
         "addon_ai_videos_remaining":1,"addon_ai_video_max_seconds":1,"_id":0})
    print("STATE:", u)
asyncio.run(main())
'''
    p = subprocess.run(['python', '-c', script], capture_output=True, text=True, timeout=30)
    print('--- reset_free_user ---')
    print((p.stdout or '') + (p.stderr or ''))


def main():
    # Pre-test cleanup — ensure clean state
    reset_free_user()

    try:
        free_token = login(FREE)
    except Exception as e:
        record('login demo_free', False, str(e))
        return
    record('login demo_free', True, 'token issued')

    hdr = {'Authorization': f'Bearer {free_token}'}

    # Verify BETA mode
    r = requests.get(f'{API}/mode', timeout=15)
    print(f"GET /mode => {r.status_code} {r.text[:150]}")

    img_path = get_sample_image()
    assert img_path, 'No sample image'
    print(f'sample image: {img_path}')

    # ========== (A) Free tier ==========
    payload5 = {'image_path': img_path, 'prompt': 'test devotional slow zoom', 'duration': 5}
    r = requests.post(f'{API}/create-image-to-video', json=payload5, headers=hdr, timeout=30)
    body = r.text or ''
    expected_msg_creator = 'AI Video requires Creator plan or higher, or purchase an add-on.'
    ok_a = (r.status_code == 402 and expected_msg_creator in body)
    record('(A) Free user POST duration=5 -> 402 with "Creator plan" msg', ok_a,
           f'status={r.status_code} body={body[:250]}')

    # ========== (B) Upgrade to Starter ==========
    r = requests.post(f'{API}/subscription/upgrade',
                      json={'plan_id': 'starter', 'billing_cycle': 'monthly'},
                      headers=hdr, timeout=30)
    record('(B-prep) upgrade -> starter', r.status_code == 200,
           f'status={r.status_code} body={r.text[:200]}')

    r = requests.post(f'{API}/create-image-to-video', json=payload5, headers=hdr, timeout=30)
    body = r.text or ''
    ok_b = (r.status_code == 402 and expected_msg_creator in body)
    record('(B) Starter user POST duration=5 -> 402 with "Creator plan" msg', ok_b,
           f'status={r.status_code} body={body[:250]}')

    # ========== (C) Upgrade to Creator ==========
    r = requests.post(f'{API}/subscription/upgrade',
                      json={'plan_id': 'creator', 'billing_cycle': 'monthly'},
                      headers=hdr, timeout=30)
    record('(C-prep) upgrade -> creator', r.status_code == 200,
           f'status={r.status_code} body={r.text[:200]}')

    # (C.1) duration=5 → 402 duration message (NOT Creator message)
    r = requests.post(f'{API}/create-image-to-video', json=payload5, headers=hdr, timeout=30)
    body = r.text or ''
    expected_msg_duration = 'AI Video max duration on your plan/add-on is 3s.'
    ok_c1 = (r.status_code == 402 and expected_msg_duration in body and
             expected_msg_creator not in body)
    record('(C.1) Creator user POST duration=5 -> 402 "max duration 3s" (NOT old Creator msg)',
           ok_c1, f'status={r.status_code} body={body[:250]}')

    # (C.2) duration=3 → NOT 402 (expect 200 project_id)
    payload3 = {'image_path': img_path, 'prompt': 'test devotional slow zoom', 'duration': 3}
    r = requests.post(f'{API}/create-image-to-video', json=payload3, headers=hdr, timeout=60)
    body = r.text or ''
    ok_c2 = (r.status_code != 402)
    try:
        j = r.json() if r.status_code == 200 else {}
        has_pid = bool(j.get('project_id'))
    except Exception:
        has_pid = False
    record('(C.2) Creator user POST duration=3 -> NOT 402',
           ok_c2, f'status={r.status_code} has_project_id={has_pid} body={body[:250]}')

    # ========== (D) Regression ==========
    r = requests.get(f'{API}/credits-info', headers=hdr, timeout=15)
    record('(D) GET /credits-info -> 200', r.status_code == 200, f'status={r.status_code}')

    r = requests.get(f'{API}/mode', timeout=15)
    ok_mode = (r.status_code == 200)
    env = ''
    try:
        env = r.json().get('env', '')
    except Exception:
        pass
    record('(D) GET /mode -> 200', ok_mode, f'status={r.status_code} env={env}')

    r = requests.get(f'{API}/voices', timeout=15)
    ok_voices = (r.status_code == 200)
    vc = 0
    try:
        vc = len(r.json().get('voices', []))
    except Exception:
        pass
    record('(D) GET /voices -> 200', ok_voices, f'status={r.status_code} count={vc}')

    # ========== Cleanup ==========
    reset_free_user()

    passed = sum(1 for _, o, _ in results if o)
    print(f'\n===== SUMMARY {passed}/{len(results)} =====')
    for n, o, d in results:
        print(f'{"OK" if o else "XX"} {n}: {d[:200]}')

    return passed == len(results)


if __name__ == '__main__':
    ok = main()
    sys.exit(0 if ok else 1)
