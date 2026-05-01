"""Centralised MongoDB client + database handle.

Many modules today each call AsyncIOMotorClient(MONGO_URL) separately, which
opens multiple connection pools and scatters the "which DB is this" logic.
This module is the single source of truth — import `db` or `get_db()` and be
done with it.

Env var resolution order for DB name:
  1. ``DB_NAME``                     (legacy — highest priority)
  2. ``DB_NAME_BETA`` when ENV=BETA
  3. ``DB_NAME_PROD`` when ENV=PROD
  4. ``videoai_database``            (default)
"""

from __future__ import annotations

import os

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


def _resolve_db_name() -> str:
    explicit = os.environ.get("DB_NAME", "").strip()
    if explicit:
        return explicit
    env = os.environ.get("ENV", "DEV").upper()
    if env == "BETA":
        return os.environ.get("DB_NAME_BETA", "magicai_beta")
    if env == "PROD":
        return os.environ.get("DB_NAME_PROD", "magicai_prod")
    return "videoai_database"


MONGO_URL: str = os.environ["MONGO_URL"]
DB_NAME: str = _resolve_db_name()

client: AsyncIOMotorClient = AsyncIOMotorClient(MONGO_URL)
db: AsyncIOMotorDatabase = client[DB_NAME]


def get_db() -> AsyncIOMotorDatabase:
    """FastAPI `Depends()`-friendly accessor for the shared DB handle."""
    return db


__all__ = ["MONGO_URL", "DB_NAME", "client", "db", "get_db"]
