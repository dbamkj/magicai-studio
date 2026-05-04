"""Phase-4 backend test — POST /api/avatar/remix-dialogue.

Test plan (per review request):
  A) 4 styles × 3 variations each (rewrite/funny/emotional/viral)
  B) 5 input-validation cases
  C) source flag: when LLM healthy, source==llm AND variations are not
     the rule-based fallback strings.
  D) Regression sweep — cinematic-presets, detect-emotion, login.
"""
from __future__ import annotations

import os
import sys
import json
import time
from typing import Any

import requests

BASE = os.environ.get("BACKEND_URL") or "https://creative-plan-engine.preview.emergentagent.com"
API = f"{BASE}/api"
TIMEOUT = 60

BASE_TEXT = "Namaste doston, aaj ham Krishna ki kahani sunenge. Hari Om."

FALLBACK_TAGS = ("(rewritten)", "(funny version)", "(heart version)", "(viral hook version)")

results = []


def _record(name: str, ok: bool, detail: str = "") -> None:
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name} :: {detail}")
    results.append((name, ok, detail))


def _post(path: str, body: dict[str, Any]) -> requests.Response:
    return requests.post(f"{API}{path}", json=body, timeout=TIMEOUT)


def _get(path: str, **kwargs) -> requests.Response:
    return requests.get(f"{API}{path}", timeout=TIMEOUT, **kwargs)


# =====================================================================
# A) 4 styles, 3 variations each
# =====================================================================
print("\n=== A) Remix dialogue — 4 styles × 3 variations ===")
samples = {}
for style in ["rewrite", "funny", "emotional", "viral"]:
    body = {"text": BASE_TEXT, "style": style, "count": 3, "language": "hindi"}
    try:
        r = _post("/avatar/remix-dialogue", body)
        ok = r.status_code == 200
        if not ok:
            _record(f"A-{style}/200", False, f"status={r.status_code} body={r.text[:300]}")
            continue
        data = r.json()
        variations = data.get("variations") or []
        source = data.get("source")
        if len(variations) != 3:
            _record(f"A-{style}/3vars", False, f"got {len(variations)} variations")
            continue
        # Validate shape
        shape_ok = True
        for v in variations:
            if not (isinstance(v, dict) and v.get("id") and v.get("style") == style and isinstance(v.get("text"), str)):
                shape_ok = False
                break
            if len(v["text"].strip()) <= 10:
                shape_ok = False
                break
        if not shape_ok:
            _record(f"A-{style}/shape", False, f"variation shape invalid: {variations}")
            continue
        # Source field
        if source not in ("llm", "fallback"):
            _record(f"A-{style}/source", False, f"source={source!r}")
            continue
        samples[style] = {
            "source": source,
            "texts": [v["text"] for v in variations],
        }
        # Style-specific sanity
        first_lower = variations[0]["text"].lower()
        all_text_concat = " ".join(v["text"] for v in variations).lower()
        if style == "rewrite":
            topic_ok = any(k in all_text_concat for k in ["krishna", "hari om", "kahani"])
            _record(
                f"A-rewrite/topic_preserved",
                topic_ok,
                f"source={source} topic_kw_in_text={topic_ok} sample={variations[0]['text'][:140]!r}",
            )
        elif style == "funny":
            diff_from_input = all(v["text"].strip() != BASE_TEXT for v in variations)
            _record(
                f"A-funny/different_from_input",
                diff_from_input,
                f"source={source} diff={diff_from_input} sample={variations[0]['text'][:140]!r}",
            )
        elif style == "emotional":
            diff_from_input = all(v["text"].strip() != BASE_TEXT for v in variations)
            _record(
                f"A-emotional/different_from_input",
                diff_from_input,
                f"source={source} diff={diff_from_input} sample={variations[0]['text'][:140]!r}",
            )
        elif style == "viral":
            # Hook: opens with question, exclamation, or hook-y phrasing
            hook_chars = ("?", "!", "…")
            hook_words = ("you won't", "wait", "here's why", "did you", "imagine", "what if",
                           "क्या", "रुक", "देखो", "सुनो", "ज़रा", "अगर")
            t0 = variations[0]["text"].lstrip()
            # Strip common A:/B: prefix if present
            import re as _re
            t0_clean = _re.sub(r"^[AB][:：]\s*", "", t0).lstrip().lstrip("*")
            opens_with_hook = (
                any(c in t0_clean[:40] for c in hook_chars)
                or any(t0_clean.lower().startswith(w) for w in hook_words)
            )
            _record(
                f"A-viral/hook_first",
                opens_with_hook,
                f"source={source} hook={opens_with_hook} first={t0[:160]!r}",
            )

        # Print FULL sample outputs as required
        print(f"\n--- SAMPLE OUTPUTS for style={style} (source={source}) ---")
        for i, v in enumerate(variations):
            print(f"  [{v['id']}] {v['text']}")

        _record(f"A-{style}/all_checks", True, f"3 vars, source={source}")
    except Exception as e:
        _record(f"A-{style}/exception", False, repr(e))


