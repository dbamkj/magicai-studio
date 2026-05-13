"""Sprint 1 migration script — Session 35 (2026-05-13)

Decisions implemented:
  * Force-cap existing Creator users from 3000 → 1200 credits.
  * Create demo_trial@test.com (trial tier, 50 cr, 7d).
  * Create demo_basic@test.com (basic tier, 100 cr).

Idempotent — safe to re-run.

Usage:
  python /app/backend/scripts/migrate_sprint1.py
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

# Make the parent backend dir importable when invoked as a script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env')))

from core.config import MONGO_URL, DB_NAME  # noqa: E402
from core.auth import hash_password         # noqa: E402
from core.pricing import plan_by_id, trial_expiry_payload  # noqa: E402


async def cap_creator_credits(db):
    """Cap all CURRENT creator-tier users to the new 1200 cap.

    We don't subtract spent credits — we just ensure their balance is
    not above the new ceiling. Users who already spent below 1200 are
    left alone.
    """
    cursor = db.users.find({'subscription_tier': 'creator', 'credits_balance': {'$gt': 1200}})
    capped = 0
    async for u in cursor:
        old = u.get('credits_balance', 0)
        await db.users.update_one(
            {'id': u['id']},
            {'$set': {
                'credits_balance': 1200,
                'credits_capped_at': datetime.now(timezone.utc).isoformat(),
                'credits_capped_from': old,
            }},
        )
        capped += 1
        print(f"  capped: {u.get('email')} {old} → 1200")
    print(f"✅ Creator-credit cap: {capped} users updated")
    return capped


async def ensure_demo_user(db, email: str, tier: str, name: str, extra: dict | None = None):
    existing = await db.users.find_one({'email': email})
    plan = plan_by_id(tier)
    base = {
        'email': email,
        'name': name,
        'password_hash': hash_password('Test@123'),
        'subscription_tier': tier,
        'credits_balance': plan['credits'],
        'credits_reserved': 0,
        'daily_usage': 0,
        'daily_usage_date': None,
        'is_admin': False,
        'created_at': datetime.now(timezone.utc).isoformat(),
        **(extra or {}),
    }
    if existing:
        # Refresh to canonical tier/credits but preserve id
        await db.users.update_one(
            {'email': email},
            {'$set': {**base, 'id': existing.get('id') or str(uuid.uuid4())}},
        )
        print(f"  refreshed: {email} → {tier} ({plan['credits']} cr)")
    else:
        base['id'] = str(uuid.uuid4())
        await db.users.insert_one(base)
        print(f"  created: {email} → {tier} ({plan['credits']} cr)")


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    print(f"== Sprint 1 Migration — DB: {DB_NAME} ==")

    print("\n[1] Cap Creator users to 1200 credits...")
    await cap_creator_credits(db)

    print("\n[2] Seed Trial + Basic demo accounts...")
    trial_meta = trial_expiry_payload()
    # Serialize datetimes for Mongo (they're already datetime objects — Mongo handles them natively)
    await ensure_demo_user(
        db, 'demo_trial@test.com', 'trial', 'Demo Trial',
        extra=trial_meta,
    )
    await ensure_demo_user(
        db, 'demo_basic@test.com', 'basic', 'Demo Basic',
    )

    print("\n[3] Update existing demo_creator to new 1200 ceiling")
    await ensure_demo_user(db, 'demo_creator@test.com', 'creator', 'Demo Creator')

    print("\n✅ Sprint 1 migration complete.")


if __name__ == '__main__':
    asyncio.run(main())
