"""Sprint 4 — Admin dashboard routes (web-optimized)."""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient

from core.config import MONGO_URL, DB_NAME, ENV, IS_BETA
from core.auth import require_admin
from core.pricing import PLANS, plan_by_id

_client = AsyncIOMotorClient(MONGO_URL)
db = _client[DB_NAME]

router = APIRouter(prefix='/api/admin', tags=['admin'])


class AdjustCreditsRequest(BaseModel):
    delta: int  # positive to add, negative to subtract
    reason: str = ''


class SetTierRequest(BaseModel):
    tier: str  # 'free' | 'starter' | 'pro'


class ProfitCalcRequest(BaseModel):
    total_users: int
    starter_users: int
    pro_users: int
    avg_videos_per_user_per_month: float = 10.0
    avg_cost_per_video_inr: float = 8.0


@router.get('/users')
async def list_users(request: Request, limit: int = 200):
    await require_admin(request)
    users = await db.users.find({}, {'_id': 0, 'password_hash': 0}).sort('created_at', -1).to_list(length=limit)
    return {'users': users, 'count': len(users), 'env': ENV}


@router.post('/users/{user_id}/credits')
async def adjust_credits(user_id: str, req: AdjustCreditsRequest, request: Request):
    await require_admin(request)
    u = await db.users.find_one({'id': user_id})
    if not u:
        raise HTTPException(status_code=404, detail='User not found')
    new_bal = max(0, int(u.get('credits_balance', 0)) + int(req.delta))
    await db.users.update_one({'id': user_id}, {'$set': {'credits_balance': new_bal}})
    await db.admin_audit.insert_one({
        'at': datetime.now(timezone.utc).isoformat(), 'action': 'credit_adjust',
        'user_id': user_id, 'delta': req.delta, 'reason': req.reason, 'new_balance': new_bal,
    })
    return {'ok': True, 'new_balance': new_bal}


@router.post('/users/{user_id}/tier')
async def set_tier(user_id: str, req: SetTierRequest, request: Request):
    await require_admin(request)
    if req.tier not in PLANS:
        raise HTTPException(status_code=400, detail='Invalid tier')
    await db.users.update_one({'id': user_id}, {'$set': {
        'subscription_tier': req.tier,
        'credits_balance': PLANS[req.tier]['credits'],
    }})
    return {'ok': True}


@router.post('/users/{user_id}/reset-daily')
async def reset_daily(user_id: str, request: Request):
    """BETA only: reset daily_usage for testing."""
    await require_admin(request)
    if not IS_BETA:
        raise HTTPException(status_code=403, detail='Only available in BETA mode')
    await db.users.update_one({'id': user_id}, {'$set': {'daily_usage': 0, 'daily_usage_date': None}})
    return {'ok': True}


@router.get('/usage')
async def usage_stats(request: Request):
    await require_admin(request)
    total_users = await db.users.count_documents({})
    by_tier = {}
    for tier in PLANS.keys():
        by_tier[tier] = await db.users.count_documents({'subscription_tier': tier})
    # Projects counts
    total_projects = await db.video_projects.count_documents({})
    # Recent projects (last 7 days by created_at string prefix)
    seven_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    recent_projects = await db.video_projects.count_documents({'created_at': {'$gte': seven_ago}})
    # Templates
    templates_count = await db.templates.count_documents({'is_active': True})
    return {
        'env': ENV, 'total_users': total_users, 'by_tier': by_tier,
        'total_projects': total_projects, 'recent_projects': recent_projects,
        'active_templates': templates_count,
    }


@router.post('/profit')
async def profit_calc(req: ProfitCalcRequest, request: Request):
    await require_admin(request)
    starter_revenue = req.starter_users * PLANS['starter']['price_inr']
    pro_revenue = req.pro_users * PLANS['pro']['price_inr']
    revenue = starter_revenue + pro_revenue
    # Assume paid users generate the avg videos; free users generate 1 video/month
    free_users = max(0, req.total_users - req.starter_users - req.pro_users)
    total_videos = (
        (req.starter_users + req.pro_users) * req.avg_videos_per_user_per_month
        + free_users * 1.0
    )
    cost = total_videos * req.avg_cost_per_video_inr
    profit = revenue - cost
    margin = (profit / revenue * 100.0) if revenue > 0 else 0.0
    return {
        'total_users': req.total_users,
        'paid_users': req.starter_users + req.pro_users,
        'free_users': free_users,
        'revenue_inr': round(revenue, 2),
        'estimated_videos': round(total_videos, 0),
        'estimated_cost_inr': round(cost, 2),
        'profit_inr': round(profit, 2),
        'margin_pct': round(margin, 2),
    }


