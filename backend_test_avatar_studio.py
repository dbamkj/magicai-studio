"""Backend tests for AI Avatar Studio — styles schema, dialogues endpoint,
cache, validation, moderation, regression for cartoonize + talking-avatar.

Usage: python3 /app/backend_test_avatar_studio.py
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
import traceback
from pathlib import Path

import requests

BASE = os.environ.get("BASE_URL") or "https://creative-plan-engine.preview.emergentagent.com"
API = f"{BASE}/api"

# Test creds from /app/memory/test_credentials.md
EMAIL = "demo_creator@test.com"
PASSWORD = "Test@123"

passes: list[str] = []
fails: list[tuple[str, str]] = []


def ok(name: str, detail: str = ""):
    msg = f"[PASS] {name}"
    if detail:
        msg += f" :: {detail}"
    print(msg, flush=True)
    passes.append(name)


def fail(name: str, detail: str):
    msg = f"[FAIL] {name} :: {detail}"
    print(msg, flush=True)
    fails.append((name, detail))


def expect(cond: bool, name: str, detail: str = ""):
    if cond:
        ok(name, detail)
    else:
        fail(name, detail)


# ---------------------------------------------------------------
# 0. LOGIN → token
# ---------------------------------------------------------------
def login() -> str:
    r = requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    r.raise_for_status()
    tok = r.json().get("token")
    assert tok, f"no token: {r.text[:300]}"
    print(f"Logged in as {EMAIL}. token_len={len(tok)}", flush=True)
    return tok


# ---------------------------------------------------------------
# 1. GET /api/avatar/styles — schema update
# ---------------------------------------------------------------
def test_styles_schema():
    r = requests.get(f"{API}/avatar/styles", timeout=20)
    expect(r.status_code == 200, "styles.status_200", f"got {r.status_code}")
    if r.status_code != 200:
        return
    data = r.json()

    # (b) categories array with 4 entries
    cats = data.get("categories")
    expect(isinstance(cats, list) and len(cats) == 4,
           "styles.categories.len4",
           f"got {cats if isinstance(cats, list) else type(cats)}")
    if isinstance(cats, list):
        ids = [c.get("id") for c in cats]
        expected_ids = ["indian", "funny", "spiritual", "influencer"]
        expect(set(ids) == set(expected_ids),
               "styles.categories.ids",
               f"got {ids}")
        for c in cats:
            expect(bool(c.get("label")) and bool(c.get("icon")),
                   f"styles.categories.{c.get('id')}.has_label_icon",
                   f"{c}")

    # (c) Each style has category + personality
    styles = data.get("styles") or []
    expect(len(styles) > 0, "styles.styles_nonempty", f"len={len(styles)}")

    missing_cat = []
    missing_pers = []
    for s in styles:
        if not s.get("category"):
            missing_cat.append(s.get("id"))
        p = s.get("personality")
        if not isinstance(p, dict):
            missing_pers.append(s.get("id"))
            continue
        required = ["voice_id", "voice_style", "mood", "bgm_style", "tone"]
        for k in required:
            if not p.get(k):
                missing_pers.append(f"{s.get('id')}.{k}")
    expect(len(missing_cat) == 0, "styles.each.has_category", f"missing={missing_cat}")
    expect(len(missing_pers) == 0, "styles.each.has_full_personality", f"missing={missing_pers}")

    # (d) specific mappings
    by_id = {s["id"]: s for s in styles if s.get("id")}

    def chk(sid, cat=None, voice_id=None, voice_style=None, mood=None):
        s = by_id.get(sid)
        if not s:
            fail(f"styles.specific.{sid}.present", "style missing")
            return
        p = s.get("personality") or {}
        if cat is not None:
            expect(s.get("category") == cat,
                   f"styles.{sid}.category", f"got {s.get('category')} expected {cat}")
        if voice_id is not None:
            expect(p.get("voice_id") == voice_id,
                   f"styles.{sid}.personality.voice_id", f"got {p.get('voice_id')}")
        if voice_style is not None:
            expect(p.get("voice_style") == voice_style,
                   f"styles.{sid}.personality.voice_style", f"got {p.get('voice_style')}")
        if mood is not None:
            expect(p.get("mood") == mood,
                   f"styles.{sid}.personality.mood", f"got {p.get('mood')}")

    chk("mythological", cat="spiritual", voice_id="hi-IN-MadhurNeural", voice_style="devotional")
    chk("cricket_champion", cat="indian", voice_style="motivation", mood="energetic")
    chk("pixar", cat="influencer")
    chk("comic", cat="funny")

    # (e) count field accurate
    expect(data.get("count") == len(styles),
           "styles.count_matches", f"count={data.get('count')} len={len(styles)}")


# ---------------------------------------------------------------
# 2. POST /api/avatar/dialogues — happy paths
# ---------------------------------------------------------------
def test_dialogues_hindi_mytho():
    body = {"style_id": "mythological", "idea": "Festival greeting for Diwali",
            "language": "hindi", "count": 3}
    t0 = time.time()
    r = requests.post(f"{API}/avatar/dialogues", json=body, timeout=60)
    dt = time.time() - t0
    expect(r.status_code == 200, "dialogues.hindi.status", f"got {r.status_code} body={r.text[:300]}")
    if r.status_code != 200:
        return None
    d = r.json()
    dlg = d.get("dialogues") or []
    expect(len(dlg) == 3, "dialogues.hindi.count3", f"got {len(dlg)}")
    # each dialogue id/text/tone
    expected_ids = {"d1", "d2", "d3"}
    got_ids = {x.get("id") for x in dlg}
    expect(got_ids == expected_ids, "dialogues.hindi.ids", f"got {got_ids}")
    for i, x in enumerate(dlg):
        expect(bool(x.get("text")), f"dialogues.hindi.d{i+1}.text_nonempty", "")
        expect(bool(x.get("tone")), f"dialogues.hindi.d{i+1}.tone_nonempty", "")
        # Devanagari check — at least one char in U+0900..U+097F
        has_deva = any('\u0900' <= ch <= '\u097f' for ch in (x.get("text") or ""))
        expect(has_deva, f"dialogues.hindi.d{i+1}.has_devanagari", f"text={x.get('text')[:80]}")
    pers = d.get("personality") or {}
    expect(pers.get("voice_id") == "hi-IN-MadhurNeural",
           "dialogues.hindi.personality.voice_id",
           f"got {pers.get('voice_id')}")
    src = d.get("source")
    expect(src in ("llm", "fallback"), "dialogues.hindi.source", f"got {src}")
    print(f"    … dialogues hindi t={dt:.2f}s source={src}", flush=True)
    return d


def test_dialogues_english_pixar():
    body = {"style_id": "pixar",
            "idea": "Motivate my team before a big launch",
            "language": "english", "count": 3}
    r = requests.post(f"{API}/avatar/dialogues", json=body, timeout=60)
    expect(r.status_code == 200, "dialogues.en.status", f"got {r.status_code}")
    if r.status_code != 200:
        return
    d = r.json()
    dlg = d.get("dialogues") or []
    expect(len(dlg) == 3, "dialogues.en.count3", f"got {len(dlg)}")
    # Texts should be mostly ASCII/english — no devanagari
    for i, x in enumerate(dlg):
        text = x.get("text") or ""
        has_deva = any('\u0900' <= ch <= '\u097f' for ch in text)
        expect(not has_deva, f"dialogues.en.d{i+1}.no_devanagari", f"text={text[:80]}")
        expect(bool(text.strip()), f"dialogues.en.d{i+1}.nonempty", "")
    pers = d.get("personality") or {}
    # pixar expected: voice_id=en-US-JennyNeural, tone="warm, cinematic, imaginative"
    tone_str = (pers.get("tone") or "").lower()
    expect("warm" in tone_str and "cinematic" in tone_str and "imaginative" in tone_str,
           "dialogues.en.personality.tone_pixar", f"got tone={pers.get('tone')}")


def test_dialogues_hinglish_desi():
    body = {"style_id": "desi_toon", "idea": "funny office moment",
            "language": "hinglish", "count": 3}
    r = requests.post(f"{API}/avatar/dialogues", json=body, timeout=60)
    expect(r.status_code == 200, "dialogues.hinglish.status", f"got {r.status_code}")
    if r.status_code != 200:
        return
    d = r.json()
    dlg = d.get("dialogues") or []
    expect(len(dlg) == 3, "dialogues.hinglish.count3", f"got {len(dlg)}")
    src = d.get("source")
    expect(src in ("llm", "fallback"), "dialogues.hinglish.source_ok", f"got {src}")
    # No hard language check but ensure all have text
    for i, x in enumerate(dlg):
        expect(bool((x.get("text") or "").strip()),
               f"dialogues.hinglish.d{i+1}.nonempty", f"text={x.get('text')}")


# ---------------------------------------------------------------
# 3. Caching
# ---------------------------------------------------------------
def test_dialogues_cache(first_call: dict | None):
    if not first_call:
        fail("dialogues.cache", "skipped — first call failed")
        return
    body = {"style_id": "mythological", "idea": "Festival greeting for Diwali",
            "language": "hindi", "count": 3}
    t0 = time.time()
    r = requests.post(f"{API}/avatar/dialogues", json=body, timeout=30)
    dt = time.time() - t0
    expect(r.status_code == 200, "dialogues.cache.status", f"got {r.status_code}")
    if r.status_code != 200:
        return
    d = r.json()
    expect(d.get("source") == "cache", "dialogues.cache.source", f"got {d.get('source')}")
    expect(d.get("cached") is True, "dialogues.cache.flag", f"got {d.get('cached')}")
    expect(dt < 0.5, "dialogues.cache.fast_<500ms", f"t={dt*1000:.0f}ms")
    # dialogue text byte-for-byte match
    prev_texts = [x.get("text") for x in (first_call.get("dialogues") or [])]
    cur_texts = [x.get("text") for x in (d.get("dialogues") or [])]
    expect(prev_texts == cur_texts, "dialogues.cache.texts_match",
           f"first={prev_texts}\n    curr={cur_texts}")


# ---------------------------------------------------------------
# 4. Validation
# ---------------------------------------------------------------
def test_validation_unknown_style():
    body = {"style_id": "does_not_exist", "idea": "something nice", "language": "english", "count": 3}
    r = requests.post(f"{API}/avatar/dialogues", json=body, timeout=20)
    expect(r.status_code == 400, "validation.unknown_style.400", f"got {r.status_code} body={r.text[:300]}")
    if r.status_code == 400:
        detail = r.json().get("detail", "")
        expect("Unknown style" in str(detail) or "valid" in str(detail).lower() or "pixar" in str(detail).lower(),
               "validation.unknown_style.detail_mentions_valid",
               f"got {detail}")


def test_validation_empty_idea():
    body = {"style_id": "pixar", "idea": "", "language": "english", "count": 3}
    r = requests.post(f"{API}/avatar/dialogues", json=body, timeout=20)
    expect(r.status_code == 422, "validation.empty_idea.422", f"got {r.status_code}")


def test_validation_count_too_high():
    body = {"style_id": "pixar", "idea": "motivational quote", "language": "english", "count": 10}
    r = requests.post(f"{API}/avatar/dialogues", json=body, timeout=20)
    expect(r.status_code == 422, "validation.count_10.422", f"got {r.status_code}")


# ---------------------------------------------------------------
# 5. Moderation gate
# ---------------------------------------------------------------
def test_moderation():
    body = {"style_id": "pixar",
            "idea": "how to fuck someone up badly and hurt them",
            "language": "english", "count": 3}
    r = requests.post(f"{API}/avatar/dialogues", json=body, timeout=20)
    expect(r.status_code == 400, "moderation.400", f"got {r.status_code} body={r.text[:300]}")
    if r.status_code == 400:
        try:
            detail = r.json().get("detail")
        except Exception:
            detail = r.text
        if isinstance(detail, dict):
            expect(detail.get("moderation_blocked") is True,
                   "moderation.detail_has_blocked_flag", f"detail={detail}")
        else:
            expect("moderation" in str(detail).lower() or "allow" in str(detail).lower() or "language" in str(detail).lower(),
                   "moderation.detail_generic", f"detail={detail}")


# ---------------------------------------------------------------
# 6. Regression — existing avatar endpoints
# ---------------------------------------------------------------
def _tiny_png_b64() -> str:
    # 1x1 transparent png
    return ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")


def _png_bytes() -> bytes:
    return base64.b64decode(_tiny_png_b64())


def test_regression_cartoonize(token: str):
    hdrs = {"Authorization": f"Bearer {token}"}
    body = {"style": "pixar", "image_b64": _tiny_png_b64(),
            "emotion": "happy", "prompt": "friendly developer portrait"}
    r = requests.post(f"{API}/avatar/cartoonize", json=body, headers=hdrs, timeout=30)
    expect(r.status_code == 200, "reg.cartoonize.status", f"got {r.status_code} body={r.text[:300]}")
    if r.status_code != 200:
        return None
    d = r.json()
    job_id = d.get("job_id")
    expect(bool(job_id), "reg.cartoonize.job_id", f"got {d}")
    return job_id


def test_regression_job_poll(job_id: str | None):
    if not job_id:
        fail("reg.jobs.get", "skipped — no job_id")
        return
    r = requests.get(f"{API}/avatar/jobs/{job_id}", timeout=20)
    expect(r.status_code == 200, "reg.jobs.get.status", f"got {r.status_code}")
    if r.status_code == 200:
        expect(bool(r.json().get("status")), "reg.jobs.get.has_status", f"{r.json()}")


def test_regression_talking_avatar(token: str):
    # Upload a tiny image first
    hdrs = {"Authorization": f"Bearer {token}"}
    png = _png_bytes()
    files = {"file": ("test.png", png, "image/png")}
    up = requests.post(f"{API}/upload-image", files=files, headers=hdrs, timeout=30)
    if up.status_code != 200:
        fail("reg.talking.upload_image", f"got {up.status_code} body={up.text[:200]}")
        return
    image_path = up.json().get("file_path")
    expect(bool(image_path), "reg.talking.upload_path", f"{up.json()}")

    body = {"image_path": image_path, "script": "hi there, quick test of talking avatar endpoint.",
            "voice_id": "hi-IN-SwaraNeural"}
    r = requests.post(f"{API}/create-talking-avatar", json=body, headers=hdrs, timeout=45)
    expect(r.status_code == 200, "reg.talking.status", f"got {r.status_code} body={r.text[:300]}")
    if r.status_code == 200:
        expect(bool(r.json().get("project_id")), "reg.talking.project_id", f"{r.json()}")


# ---------------------------------------------------------------
# 7. openapi.json — /api/avatar/dialogues registered exactly once (internal)
# ---------------------------------------------------------------
def test_openapi_single_registration():
    # External ingress strips non-/api; use internal 8001 for openapi.json
    url = "http://localhost:8001/openapi.json"
    try:
        r = requests.get(url, timeout=15)
    except Exception as e:
        fail("openapi.reachable", f"{e}")
        return
    expect(r.status_code == 200, "openapi.status", f"got {r.status_code}")
    if r.status_code != 200:
        return
    schema = r.json()
    paths = schema.get("paths") or {}
    key = "/api/avatar/dialogues"
    present = key in paths
    expect(present, "openapi.dialogues.registered", f"path found={present}")
    if present:
        methods = list((paths[key] or {}).keys())
        expect(methods == ["post"] or (len(methods) == 1 and methods[0] == "post"),
               "openapi.dialogues.only_post",
               f"got methods={methods}")
    # Also make sure no trailing-slash duplicate
    dupes = [p for p in paths if "avatar/dialogues" in p]
    expect(len(dupes) == 1, "openapi.dialogues.no_duplicates", f"got={dupes}")


# ---------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------
def main():
    print(f"BASE={BASE}", flush=True)
    print("=" * 72, flush=True)
    try:
        token = login()
    except Exception as e:
        fail("login", str(e))
        _summary()
        return

    print("\n--- 1. styles schema ---", flush=True)
    test_styles_schema()

    print("\n--- 2a. dialogues hindi mytho (+ 3. cache) ---", flush=True)
    first = test_dialogues_hindi_mytho()

    print("\n--- 2b. dialogues english pixar ---", flush=True)
    test_dialogues_english_pixar()

    print("\n--- 2c. dialogues hinglish desi ---", flush=True)
    test_dialogues_hinglish_desi()

    print("\n--- 3. cache (second call) ---", flush=True)
    test_dialogues_cache(first)

    print("\n--- 4. validation ---", flush=True)
    test_validation_unknown_style()
    test_validation_empty_idea()
    test_validation_count_too_high()

    print("\n--- 5. moderation ---", flush=True)
    test_moderation()

    print("\n--- 6. regression ---", flush=True)
    job_id = test_regression_cartoonize(token)
    test_regression_job_poll(job_id)
    test_regression_talking_avatar(token)

    print("\n--- 7. openapi ---", flush=True)
    test_openapi_single_registration()

    _summary()


def _summary():
    print("\n" + "=" * 72, flush=True)
    print(f"PASSES: {len(passes)}", flush=True)
    print(f"FAILS : {len(fails)}", flush=True)
    if fails:
        print("\nFailures:")
        for n, d in fails:
            print(f"  - {n} :: {d}")
    print("=" * 72, flush=True)


if __name__ == "__main__":
    main()
