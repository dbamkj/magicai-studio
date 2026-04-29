"""Sprint 4 — Billing preflight + post-deduct helpers.

Usage inside any generation endpoint:
    from core.billing import preflight_and_reserve, settle_credits

    # at the top, before kicking off the background task
    user, cost = await preflight_and_reserve(request, job_type='video', duration=req.duration)
    # ... existing project-create logic ...
    await settle_credits(user['id'], cost)

`preflight_and_reserve` raises HTTPException on any failure (402 insufficient credits,
402 plan-locked feature, 429 daily cap). In DEV mode without a Bearer token, it returns
a guest user with infinite credits so existing tests keep working.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient

from core.config import MONGO_URL, DB_NAME, IS_BETA, IS_DEV, ENV
from core.auth import get_current_user
from core.pricing import (
    estimate_credits,
    can_run_today,
    check_feature_access,
)

_client = AsyncIOMotorClient(MONGO_URL)
_db = _client[DB_NAME]


async def preflight_and_reserve(
    request: Request,
    *,
    job_type: str,
    feature: Optional[str] = None,
    duration: Optional[int] = None,
    shots: Optional[int] = None,
    face_swap: bool = False,
    lip_sync: bool = False,
) -> tuple[dict, int]:
    """Validate credits + plan + daily quota BEFORE starting a job.

    Returns (user_doc, cost_credits). Guest users in DEV bypass checks.
    """
    # In BETA/PROD, require a valid JWT. In DEV, fall back to guest.
    strict = IS_BETA or (not IS_DEV)
    user = await get_current_user(request, strict=strict)

    # Normalize: ensure `user_id` key exists (legacy endpoints reference `user["user_id"]`).
    if user and 'user_id' not in user:
        user['user_id'] = user.get('id') or 'guest'

    # Guest bypass in DEV — no charges
    if user.get('user_id') == 'guest' or user.get('id') in (None, 'guest_default'):
        return user, 0

    # Plan-level feature access
    if feature:
        ok, reason = check_feature_access(user, feature=feature, duration=duration, shots=shots)
        if not ok:
            raise HTTPException(status_code=402, detail=reason)

    # Daily quota
    ok, reason = can_run_today(user)
    if not ok:
        raise HTTPException(status_code=429, detail=reason)

    # Credits
    cost = estimate_credits(
        job_type,
        duration=duration,
        face_swap=face_swap,
        lip_sync=lip_sync,
        shots=shots or 0,
    )
    balance = int(user.get('credits_balance', 0))
    if balance < cost:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits. Need {cost}, you have {balance}. Upgrade your plan or buy more.",
        )
    return user, cost


async def settle_credits(
    user_id: str,
    cost: int,
    *,
    user_tier: Optional[str] = None,
    project_id: Optional[str] = None,
    asset_kind: str = "video",
    background_tasks=None,
) -> None:
    """Deduct credits + bump daily_usage. Optionally schedule Free-tier watermark.

    If `background_tasks`, `project_id` and `user_tier` are provided, a watermark
    job will be queued for Free-tier users. Non-free tiers will be a no-op inside
    the watermark helper, but we skip scheduling to save an unused background task.
    """
    # Schedule watermark (best-effort, not blocking) -- imported lazily to avoid circular
    if background_tasks is not None and project_id and (user_tier or "").lower() == "free":
        try:
            from server import apply_watermark_if_free  # type: ignore
            background_tasks.add_task(apply_watermark_if_free, project_id, user_tier, asset_kind)
        except Exception:
            pass

    if not user_id or cost <= 0:
        return
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    # Persist the spent amount on the project so refund_credits_on_failure can find it
    if project_id:
        try:
            await _db.projects.update_one(
                {'id': project_id},
                {'$set': {'credits_spent': int(cost), 'refunded': False}},
            )
            await _db.video_projects.update_one(
                {'id': project_id},
                {'$set': {'credits_spent': int(cost), 'refunded': False}},
            )
        except Exception:
            pass

    # If today is a new day, reset daily_usage to 1; else increment by 1.
    user = await _db.users.find_one({'id': user_id}, {'daily_usage': 1, 'daily_usage_date': 1})
    if not user:
        return
    if user.get('daily_usage_date') != today:
        await _db.users.update_one(
            {'id': user_id},
            {
                '$inc': {'credits_balance': -cost},
                '$set': {'daily_usage_date': today, 'daily_usage': 1},
            },
        )
    else:
        await _db.users.update_one(
            {'id': user_id},
            {'$inc': {'credits_balance': -cost, 'daily_usage': 1}},
        )


async def refund_credits(
    user_id: str,
    cost: int,
    *,
    project_id: Optional[str] = None,
    reason: str = "job_failed",
) -> bool:
    """Trust feature — refund previously-deducted credits when a paid job fails.

    Idempotent — checks the project's `refunded` flag (if project_id given) and skips
    if already refunded. Emits an audit log so disputes can be reconciled.

    Returns True if a refund was actually applied, False otherwise.
    """
    if not user_id or cost <= 0:
        return False

    # Idempotency: if project already marked refunded, no-op.
    if project_id:
        existing = await _db.projects.find_one({'id': project_id}, {'refunded': 1})
        if existing and existing.get('refunded'):
            return False

    # Apply the refund — increment credits_balance back, decrement daily_usage if positive.
    await _db.users.update_one(
        {'id': user_id},
        {
            '$inc': {
                'credits_balance': int(cost),
                'daily_usage': -1,           # reverse the daily usage bump done in settle_credits
            },
        },
    )
    # Floor daily_usage at 0 in case of double-refund races
    await _db.users.update_one(
        {'id': user_id, 'daily_usage': {'$lt': 0}},
        {'$set': {'daily_usage': 0}},
    )

    # Mark project as refunded (idempotency anchor)
    if project_id:
        try:
            await _db.projects.update_one(
                {'id': project_id},
                {'$set': {
                    'refunded': True,
                    'refunded_at': datetime.now(timezone.utc),
                    'refund_amount': int(cost),
                    'refund_reason': reason,
                }},
            )
        except Exception:
            pass

    # Append audit row
    try:
        await _db.credit_refunds.insert_one({
            'user_id': user_id,
            'project_id': project_id,
            'amount': int(cost),
            'reason': reason,
            'created_at': datetime.now(timezone.utc),
        })
    except Exception:
        pass

    import logging
    logging.getLogger('billing').info(
        "credits refunded: user=%s amount=%d project=%s reason=%s",
        user_id, cost, project_id, reason,
    )
    return True
