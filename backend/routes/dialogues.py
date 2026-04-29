"""Phase-4B Dialogues API — viral one-liners catalog.

Endpoints:
  GET /api/dialogues                  → list dialogues (filter by vibe, lang, limit)
  GET /api/dialogues/random           → 1 random pick (optional vibe filter)
  GET /api/dialogues/vibes            → distinct vibes with counts
  POST /api/dialogues/{id}/use        → bumps usage_count, returns the dialogue
"""
from __future__ import annotations
import os, random, logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

from core.config import DB_NAME

log = logging.getLogger("dialogues")
router = APIRouter(prefix="/api/dialogues", tags=["dialogues"])

MONGO_URL = os.environ["MONGO_URL"]
_client = AsyncIOMotorClient(MONGO_URL)
db = _client[DB_NAME]


def _serialize(d: dict) -> dict:
    out = {k: v for k, v in d.items() if k != "_id"}
    for k, v in out.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
    return out


@router.get("")
async def list_dialogues(
    vibe: Optional[str] = None,
    lang: Optional[str] = None,
    limit: int = 50,
    sort: str = "popular",  # popular | recent | random
):
    q: dict = {"is_active": True}
    if vibe and vibe != "all":
        q["vibe"] = vibe
    if lang:
        q["lang"] = lang

    cursor = db.viral_dialogues.find(q, {"_id": 0})
    items = await cursor.to_list(length=400)

    if sort == "recent":
        items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    elif sort == "random":
        random.shuffle(items)
    else:  # popular
        items.sort(key=lambda x: (int(x.get("usage_count", 0)), int(x.get("share_score", 0))), reverse=True)

    items = [_serialize(x) for x in items[:max(1, min(limit, 200))]]
    return {"dialogues": items, "count": len(items), "vibe": vibe or "all"}


@router.get("/random")
async def random_dialogue(vibe: Optional[str] = None):
    q: dict = {"is_active": True}
    if vibe and vibe != "all":
        q["vibe"] = vibe
    cursor = db.viral_dialogues.aggregate([{"$match": q}, {"$sample": {"size": 1}}, {"$project": {"_id": 0}}])
    docs = await cursor.to_list(length=1)
    if not docs:
        raise HTTPException(status_code=404, detail="No dialogue found.")
    return _serialize(docs[0])


@router.get("/vibes")
async def list_vibes():
    pipe = [
        {"$match": {"is_active": True}},
        {"$group": {"_id": "$vibe", "count": {"$sum": 1}, "lang": {"$first": "$lang"}}},
        {"$sort": {"count": -1}},
    ]
    docs = await db.viral_dialogues.aggregate(pipe).to_list(length=50)
    return {"vibes": [{"id": d["_id"], "count": d["count"], "lang": d.get("lang")} for d in docs], "total": len(docs)}


@router.post("/{dialogue_id}/use")
async def use_dialogue(dialogue_id: str):
    doc = await db.viral_dialogues.find_one({"id": dialogue_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Dialogue not found.")
    try:
        await db.viral_dialogues.update_one({"id": dialogue_id}, {"$inc": {"usage_count": 1}})
    except Exception:
        pass
    return _serialize(doc)
