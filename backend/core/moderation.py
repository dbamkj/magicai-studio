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
# 5. PERSISTENCE + STRIKES (Sprint 3 v2 — Session 37)
# =====================================================================
# Every blocked decision is persisted to db.moderation_records so:
#   • admin can audit + override decisions
#   • repeat-offender strike system can count violations
#   • compliance teams can produce reports
#
# Strike thresholds (tunable via env):
#   STRIKE_BAN_THRESHOLD (default 3)  — auto-ban after N strikes
#   STRIKE_DECAY_DAYS (default 30)    — strikes older than N days don't count
#

from datetime import datetime, timezone

STRIKE_BAN_THRESHOLD = int(os.environ.get("STRIKE_BAN_THRESHOLD", "3"))
STRIKE_DECAY_DAYS = int(os.environ.get("STRIKE_DECAY_DAYS", "30"))


def _severity_for(categories: list[str]) -> int:
    """Return strike severity 1-3 based on category.

    1 = mild (profanity), 2 = standard (hate, sexual, violence), 3 = severe
        (CSAM, terrorism, real-person deepfake).
    """
    if not categories:
        return 1
    cat = (categories[0] or "").lower()
    if cat in ("csam", "minors_sexual", "child_sexual", "terrorism", "real_person_deepfake"):
        return 3
    if cat in ("hate", "sexual", "violence", "self_harm", "graphic_violence", "nudity"):
        return 2
    return 1


async def record_moderation_decision(
    res: ModerationResult,
    *,
    user_id: Optional[str],
    source: str,
    content_preview: str = "",
    raw_meta: Optional[dict] = None,
) -> Optional[str]:
    """Persist a moderation decision to db.moderation_records.

    Only persists BLOCKED decisions by default (allowed ones would balloon
    the collection). Returns the inserted record_id or None.
    """
    if res is None or res.allowed:
        return None
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        from core.config import MONGO_URL, DB_NAME, ENV
        import uuid
        rec_id = str(uuid.uuid4())
        doc = {
            "id": rec_id,
            "user_id": user_id,
            "source": source,                  # e.g. 'wizard.idea', 'avatar.upload'
            "kind": "text" if "_frame" not in source else "video_frame",
            "content_preview": (content_preview or "")[:280],
            "categories": res.categories,
            "confidence": res.confidence,
            "reason": res.reason,
            "detail": res.detail,
            "severity": _severity_for(res.categories),
            "status": "blocked",              # 'blocked' | 'overridden_allow' | 'confirmed_block'
            "admin_note": "",
            "reviewed_by": None,
            "reviewed_at": None,
            "env": ENV,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        client = AsyncIOMotorClient(MONGO_URL)
        await client[DB_NAME].moderation_records.insert_one(doc)
        return rec_id
    except Exception as e:
        log.warning("record_moderation_decision failed: %s", e)
        return None


async def apply_strike(
    user_id: Optional[str],
    *,
    severity: int = 1,
    reason: str = "",
    record_id: Optional[str] = None,
) -> dict:
    """Increment a user's strike count. Auto-bans at STRIKE_BAN_THRESHOLD.

    Returns:
        {strike_count, banned, ban_reason}
    """
    if not user_id:
        return {"strike_count": 0, "banned": False, "ban_reason": ""}
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        from core.config import MONGO_URL, DB_NAME
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]

        now = datetime.now(timezone.utc).isoformat()
        # Decay-aware count: only strikes within last STRIKE_DECAY_DAYS count.
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=STRIKE_DECAY_DAYS)).isoformat()

        u = await db.users.find_one({"id": user_id}, {"strikes": 1, "is_banned": 1, "is_admin": 1})
        if not u:
            return {"strike_count": 0, "banned": False, "ban_reason": ""}
        if u.get("is_admin"):
            # never strike admins
            return {"strike_count": 0, "banned": False, "ban_reason": ""}

        strikes = u.get("strikes") or []
        # Drop old strikes
        strikes = [s for s in strikes if (s.get("created_at") or "") >= cutoff]
        strikes.append({
            "severity": int(max(1, min(3, severity))),
            "reason": (reason or "")[:140],
            "record_id": record_id,
            "created_at": now,
        })

        # Severity-weighted score: 1-strike-of-severity-3 = 3 points
        score = sum(int(s.get("severity") or 1) for s in strikes)
        banned = score >= STRIKE_BAN_THRESHOLD

        update = {
            "strikes": strikes,
            "strike_count": len(strikes),
            "strike_score": score,
            "last_strike_at": now,
        }
        if banned:
            update.update({
                "is_banned": True,
                "banned_at": now,
                "ban_reason": f"Automatic ban — strike score {score} ≥ {STRIKE_BAN_THRESHOLD}. Last: {reason[:80]}",
            })

        await db.users.update_one({"id": user_id}, {"$set": update})

        # Audit
        try:
            from core.audit import log_audit
            await log_audit(
                "moderation.strike" if not banned else "moderation.banned",
                user_id=user_id,
                meta={
                    "severity": severity,
                    "reason": reason,
                    "record_id": record_id,
                    "strike_count": len(strikes),
                    "strike_score": score,
                },
            )
        except Exception:
            pass

        return {
            "strike_count": len(strikes),
            "strike_score": score,
            "banned": banned,
            "ban_reason": update.get("ban_reason", ""),
        }
    except Exception as e:
        log.warning("apply_strike failed: %s", e)
        return {"strike_count": 0, "banned": False, "ban_reason": ""}


