"""Upload endpoints — Phase-B server.py refactor (first extraction).

Consolidates the image / URL / base64 / face-image upload routes that
used to live inline in server.py. All accept authenticated requests
(via get_current_user), persist the payload under UPLOAD_DIR, and
return a consistent { url, file_id, file_path, file_type } shape.

Extracted endpoints:
  • POST /api/upload-image        — multipart image upload
  • POST /api/upload-from-url     — download a remote image/video URL
  • POST /api/upload-base64       — raw or dataURL base64 image
  • POST /api/upload-face-image   — face-image upload (for swap/lipsync)

Next candidates for extraction: /upload-video, /upload-audio,
/extract-frames, /transcribe-audio, /merge-segments (audio+video IO
helpers — lines 1811-2295 of the legacy server.py).
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from PIL import Image
from pydantic import BaseModel

from core.auth import get_current_user

log = logging.getLogger("routes.uploads")
router = APIRouter(prefix="/api", tags=["uploads"])

# Shared with server.py — same upload directory.
UPLOAD_DIR = Path("/app/backend/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────── Schemas ───────────────────────────────────────

class Base64UploadRequest(BaseModel):
    base64: str
    filename: Optional[str] = None


class UploadFromUrlRequest(BaseModel):
    url: str
    filename: Optional[str] = None


# ─────────────────────────── Routes ────────────────────────────────────────

@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...), request: Request = None):
    """Standard multipart image upload. Re-encodes files > 10MB to JPEG q=85."""
    from core.upload_safety import validate_image_upload
    await get_current_user(request)
    fid = str(uuid.uuid4())
    ext = Path(file.filename or "img.jpg").suffix or ".jpg"
    sp = UPLOAD_DIR / f"img_{fid}{ext}"
    content = await file.read()
    validate_image_upload(content, content_type=file.content_type, filename=file.filename)
    with open(sp, "wb") as f:
        f.write(content)
    try:
        Image.open(sp)
        if len(content) / (1024 * 1024) > 10:
            Image.open(sp).save(sp, "JPEG", quality=85)
    except Exception:
        pass
    serve_url = f"/api/serve-file/{sp.name}"
    return {"url": serve_url, "file_id": fid, "file_path": str(sp), "file_type": "image"}


@router.post("/upload-from-url")
async def upload_from_url(req: UploadFromUrlRequest, request: Request = None):
    """Download a remote image / short video URL and stash it under
    UPLOAD_DIR. Lets the frontend avoid browser CORS restrictions when
    re-using template thumbnails / preview clips that live on an external
    CDN (e.g. Pexels). Returns the same shape as /upload-image.
    """
    await get_current_user(request)
    url = (req.url or "").strip()
    if not url or not url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="url must be http(s)")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), follow_redirects=True) as c:
            r = await c.get(url)
            if r.status_code != 200:
                raise HTTPException(status_code=400, detail=f"fetch failed {r.status_code}")
            data = r.content
            ct = (r.headers.get("content-type") or "").lower()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"download error: {e}")
    if len(data) < 200:
        raise HTTPException(status_code=400, detail="empty payload")
    if ct.startswith("video/"):
        ext = ".mp4"
        ftype = "video"
    elif ct.startswith("image/"):
        ext = (
            ".jpg" if ("jpeg" in ct or "jpg" in ct)
            else ".png" if "png" in ct
            else ".webp" if "webp" in ct
            else ".jpg"
        )
        ftype = "image"
    else:
        low = url.lower().split("?")[0]
        if low.endswith((".mp4", ".mov", ".webm")):
            ext, ftype = ".mp4", "video"
        elif low.endswith((".png", ".webp", ".jpg", ".jpeg")):
            ext, ftype = "." + low.rsplit(".", 1)[-1], "image"
        else:
            raise HTTPException(status_code=400, detail=f"unsupported content-type: {ct}")
    fid = str(uuid.uuid4())
    sp = UPLOAD_DIR / f"fromurl_{fid}{ext}"
    with open(sp, "wb") as f:
        f.write(data)
    if ftype == "image":
        try:
            Image.open(sp)
            if len(data) / (1024 * 1024) > 10:
                Image.open(sp).save(sp, "JPEG", quality=85)
        except Exception:
            pass
    serve_url = f"/api/serve-file/{sp.name}"
    return {"url": serve_url, "file_id": fid, "file_path": str(sp), "file_type": ftype}


@router.post("/upload-base64")
async def upload_base64(req: Base64UploadRequest, request: Request = None):
    """Simple base64 upload helper used by Divine Transform wizard and any
    future screens that have images pre-loaded in memory. Accepts raw
    base64 (no prefix) OR a dataURL (data:image/...;base64,...).
    """
    await get_current_user(request)
    import base64 as _b64
    raw = req.base64 or ""
    if raw.startswith("data:"):
        try:
            raw = raw.split(",", 1)[1]
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid dataURL")
    try:
        blob = _b64.b64decode(raw, validate=False)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64")
    if len(blob) < 128:
        raise HTTPException(status_code=400, detail="Image too small")
    if len(blob) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (>15MB)")
    fid = str(uuid.uuid4())
    ext = Path(req.filename or "img.jpg").suffix.lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    sp = UPLOAD_DIR / f"b64_{fid}{ext}"
    with open(sp, "wb") as f:
        f.write(blob)
    serve_url = f"/api/serve-file/{sp.name}"
    return {"url": serve_url, "file_id": fid, "file_path": str(sp), "file_type": "image"}


@router.post("/upload-face-image")
async def upload_face_image(file: UploadFile = File(...), request: Request = None):
    """Face-image upload for faceswap / lipsync / headswap flows. Returns
    file_id + path (no public serve URL since these are private inputs).
    """
    from core.upload_safety import validate_image_upload
    await get_current_user(request)
    fid = str(uuid.uuid4())
    ext = Path(file.filename or "img.jpg").suffix or ".jpg"
    sp = UPLOAD_DIR / f"{fid}{ext}"
    content = await file.read()
    validate_image_upload(content, content_type=file.content_type, filename=file.filename)
    with open(sp, "wb") as f:
        f.write(content)
    return {"file_id": fid, "file_path": str(sp), "file_type": "face_image"}


__all__ = ["router"]
