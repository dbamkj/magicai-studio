"""Phase 3 — Content Intelligence: Nightly Trending Score Engine.

Computes a `score` for every active template using:
  * usage_count (weighted 10x)   — strongest signal
  * view_count  (weighted 1x)    — discovery signal
  * completion_count (weighted 5x) — conversion signal
  * rating_avg  (weighted 15x)   — quality signal
  * share_count (weighted 8x)    — virality signal
  * recency_bonus — boost for recently created / recently used templates
  * festival_bonus — large boost if this template's festival_pack matches
    the current calendar month's festival(s).

The top 20% of scored templates get `is_trending=True` automatically.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("trending")
logger.setLevel(logging.INFO)


# Festival → month calendar (approximate — real festivals are lunar; a human
# editor can tune these via the constants file).
FESTIVAL_MONTHS = {
    "janmashtami": [8, 9],     # Aug / Sep
    "mahashivratri": [2, 3],   # Feb / Mar
    "navratri": [9, 10, 4],    # Sep / Oct (Sharad) + Apr (Chaitra)
}


def _recency_bonus(iso_ts: Optional[str], now: datetime) -> float:
    """Templates < 7 days old get +50, <30 days +20, <90 days +5."""
    if not iso_ts:
        return 0.0
    try:
        ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except Exception:
        return 0.0
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    age_days = (now - ts).total_seconds() / 86400.0
    if age_days < 7:
        return 50.0
    if age_days < 30:
        return 20.0
    if age_days < 90:
        return 5.0
    return 0.0


def _festival_bonus(festival_pack: Optional[str], now: datetime) -> float:
    """+120 if this festival's month window contains today. +40 if it's adjacent month (±1)."""
    if not festival_pack:
        return 0.0
    months = FESTIVAL_MONTHS.get(festival_pack)
    if not months:
        return 0.0
    m = now.month
    if m in months:
        return 120.0
    # Adjacent month boost
    for ftm in months:
        if abs(ftm - m) == 1 or abs(ftm - m) == 11:
            return 40.0
    return 0.0


def compute_score(tpl: dict, *, now: Optional[datetime] = None) -> float:
    """Pure function — compute trending score for a single template doc."""
    now = now or datetime.now(timezone.utc)
    usage = int(tpl.get("usage_count", 0) or 0)
    views = int(tpl.get("view_count", 0) or 0)
    completions = int(tpl.get("completion_count", 0) or 0)
    shares = int(tpl.get("share_count", 0) or 0)
    r_sum = float(tpl.get("rating_sum", 0.0) or 0.0)
    r_cnt = int(tpl.get("rating_count", 0) or 0)
    rating_avg = (r_sum / r_cnt) if r_cnt else 0.0  # 0 to 5

    base = (
        usage * 10.0
        + views * 1.0
        + completions * 5.0
        + shares * 8.0
        + rating_avg * 15.0
    )
    base += _recency_bonus(tpl.get("created_at"), now)
    base += _recency_bonus(tpl.get("updated_at"), now) * 0.5
    base += _festival_bonus(tpl.get("festival_pack"), now)
    return round(base, 2)


async def recompute_all(db) -> dict:
    """Recompute `score` on every active template. Flag top 20% as is_trending.

    Returns {total, updated, trending_count, top_3:[...]} for logging / admin UI.
    """
    now = datetime.now(timezone.utc)
    cursor = db.templates.find({"is_active": True}, {"_id": 0})
    docs = await cursor.to_list(length=10000)
    if not docs:
        return {"total": 0, "updated": 0, "trending_count": 0, "top_3": []}

    scored = []
    for d in docs:
        s = compute_score(d, now=now)
        scored.append((d["id"], s, d.get("title", "")))

    # Decide trending: top 20% by score (min 3 cap)
    scored.sort(key=lambda t: t[1], reverse=True)
    trend_cutoff = max(3, int(len(scored) * 0.2))
    trending_ids = {tid for tid, _, _ in scored[:trend_cutoff]}

    # Bulk update. Motor doesn't have bulk_write for 1-by-1 simplicity, but we
    # can batch via update_many per value bucket.
    updated = 0
    for tid, s, _ in scored:
        await db.templates.update_one(
            {"id": tid},
            {"$set": {
                "score": s,
                "is_trending": tid in trending_ids,
                "updated_at": now.isoformat(),
            }},
        )
        updated += 1

    top_3 = [{"id": tid, "score": s, "title": title} for tid, s, title in scored[:3]]
    logger.info(
        f"trending: recomputed={updated} trending_flagged={len(trending_ids)} "
        f"top1={top_3[0]['title'] if top_3 else 'n/a'} ({top_3[0]['score'] if top_3 else 0})"
    )
    return {
        "total": len(scored),
        "updated": updated,
        "trending_count": len(trending_ids),
        "top_3": top_3,
        "ran_at": now.isoformat(),
    }
