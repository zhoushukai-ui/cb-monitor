"""Admin API — auth, stats dashboard, and manual data sync.

All endpoints require a valid admin_token cookie matching ADMIN_TOKEN.
"""

import datetime
import logging

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import ADMIN_TOKEN
from database import PageViewLog, AsyncSessionLocal, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin")


# ── Auth dependency ───────────────────────────────────────────────

async def require_admin(admin_token: str = Cookie("", alias="admin_token")):
    """Raise 403 if admin token cookie is invalid."""
    if not ADMIN_TOKEN or admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Unauthorized")


# ── Login ─────────────────────────────────────────────────────────

@router.post("/login")
async def admin_login(token: str = Form(...)):
    """Validate token and set auth cookie."""
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

    resp = JSONResponse({"ok": True})
    resp.set_cookie(
        key="admin_token", value=token,
        max_age=86400 * 7, path="/", httponly=True,
    )
    return resp


@router.post("/logout")
async def admin_logout():
    """Clear admin auth cookie."""
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(key="admin_token", path="/")
    return resp


# ── Stats ─────────────────────────────────────────────────────────

@router.get("/stats")
async def admin_stats(
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Return daily page view stats for the last 14 days."""
    cutoff = datetime.date.today() - datetime.timedelta(days=14)

    result = await db.execute(
        select(PageViewLog)
        .where(PageViewLog.date >= cutoff)
        .order_by(desc(PageViewLog.date), PageViewLog.path)
    )
    logs = result.scalars().all()

    # Group by date
    stats = {}
    for log in logs:
        key = str(log.date)
        if key not in stats:
            stats[key] = {"date": key, "total": 0, "paths": {}}
        stats[key]["total"] += log.count
        stats[key]["paths"][log.path] = log.count

    return [
        {"date": k, "total": v["total"], "paths": v["paths"]}
        for k, v in sorted(stats.items(), reverse=True)
    ]


# ── Sync (in-memory status) ──────────────────────────────────────

_sync_running = False
_last_sync_time: datetime.datetime | None = None
_last_sync_result: str = ""


@router.post("/sync")
async def admin_sync(
    _=Depends(require_admin),
):
    """Trigger data sync in the background."""
    global _sync_running

    if _sync_running:
        return {"status": "running", "message": "Sync already in progress"}

    _sync_running = True

    import asyncio
    from services.collector import collect_all

    async def _run_sync():
        global _sync_running, _last_sync_time, _last_sync_result
        try:
            async with AsyncSessionLocal() as session:
                result = await collect_all(session)
            _last_sync_result = f"OK: {result}"
            logger.info("Admin sync completed: %s", result)
        except Exception as exc:
            _last_sync_result = f"ERROR: {exc}"
            logger.error("Admin sync failed: %s", exc)
        finally:
            _sync_running = False

    _last_sync_time = datetime.datetime.now()
    asyncio.create_task(_run_sync())

    return {"status": "started", "message": "Sync started"}


@router.get("/sync-status")
async def admin_sync_status(
    _=Depends(require_admin),
):
    """Return current sync status."""
    return {
        "running": _sync_running,
        "last_sync": _last_sync_time.isoformat() if _last_sync_time else None,
        "last_result": _last_sync_result,
    }
