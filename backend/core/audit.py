"""Session 36 — DPDPA Audit log helper (Sprint 2).

DPDPA Article 7(f): Data Fiduciaries must maintain logs of consent and
material data-processing activities for audit. Records are immutable
(append-only) and indexed by user_id + timestamp.

Schema (db.audit_logs):
    {
      _id: ObjectId,
      user_id: str | None,    # null for anonymous events
      action: str,            # e.g. 'auth.login', 'plan.upgrade', 'dsar.export'
      meta: dict,             # action-specific payload (no raw PII — store ids)
      ip: str | None,
      user_agent: str | None,
      env: str,
      timestamp: ISO-8601 str,
    }

Action namespace (extensible):
    auth.{register,login,logout,login_failed,google_signup}
    plan.{upgrade,downgrade,trial_started,trial_expired,addon_purchased}
    dsar.{export,deletion_requested,deletion_completed}
    admin.{plan_visibility_toggled,feature_flag_set,user_credits_adjusted,user_tier_set}
    moderation.{strike,banned,unbanned}
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import Request
from motor.motor_asyncio import AsyncIOMotorClient

from core.config import MONGO_URL, DB_NAME, ENV

logger = logging.getLogger("audit")
_client = AsyncIOMotorClient(MONGO_URL)
_db = _client[DB_NAME]


def _request_meta(request: Optional[Request]) -> dict:
    if not request:
        return {}
    try:
        ip = request.headers.get('x-forwarded-for') or (request.client.host if request.client else None)
        ua = request.headers.get('user-agent', '')[:240]
    except Exception:
        ip, ua = None, ''
    return {'ip': ip, 'user_agent': ua}


async def log_audit(
    action: str,
    *,
    user_id: Optional[str] = None,
    meta: Optional[dict] = None,
    request: Optional[Request] = None,
) -> None:
    """Append-only audit log. Failures are logged but do not raise —
    audit must never break the user-facing flow.
    """
    try:
        doc = {
            'user_id': user_id,
            'action': action,
            'meta': meta or {},
            'env': ENV,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            **_request_meta(request),
        }
        await _db.audit_logs.insert_one(doc)
    except Exception as e:
        logger.warning("audit log insert failed action=%s err=%s", action, e)
