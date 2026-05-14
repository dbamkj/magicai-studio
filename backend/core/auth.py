"""Sprint 4 — Real JWT + bcrypt auth. Replaces guest-mode stub."""
import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient

from core.config import (
    MONGO_URL, DB_NAME, JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_HOURS,
    ADMIN_EMAIL, ENV, IS_BETA, IS_DEV,
)

_client = AsyncIOMotorClient(MONGO_URL)
_db = _client[DB_NAME]


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode('utf-8'), bcrypt.gensalt(rounds=10)).decode('utf-8')


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


def create_token(user_id: str, email: str) -> str:
    payload = {
        'sub': user_id,
        'email': email,
        'iat': datetime.now(timezone.utc),
        'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:
        return None


async def get_current_user(request: Optional[Request] = None, strict: bool = False) -> dict:
    """Resolve user from Authorization header. In DEV mode, falls back to guest.
    In BETA/PROD mode with strict=True, requires a valid token."""
    if request is None:
        if IS_DEV:
            return {'user_id': 'guest', 'email': 'guest@dev', 'subscription_tier': 'pro', 'credits_balance': 99999, 'daily_usage': 0, 'is_admin': False, 'env': ENV}
        raise HTTPException(status_code=401, detail='Authentication required')
    auth_header = request.headers.get('authorization') or request.headers.get('Authorization', '')
    token = None
    if auth_header.lower().startswith('bearer '):
        token = auth_header.split(' ', 1)[1].strip()
    if not token:
        if IS_DEV and not strict:
            return {'user_id': 'guest', 'email': 'guest@dev', 'subscription_tier': 'pro', 'credits_balance': 99999, 'daily_usage': 0, 'is_admin': False, 'env': ENV}
        raise HTTPException(status_code=401, detail='Authentication required')
    data = decode_token(token)
    if not data or not data.get('sub'):
        raise HTTPException(status_code=401, detail='Invalid or expired token')
    user = await _db.users.find_one({'id': data['sub']}, {'_id': 0, 'password_hash': 0})
    if not user:
        raise HTTPException(status_code=401, detail='User not found')
    # Session 37 — Sprint 3: hard-stop banned users.
    if user.get('is_banned') and not user.get('is_admin'):
        raise HTTPException(
            status_code=403,
            detail={
                'banned': True,
                'reason': user.get('ban_reason') or 'Account suspended for safety policy violations.',
                'banned_at': user.get('banned_at'),
            },
        )
    user['env'] = ENV
    return user


async def require_admin(request: Request) -> dict:
    user = await get_current_user(request, strict=True)
    if not user.get('is_admin'):
        raise HTTPException(status_code=403, detail='Admin access required')
    return user