# =====================================================================
# C) LLM source vs fallback content check
# =====================================================================
print("\n=== C) source==llm implies variations NOT rule-based ===")
for style, info in samples.items():
    if info["source"] == "llm":
        any_fallback = any(
            t.strip().endswith(FALLBACK_TAGS) for t in info["texts"]
        )
        _record(
            f"C-{style}/llm_not_rule_based",
            not any_fallback,
            f"source=llm any_endswith_fallback_tag={any_fallback}",
        )
    else:
        # Fallback path is acceptable; just print so reviewer sees it.
        print(f"  (style={style} returned source=fallback; skipped LLM-only check)")


# =====================================================================
# B) Input validation
# =====================================================================
print("\n=== B) Input validation ===")

# B1: empty text
r = _post("/avatar/remix-dialogue", {"text": "", "style": "funny"})
_record("B1/empty_text_422", r.status_code == 422, f"status={r.status_code} body={r.text[:200]}")

# B2: text length 3 (< min_length=4)
r = _post("/avatar/remix-dialogue", {"text": "abc", "style": "funny"})
_record("B2/text_len3_422", r.status_code == 422, f"status={r.status_code} body={r.text[:200]}")

# B3: unknown style
r = _post("/avatar/remix-dialogue", {"text": "hello world", "style": "cosmic"})
detail_str = ""
try:
    detail_str = json.dumps(r.json())
except Exception:
    detail_str = r.text
ok_b3 = r.status_code == 400 and ("Unknown style" in detail_str)
_record("B3/unknown_style_400", ok_b3, f"status={r.status_code} detail={detail_str[:200]}")

# B4: count=0
r = _post("/avatar/remix-dialogue", {"text": "hello world", "style": "funny", "count": 0})
_record("B4/count0_422", r.status_code == 422, f"status={r.status_code} body={r.text[:200]}")

# B5: count=6
r = _post("/avatar/remix-dialogue", {"text": "hello world", "style": "funny", "count": 6})
_record("B5/count6_422", r.status_code == 422, f"status={r.status_code} body={r.text[:200]}")


# =====================================================================
# D) Regression sweep
# =====================================================================
print("\n=== D) Regression sweep ===")
# D1
try:
    r = _get("/cinematic-presets")
    if r.status_code == 200:
        data = r.json()
        presets = data.get("presets") or data
        if isinstance(presets, list):
            count = len(presets)
        elif isinstance(presets, dict):
            count = len(presets)
        else:
            count = 0
        _record("D1/cinematic_presets_6", count == 6, f"status={r.status_code} count={count}")
    else:
        _record("D1/cinematic_presets_6", False, f"status={r.status_code} body={r.text[:200]}")
except Exception as e:
    _record("D1/cinematic_presets_6", False, repr(e))

# D2
try:
    r = _post("/avatar/detect-emotion", {"text": "happy day! 😊"})
    if r.status_code == 200:
        data = r.json()
        em = data.get("emotion")
        _record("D2/detect_emotion_happy", em == "happy", f"status=200 emotion={em}")
    else:
        _record("D2/detect_emotion_happy", False, f"status={r.status_code} body={r.text[:200]}")
except Exception as e:
    _record("D2/detect_emotion_happy", False, repr(e))

# D3
try:
    r = _post("/auth/login", {"email": "demo_creator@test.com", "password": "Test@123"})
    if r.status_code == 200:
        d = r.json()
        has_token = bool(d.get("token") or d.get("access_token"))
        _record("D3/login_demo_creator_200", has_token, f"status=200 has_token={has_token}")
    else:
        _record("D3/login_demo_creator_200", False, f"status={r.status_code} body={r.text[:200]}")
except Exception as e:
    _record("D3/login_demo_creator_200", False, repr(e))


# =====================================================================
# Summary
# =====================================================================
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed
print(f"Pass: {passed}/{total} | Fail: {failed}")
for name, ok, detail in results:
    if not ok:
        print(f"  FAIL  {name} :: {detail}")
sys.exit(0 if failed == 0 else 1)
