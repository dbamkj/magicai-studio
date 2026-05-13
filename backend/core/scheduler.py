"""Phase 3 — Lightweight nightly scheduler.

Instead of APScheduler (heavy dep + process model issues with uvicorn
--reload), we spin a long-running asyncio task at FastAPI startup that
sleeps until the next 02:00 UTC window and then calls
`recompute_all(db)` from core.trending.

Tolerant to:
  * Uvicorn auto-reload (task is cancelled + restarted each reload — safe)
  * Server crashes (task dies with process; next restart re-schedules)
  * Manual trigger via /api/admin/trending/recompute at any time
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

import httpx

from core.trending import recompute_all

EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send'


async def _send_expo_push(tokens: list, title: str, body: str, data: dict | None = None) -> dict:
    """Send an Expo push payload to one or more tokens.

    Session 27g: tolerant — returns `{sent:int, failed:int, errors:[...]}` but
    does not raise. Falls back to no-op if no tokens are given.
    """
    tokens = [t for t in (tokens or []) if isinstance(t, str) and t.startswith('ExponentPushToken')]
    if not tokens:
        return {'sent': 0, 'failed': 0, 'errors': []}
    msgs = [{'to': t, 'title': title, 'body': body, 'sound': 'default', 'data': data or {}, 'priority': 'high'} for t in tokens]
    sent, failed, errors = 0, 0, []
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0)) as c:
            r = await c.post(EXPO_PUSH_URL, json=msgs, headers={'Accept': 'application/json', 'Content-Type': 'application/json'})
            if r.status_code == 200:
                data_r = r.json()
                items = data_r.get('data') if isinstance(data_r, dict) else data_r
                for item in (items or []):
                    if isinstance(item, dict) and item.get('status') == 'ok':
                        sent += 1
                    else:
                        failed += 1
                        errors.append(item)
            else:
                failed = len(tokens)
                errors.append({'status': r.status_code, 'body': r.text[:160]})
    except Exception as e:
        failed = len(tokens)
        errors.append(str(e))
    return {'sent': sent, 'failed': failed, 'errors': errors}

logger = logging.getLogger("scheduler")
logger.setLevel(logging.INFO)

_running_task = None
_trial_task = None


async def _expire_trials(db) -> int:
    """Downgrade users whose trial has ended.

    Session 27d: legacy paid-plan trial (trial_active=true, trial_end set).
    Session 35: new auto-enrolled 7-day Trial tier (subscription_tier='trial',
                trial_expires_at set).

    Both flows now downgrade to **basic** (Session 35 decision: no permanent
    free tier). User must purchase Basic ₹99 to continue, or stay locked.

    Returns the number of users downgraded.
    """
    from core.pricing import plan_by_id
    basic_plan = plan_by_id('basic')
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    count = 0

    # ── Flow 1: Legacy paid-plan trial conversions ──
    cursor = db.users.find({
        'trial_active': True,
        'trial_end': {'$lt': now},
    })
    async for u in cursor:
        try:
            await db.users.update_one({'id': u['id']}, {
                '$set': {
                    'subscription_tier': 'basic',
                    'subscription_cycle': 'expired',
                    'subscription_price_inr': 0,
                    'credits_balance': basic_plan['credits'],
                    'trial_active': False,
                    'trial_expired_at': now,
                },
            })
            count += 1
            logger.info(f"trial_cron[legacy]: expired user_id={u.get('id')} email={u.get('email','?')} plan_was={u.get('trial_plan')}")
        except Exception as e:
            logger.error(f"trial_cron[legacy]: failed to expire {u.get('id')}: {e}")

    # ── Flow 2: Session 35 auto-enrolled Trial-tier users ──
    cursor2 = db.users.find({
        'subscription_tier': 'trial',
        'trial_expires_at': {'$lt': now_dt},
    })
    async for u in cursor2:
        try:
            await db.users.update_one({'id': u['id']}, {
                '$set': {
                    'subscription_tier': 'basic',
                    'subscription_cycle': 'trial_ended',
                    'subscription_price_inr': 0,
                    # Force-upgrade: zero credits so they MUST buy Basic to use
                    # the app. (Alt strategy: gift Basic's 100 credits to soften
                    # the wall. We pick the firm wall to drive conversion.)
                    'credits_balance': 0,
                    'trial_active': False,
                    'trial_expired_at': now,
                    'requires_upgrade': True,
                },
            })
            count += 1
            logger.info(f"trial_cron[v35]: trial→basic user_id={u.get('id')} email={u.get('email','?')}")
        except Exception as e:
            logger.error(f"trial_cron[v35]: failed to expire {u.get('id')}: {e}")

    return count


async def _send_trial_reminders(db) -> dict:
    """Post an in-app notification on day 25, 28, and 30 of the user's trial.

    Session 27e: Enqueues docs into db.notifications so the frontend can poll
    and display reminders. Each reminder is idempotent — we stamp the user
    with `trial_reminder_sent_days` (array of int) so the same reminder is
    only posted once.

    Day-of-trial = days_elapsed_since_trial_started_at = 30 − days_remaining.
    Reminder buckets and copy:
      25 → "5 days left in your trial. Upgrade to keep your creator tools."
      28 → "⏰ 2 days left — pick a plan to stay on Creator."
      30 → "Last day of trial. Tomorrow you'll be moved to Free unless you upgrade."
    """
    from core.pricing import plan_by_id
    now = datetime.now(timezone.utc)
    sent = {25: 0, 28: 0, 30: 0}
    cursor = db.users.find({'trial_active': True, 'trial_end': {'$gt': now.isoformat()}})
    async for u in cursor:
        try:
            started = u.get('trial_started_at')
            if not started:
                continue
            try:
                started_dt = datetime.fromisoformat(started.replace('Z', '+00:00'))
            except Exception:
                continue
            elapsed_days = int((now - started_dt).total_seconds() // 86400)
            # Map day → reminder bucket: fire at days 25, 28, 30 exactly.
            target = None
            if elapsed_days >= 30:
                target = 30
            elif elapsed_days >= 28:
                target = 28
            elif elapsed_days >= 25:
                target = 25
            if target is None:
                continue
            already = u.get('trial_reminder_sent_days') or []
            if target in already:
                continue
            plan = plan_by_id(u.get('trial_plan', 'creator'))['label']
            days_left = max(0, 30 - elapsed_days)
            copy = {
                25: f"📣 5 days left in your {plan} trial. Upgrade to keep all creator tools.",
                28: f"⏰ Only {days_left} days left on your {plan} trial! Pick a plan to stay.",
                30: f"🚨 Today is the last day of your {plan} trial. Upgrade now — tomorrow you'll be moved to Free.",
            }[target]
            await db.notifications.insert_one({
                'user_id': u['id'],
                'email': u.get('email'),
                'kind': 'trial_reminder',
                'day': target,
                'title': 'Trial reminder',
                'body': copy,
                'read': False,
                'created_at': now.isoformat(),
                'cta_route': '/subscription',
            })
            # Session 27g — also send Expo push to the user's registered devices.
            push_tokens = u.get('expo_push_tokens') or []
            if push_tokens:
                push_result = await _send_expo_push(
                    push_tokens,
                    title='MagiCAi — Trial reminder',
                    body=copy,
                    data={'kind': 'trial_reminder', 'day': target, 'cta_route': '/subscription'},
                )
                logger.info(f"trial_cron: push day={target} user_id={u.get('id')} sent={push_result['sent']} failed={push_result['failed']}")
            await db.users.update_one({'id': u['id']}, {
                '$push': {'trial_reminder_sent_days': target},
                '$set': {'last_trial_reminder_at': now.isoformat()},
            })
            sent[target] += 1
            logger.info(f"trial_cron: reminder day={target} user_id={u.get('id')} email={u.get('email','?')}")
        except Exception as e:
            logger.error(f"trial_cron: reminder failed for {u.get('id')}: {e}")
    return sent


async def _trial_expiry_loop(db):
    """Runs every 6 hours — expires trials past their end-date AND sends reminders."""
    # Bootstrap check on startup
    try:
        n = await _expire_trials(db)
        if n > 0:
            logger.info(f"trial_cron: bootstrap expired {n} trials")
        r = await _send_trial_reminders(db)
        total_r = sum(r.values())
        if total_r > 0:
            logger.info(f"trial_cron: bootstrap reminders sent {r}")
    except Exception as e:
        logger.error(f"trial_cron: bootstrap failed: {e}")

    while True:
        try:
            await asyncio.sleep(6 * 3600)      # every 6h
        except asyncio.CancelledError:
            logger.info("trial_cron: cancelled (graceful shutdown)")
            raise
        try:
            n = await _expire_trials(db)
            if n > 0:
                logger.info(f"trial_cron: expired {n} trials")
            r = await _send_trial_reminders(db)
            total_r = sum(r.values())
            if total_r > 0:
                logger.info(f"trial_cron: reminders sent {r}")
        except Exception as e:
            logger.error(f"trial_cron: cycle failed: {e}")



def _seconds_until(hour_utc: int = 2, minute_utc: int = 0) -> float:
    """Seconds until the next hour_utc:minute_utc window."""
    now = datetime.now(timezone.utc)
    target = now.replace(hour=hour_utc, minute=minute_utc, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def _nightly_loop(db):
    """Runs forever. Waits until next 02:00 UTC, recomputes trending, repeats."""
    # Fire once on startup so fresh deployments have correct scores immediately.
    try:
        logger.info("scheduler: bootstrap recompute on startup")
        await recompute_all(db)
    except Exception as e:
        logger.error(f"scheduler: bootstrap recompute failed: {e}")

    while True:
        wait_s = _seconds_until(2, 0)
        logger.info(f"scheduler: next trending recompute in {wait_s/3600:.1f}h")
        try:
            await asyncio.sleep(wait_s)
        except asyncio.CancelledError:
            logger.info("scheduler: cancelled (graceful shutdown)")
            raise
        try:
            logger.info("scheduler: running nightly recompute")
            await recompute_all(db)
        except Exception as e:
            logger.error(f"scheduler: recompute failed: {e}")


def start_scheduler(db):
    """Idempotent — starts the trending + trial-expiry loops if not already running."""
    global _running_task, _trial_task
    if _running_task is None or _running_task.done():
        _running_task = asyncio.create_task(_nightly_loop(db))
        logger.info("scheduler: started nightly trending loop")
    else:
        logger.info("scheduler: trending loop already running, skip")
    if _trial_task is None or _trial_task.done():
        _trial_task = asyncio.create_task(_trial_expiry_loop(db))
        logger.info("scheduler: started 6h trial-expiry loop")
    else:
        logger.info("scheduler: trial loop already running, skip")
    return _running_task


def stop_scheduler():
    global _running_task, _trial_task
    if _running_task and not _running_task.done():
        _running_task.cancel()
        _running_task = None
    if _trial_task and not _trial_task.done():
        _trial_task.cancel()
        _trial_task = None