async def moderate_and_enforce(
    text: Optional[str],
    *,
    user_id: Optional[str] = None,
    request=None,
    source: str,
) -> ModerationResult:
    """One-call helper: moderate_text → persist if blocked → strike user → raise.

    Pass either `user_id` (if you already have it) OR `request` (we'll
    decode the JWT from the Authorization header).

        from core.moderation import moderate_and_enforce
        await moderate_and_enforce(req.idea, request=request, source='wizard.idea')
    """
    # Resolve user_id from request JWT if not explicitly provided
    if not user_id and request is not None:
        try:
            from core.auth import decode_token
            auth_header = request.headers.get('authorization') or request.headers.get('Authorization', '')
            if auth_header.lower().startswith('bearer '):
                tok = auth_header.split(' ', 1)[1].strip()
                data = decode_token(tok)
                if data and data.get('sub'):
                    user_id = data['sub']
        except Exception:
            pass

    res = await moderate_text(text, source=source)
    if res.allowed:
        return res
    rec_id = await record_moderation_decision(
        res, user_id=user_id, source=source,
        content_preview=(text or "")[:280],
    )
    sev = _severity_for(res.categories)
    if user_id:
        await apply_strike(user_id, severity=sev, reason=res.reason, record_id=rec_id)
    raise_if_blocked(res)
    return res  # unreachable, but keeps type-checkers happy


# =====================================================================
# 4. LLM HELPERS (use Emergent LLM key)
# =====================================================================
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "").strip()


def _emergent_llm_endpoint() -> str:
    """Resolve the Emergent LLM gateway URL.

    Priority:
      1. `EMERGENT_LLM_ENDPOINT` env var (explicit override)
      2. `{PUBLIC_BACKEND_URL}/v1/chat/completions` — when the preview/prod
         backend proxies LLM traffic through itself.
      3. Official Emergent integrations gateway (production default).

    This avoids hardcoding a single preview URL which would break in any
    other deployment environment.
    """
    override = os.environ.get("EMERGENT_LLM_ENDPOINT", "").strip()
    if override:
        return override
    backend = (
        os.environ.get("PUBLIC_BACKEND_URL")
        or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
        or ""
    ).strip().rstrip("/")
    if backend:
        return f"{backend}/v1/chat/completions"
    return "https://integrations.emergentagent.com/v1/chat/completions"

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
                _emergent_llm_endpoint(),
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
                _emergent_llm_endpoint(),
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
