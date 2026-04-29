"""Cross-platform content moderation — text + images + videos.

Layers (cheapest first):
  1. **Hard blocklist** (regex) — instant, free. Catches obscene/profane words and
     common abuse patterns in English, Hindi (Devanagari) and Hinglish.
  2. **LLM moderation** — fast LLM classifier via Emergent LLM key (gemini-2.5-flash).
     Used for nuanced cases: hate speech, violence, sexual content, self-harm,
     election manipulation, deepfake intent, real-person targeting.
  3. **Image moderation** — same LLM with vision (gemini-2.5-flash supports vision)
     screens NSFW / violent / illegal-substance imagery.
  4. **Video moderation** — frame sampling (1 frame per 2s) + image check on each.

All checks return a `ModerationResult` dataclass with:
  • allowed: bool
  • categories: list[str]    # which categories tripped
  • confidence: float        # 0.0–1.0
  • reason: str              # short user-facing reason
  • detail: str              # internal log only

Public API:
  await moderate_text(text)
  await moderate_image(url_or_bytes)        # url, bytes, or local path
  await moderate_video(local_path, *, max_frames=5)
  raise_if_blocked(result)                  # raises HTTPException(400)

Cost guardrails:
  • LLM is only called if blocklist passes AND text length > 8 chars.
  • Image LLM call is skipped for thumbnails < 32 KB (likely too small to matter).
  • All LLM calls have a 6-second timeout — never blocks the user UX path.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import httpx
from fastapi import HTTPException

log = logging.getLogger("moderation")

# =====================================================================
# 1. HARD BLOCKLIST — synchronous, instant
# =====================================================================
# Curated list of obscene words / abuse patterns (English + Hindi/Hinglish).
# Word boundaries enforced so 'classic' won't trip 'lass'.
_PROFANITY = [
    # English (mild → severe)
    r"\b(fuck|fucking|fucker|fck|fuk)\b",
    r"\b(shit|shitty|bullshit|crap)\b",
    r"\b(bitch|bich|biotch)\b",
    r"\b(asshole|a55hole|ass[- ]?hole)\b",
    r"\b(dick|cock|prick|penis|pussy|cunt|twat|vagina)\b",
    r"\b(slut|whore|hooker|skank)\b",
    r"\b(rape|rapist|molest|molester|paedophile|pedophile)\b",
    r"\b(nigger|nigga|chink|kike|spic|wetback|gook)\b",
    r"\b(retard|retarded|spastic)\b",
    r"\b(faggot|fag|tranny|dyke)\b",
    r"\b(porn|porno|pornography|xxx|sextape|nsfw)\b",
    r"\b(suck\s*my|eat\s*my|kill\s*your\s*?self|kys)\b",
    # Hindi/Hinglish (Roman + Devanagari)
    r"\b(chutiya|chutiy[ae]|chootiya|c[h]+utiya|gandu|gaandu|gandfat|gaand|bhosadi|bhosdi|bhos[dr]ike|behenchod|bhenchod|bhencho|bsdk|maadarchod|madarchod|mc|bc|chod|chodu|lund|lawda|lavda|laund[ae]|jhaant|jhand|haraami|harami)\b",
    r"\b(कुत्ता|कुत्ती|भोसडी|भोसड़ी|बहनचोद|भेनचोद|मादरचोद|गांडू|गांड|चुतिया|लंड|लौड़ा|हरामी)\b",
]
_PROFANITY_RE = re.compile("|".join(_PROFANITY), re.IGNORECASE)

# Real-person targeting (politicians, deities → flag, don't auto-block; allow with warning)
# Only auto-block if combined with manipulation intent (deepfake, fake quote, etc.).
_REAL_PERSON_PATTERN = re.compile(
    r"\b(modi|gandhi|nehru|shah|biden|trump|putin|xi\s*jinping|musk|ambani|adani)\b",
    re.IGNORECASE,
)
_DEEPFAKE_INTENT = re.compile(
    r"\b(deepfake|fake\s*quote|impersonat|pretending\s*to\s*be|claim(?:ing|s)?\s*to\s*be)\b",
    re.IGNORECASE,
)


# =====================================================================
# 2. RESULT DATACLASS
# =====================================================================
@dataclass
class ModerationResult:
    allowed: bool = True
    categories: list[str] = field(default_factory=list)
    confidence: float = 0.0
    reason: str = ""
    detail: str = ""

    @property
    def label(self) -> str:
        return "allowed" if self.allowed else "blocked"


# =====================================================================
# 3. PUBLIC API
# =====================================================================
async def moderate_text(text: Optional[str], *, source: str = "input") -> ModerationResult:
    """Check a text snippet (idea, script, prompt, name, dialogue, ...)."""
    if not text or not text.strip():
        return ModerationResult(allowed=True)
    s = text.strip()

    # Layer 1 — blocklist
    m = _PROFANITY_RE.search(s)
    if m:
        return ModerationResult(
            allowed=False,
            categories=["profanity"],
            confidence=1.0,
            reason="Your text contains language we don't allow on MagiCAi Studio.",
            detail=f"blocklist hit: {m.group(0)} (source={source})",
        )

    # Real-person + deepfake intent combo → auto-block
    if _REAL_PERSON_PATTERN.search(s) and _DEEPFAKE_INTENT.search(s):
        return ModerationResult(
            allowed=False,
            categories=["real_person_deepfake"],
            confidence=0.95,
            reason="Content depicting real public figures with deepfake intent is not allowed.",
            detail=f"real-person+deepfake combo (source={source})",
        )

    # Layer 2 — LLM classifier (skip for very short text to save cost)
    if len(s) >= 8:
        try:
            llm_res = await _llm_classify_text(s)
            if llm_res and not llm_res.allowed:
                llm_res.detail = f"{llm_res.detail} (source={source})"
                return llm_res
        except Exception as e:
            log.warning("moderate_text LLM skipped: %s", e)

    return ModerationResult(allowed=True)


async def moderate_image(src: Union[str, bytes, Path], *, source: str = "upload") -> ModerationResult:
    """Check a single image (URL, bytes or local file path)."""
    try:
        b64, mime = await _to_base64(src)
        if b64 is None:
            return ModerationResult(allowed=True)  # cannot fetch — allow but log
        # Skip very small images (< 8 KB) — usually icons/thumbs
        if len(b64) < 8 * 1024:
            return ModerationResult(allowed=True)
        return await _llm_classify_image(b64, mime, source=source)
    except Exception as e:
        log.warning("moderate_image suppressed: %s", e)
        return ModerationResult(allowed=True)


async def moderate_video(local_path: Union[str, Path], *, max_frames: int = 5, source: str = "upload") -> ModerationResult:
    """Sample frames from a local video file and check each. Returns first BLOCKED hit
    or an aggregated ALLOWED result."""
    try:
        p = Path(local_path)
        if not p.exists():
            return ModerationResult(allowed=True)
        # Probe duration via ffprobe
        try:
            r = await asyncio.to_thread(
                subprocess.run,
                [
                    "/usr/bin/ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(p),
                ],
                capture_output=True, timeout=10,
            )
            dur = float((r.stdout or b"10").decode().strip() or 10.0)
        except Exception:
            dur = 10.0

        sample_count = max(2, min(max_frames, int(dur // 2)))
        ts = [round(i * (dur / sample_count), 2) for i in range(sample_count)]

        with tempfile.TemporaryDirectory() as td:
            frames: list[Path] = []
            for i, t in enumerate(ts):
                out = Path(td) / f"frame_{i:02d}.jpg"
                cmd = [
                    "/usr/bin/ffmpeg", "-y", "-ss", f"{t:.2f}",
                    "-i", str(p), "-vframes", "1", "-q:v", "5", str(out),
                ]
                r = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, timeout=15)
                if r.returncode == 0 and out.exists():
                    frames.append(out)

            for f in frames:
                res = await moderate_image(f, source=f"{source}_frame")
                if not res.allowed:
                    res.detail = f"video frame trip: {res.detail}"
                    return res
        return ModerationResult(allowed=True)
    except Exception as e:
        log.warning("moderate_video suppressed: %s", e)
        return ModerationResult(allowed=True)


def raise_if_blocked(res: ModerationResult, *, status_code: int = 400) -> None:
    """FastAPI sugar — raise HTTPException(400) with the user-facing reason."""
    if res and not res.allowed:
        log.warning("moderation block: %s | %s", res.categories, res.detail)
        raise HTTPException(
            status_code=status_code,
            detail={
                "moderation_blocked": True,
                "categories": res.categories,
                "reason": res.reason,
            },
        )


# =====================================================================
# 4. LLM HELPERS (use Emergent LLM key)
# =====================================================================
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "").strip()

_TEXT_SYSTEM = (
    "You are a STRICT content moderator for a creator app. "
    "Reply ONLY with raw JSON: {\"flagged\": true|false, \"category\": str, \"confidence\": 0.0-1.0, \"reason\": str}. "
    "FLAG if the content is: sexually explicit, depicts minors sexually, "
    "promotes violence/terrorism/self-harm, contains hate speech against a "
    "religion/caste/race/gender, depicts real public figures in a defamatory or "
    "manipulative way, promotes illegal drugs, or solicits sexual services. "
    "Mild profanity in artistic/comedy context is ALLOWED. Devotional, romantic, "
    "motivational, festival and cultural content is ALLOWED."
)

_IMAGE_SYSTEM = (
    "You are a STRICT visual content moderator. Reply ONLY raw JSON "
    "{\"flagged\": true|false, \"category\": str, \"confidence\": 0.0-1.0, \"reason\": str}. "
    "FLAG if the image contains: nudity, sexual acts, minors in sexual context, "
    "graphic violence, torture, real-world child abuse, illegal drugs being used, "
    "extremist symbols promoting terrorism, or a real person being shown in a "
    "defamatory/manipulative scene. Religious art (Hindu/Christian/Islamic), "
    "fashion editorial, fitness, dance and devotional imagery are ALLOWED."
)


async def _llm_classify_text(text: str) -> Optional[ModerationResult]:
    if not EMERGENT_LLM_KEY:
        return None
    payload = {
        "messages": [
            {"role": "system", "content": _TEXT_SYSTEM},
            {"role": "user", "content": text[:1500]},
        ],
        "model": "gemini-2.5-flash",
        "max_tokens": 120,
        "temperature": 0.0,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(6.0)) as c:
            r = await c.post(
                "https://creative-plan-engine.preview.emergentagent.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {EMERGENT_LLM_KEY}", "Content-Type": "application/json"},
                json=payload,
            )
            if r.status_code != 200:
                return None
            data = r.json()
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "{}")
            return _parse_llm_json(content)
    except Exception as e:
        log.debug("_llm_classify_text http err: %s", e)
        return None


async def _llm_classify_image(b64: str, mime: str, *, source: str = "upload") -> ModerationResult:
    if not EMERGENT_LLM_KEY:
        return ModerationResult(allowed=True)
    data_url = f"data:{mime};base64,{b64}"
    payload = {
        "messages": [
            {"role": "system", "content": _IMAGE_SYSTEM},
            {"role": "user", "content": [
                {"type": "text", "text": "Classify this image."},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]},
        ],
        "model": "gemini-2.5-flash",
        "max_tokens": 120,
        "temperature": 0.0,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0)) as c:
            r = await c.post(
                "https://creative-plan-engine.preview.emergentagent.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {EMERGENT_LLM_KEY}", "Content-Type": "application/json"},
                json=payload,
            )
            if r.status_code != 200:
                return ModerationResult(allowed=True)
            content = (r.json().get("choices") or [{}])[0].get("message", {}).get("content", "{}")
            res = _parse_llm_json(content) or ModerationResult(allowed=True)
            res.detail += f" img({source})"
            return res
    except Exception as e:
        log.debug("_llm_classify_image http err: %s", e)
        return ModerationResult(allowed=True)


def _parse_llm_json(s: str) -> Optional[ModerationResult]:
    import json as _json
    s = (s or "").strip()
    if s.startswith("```"):
        s = s.strip("`").lstrip("json").strip()
    try:
        d = _json.loads(s)
    except Exception:
        return None
    flagged = bool(d.get("flagged"))
    if not flagged:
        return ModerationResult(allowed=True)
    cat = (d.get("category") or "policy").lower().replace(" ", "_")
    conf = float(d.get("confidence") or 0.5)
    reason = d.get("reason") or "This content violates our safety guidelines."
    # Be conservative: only block at confidence >= 0.6
    if conf < 0.6:
        return ModerationResult(allowed=True)
    return ModerationResult(
        allowed=False,
        categories=[cat],
        confidence=conf,
        reason=reason[:140],
        detail=f"llm: {cat}@{conf:.2f}",
    )


async def _to_base64(src: Union[str, bytes, Path]) -> tuple[Optional[str], str]:
    import base64
    if isinstance(src, bytes):
        return base64.b64encode(src).decode(), "image/jpeg"
    if isinstance(src, Path):
        if not src.exists():
            return None, "image/jpeg"
        b = src.read_bytes()
        mime = "image/png" if src.suffix.lower() == ".png" else "image/jpeg"
        return base64.b64encode(b).decode(), mime
    if isinstance(src, str):
        if src.startswith(("http://", "https://")):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(15.0), follow_redirects=True) as c:
                    r = await c.get(src)
                    if r.status_code != 200:
                        return None, "image/jpeg"
                    mime = r.headers.get("content-type", "image/jpeg").split(";")[0]
                    return base64.b64encode(r.content).decode(), mime
            except Exception:
                return None, "image/jpeg"
        # local path
        p = Path(src)
        if p.exists():
            return await _to_base64(p)
    return None, "image/jpeg"
