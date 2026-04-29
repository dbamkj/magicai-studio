"""Sprint 4 — Subscription: plans + add-ons + mock checkout + trial + annual billing.

Session 27c: Added /start-trial and /upgrade now accepts billing_cycle ('monthly'|'annual').
All flows remain MOCK — no real payment gateway is invoked.
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient

from core.config import MONGO_URL, DB_NAME
from core.auth import get_current_user
from core.pricing import (
    PLANS, ADDONS, plan_by_id, addon_by_sku, utc_month_str,
    TRIAL_PRICE_INR, TRIAL_DAYS, ANNUAL_MULTIPLIER, trial_savings_pct_annual,
)

_client = AsyncIOMotorClient(MONGO_URL)
db = _client[DB_NAME]

router = APIRouter(prefix='/api/subscription', tags=['subscription'])


class UpgradeRequest(BaseModel):
    plan_id: str  # 'free' | 'starter' | 'creator' | 'pro'
    billing_cycle: Optional[str] = 'monthly'   # 'monthly' | 'annual'


class TrialRequest(BaseModel):
    plan_id: str  # 'starter' | 'creator' | 'pro'


class AddonPurchaseRequest(BaseModel):
    sku: str


def _compute_price(plan: dict, billing_cycle: str) -> int:
    if billing_cycle == 'annual':
        return int(plan.get('price_annual_inr') or plan['price_inr'] * ANNUAL_MULTIPLIER)
    return int(plan['price_inr'])


@router.get('/plans')
async def list_plans():
    return {
        'plans': list(PLANS.values()),
        'addons': ADDONS,
        'trial': {
            'price_inr': TRIAL_PRICE_INR,
            'days': TRIAL_DAYS,
            'eligible_plans': [pid for pid, p in PLANS.items() if p.get('trial_eligible')],
        },
        'annual': {
            'multiplier': ANNUAL_MULTIPLIER,
            'savings_pct': trial_savings_pct_annual(),
        },
    }


@router.get('/addons')
async def list_addons():
    return {'addons': ADDONS}


@router.post('/upgrade')
async def upgrade(req: UpgradeRequest, request: Request):
    """MOCK payment — immediately upgrades the user, refills credits, resets monthly counters.

    Supports:
      * billing_cycle='monthly' → price = plan.price_inr, billing_cycle_end = now+30d
      * billing_cycle='annual'  → price = plan.price_annual_inr (≈10× monthly), billing_cycle_end = now+365d
    """
    user = await get_current_user(request, strict=True)
    target = (req.plan_id or '').lower()
    if target not in PLANS:
        raise HTTPException(status_code=400, detail='Invalid plan_id')
    plan = PLANS[target]
    cycle = (req.billing_cycle or 'monthly').lower()
    if cycle not in ('monthly', 'annual'):
        cycle = 'monthly'
    price = _compute_price(plan, cycle)
    now = datetime.now(timezone.utc)
    period_end = now + timedelta(days=365 if cycle == 'annual' else 30)
    await db.users.update_one({'id': user['id']}, {'$set': {
        'subscription_tier': target,
        'subscription_cycle': cycle,
        'subscription_price_inr': price,
        'subscription_renews_at': period_end.isoformat(),
        'credits_balance': plan['credits'] * (12 if cycle == 'annual' else 1) if target != 'free' else plan['credits'],
        'monthly_reels_used': 0,
        'monthly_lipsync_used': 0,
        'monthly_ai_videos_used': 0,
        'monthly_counter_period': utc_month_str(),
        'trial_active': False,
        'upgraded_at': now.isoformat(),
    }})
    u = await db.users.find_one({'id': user['id']}, {'_id': 0, 'password_hash': 0})
    return {
        'ok': True,
        'message': f"Mock upgrade to {plan['label']} ({cycle}) complete — ₹{price}",
        'price_inr': price,
        'billing_cycle': cycle,
        'renews_at': period_end.isoformat(),
        'user': u,
    }


@router.post('/start-trial')
async def start_trial(req: TrialRequest, request: Request):
    """MOCK ₹1 first-month trial. User gets full plan features for TRIAL_DAYS.

    After trial_end, the user is NOT auto-downgraded in this MOCK — admin/UI
    should prompt them to upgrade. trial_active flag makes this easy to track.
    """
    user = await get_current_user(request, strict=True)
    target = (req.plan_id or '').lower()
    if target not in PLANS:
        raise HTTPException(status_code=400, detail='Invalid plan_id')
    plan = PLANS[target]
    if not plan.get('trial_eligible'):
        raise HTTPException(status_code=400, detail='This plan is not trial-eligible.')
    # One-time only
    if user.get('trial_used'):
        raise HTTPException(status_code=400, detail='You have already used your free trial.')
    now = datetime.now(timezone.utc)
    trial_end = now + timedelta(days=TRIAL_DAYS)
    await db.users.update_one({'id': user['id']}, {'$set': {
        'subscription_tier': target,
        'subscription_cycle': 'trial',
        'subscription_price_inr': TRIAL_PRICE_INR,
        'subscription_renews_at': trial_end.isoformat(),
        'credits_balance': plan['credits'],
        'monthly_reels_used': 0,
        'monthly_lipsync_used': 0,
        'monthly_ai_videos_used': 0,
        'monthly_counter_period': utc_month_str(),
        'trial_active': True,
        'trial_used': True,
        'trial_plan': target,
        'trial_started_at': now.isoformat(),
        'trial_end': trial_end.isoformat(),
        'upgraded_at': now.isoformat(),
    }})
    u = await db.users.find_one({'id': user['id']}, {'_id': 0, 'password_hash': 0})
    return {
        'ok': True,
        'message': f"Trial started — {plan['label']} for ₹{TRIAL_PRICE_INR} ({TRIAL_DAYS} days)",
        'trial_end': trial_end.isoformat(),
        'price_inr': TRIAL_PRICE_INR,
        'user': u,
    }


@router.post('/addons/purchase')
async def buy_addon(req: AddonPurchaseRequest, request: Request):
    """MOCK IAP checkout — grants AI-video credits on top of the monthly plan quota."""
    user = await get_current_user(request, strict=True)
    a = addon_by_sku(req.sku)
    if not a:
        raise HTTPException(status_code=400, detail='Unknown SKU')
    remaining = int(user.get('addon_ai_videos_remaining', 0) or 0) + int(a['ai_videos'])
    max_s = max(int(user.get('addon_ai_video_max_seconds', 0) or 0), int(a['ai_video_max_seconds']))
    await db.users.update_one({'id': user['id']}, {'$set': {
        'addon_ai_videos_remaining': remaining,
        'addon_ai_video_max_seconds': max_s,
        'last_addon_sku': a['sku'],
        'last_addon_purchased_at': datetime.now(timezone.utc).isoformat(),
    }, '$push': {
        'addon_purchases': {
            'sku': a['sku'], 'price_inr': a['price_inr'],
            'ai_videos': a['ai_videos'], 'ai_video_max_seconds': a['ai_video_max_seconds'],
            'purchased_at': datetime.now(timezone.utc).isoformat(),
        },
    }})
    u = await db.users.find_one({'id': user['id']}, {'_id': 0, 'password_hash': 0})
    return {
        'ok': True,
        'message': f"{a['label']} unlocked (₹{a['price_inr']})",
        'ai_videos_remaining': remaining,
        'ai_video_max_seconds': max_s,
        'user': u,
    }


@router.get('/balance')
async def balance(request: Request):
    """Rich balance + monthly quota view for the subscription screen."""
    user = await get_current_user(request, strict=True)
    plan = plan_by_id(user.get('subscription_tier', 'free'))

    current_period = utc_month_str()
    if user.get('monthly_counter_period') != current_period:
        await db.users.update_one({'id': user['id']}, {'$set': {
            'monthly_reels_used': 0,
            'monthly_lipsync_used': 0,
            'monthly_ai_videos_used': 0,
            'monthly_counter_period': current_period,
        }})
        user['monthly_reels_used'] = 0
        user['monthly_lipsync_used'] = 0
        user['monthly_ai_videos_used'] = 0

    reels_used = int(user.get('monthly_reels_used', 0) or 0)
    lipsync_used = int(user.get('monthly_lipsync_used', 0) or 0)
    ai_used = int(user.get('monthly_ai_videos_used', 0) or 0)
    addon_remaining = int(user.get('addon_ai_videos_remaining', 0) or 0)
    addon_max_s = int(user.get('addon_ai_video_max_seconds', 0) or 0)

    def _usage(used, limit):
        if limit >= 9999:
            return {'used': used, 'limit': 'unlimited', 'remaining': 'unlimited'}
        return {'used': used, 'limit': limit, 'remaining': max(0, limit - used)}

    return {
        'credits_balance': int(user.get('credits_balance', 0)),
        'subscription_tier': user.get('subscription_tier', 'free'),
        'plan': plan,
        'subscription_cycle': user.get('subscription_cycle', 'monthly'),
        'subscription_price_inr': user.get('subscription_price_inr', 0),
        'subscription_renews_at': user.get('subscription_renews_at'),
        'trial_active': bool(user.get('trial_active', False)),
        'trial_end': user.get('trial_end'),
        'trial_used': bool(user.get('trial_used', False)),
        'usage': {
            'reels': _usage(reels_used, int(plan.get('monthly_reels_limit', 0))),
            'lipsync': _usage(lipsync_used, int(plan.get('monthly_lipsync_limit', 0))),
            'ai_videos': _usage(ai_used, int(plan.get('monthly_ai_videos_limit', 0))),
        },
        'addons': {
            'ai_videos_remaining': addon_remaining,
            'ai_video_max_seconds': addon_max_s,
        },
        'period': current_period,
    }

