"""MH credit circuit-breaker & budget guardrails.

Prevents runaway spend on our ₹1,350/mo MH Creator plan (10,000 MH credits).

Rules:
 1. Daily soft cap = 333 cr/day (10000 / 30).
 2. Per-user daily cap = 40% of their monthly quota.
 3. When daily budget exhausted, jobs queue to next day.
 4. Admin alerts fire at 80% of daily or monthly budget.

State lives in Mongo collection `mh_usage_daily` so it survives restarts.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

# Soft cap defaults (tunable by admin)
MONTHLY_BUDGET_CREDITS = 10_000
DAILY_SOFT_CAP = MONTHLY_BUDGET_CREDITS // 30  # ~333
ALERT_THRESHOLD_PCT = 0.80
PER_USER_DAILY_CAP_PCT = 0.40  # 40% of monthly user quota


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def _utc_month() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m')


async def can_spend(db, user_id: str, needed_credits: int, user_monthly_quota: int) -> dict:
    """Return {allowed: bool, reason, queued: bool, wait_hours, current_day, current_month}."""
    day = _utc_day()
    month = _utc_month()
    # Daily aggregate
    day_doc = await db.mh_usage_daily.find_one({'day': day}) or {'total': 0, 'by_user': {}}
    day_total = int(day_doc.get('total', 0))
    user_day = int(day_doc.get('by_user', {}).get(user_id, 0))
    # Monthly aggregate (sum)
    month_doc = await db.mh_usage_monthly.find_one({'month': month}) or {'total': 0}
    month_total = int(month_doc.get('total', 0))
    # User per-day cap
    per_user_cap = int(user_monthly_quota * PER_USER_DAILY_CAP_PCT)
    if user_day + needed_credits > per_user_cap and user_monthly_quota > 0:
        return {'allowed': False, 'reason': f'Per-user daily cap reached ({per_user_cap} cr). Come back tomorrow or buy an add-on.', 'queued': True, 'wait_hours': 24, 'current_day': day_total, 'current_month': month_total}
    # Daily global cap
    if day_total + needed_credits > DAILY_SOFT_CAP:
        return {'allowed': False, 'reason': 'Daily MH budget exhausted. Your job is queued for tomorrow.', 'queued': True, 'wait_hours': 24, 'current_day': day_total, 'current_month': month_total}
    # Monthly hard cap
    if month_total + needed_credits > MONTHLY_BUDGET_CREDITS:
        return {'allowed': False, 'reason': 'Monthly MH budget reached. Admin has been notified.', 'queued': False, 'wait_hours': 0, 'current_day': day_total, 'current_month': month_total}
    return {'allowed': True, 'reason': 'ok', 'queued': False, 'wait_hours': 0, 'current_day': day_total, 'current_month': month_total}


async def record_spend(db, user_id: str, credits: int, model: str = 'unknown'):
    day = _utc_day()
    month = _utc_month()
    await db.mh_usage_daily.update_one(
        {'day': day},
        {'$inc': {'total': credits, f'by_user.{user_id}': credits, f'by_model.{model}': credits}},
        upsert=True,
    )
    await db.mh_usage_monthly.update_one(
        {'month': month},
        {'$inc': {'total': credits, f'by_model.{model}': credits}},
        upsert=True,
    )


async def get_admin_usage(db) -> dict:
    """Return dashboard payload for /api/admin/mh-usage."""
    day = _utc_day()
    month = _utc_month()
    day_doc = await db.mh_usage_daily.find_one({'day': day}) or {}
    month_doc = await db.mh_usage_monthly.find_one({'month': month}) or {}
    day_total = int(day_doc.get('total', 0))
    month_total = int(month_doc.get('total', 0))
    projected = int(month_total * (30 / max(int(datetime.now(timezone.utc).strftime('%d')), 1)))
    by_user = day_doc.get('by_user', {})
    top_users = sorted(by_user.items(), key=lambda x: -int(x[1]))[:10]
    return {
        'day': day, 'day_total': day_total, 'daily_cap': DAILY_SOFT_CAP,
        'day_pct': round(day_total / DAILY_SOFT_CAP * 100, 1) if DAILY_SOFT_CAP else 0,
        'month': month, 'month_total': month_total, 'monthly_cap': MONTHLY_BUDGET_CREDITS,
        'month_pct': round(month_total / MONTHLY_BUDGET_CREDITS * 100, 1) if MONTHLY_BUDGET_CREDITS else 0,
        'projected_month_total': projected,
        'top_users_today': [{'user_id': u, 'credits': int(c)} for u, c in top_users],
        'by_model_day': day_doc.get('by_model', {}),
        'alert_active': (day_total >= DAILY_SOFT_CAP * ALERT_THRESHOLD_PCT) or (month_total >= MONTHLY_BUDGET_CREDITS * ALERT_THRESHOLD_PCT),
    }
