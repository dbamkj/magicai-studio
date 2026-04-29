"""
Upload Safety Guardrails — production-grade file validation for /upload-*
endpoints. Enforces size caps, MIME-type whitelists, and magic-byte sniffing
to reject spoofed uploads.

Usage:
    from core.upload_safety import validate_image_upload, validate_video_upload
    bytes_payload = await file.read()
    validate_image_upload(bytes_payload, content_type=file.content_type, filename=file.filename)
"""
from __future__ import annotations

import os
from fastapi import HTTPException

# ---------- Size caps ----------
MAX_IMAGE_BYTES  = int(os.getenv("UPLOAD_MAX_IMAGE_MB", "25")) * 1024 * 1024
MAX_VIDEO_BYTES  = int(os.getenv("UPLOAD_MAX_VIDEO_MB", "200")) * 1024 * 1024
MAX_AUDIO_BYTES  = int(os.getenv("UPLOAD_MAX_AUDIO_MB", "60")) * 1024 * 1024

# ---------- MIME whitelists ----------
IMAGE_MIME_WHITELIST = {
    "image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif",
}
VIDEO_MIME_WHITELIST = {
    "video/mp4", "video/quicktime", "video/x-m4v", "video/webm", "video/mpeg",
}
AUDIO_MIME_WHITELIST = {
    "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/ogg",
    "audio/m4a", "audio/mp4", "audio/aac",
}

# ---------- Magic-byte signatures ----------
# Maps file-format → list of (offset, signature_bytes).
IMAGE_SIGNATURES = {
    "jpeg": [(0, b"\xff\xd8\xff")],
    "png":  [(0, b"\x89PNG\r\n\x1a\n")],
    "webp": [(0, b"RIFF"), (8, b"WEBP")],
    "heic": [(4, b"ftypheic"), (4, b"ftypheix"), (4, b"ftyphevc"), (4, b"ftypmif1"), (4, b"ftypmsf1")],
}
VIDEO_SIGNATURES = {
    "mp4":  [(4, b"ftyp")],   # all ISO BMFF (mp4/m4v/mov-modern) start with ftyp at offset 4
    "mov":  [(4, b"ftypqt"), (4, b"moov"), (4, b"mdat")],
    "webm": [(0, b"\x1a\x45\xdf\xa3")],  # EBML
    "mpeg": [(0, b"\x00\x00\x01\xba"), (0, b"\x00\x00\x01\xb3")],
}


def _matches_any(payload: bytes, sig_dict: dict) -> bool:
    for sigs in sig_dict.values():
        for offset, sig in sigs:
            if payload[offset: offset + len(sig)] == sig:
                return True
    return False


def validate_image_upload(payload: bytes, content_type: str | None = None, filename: str | None = None) -> None:
    """Raise HTTPException 400/413 if the uploaded image violates safety policy."""
    if not payload:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(payload) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image too large (>{MAX_IMAGE_BYTES // (1024 * 1024)} MB). Please compress and try again.",
        )
    ct = (content_type or "").lower().strip()
    if ct and not ct.startswith("image/"):
        raise HTTPException(status_code=400, detail=f"Not an image (Content-Type: {ct})")
    if ct and ct not in IMAGE_MIME_WHITELIST:
        raise HTTPException(status_code=400, detail=f"Unsupported image type: {ct}. Allowed: jpeg, png, webp, heic.")
    # Magic-byte sniff — confirm the file is what its MIME says.
    if not _matches_any(payload[:32], IMAGE_SIGNATURES):
        raise HTTPException(status_code=400, detail="File contents do not look like a valid image (signature mismatch)")


def validate_video_upload(payload: bytes, content_type: str | None = None, filename: str | None = None) -> None:
    """Raise HTTPException 400/413 if the uploaded video violates safety policy."""
    if not payload:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(payload) > MAX_VIDEO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Video too large (>{MAX_VIDEO_BYTES // (1024 * 1024)} MB). Please trim or compress.",
        )
    ct = (content_type or "").lower().strip()
    if ct and not ct.startswith("video/"):
        raise HTTPException(status_code=400, detail=f"Not a video (Content-Type: {ct})")
    if ct and ct not in VIDEO_MIME_WHITELIST:
        raise HTTPException(status_code=400, detail=f"Unsupported video type: {ct}. Allowed: mp4, mov, webm, m4v.")
    if not _matches_any(payload[:32], VIDEO_SIGNATURES):
        raise HTTPException(status_code=400, detail="File contents do not look like a valid video (signature mismatch)")


def validate_audio_upload(payload: bytes, content_type: str | None = None, filename: str | None = None) -> None:
    """Lightweight audio validation — size + MIME only (audio sigs vary too widely)."""
    if not payload:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(payload) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio too large (>{MAX_AUDIO_BYTES // (1024 * 1024)} MB).",
        )
    ct = (content_type or "").lower().strip()
    if ct and not ct.startswith("audio/"):
        raise HTTPException(status_code=400, detail=f"Not an audio file (Content-Type: {ct})")
    if ct and ct not in AUDIO_MIME_WHITELIST:
        raise HTTPException(status_code=400, detail=f"Unsupported audio type: {ct}.")