@router.get('/env')
async def env_info(request: Request):
    await require_admin(request)
    return {'env': ENV, 'is_beta': IS_BETA}


class SwitchEnvRequest(BaseModel):
    env: str  # 'DEV' | 'BETA' | 'PROD'


@router.post('/env/switch')
async def switch_env(req: SwitchEnvRequest, request: Request):
    """Admin-only: hot-swap ENV at runtime.

    Rewrites ENV= in /app/backend/.env and touches server.py so uvicorn
    --reload picks up the change. JWTs issued in the previous DB will NOT
    work in the new DB, so the frontend MUST force-logout after calling this.
    """
    await require_admin(request)
    import os as _os
    import re as _re
    from pathlib import Path as _P

    new_env = (req.env or '').upper()
    if new_env not in ('DEV', 'BETA', 'PROD'):
        raise HTTPException(status_code=400, detail='env must be one of DEV, BETA, PROD')
    if new_env == ENV:
        return {'ok': True, 'env': ENV, 'unchanged': True}

    env_path = _P('/app/backend/.env')
    if not env_path.exists():
        raise HTTPException(status_code=500, detail='.env file missing on server')

    text = env_path.read_text()
    if _re.search(r'^ENV=.*$', text, flags=_re.MULTILINE):
        text = _re.sub(r'^ENV=.*$', f'ENV={new_env}', text, flags=_re.MULTILINE)
    else:
        text = text.rstrip('\n') + f'\nENV={new_env}\n'
    env_path.write_text(text)

    # Audit trail
    await db.admin_audit.insert_one({
        'at': datetime.now(timezone.utc).isoformat(),
        'action': 'env_switch', 'from': ENV, 'to': new_env,
    })

    # Touch server.py to trigger uvicorn --reload. Backend will be back in ~2s.
    try:
        server_py = _P('/app/backend/server.py')
        server_py.touch()
    except Exception:
        pass

    return {'ok': True, 'env': new_env, 'previous': ENV,
            'note': 'Backend reloading. Frontend should log out and re-login in ~3s.'}


# ============================================================
# Session 31 — MH credit budget dashboard
# ============================================================
from core import mh_guardrails


@router.get('/mh-usage')
async def mh_usage(request: Request):
    """Real-time MH credit burn stats for the ₹1,350/mo Creator plan.

    Returns daily + monthly totals, projected end-of-month usage, top users,
    and per-model breakdown so admins can proactively upgrade the MH tier
    before running out mid-cycle.
    """
    await require_admin(request)
    data = await mh_guardrails.get_admin_usage(db)
    return data


# ============================================================
# Session 31 — Pattern Lab admin endpoints
# ============================================================
@router.post('/pattern-lab/trigger')
async def pattern_lab_trigger(request: Request):
    """Manually fire a Pattern Lab refresh."""
    await require_admin(request)
    from core import pattern_lab
    return await pattern_lab.run_refresh(db)


