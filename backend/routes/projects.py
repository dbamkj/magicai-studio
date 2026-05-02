"""Project CRUD endpoints — extracted from server.py (Phase-B refactor).

Moved here in Session 25 round 9 to shrink server.py. These are the pure
READ/DELETE/download endpoints that don't depend on any background-task
factories. The heavier /project/{id}/rerun endpoint stays in server.py
because it touches ~10 bg-task functions and _dispatch_rerun().

Endpoints:
 • GET    /api/project/{project_id}
 • GET    /api/project/{project_id}/versions
 • GET    /api/projects
 • DELETE /api/project/{project_id}
 • GET    /api/download-video

Auth: All require a valid session via get_current_user (guest allowed
with a synthetic user_id, same semantics as before).
"""
from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from core.db import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["projects"])


def _get_current_user_dep():
    """Lazy-import server.get_current_user to avoid circular import at
    module load time (server.py imports these routes at the bottom)."""
    import server as _srv
    return _srv.get_current_user


@router.get("/project/{project_id}")
async def get_project(project_id: str, request: Request = None):
    """Fetch a single project by ID. Used by avatar-studio / wizard / library
    polling loops — MUST return fast and never 5xx for missing records."""
    get_current_user = _get_current_user_dep()
    await get_current_user(request)
    p = await db.video_projects.find_one({"id": project_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    return p


@router.get("/project/{project_id}/versions")
async def list_project_versions(project_id: str, request: Request = None):
    """Return all versions in the same family (parent + children),
    sorted by version asc. Used by the Library screen to group edits."""
    get_current_user = _get_current_user_dep()
    await get_current_user(request)
    p = await db.video_projects.find_one({"id": project_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    # Root of family = parent_id if set, else the project itself.
    root_id = p.get("parent_id") or p["id"]
    cursor = db.video_projects.find(
        {"$or": [{"id": root_id}, {"parent_id": root_id}]},
        {"_id": 0},
    ).sort("version", 1)
    rows = await cursor.to_list(length=50)
    return {"parent_id": root_id, "count": len(rows), "versions": rows}


@router.get("/projects")
async def get_projects(request: Request = None):
    """List the current user's 100 most-recent projects, newest first.
    Powers the Library / My Videos screen. Guests get their ephemeral
    guest user_id and see only what they created this session."""
    get_current_user = _get_current_user_dep()
    user = await get_current_user(request)
    return (
        await db.video_projects.find(
            {"user_id": user["user_id"]}, {"_id": 0}
        ).sort("created_at", -1).to_list(100)
    )


@router.delete("/project/{project_id}")
async def delete_project(project_id: str, request: Request = None):
    """Hard-delete a project document. Assets on disk are left behind for
    garbage collection (they may still be referenced as parent/source)."""
    get_current_user = _get_current_user_dep()
    await get_current_user(request)
    r = await db.video_projects.delete_one({"id": project_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"message": "Deleted"}


@router.get("/download-video")
async def download_video(url: str):
    """Proxy-download a remote MP4 / PNG so the client gets a proper
    Content-Disposition attachment. Bypasses CORS on the CDN."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), follow_redirects=True) as c:
        resp = await c.get(url)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Download failed")
        ct = resp.headers.get("content-type", "video/mp4")
        ext = "mp4" if "video" in ct else "png"
        return StreamingResponse(
            iter([resp.content]),
            media_type=ct,
            headers={"Content-Disposition": f"attachment; filename=magicai_output.{ext}"},
        )


__all__ = ["router"]
