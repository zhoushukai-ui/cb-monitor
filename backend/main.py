"""CB Monitor — FastAPI application entry point.

A lightweight convertible-bond redemption calendar and market ranking tool.
Designed for single-person operation on AWS EC2.

Usage:
    uvicorn main:app --reload
    # or
    python main.py
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from config import BACKEND_DIR, DEBUG
from database import init_db
from routers import pages, api, admin

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cb-monitor")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("Starting CB Monitor…")
    await init_db()
    logger.info("Database ready.")
    yield
    logger.info("Shutdown complete.")


app = FastAPI(
    title="CB Monitor",
    description="Convertible Bond Redemption Calendar & Market Data",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Static files ──────────────────────────────────────────────────

static_dir = BACKEND_DIR / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ── Routes ────────────────────────────────────────────────────────

app.include_router(pages.router)
app.include_router(api.router)
app.include_router(admin.router)


# ── Page view tracking middleware ─────────────────────────────────

_SKIP_PATHS = {"/health", "/favicon.ico"}
_SKIP_PREFIXES = {"/static", "/api/"}


@app.middleware("http")
async def track_page_view(request: Request, call_next):
    """Increment daily page view counter for non-API page loads."""
    response = await call_next(request)
    path = request.url.path

    # Skip non-page paths
    if path in _SKIP_PATHS or any(path.startswith(p) for p in _SKIP_PREFIXES):
        return response

    # Ensure path ends with / for consistency
    if path and not path.endswith("/"):
        path += "/"

    import datetime
    from database import PageViewLog, AsyncSessionLocal
    from sqlalchemy import select

    async def _log_view():
        try:
            async with AsyncSessionLocal() as session:
                today = datetime.date.today()
                result = await session.execute(
                    select(PageViewLog).where(
                        PageViewLog.path == path,
                        PageViewLog.date == today,
                    )
                )
                existing = result.scalar_one_or_none()
                if existing:
                    existing.count += 1
                    existing.updated_at = datetime.datetime.utcnow()
                else:
                    session.add(PageViewLog(path=path, date=today))
                await session.commit()
        except Exception:
            logger.debug("Failed to log page view for %s", path, exc_info=True)

    import asyncio
    asyncio.create_task(_log_view())

    return response


# ── Language switch ───────────────────────────────────────────────

@app.post("/api/set-lang")
async def set_lang(lang: str = Form(...), redirect: str = Form("/")):
    """Set language preference via cookie and redirect back."""
    response = RedirectResponse(url=redirect, status_code=302)
    response.set_cookie(key="lang", value=lang, max_age=365 * 24 * 3600, path="/")
    return response


# ── Theme switch ─────────────────────────────────────────────────

@app.post("/api/set-theme")
async def set_theme(theme: str = Form(...), redirect: str = Form("/")):
    """Set theme preference (dark/light) via cookie."""
    response = RedirectResponse(url=redirect, status_code=302)
    response.set_cookie(key="theme", value=theme, max_age=365 * 24 * 3600, path="/")
    return response


# ── Health check ──────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


# ── Run directly ──────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    from config import PORT
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=DEBUG)