@router.post('/pattern-lab/flag/{template_id}')
async def pattern_lab_flag(template_id: str, request: Request):
    """User-accessible endpoint (not actually admin-gated) — records a flag."""
    # NOTE: auth optional — any logged-in user can flag. We don't require admin here.
    body = await request.json() if request.headers.get('content-type') == 'application/json' else {}
    reason = (body or {}).get('reason', 'user_flagged')[:200]
    try:
        user_id = None
        try:
            from core.auth import get_current_user
            u = await get_current_user(request)
            user_id = u.get('id') if u else None
        except Exception:
            pass
        await db.templates.update_one(
            {'id': template_id},
            {'$inc': {'flag_count': 1}, '$push': {'flags': {'user_id': user_id, 'reason': reason, 'at': datetime.now(timezone.utc).isoformat()}}},
        )
        # Auto-deactivate if flag_count ≥ 5
        t = await db.templates.find_one({'id': template_id})
        if t and int(t.get('flag_count', 0)) >= 5:
            await db.templates.update_one({'id': template_id}, {'$set': {'is_active': False, 'auto_deactivated': True}})
        return {'ok': True, 'flag_count': int((t or {}).get('flag_count', 1))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/pattern-lab/flagged')
async def pattern_lab_flagged(request: Request, limit: int = 50):
    await require_admin(request)
    cur = db.templates.find({'source': 'pattern_lab', 'flag_count': {'$gt': 0}}).sort('flag_count', -1).limit(limit)
    items = await cur.to_list(length=limit)
    for it in items:
        it.pop('_id', None)
    return {'flagged': items, 'count': len(items)}


@router.post('/pattern-lab/moderate/{template_id}')
async def pattern_lab_moderate(template_id: str, request: Request):
    await require_admin(request)
    body = await request.json() if request.headers.get('content-type') == 'application/json' else {}
    action = (body or {}).get('action', 'deactivate')  # 'deactivate' | 'approve' | 'delete'
    if action == 'approve':
        await db.templates.update_one({'id': template_id}, {'$set': {'flag_count': 0, 'flags': [], 'auto_deactivated': False, 'is_active': True}})
    elif action == 'delete':
        await db.templates.delete_one({'id': template_id})
    else:
        await db.templates.update_one({'id': template_id}, {'$set': {'is_active': False}})
    return {'ok': True, 'action': action}



# ═══════════════════════════════════════════════════════════════════
# Session 35 — Feature Flags & Plan Visibility (Sprint 1)
# ═══════════════════════════════════════════════════════════════════

class FeatureFlagUpsert(BaseModel):
    key: str
    enabled: bool
    description: str = ''
    rollout_pct: int = 100  # 0..100 — percentage of users this flag applies to


class PlanVisibilityToggle(BaseModel):
    visible: bool


@router.get('/feature-flags')
async def list_feature_flags(request: Request):
    """List all dynamic feature flags. Admin-only.

    Flags live in the `feature_flags` Mongo collection and override or
    extend behavior of statically-defined features in code. Useful for
    gradual rollouts and emergency kills.
    """
    await require_admin(request)
    flags = await db.feature_flags.find({}, {'_id': 0}).to_list(length=500)
    # Also report current plan visibility (computed from PLANS + overrides)
    plan_overrides = await db.feature_flags.find_one(
        {'key': '__plan_visibility_overrides__'}, {'_id': 0}
    ) or {}
    overrides = (plan_overrides.get('value') or {})
    plans_status = []
    for pid, plan in PLANS.items():
        default_vis = bool(plan.get('is_visible_in_pricing_page', False))
        plans_status.append({
            'id': pid,
            'label': plan.get('label'),
            'price_inr': plan.get('price_inr'),
            'default_visible': default_vis,
            'override_visible': overrides.get(pid),  # None | True | False
            'effective_visible': overrides.get(pid, default_vis),
        })
    return {'flags': flags, 'plans': plans_status, 'env': ENV}


@router.post('/feature-flags')
async def upsert_feature_flag(req: FeatureFlagUpsert, request: Request):
    """Create or update a feature flag. Admin-only."""
    await require_admin(request)
    key = (req.key or '').strip()
    if not key:
        raise HTTPException(status_code=400, detail='key required')
    if key.startswith('__'):
        raise HTTPException(status_code=400, detail='Reserved key prefix')
    if not (0 <= req.rollout_pct <= 100):
        raise HTTPException(status_code=400, detail='rollout_pct must be 0..100')
    doc = {
        'key': key,
        'enabled': bool(req.enabled),
        'description': req.description,
        'rollout_pct': int(req.rollout_pct),
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    await db.feature_flags.update_one(
        {'key': key}, {'$set': doc, '$setOnInsert': {'created_at': doc['updated_at']}},
        upsert=True,
    )
    return {'ok': True, 'flag': doc}


@router.delete('/feature-flags/{key}')
async def delete_feature_flag(key: str, request: Request):
    """Delete a feature flag override. Admin-only."""
    await require_admin(request)
    r = await db.feature_flags.delete_one({'key': key})
    return {'ok': True, 'deleted': r.deleted_count}


@router.get('/audit-logs')
async def admin_audit_logs(
    request: Request,
    user_id: str = None,
    action: str = None,
    limit: int = 200,
):
    """View audit-log entries. Admin-only. Session 36 — DPDPA Sprint 2."""
    await require_admin(request)
    q: dict = {}
    if user_id:
        q['user_id'] = user_id
    if action:
        q['action'] = action
    limit = max(1, min(int(limit or 200), 2000))
    rows = await db.audit_logs.find(q, {'_id': 0}).sort('timestamp', -1).to_list(length=limit)
    return {'logs': rows, 'count': len(rows)}


# ═══════════════════════════════════════════════════════════════════
# Session 38 — Sprint 4: Job Queue Admin
# ═══════════════════════════════════════════════════════════════════

@router.get('/queue/stats')
async def admin_queue_stats(request: Request):
    """Counters and registered handlers for the persistent job queue."""
    await require_admin(request)
    from core.queue import queue_stats
    return await queue_stats()


@router.get('/queue/jobs')
async def admin_queue_jobs(
    request: Request,
    status: str = None,
    name: str = None,
    limit: int = 100,
):
    """List recent jobs. Admin-only."""
    await require_admin(request)
    q: dict = {}
    if status:
        q['status'] = status
    if name:
        q['name'] = name
    limit = max(1, min(int(limit or 100), 1000))
    rows = await db.job_queue.find(q, {'_id': 0}).sort('created_at', -1).to_list(length=limit)
    return {'jobs': rows, 'count': len(rows)}


@router.post('/queue/enqueue-test')
async def admin_queue_enqueue_test(request: Request):
    """Enqueue a system.ping job for smoke-testing the worker."""
    await require_admin(request)
    from core.queue import enqueue
    job_id = await enqueue('system.ping', {'src': 'admin_smoke'}, priority=10)
    return {'ok': True, 'job_id': job_id}


# ═══════════════════════════════════════════════════════════════════
# Session 37 — Sprint 3: Content Moderation v2 Admin Dashboard
# ═══════════════════════════════════════════════════════════════════

class ModerationOverride(BaseModel):
    decision: str  # 'overridden_allow' | 'confirmed_block'
    admin_note: str = ''


class UserBanRequest(BaseModel):
    reason: str = ''


@router.get('/moderation/records')
async def admin_moderation_records(
    request: Request,
    user_id: str = None,
    status: str = None,
    severity: int = None,
    limit: int = 100,
):
    """List moderation decisions. Admin-only."""
    await require_admin(request)
    q: dict = {}
    if user_id:
        q['user_id'] = user_id
    if status:
        q['status'] = status
    if severity is not None:
        q['severity'] = int(severity)
    limit = max(1, min(int(limit or 100), 1000))
    rows = await db.moderation_records.find(q, {'_id': 0}).sort('created_at', -1).to_list(length=limit)
    # Compact stats for dashboard cards
    total = await db.moderation_records.count_documents({})
    blocked = await db.moderation_records.count_documents({'status': 'blocked'})
    overridden = await db.moderation_records.count_documents({'status': 'overridden_allow'})
    confirmed = await db.moderation_records.count_documents({'status': 'confirmed_block'})
    return {
        'records': rows,
        'count': len(rows),
        'stats': {
            'total': total,
            'open': blocked,
            'overridden': overridden,
            'confirmed': confirmed,
        },
    }


@router.post('/moderation/records/{record_id}/override')
async def admin_override_moderation(record_id: str, req: ModerationOverride, request: Request):
    """Override or confirm a moderation decision. Admin-only.

    decision = 'overridden_allow' → the block was wrong; do NOT count toward
                                    the user's strikes (remove strike).
    decision = 'confirmed_block'  → the block was correct; keep as-is.
    """
    admin = await require_admin(request)
    if req.decision not in ('overridden_allow', 'confirmed_block'):
        raise HTTPException(status_code=400, detail='decision must be overridden_allow or confirmed_block')
    rec = await db.moderation_records.find_one({'id': record_id})
    if not rec:
        raise HTTPException(status_code=404, detail='record not found')

    now = datetime.now(timezone.utc).isoformat()
    await db.moderation_records.update_one(
        {'id': record_id},
        {'$set': {
            'status': req.decision,
            'admin_note': (req.admin_note or '')[:500],
            'reviewed_by': admin.get('id'),
            'reviewed_at': now,
        }},
    )

    # If overridden to allow, retroactively remove that strike from the user.
    if req.decision == 'overridden_allow' and rec.get('user_id'):
        u = await db.users.find_one({'id': rec['user_id']}, {'strikes': 1})
        if u:
            strikes = [s for s in (u.get('strikes') or []) if s.get('record_id') != record_id]
            score = sum(int(s.get('severity') or 1) for s in strikes)
            update = {
                'strikes': strikes,
                'strike_count': len(strikes),
                'strike_score': score,
            }
            # If user was banned BECAUSE of this strike, also unban.
            if u.get('is_banned'):  # type: ignore[unreachable]
                pass  # leave is_banned; admin should explicitly /unban
            await db.users.update_one({'id': rec['user_id']}, {'$set': update})

    # Audit
    try:
        from core.audit import log_audit
        await log_audit(
            f'moderation.{req.decision}',
            user_id=admin.get('id'),
            meta={'record_id': record_id, 'note': req.admin_note},
            request=request,
        )
    except Exception:
        pass

    return {'ok': True, 'record_id': record_id, 'status': req.decision}


@router.get('/moderation/users-strikes')
async def admin_users_with_strikes(request: Request, min_score: int = 1, limit: int = 100):
    """List users with active strikes, sorted by strike_score desc. Admin-only."""
    await require_admin(request)
    limit = max(1, min(int(limit or 100), 500))
    rows = await db.users.find(
        {'strike_score': {'$gte': int(min_score)}},
        {'_id': 0, 'password_hash': 0, 'google_email': 0},
    ).sort('strike_score', -1).to_list(length=limit)
    # Strip super-long fields to keep payload small
    for u in rows:
        u.pop('push_tokens', None)
    return {'users': rows, 'count': len(rows)}


@router.post('/users/{user_id}/ban')
async def admin_ban_user(user_id: str, req: UserBanRequest, request: Request):
    """Manually ban a user. Admin-only."""
    admin = await require_admin(request)
    u = await db.users.find_one({'id': user_id}, {'id': 1, 'email': 1, 'is_admin': 1})
    if not u:
        raise HTTPException(status_code=404, detail='user not found')
    if u.get('is_admin'):
        raise HTTPException(status_code=400, detail='cannot ban an admin')
    now = datetime.now(timezone.utc).isoformat()
    reason = (req.reason or 'Manually banned by admin')[:240]
    await db.users.update_one(
        {'id': user_id},
        {'$set': {'is_banned': True, 'banned_at': now, 'ban_reason': reason}},
    )
    try:
        from core.audit import log_audit
        await log_audit('moderation.banned', user_id=user_id,
                        meta={'by_admin': admin.get('id'), 'reason': reason}, request=request)
    except Exception:
        pass
    return {'ok': True, 'user_id': user_id, 'banned_at': now, 'reason': reason}


@router.post('/users/{user_id}/unban')
async def admin_unban_user(user_id: str, request: Request):
    """Manually unban a user. Admin-only. Also resets strike_score to 0."""
    admin = await require_admin(request)
    u = await db.users.find_one({'id': user_id}, {'id': 1})
    if not u:
        raise HTTPException(status_code=404, detail='user not found')
    now = datetime.now(timezone.utc).isoformat()
    await db.users.update_one(
        {'id': user_id},
        {'$set': {
            'is_banned': False,
            'unbanned_at': now,
            'strikes': [],
            'strike_count': 0,
            'strike_score': 0,
        }},
    )
    try:
        from core.audit import log_audit
        await log_audit('moderation.unbanned', user_id=user_id,
                        meta={'by_admin': admin.get('id')}, request=request)
    except Exception:
        pass
    return {'ok': True, 'user_id': user_id, 'unbanned_at': now}


@router.post('/plans/{plan_id}/toggle-visibility')
async def toggle_plan_visibility(plan_id: str, req: PlanVisibilityToggle, request: Request):
    """Override `is_visible_in_pricing_page` for a plan at runtime.

    The override is stored under the reserved key `__plan_visibility_overrides__`.
    Pass {visible: null} to clear the override and fall back to PLANS default.
    """
    await require_admin(request)
    if plan_id not in PLANS:
        raise HTTPException(status_code=404, detail=f'Unknown plan {plan_id}')
    existing = await db.feature_flags.find_one(
        {'key': '__plan_visibility_overrides__'}
    ) or {'key': '__plan_visibility_overrides__', 'value': {}}
    overrides = existing.get('value') or {}
    overrides[plan_id] = bool(req.visible)
    await db.feature_flags.update_one(
        {'key': '__plan_visibility_overrides__'},
        {'$set': {
            'value': overrides,
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {'ok': True, 'plan_id': plan_id, 'visible': bool(req.visible), 'overrides': overrides}
