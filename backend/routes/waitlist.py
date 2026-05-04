"""Waitlist signup — landing-page email capture for Beta v1.

Storage: db.waitlist  (one doc per email, idempotent).
Schema:
    {
      email: str (lowercased, unique key),
      name: Optional[str],
      source: Optional[str]  e.g. 'landing', 'twitter', 'reddit'
      tier_interest: Optional[str]  'free' | 'starter' | 'creator' | 'pro'
      utm: Optional[dict]
      created_at: datetime,
      invited: bool (default False),
      invited_at: Optional[datetime],
      meta: dict — IP, user-agent for spam triage
    }

Invariants:
  * Same email POSTed twice → 200 with `already_signed_up: True`
    (no duplicate row, idempotent).
  * Public endpoint, no auth required.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from core.db import db

log = logging.getLogger("routes.waitlist")
router = APIRouter(prefix="/api", tags=["waitlist"])


# ─────────────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────────────
class WaitlistSignup(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    source: Optional[str] = "landing"
    tier_interest: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None


_VALID_TIERS = {"free", "starter", "creator", "pro"}
_NAME_RE = re.compile(r"[<>{}\\\"';`]")  # very basic injection guard for name field


# ─────────────────────────────────────────────────────────────────────
# POST /api/waitlist-signup — public email capture
# ─────────────────────────────────────────────────────────────────────
@router.post("/waitlist-signup")
async def waitlist_signup(payload: WaitlistSignup, request: Request):
    """Add an email to the beta waitlist. Idempotent — same email returns
    `already_signed_up: True` instead of duplicating.
    """
    email = payload.email.lower().strip()
    name = (payload.name or "").strip()[:80]
    if name and _NAME_RE.search(name):
        raise HTTPException(status_code=400, detail="Name contains invalid characters.")

    tier = (payload.tier_interest or "").lower().strip() or None
    if tier and tier not in _VALID_TIERS:
        tier = None  # silently ignore garbage

    # Idempotency: check existing
    existing = await db.waitlist.find_one({"email": email}, {"_id": 0, "email": 1, "created_at": 1})
    if existing:
        position = await db.waitlist.count_documents({
            "created_at": {"$lte": existing.get("created_at") or datetime.now(timezone.utc)}
        })
        return {
            "ok": True,
            "already_signed_up": True,
            "email": email,
            "position": position,
            "message": "You're already on the list — we'll email you when a slot opens up.",
        }

    # Spam triage metadata
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:200]

    doc = {
        "email": email,
        "name": name or None,
        "source": (payload.source or "landing").strip()[:30],
        "tier_interest": tier,
        "utm": {
            "source": (payload.utm_source or "")[:60] or None,
            "medium": (payload.utm_medium or "")[:60] or None,
            "campaign": (payload.utm_campaign or "")[:60] or None,
        },
        "created_at": datetime.now(timezone.utc),
        "invited": False,
        "invited_at": None,
        "meta": {"ip": ip, "ua": ua},
    }
    await db.waitlist.insert_one(doc)

    # Position = ordinal in list (1-indexed by created_at)
    position = await db.waitlist.count_documents({})

    log.info("waitlist signup: %s (%s) #%d source=%s tier=%s",
             email, name or "anon", position, payload.source, tier)

    return {
        "ok": True,
        "already_signed_up": False,
        "email": email,
        "position": position,
        "message": (
            f"You're #{position} on the list! We're inviting users in batches of 5 — "
            f"watch your inbox."
        ),
    }


# ─────────────────────────────────────────────────────────────────────
# GET /api/waitlist-stats — public summary for the landing page counter
# ─────────────────────────────────────────────────────────────────────
@router.get("/waitlist-stats")
async def waitlist_stats():
    """Public counter — drives 'Join 247 creators on the list' banner."""
    total = await db.waitlist.count_documents({})
    invited = await db.waitlist.count_documents({"invited": True})
    return {
        "total": total,
        "invited": invited,
        "remaining_seats": max(0, 20 - invited),  # Phase 1 cap = 20 paying users
    }


# ─────────────────────────────────────────────────────────────────────
# GET /api/admin/waitlist — admin-only list view (Bearer token + admin role)
# ─────────────────────────────────────────────────────────────────────
@router.get("/admin/waitlist")
async def admin_waitlist(request: Request, limit: int = 100, only_uninvited: bool = False):
    """Admin export — full waitlist with filters. Used by the Admin tab to
    pick the next batch of 5 invitees."""
    from core.auth import get_current_user
    user = await get_current_user(request)
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin only.")
    q: dict = {}
    if only_uninvited:
        q["invited"] = False
    cur = db.waitlist.find(q, {"_id": 0, "meta": 0}).sort("created_at", 1).limit(min(limit, 500))
    rows = await cur.to_list(length=limit)
    return {"total": len(rows), "items": rows}
