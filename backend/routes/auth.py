"""Sprint 4 — Auth routes: register, login, me."""
import uuid
import re
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr
from motor.motor_asyncio import AsyncIOMotorClient

from core.config import MONGO_URL, DB_NAME, ADMIN_EMAIL, ENV, IS_BETA, IS_DEV
from core.auth import hash_password, verify_password, create_token, get_current_user
from core.pricing import plan_by_id, PLANS, SIGNUP_DEFAULT_TIER, trial_expiry_payload
from core.audit import log_audit

_client = AsyncIOMotorClient(MONGO_URL)
db = _client[DB_NAME]

router = APIRouter(prefix='/api/auth', tags=['auth'])


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ''
    # Session 35: default is 'trial' (auto-enrol funnel). Paid plans still
    # supported but typically arrive via /api/checkout after payment.
    plan: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post('/register')
async def register(req: RegisterRequest, request: Request):
    email = (req.email or '').strip().lower()
    if not email or not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        raise HTTPException(status_code=400, detail='Invalid email')
    if len(req.password or '') < 6:
        raise HTTPException(status_code=400, detail='Password must be at least 6 chars')
    if await db.users.find_one({'email': email}):
        raise HTTPException(status_code=409, detail='Email already registered')
    is_admin = (email == ADMIN_EMAIL)
    # Session 35: auto-enrol new users into 7-day Trial (50 cr, watermark).
    # Existing plan-pick on signup form still works for explicit upgrades.
    chosen = (req.plan or SIGNUP_DEFAULT_TIER).lower()
    if chosen not in PLANS:
        chosen = SIGNUP_DEFAULT_TIER
    plan_meta = plan_by_id(chosen)
    user = {
        'id': str(uuid.uuid4()),
        'email': email,
        'name': req.name or email.split('@')[0],
        'password_hash': hash_password(req.password),
        'subscription_tier': chosen,
        'credits_balance': plan_meta['credits'],
        'credits_reserved': 0,
        'daily_usage': 0,
        'daily_usage_date': None,
        'is_admin': is_admin,
        'env': ENV,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    # Attach trial expiry if user landed on Trial tier
    if chosen == 'trial':
        user.update(trial_expiry_payload())
    await db.users.insert_one(user)
    token = create_token(user['id'], user['email'])
    user.pop('password_hash', None)
    user.pop('_id', None)
    # Serialize datetime fields for JSON response
    for k in ('trial_expires_at', 'trial_started_at'):
        if k in user and hasattr(user[k], 'isoformat'):
            user[k] = user[k].isoformat()
    # Session 36 — Audit: register event
    await log_audit('auth.register', user_id=user['id'],
                    meta={'tier': chosen, 'provider': 'email'}, request=request)
    return {'token': token, 'user': user, 'env': ENV}


@router.post('/login')
async def login(req: LoginRequest, request: Request):
    email = (req.email or '').strip().lower()
    u = await db.users.find_one({'email': email})
    if not u or not verify_password(req.password, u.get('password_hash', '')):
        await log_audit('auth.login_failed', meta={'email': email}, request=request)
        raise HTTPException(status_code=401, detail='Invalid email or password')
    # Legacy/DEV DB safety: older docs may miss `id`. Auto-heal.
    if not u.get('id'):
        new_id = str(uuid.uuid4())
        await db.users.update_one({'email': email}, {'$set': {'id': new_id}})
        u['id'] = new_id
    u.setdefault('subscription_tier', 'free')
    u.setdefault('credits_balance', 30)
    u.setdefault('is_admin', False)
    token = create_token(u['id'], u['email'])
    u.pop('password_hash', None)
    u.pop('_id', None)
    await log_audit('auth.login', user_id=u['id'],
                    meta={'tier': u.get('subscription_tier')}, request=request)
    return {'token': token, 'user': u, 'env': ENV}


@router.get('/me')
async def me(request: Request):
    user = await get_current_user(request, strict=True)
    return {'user': user, 'env': ENV, 'is_beta': IS_BETA, 'is_dev': IS_DEV}


@router.post('/logout')
async def logout():
    # Stateless JWT — client just drops the token
    return {'ok': True}


class GoogleSSORequest(BaseModel):
    session_id: str


@router.post('/google-finish')
async def google_finish(req: GoogleSSORequest):
    """Exchange an Emergent SSO session_id for a MagicAi JWT.

    Flow: frontend redirects user to auth.emergentagent.com → on return we get
    a session_id → we call Emergent's /api/auth/user to get email+name → we
    find-or-create the user in our DB → issue a JWT that works in BETA mode.
    """
    import httpx as _httpx
    try:
        async with _httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                'https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data',
                headers={'X-Session-ID': req.session_id},
            )
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail='Google session invalid or expired')
        data = r.json() or {}
        email = (data.get('email') or '').lower().strip()
        name = (data.get('name') or data.get('user_name') or '').strip()
        picture = data.get('picture') or ''
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Google session lookup failed: {str(e)[:160]}')
    if not email:
        raise HTTPException(status_code=400, detail='No email returned from Google')

    user = await db.users.find_one({'email': email}, {'password_hash': 0})
    if not user:
        # Session 35: new Google users also auto-enrol into Trial.
        trial_meta = trial_expiry_payload()
        plan_meta = plan_by_id(SIGNUP_DEFAULT_TIER)
        user = {
            'id': str(uuid.uuid4()),
            'email': email,
            'name': name or email.split('@')[0],
            'picture': picture,
            'auth_provider': 'google',
            'password_hash': '',  # no password for google users
            'subscription_tier': SIGNUP_DEFAULT_TIER,
            'credits_balance': plan_meta['credits'],
            'daily_usage': 0,
            'daily_usage_date': '',
            'is_admin': False,
            'created_at': datetime.now(timezone.utc).isoformat(),
            **trial_meta,
        }
        await db.users.insert_one(user.copy())
        user.pop('password_hash', None)
    else:
        # Legacy/DEV DB safety: some older user docs lack the `id` UUID
        # field. Auto-heal by assigning one and persisting. Without this,
        # create_token(user['id'], ...) raised KeyError: 'id' → HTTP 500.
        if not user.get('id'):
            new_id = str(uuid.uuid4())
            await db.users.update_one(
                {'email': email},
                {'$set': {'id': new_id}},
            )
            user['id'] = new_id
        # Normalise optional fields that older schemas may miss
        user.setdefault('subscription_tier', 'free')
        user.setdefault('credits_balance', 30)
        user.setdefault('is_admin', False)

    token = create_token(user['id'], user['email'])
    # Ensure nothing internal leaks into response
    user.pop('_id', None)
    user.pop('password_hash', None)
    return {'token': token, 'user': user, 'env': ENV, 'is_beta': IS_BETA}
