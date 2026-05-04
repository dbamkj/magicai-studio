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
    monthly_bucket_for,
    utc_month_str,
    utc_today_str,
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
    quality_mode: Optional[str] = None,
) -> tuple[dict, int]:
    """Validate credits + plan + daily/monthly quota BEFORE starting a job.

    Returns (user_doc, cost_credits). Guest users in DEV bypass checks.
    """
    strict = IS_BETA or (not IS_DEV)
    user = await get_current_user(request, strict=strict)

    if user and 'user_id' not in user:
        user['user_id'] = user.get('id') or 'guest'

    # Guest bypass in DEV — no charges
    if user.get('user_id') == 'guest' or user.get('id') in (None, 'guest_default'):
        return user, 0

    # Plan-level feature access (session 34 — now passes quality_mode too)
    if feature:
        ok, reason = check_feature_access(
            user, feature=feature, duration=duration, shots=shots, quality_mode=quality_mode,
        )
        if not ok:
            raise HTTPException(status_code=402, detail=reason)

    # Daily quota (generic — image cap for Free is enforced via feature='image',
    # but also check here as a defense-in-depth for legacy callers).
    ok, reason = can_run_today(user, job_type=job_type)
    if not ok:
        raise HTTPException(status_code=429, detail=reason)

    # Credits
    cost = estimate_credits(
        job_type,
        duration=duration,
        face_swap=face_swap,
        lip_sync=lip_sync,
        shots=shots or 0,
        quality_mode=quality_mode,
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
    job_type: Optional[str] = None,
) -> None:
    """Deduct credits + bump daily/monthly counters. Optionally schedule Free-tier watermark.

    Session 34:
      * If `job_type` is provided, bump the matching monthly bucket
        (reels / lipsync / ai_videos / images) on the user doc and roll
        over `monthly_usage` + `monthly_usage_month` on month change.
      * For image jobs, also bump `daily_image_usage` to feed Free's
        5-image/day cap in `can_run_today`.
    """
    # Schedule watermark (best-effort, not blocking)
    if background_tasks is not None and project_id and (user_tier or "").lower() == "free":
        try:
            from server import apply_watermark_if_free  # type: ignore
            background_tasks.add_task(apply_watermark_if_free, project_id, user_tier, asset_kind)
        except Exception:
            pass

    if not user_id or cost <= 0:
        return

    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    month = utc_month_str()

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

    # Read minimal state to detect roll-overs
    u = await _db.users.find_one(
        {'id': user_id},
        {
            'daily_usage': 1, 'daily_usage_date': 1,
            'daily_image_usage': 1,
            'monthly_usage': 1, 'monthly_usage_month': 1,
        },
    )
    if not u:
        return

    set_ops: dict = {}
    inc_ops: dict = {'credits_balance': -cost}

    # Daily counters — reset on new day, else increment
    if u.get('daily_usage_date') != today:
        set_ops.update({
            'daily_usage_date': today,
            'daily_usage': 1,
            'daily_image_usage': 1 if (monthly_bucket_for(job_type or '') == 'images') else 0,
        })
    else:
        inc_ops['daily_usage'] = 1
        if monthly_bucket_for(job_type or '') == 'images':
            inc_ops['daily_image_usage'] = 1

    # Monthly counters — reset on new month, else increment relevant bucket
    bucket = monthly_bucket_for(job_type or '')
    if u.get('monthly_usage_month') != month:
        mu = {'reels': 0, 'lipsync': 0, 'ai_videos': 0, 'images': 0}
        if bucket:
            mu[bucket] = 1
        set_ops['monthly_usage_month'] = month
        set_ops['monthly_usage'] = mu
    elif bucket:
        inc_ops[f'monthly_usage.{bucket}'] = 1

    update_doc: dict = {'$inc': inc_ops}
    if set_ops:
        update_doc['$set'] = set_ops

    await _db.users.update_one({'id': user_id}, update_doc)


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
