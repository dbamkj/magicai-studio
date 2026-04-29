"""Backend test for Creator Wizard endpoints (Session 27)."""
import os
import time
import json
import requests

BACKEND = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://creative-plan-engine.preview.emergentagent.com').rstrip('/')
LOCAL = 'http://localhost:8001'
API = f'{BACKEND}/api'

PASS, FAIL = [], []


def check(name, cond, detail=''):
    if cond:
        PASS.append(name)
        print(f'✅ {name}  {detail}')
    else:
        FAIL.append((name, detail))
        print(f'❌ {name}  {detail}')


# ============ (A) BGM Catalog ============
print('\n=== (A) GET /api/wizard/bgm-catalog ===')
try:
    r = requests.get(f'{API}/wizard/bgm-catalog', timeout=30)
    data = r.json() if r.ok else {}
    tracks = data.get('tracks', [])
    check('A.1 status=200', r.status_code == 200, f'status={r.status_code}')
    check('A.2 tracks non-empty', len(tracks) >= 1, f'len={len(tracks)}')
    if tracks:
        t0 = tracks[0]
        need = {'id', 'name', 'mood', 'bpm', 'url'}
        miss = need - set(t0.keys())
        check('A.3 track has required keys', not miss, f'missing={miss} t0={t0}')
except Exception as e:
    check('A exception', False, str(e))


# ============ (B) Prompts ============
print('\n=== (B) POST /api/wizard/prompts ===')
try:
    r = requests.post(f'{API}/wizard/prompts',
                      json={'idea': 'A devotional reel about Lord Krishna flute'},
                      timeout=90)
    check('B.1 status=200', r.status_code == 200, f'status={r.status_code} body={r.text[:200]}')
    if r.ok:
        data = r.json()
        opts = data.get('options', [])
        check('B.2 options length=3', len(opts) == 3, f'len={len(opts)}')
        if opts:
            required = {'title', 'tone', 'script', 'image_query', 'music_mood', 'motion'}
            ok = all(required.issubset(set(o.keys())) for o in opts)
            check('B.3 each option has required keys', ok, f'first_opt_keys={list(opts[0].keys())}')
    # Missing/empty idea → 422
    r2 = requests.post(f'{API}/wizard/prompts', json={'idea': ''}, timeout=15)
    check('B.4 empty idea=422', r2.status_code == 422, f'status={r2.status_code}')
    r3 = requests.post(f'{API}/wizard/prompts', json={'idea': 'ab'}, timeout=15)
    check('B.5 short idea<3 =422', r3.status_code == 422, f'status={r3.status_code}')
    r4 = requests.post(f'{API}/wizard/prompts', json={}, timeout=15)
    check('B.6 missing body=422', r4.status_code == 422, f'status={r4.status_code}')
except Exception as e:
    check('B exception', False, str(e))


# ============ (C) Preview Images ============
print('\n=== (C) POST /api/wizard/preview-images ===')
try:
    r = requests.post(f'{API}/wizard/preview-images',
                      json={'image_query': 'sunrise meditation', 'count': 5},
                      timeout=30)
    check('C.1 status=200', r.status_code == 200, f'status={r.status_code}')
    if r.ok:
        data = r.json()
        imgs = data.get('images', [])
        check('C.2 images>=3', len(imgs) >= 3, f'len={len(imgs)}')
        if imgs:
            need = {'url', 'preview', 'tags', 'user', 'width', 'height'}
            miss = need - set(imgs[0].keys())
            check('C.3 image schema', not miss, f'missing={miss}')
    r2 = requests.post(f'{API}/wizard/preview-images',
                       json={'image_query': 'a'}, timeout=15)
    check('C.4 short query<2 =422', r2.status_code == 422, f'status={r2.status_code}')
except Exception as e:
    check('C exception', False, str(e))


# ============ (E) Nonexistent job (do this before full pipeline) ============
print('\n=== (E) GET /api/wizard/job/nonexistent_id ===')
try:
    r = requests.get(f'{API}/wizard/job/nonexistent_id', timeout=15)
    check('E.1 status=404', r.status_code == 404, f'status={r.status_code}')
    if r.status_code == 404:
        data = r.json()
        check('E.2 detail=Job not found', data.get('detail') == 'Job not found',
              f'detail={data.get("detail")}')
except Exception as e:
    check('E exception', False, str(e))


# ============ (F) Upsell Cinematic ============
print('\n=== (F) POST /api/wizard/upsell-cinematic ===')
try:
    body = {'script': 'test', 'voice_id': 'en-US-JennyNeural',
            'motion': 'cinematic_zoom', 'duration': 5, 'aspect_ratio': '9:16'}
    r = requests.post(f'{API}/wizard/upsell-cinematic', json=body, timeout=30)
    check('F.1 status=200', r.status_code == 200, f'status={r.status_code} body={r.text[:300]}')
    if r.ok:
        data = r.json()
        # Either ok=true with estimated_credits, or ok=false with reason
        if data.get('ok') is True:
            need = {'ok', 'estimated_credits', 'current_day', 'current_month'}
            miss = need - set(data.keys())
            check('F.2 ok=true schema', not miss, f'missing={miss} data={data}')
            check('F.3 estimated_credits=50', data.get('estimated_credits') == 50,
                  f'estimated={data.get("estimated_credits")}')
        else:
            check('F.2 ok=false schema', 'reason' in data and data.get('ok') is False,
                  f'data={data}')
