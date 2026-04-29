"""Seed admin + 3 demo users + 10 beta users in the BETA database.
Run: ENV=BETA python scripts/seed_beta_users.py
"""
import os
import sys
import uuid
import asyncio
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, '/app/backend')
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')

os.environ['ENV'] = 'BETA'
from core.config import MONGO_URL, DB_NAME, ADMIN_EMAIL, ENV  # noqa
from core.auth import hash_password  # noqa
from core.pricing import PLANS  # noqa

db = AsyncIOMotorClient(MONGO_URL)[DB_NAME]

CRED_FILE = Path('/app/memory/test_credentials.md')
CRED_FILE.parent.mkdir(parents=True, exist_ok=True)
PASSWORD = 'Test@123'

USERS = [
    {'email': ADMIN_EMAIL, 'name': 'Admin',       'tier': 'pro',     'is_admin': True},
    {'email': 'demo_free@test.com',    'name': 'Demo Free',    'tier': 'free'},
    {'email': 'demo_starter@test.com', 'name': 'Demo Starter', 'tier': 'starter'},
    {'email': 'demo_creator@test.com', 'name': 'Demo Creator', 'tier': 'creator'},
    {'email': 'demo_pro@test.com',     'name': 'Demo Pro',     'tier': 'pro'},
]
# Add 10 beta users across tiers
for i in range(1, 11):
    tier = ['free', 'starter', 'pro'][i % 3]
    USERS.append({'email': f'beta_user_{i}@test.com', 'name': f'Beta {i}', 'tier': tier})


async def main():
    print(f"Seeding into DB: {DB_NAME} (ENV={ENV})")
    # Clean previous BETA seed
    emails = [u['email'] for u in USERS]
    await db.users.delete_many({'email': {'$in': emails}})
    docs = []
    for u in USERS:
        plan = PLANS[u['tier']]
        docs.append({
            'id': str(uuid.uuid4()),
            'email': u['email'].lower(),
            'name': u['name'],
            'password_hash': hash_password(PASSWORD),
            'subscription_tier': u['tier'],
            'credits_balance': plan['credits'],
            'credits_reserved': 0,
            'daily_usage': 0,
            'daily_usage_date': None,
            'is_admin': u.get('is_admin', False),
            'env': ENV,
            'created_at': datetime.now(timezone.utc).isoformat(),
        })
    await db.users.insert_many(docs)
    print(f"Seeded {len(docs)} users.")

    # Write test_credentials.md
    lines = [
        '# Test Credentials (BETA env)',
        f'DB: `{DB_NAME}` | ENV: `{ENV}`',
        '',
        f"Password for ALL accounts: `{PASSWORD}`",
        '',
        '## Admin',
        f'- `{ADMIN_EMAIL}` / `{PASSWORD}` (is_admin=true, tier=pro)',
        '',
        '## Demo users',
        '| Email | Password | Tier | Credits |',
        '|---|---|---|---|',
    ]
    for u in USERS[1:5]:
        lines.append(f"| `{u['email']}` | `{PASSWORD}` | {u['tier']} | {PLANS[u['tier']]['credits']} |")
    lines += ['', '## Beta users (10)', '| Email | Password | Tier | Credits |', '|---|---|---|---|']
    for u in USERS[5:]:
        lines.append(f"| `{u['email']}` | `{PASSWORD}` | {u['tier']} | {PLANS[u['tier']]['credits']} |")
    CRED_FILE.write_text('\n'.join(lines) + '\n')
    print(f'Credentials written to {CRED_FILE}')

asyncio.run(main())
