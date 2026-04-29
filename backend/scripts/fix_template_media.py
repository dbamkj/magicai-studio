"""
Fix mismatched/broken Pixabay media for marketplace_templates.

Problems being fixed:
  • Devi Maa Aarti — thumbnail URL returned 404
  • Soldier's Sacrifice — thumbnail showed clouds instead of soldiers
  • Aunty Roast — thumbnail showed a silhouette instead of an Indian aunty
  • Several others with mismatched imagery

Strategy:
  • Use the live Pixabay API (`core.pixabay`) to look up the correct image
    AND a vertical short-clip video for each template in `MEDIA_OVERRIDES`.
  • Pick the first matching Pixabay hit with the cleanest tags.
  • Set both `thumbnail` (still image) and `preview_url` (mp4 small) so the
    home InspirationGrid (static thumb) and the preview Modal (video) both
    look correct.

Run:
  cd /app/backend && python -m scripts.fix_template_media
"""
from __future__ import annotations
import asyncio
import os
import sys
from pathlib import Path

# Make `core` importable when run directly
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env')

from motor.motor_asyncio import AsyncIOMotorClient
from core import pixabay


# id  →  (image_query, video_query)   — both queries are passed to Pixabay
MEDIA_OVERRIDES: dict[str, tuple[str, str]] = {
    # ---- the 3 templates the user explicitly flagged ------------------
    "mp_funny_03":      ("indian aunty saree",      "indian woman saree"),
    "mp_bhajan_04":     ("durga maa goddess",       "diya temple aarti"),
    "mp_emotional_04":  ("indian army soldier",     "indian flag soldier"),

    # ---- a handful of others that frequently looked wrong --------------
    "mp_bhajan_01":     ("krishna god flute",       "krishna idol temple"),
    "mp_bhajan_02":     ("shiva mahadev statue",    "shiva mahadev"),
    "mp_bhajan_03":     ("hanuman temple statue",   "hanuman idol"),
    "mp_festival_01":   ("diwali diya lamps",       "diwali fireworks"),
    "mp_festival_02":   ("holi colors festival",    "holi festival color"),
    "mp_festival_03":   ("ganesh chaturthi idol",   "ganesh idol procession"),
    "mp_festival_04":   ("eid lantern crescent",    "eid mubarak lantern"),
    "mp_emotional_01":  ("indian mother son",       "mother child indian"),
    "mp_emotional_02":  ("father daughter indian",  "father daughter walk"),
    "mp_emotional_03":  ("graduation cap diploma",  "graduation ceremony"),
    "mp_romantic_01":   ("indian couple love",      "couple sunset romance"),
    "mp_romantic_04":   ("indian wedding couple",   "indian wedding"),
}


async def _fetch_best(query: str, kind: str = "image") -> str | None:
    """Return the most reliable URL Pixabay gives us for `query`.

    For images we prefer `webformatURL` (640w cached, very stable).
    For videos we prefer the `tiny` MP4 (smallest, plays everywhere).
    """
    try:
        if kind == "image":
            hits = await pixabay.search_images(query, count=8, orientation="vertical")
            if not hits:
                hits = await pixabay.search_images(query, count=8, orientation="all")
            for h in hits:
                url = h.get("webformatURL") or h.get("largeImageURL") or h.get("previewURL")
                if url:
                    return url
        else:
            if not hasattr(pixabay, "search_videos"):
                return None
            hits = await pixabay.search_videos(query, count=8)
            for h in hits or []:
                vids = (h.get("videos") or {})
                # smaller MP4 → faster on mobile
                for size in ("tiny", "small", "medium", "large"):
                    cand = (vids.get(size) or {}).get("url")
                    if cand:
                        return cand
    except Exception as e:
        print(f"  ! Pixabay {kind} fetch failed for {query!r}: {e}")
    return None


async def go():
    mongo = os.environ["MONGO_URL"]
    # Try every db that might host marketplace_templates
    client = AsyncIOMotorClient(mongo)
    candidates = ["magicai_beta", os.getenv("DB_NAME", "videoai_database"),
                  "magicai_prod", "videoai_database"]
    seen = set()
    target_dbs = []
    for n in candidates:
        if n in seen:
            continue
        seen.add(n)
        cnt = await client[n].marketplace_templates.count_documents({})
        if cnt > 0:
            target_dbs.append((n, cnt))
    print(f"Will patch in: {target_dbs}")

    for dbname, total in target_dbs:
        print(f"\n=== {dbname} ({total} templates) ===")
        db = client[dbname]
        for tid, (img_q, vid_q) in MEDIA_OVERRIDES.items():
            doc = await db.marketplace_templates.find_one({"id": tid}, {"id": 1, "title": 1})
            if not doc:
                print(f"  · {tid:<18}  (skip, not in this db)")
                continue
            print(f"  → {tid:<18}  {doc.get('title','')!r}")
            img_url = await _fetch_best(img_q, "image")
            vid_url = await _fetch_best(vid_q, "video")
            patch = {}
            if img_url:
                patch["thumbnail"] = img_url
                patch["thumbnail_source"] = "pixabay"
            if vid_url:
                patch["preview_url"] = vid_url
                patch["preview_source"] = "pixabay"
            if patch:
                await db.marketplace_templates.update_one({"id": tid}, {"$set": patch})
                print(f"      ✓ thumb={'Y' if img_url else 'N'}  vid={'Y' if vid_url else 'N'}")
            else:
                print("      (no media found)")
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(go())