except Exception as e:
    check('F exception', False, str(e))


# ============ (G) Validation negatives (missing script in create-reel) ============
print('\n=== (G) Validation ===')
try:
    r = requests.post(f'{API}/wizard/create-reel',
                      json={'image_query': 'foo', 'voice_id': 'en-US-JennyNeural'},
                      timeout=15)
    check('G.1 missing script=422', r.status_code == 422, f'status={r.status_code}')
except Exception as e:
    check('G exception', False, str(e))


# ============ (H) Regression smoke ============
print('\n=== (H) Regression smoke ===')
for path, expected_len_key, expected_len in [
    ('/templates', None, None),
    ('/motion-presets', 'len', 8),
    ('/voice-styles', 'len', 5),
    ('/credits-info', None, None),
    ('/mode', None, None),
]:
    try:
        r = requests.get(f'{API}{path}', timeout=30)
        ok = r.status_code == 200
        detail = f'status={r.status_code}'
        if ok and expected_len_key:
            data = r.json()
            if isinstance(data, list):
                n = len(data)
            elif isinstance(data, dict):
                # find first list value
                n = None
                for k in ('presets', 'styles', 'items', 'motion_presets', 'voice_styles'):
                    if k in data and isinstance(data[k], list):
                        n = len(data[k]); break
                if n is None:
                    # try any list value
                    for v in data.values():
                        if isinstance(v, list):
                            n = len(v); break
            ok = (n == expected_len)
            detail += f' len={n} expected={expected_len}'
        check(f'H {path}', ok, detail)
    except Exception as e:
        check(f'H {path}', False, str(e))


# ============ (D) FULL PIPELINE ============
print('\n=== (D) FULL PIPELINE: create-reel + poll ===')
try:
    body = {
        "idea": "Morning meditation for Indian youth",
        "title": "Inner Peace",
        "script": "Take a deep breath. Feel the calm. Start your day with peace.",
        "image_query": "meditation yoga sunrise",
        "voice_id": "en-US-JennyNeural",
        "voice_style": "story",
        "music_mood": "cinematic_epic",
        "motion": "auto",
        "aspect_ratio": "9:16",
        "duration_per_shot": 2.5,
    }
    r = requests.post(f'{API}/wizard/create-reel', json=body, timeout=30)
    check('D.1 create-reel status=200', r.status_code == 200,
          f'status={r.status_code} body={r.text[:300]}')
    data = r.json() if r.ok else {}
    job_id = data.get('job_id')
    check('D.2 job_id present', bool(job_id), f'job_id={job_id}')
    check('D.3 status=queued', data.get('status') == 'queued',
          f'status={data.get("status")}')

    if job_id:
        final = None
        t0 = time.time()
        while time.time() - t0 < 90:
            time.sleep(3)
            jr = requests.get(f'{API}/wizard/job/{job_id}', timeout=15)
            if jr.ok:
                j = jr.json()
                print(f'  poll t={int(time.time()-t0)}s status={j.get("status")} stage={j.get("stage")} progress={j.get("progress")}')
                if j.get('status') in ('completed', 'failed'):
                    final = j
                    break
        check('D.4 job completed', final is not None and final.get('status') == 'completed',
              f'final_status={final and final.get("status")} error={final and final.get("error")}')
        if final and final.get('status') == 'completed':
            check('D.5 progress=100', final.get('progress') == 100, f'progress={final.get("progress")}')
            ru = final.get('result_url') or ''
            check('D.6 result_url prefix', ru.startswith('/api/serve-file/wz_reel_'),
                  f'result_url={ru}')
            check('D.7 has_voice=true', final.get('has_voice') is True, f'has_voice={final.get("has_voice")}')
            check('D.8 has_bgm=true', final.get('has_bgm') is True, f'has_bgm={final.get("has_bgm")}')
            dur = final.get('duration') or 0
            check('D.9 duration~=10s', 8.0 <= float(dur) <= 12.0, f'duration={dur}')
            # Verify direct localhost:8001 serve
            if ru:
                fname = ru.split('/')[-1]
                lr = requests.get(f'{LOCAL}/api/serve-file/{fname}', timeout=30)
                ctype = lr.headers.get('content-type', '')
                size = len(lr.content) if lr.ok else 0
                check('D.10 localhost serve-file 200', lr.status_code == 200,
                      f'status={lr.status_code}')
                check('D.11 content-type=video/mp4', 'video/mp4' in ctype, f'ctype={ctype}')
                check('D.12 size>100KB', size > 100 * 1024, f'size={size}')
except Exception as e:
    check('D exception', False, str(e))


# Summary
print('\n' + '=' * 60)
print(f'PASS: {len(PASS)}  FAIL: {len(FAIL)}')
if FAIL:
    print('\nFAILURES:')
    for n, d in FAIL:
        print(f'  - {n}: {d}')
