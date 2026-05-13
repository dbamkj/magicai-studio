"""Session 36 — HMAC-signed URL helpers for local file serving (Sprint 2).

DPDPA Article 7(c): Data Fiduciaries must protect personal data with
reasonable security safeguards. Local-disk file URLs (avatar uploads,
generated outputs) used to be unguessable but enumerable. Now URLs
are signed with a short-lived HMAC so they expire and can't be shared
indefinitely.

Helper API:
    from core.signed_urls import sign_path, verify_signature

    # Signing (server → client)
    sig, exp = sign_path('preview_xyz.mp4', expires_in=3600)
    url = f"/api/serve-file/preview_xyz.mp4?sig={sig}&exp={exp}"

    # Verifying (incoming request)
    ok = verify_signature(filename, sig=sig, exp=exp)
    if not ok:
        raise HTTPException(403, 'Signature invalid or expired')

The signing key is derived from the JWT secret so we don't need a
separate env var. Tokens are HMAC-SHA256 base64url-encoded, 22 chars
on the wire (no padding).
"""
import hmac
import hashlib
import base64
import time
from typing import Optional

from core.config import JWT_SECRET


def _sign(path: str, exp: int) -> str:
    """Compute the signature for a (path, exp) pair."""
    msg = f"{path}|{exp}".encode()
    key = (JWT_SECRET or 'unsigned-fallback-do-not-use').encode()
    digest = hmac.new(key, msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip('=')


def sign_path(path: str, *, expires_in: int = 3600) -> tuple[str, int]:
    """Generate a signature + expiry timestamp for a file path.

    Args:
        path: file name or relative path (not the absolute disk path)
        expires_in: seconds until expiry (default 1 hour)

    Returns:
        (sig, exp) where exp is a unix epoch second.
    """
    exp = int(time.time()) + max(60, int(expires_in))
    return _sign(path, exp), exp


def verify_signature(path: str, *, sig: Optional[str], exp: Optional[int]) -> bool:
    """Constant-time verify a signed-URL request.

    Returns True iff (sig, exp) match what sign_path() would produce
    AND exp is still in the future.
    """
    if not sig or not exp:
        return False
    try:
        exp_int = int(exp)
    except (TypeError, ValueError):
        return False
    if time.time() > exp_int:
        return False
    expected = _sign(path, exp_int)
    return hmac.compare_digest(expected, str(sig))


def sign_url(path: str, *, expires_in: int = 3600) -> str:
    """Convenience: returns a fully-qualified signed URL path (path?sig=...&exp=...).

    The host/scheme is left to the caller — this function only handles
    the path + querystring.
    """
    sig, exp = sign_path(path, expires_in=expires_in)
    return f"/api/serve-file/{path}?sig={sig}&exp={exp}"
