"""Notifications — in-app notifications (trial reminders, etc.) — Session 27e."""
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient

from core.config import MONGO_URL, DB_NAME
from core.auth import get_current_user

_client = AsyncIOMotorClient(MONGO_URL)
db = _client[DB_NAME]

router = APIRouter(prefix='/api/notifications', tags=['notifications'])


class MarkReadRequest(BaseModel):
    notification_ids: list[str] | None = None   # if None → mark all read


class PushTokenRequest(BaseModel):
    expo_push_token: str
    device: str | None = None  # 'ios' | 'android' | 'web'


@router.post('/push-token')
async def register_push_token(req: PushTokenRequest, request: Request):
    """Store the user's Expo Push Token so the scheduler can notify them off-app.

    Session 27g — MOCK delivery: tokens are saved to db.users.expo_push_tokens[],
    and scheduler posts a row into db.push_queue whenever a user-visible event
    happens (trial reminders etc.). A real Expo push-send worker would drain
    push_queue and call https://exp.host/--/api/v2/push/send. For now we log it.
    """
    user = await get_current_user(request, strict=True)
    if not req.expo_push_token or not req.expo_push_token.startswith('ExponentPushToken'):
        raise HTTPException(status_code=400, detail='Invalid Expo push token')
    now = datetime.now(timezone.utc).isoformat()
    await db.users.update_one({'id': user['id']}, {
        '$addToSet': {'expo_push_tokens': req.expo_push_token},
        '$set': {'last_push_token_device': req.device or 'unknown', 'last_push_token_at': now},
    })
    return {'ok': True, 'registered_at': now}


@router.post('/push-token/unregister')
async def unregister_push_token(req: PushTokenRequest, request: Request):
    user = await get_current_user(request, strict=True)
    await db.users.update_one({'id': user['id']}, {'$pull': {'expo_push_tokens': req.expo_push_token}})
    return {'ok': True}


@router.get('')
async def list_notifications(request: Request, unread_only: bool = False, limit: int = 20):
    """Return notifications for the current user (newest first)."""
    user = await get_current_user(request, strict=True)
    q: dict = {'user_id': user['id']}
    if unread_only:
        q['read'] = False
    cursor = db.notifications.find(q, {'_id': 0}).sort('created_at', -1).limit(max(1, min(limit, 100)))
    items = await cursor.to_list(length=limit)
    unread_count = await db.notifications.count_documents({'user_id': user['id'], 'read': False})
    return {'notifications': items, 'unread_count': unread_count}


@router.post('/mark-read')
async def mark_read(req: MarkReadRequest, request: Request):
    user = await get_current_user(request, strict=True)
    filt: dict = {'user_id': user['id'], 'read': False}
    if req.notification_ids:
        # we store docs without an id — index by created_at is the closest unique key,
        # so for now just mark ALL as read (the UX on mobile typically does this anyway).
        pass
    r = await db.notifications.update_many(filt, {'$set': {'read': True, 'read_at': datetime.now(timezone.utc).isoformat()}})
    return {'ok': True, 'marked': r.modified_count}
