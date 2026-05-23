"""Web page routes — server-rendered HTML pages.

All pages support i18n via cookie/header/IP detection.
"""

import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

import config
from database import get_db, Bond, RedemptionEvent, StockInfo
from i18n import resolve_lang, t

# Manual Jinja2 setup (bypassing Starlette's Jinja2Templates
# which can conflict with our templates/ directory).
from pathlib import Path
import jinja2

_templates_dir = Path(__file__).resolve().parent.parent / "templates"
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_templates_dir)),
    autoescape=True,
)

router = APIRouter()


async def _get_lang(request: Request) -> str:
    """Resolve language for the request context."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    return await resolve_lang(
        cookie_lang=request.cookies.get("lang"),
        accept_language=request.headers.get("accept-language", ""),
        client_ip=client_ip,
    )


def _get_theme(request: Request) -> str:
    """Resolve theme: cookie or default to dark (Bloomberg-style)."""
    return request.cookies.get("theme", "dark")


def _toggle_theme(current: str) -> str:
    return "light" if current == "dark" else "dark"


def _stock_prefix(stock_code: str | None) -> str:
    """Determine East Money URL prefix for a stock code.

    Shanghai: 60x/68x → 'sh'
    Shenzhen: 00x/30x → 'sz'
    Beijing:  4x/8x  → 'bj'
    """
    if not stock_code:
        return ""
    if stock_code.startswith(("60", "68", "90")):
        return "sh"
    if stock_code.startswith(("00", "30")):
        return "sz"
    if stock_code[0] in ("4", "8"):
        return "bj"
    return ""


def _days_left(target_date) -> int | None:
    """Calculate days from today to target_date."""
    if not target_date:
        return None
    delta = target_date - datetime.date.today()
    return delta.days


@router.get("/", response_class=HTMLResponse)
async def homepage(
    request: Request,
    search: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Homepage — shows upcoming redemption events and market summary."""
    lang = await _get_lang(request)
    theme = _get_theme(request)

    # Upcoming redemptions (next 30 days)
    today = datetime.date.today()
    cutoff = today + datetime.timedelta(days=30)

    query = select(RedemptionEvent).where(
        RedemptionEvent.status.in_(["announced", "ongoing"]),
        RedemptionEvent.last_trade_date.isnot(None),
        RedemptionEvent.last_trade_date >= today,
        RedemptionEvent.last_trade_date <= cutoff,
    )

    if search:
        term = f"%{search}%"
        query = query.where(
            RedemptionEvent.bond_code.ilike(term)
            | RedemptionEvent.bond_name.ilike(term)
        )

    result = await db.execute(query.order_by(RedemptionEvent.last_trade_date.asc()).limit(10))
    upcoming = list(result.scalars().all())

    # Market stats
    stats_result = await db.execute(
        select(Bond).order_by(desc(Bond.id)).limit(1)
    )
    latest_bond = stats_result.scalar_one_or_none()

    return HTMLResponse(_render_page(
        request, "index.html", _ctx(lang, theme, {
            "upcoming": upcoming,
            "stats_bonds": latest_bond,
            "search": search,
        })
    ))


@router.get("/calendar", response_class=HTMLResponse)
async def calendar_page(
    request: Request,
    status: str = "",
    search: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Redemption / put / maturity calendar with filters."""
    lang = await _get_lang(request)
    theme = _get_theme(request)

    query = select(RedemptionEvent).order_by(
        RedemptionEvent.last_trade_date.asc().nullslast()
    )

    if status:
        query = query.where(RedemptionEvent.status == status)
    else:
        query = query.where(
            RedemptionEvent.status.in_(["announced", "ongoing"])
        )

    if search:
        term = f"%{search}%"
        query = query.where(
            RedemptionEvent.bond_code.ilike(term)
            | RedemptionEvent.bond_name.ilike(term)
        )

    result = await db.execute(query)
    events = list(result.scalars().all())

    return HTMLResponse(_render_page(
        request, "calendar.html", _ctx(lang, theme, {
            "events": events,
            "current_status": status or "all",
            "search": search,
        })
    ))


@router.get("/ranking", response_class=HTMLResponse)
async def ranking_page(
    request: Request,
    sort_by: str = "premium_rate",
    order: str = "asc",
    search: str = "",
    rating: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Full market convertible-bond ranking table with search & filters."""
    lang = await _get_lang(request)
    theme = _get_theme(request)

    # Get latest snapshot of all bonds
    latest_subq = select(Bond.snapshot_date).order_by(desc(Bond.snapshot_date)).limit(1).scalar_subquery()

    query = select(Bond).where(Bond.snapshot_date == latest_subq)

    # Text search across bond code/name and stock code/name
    if search:
        term = f"%{search}%"
        query = query.where(
            Bond.bond_code.ilike(term)
            | Bond.bond_name.ilike(term)
            | Bond.stock_code.ilike(term)
            | Bond.stock_name.ilike(term)
        )

    # Rating filter
    if rating:
        query = query.where(Bond.rating == rating)

    # Ordering
    sort_col = getattr(Bond, sort_by, Bond.premium_rate)
    order_fn = asc if order == "asc" else desc
    query = query.order_by(order_fn(sort_col)).limit(500)

    result = await db.execute(query)
    bonds = list(result.scalars().all())

    return HTMLResponse(_render_page(
        request, "ranking.html", _ctx(lang, theme, {
            "bonds": bonds,
            "sort_by": sort_by,
            "order": order,
            "search": search,
            "rating": rating,
        })
    ))


@router.get("/bond/{code}", response_class=HTMLResponse)
async def bond_detail_page(
    request: Request,
    code: str,
    db: AsyncSession = Depends(get_db),
):
    """Single bond detail page."""
    lang = await _get_lang(request)
    theme = _get_theme(request)

    # Latest snapshot
    result = await db.execute(
        select(Bond)
        .where(Bond.bond_code == code)
        .order_by(desc(Bond.snapshot_date))
        .limit(1)
    )
    bond = result.scalar_one_or_none()

    # Redemption event if any
    result2 = await db.execute(
        select(RedemptionEvent)
        .where(RedemptionEvent.bond_code == code)
        .order_by(desc(RedemptionEvent.created_at))
        .limit(1)
    )
    event = result2.scalar_one_or_none()

    # Stock fundamentals if available
    stock_info = None
    if bond and bond.stock_code:
        result3 = await db.execute(
            select(StockInfo).where(StockInfo.stock_code == bond.stock_code)
        )
        stock_info = result3.scalar_one_or_none()

    return HTMLResponse(_render_page(
        request, "bond_detail.html", _ctx(lang, theme, {
            "bond": bond,
            "event": event,
            "stock_info": stock_info,
        })
    ))


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Admin dashboard — requires ADMIN_TOKEN env to be set."""
    lang = await _get_lang(request)
    theme = _get_theme(request)
    has_admin_token = bool(config.ADMIN_TOKEN)

    return HTMLResponse(_render_page(
        request, "admin.html", _ctx(lang, theme, {
            "has_admin_token": has_admin_token,
            "has_auth": request.cookies.get("admin_token") == config.ADMIN_TOKEN,
        })
    ))


# ── Helpers ────────────────────────────────────────────────────────

def _ctx(lang: str, theme: str, extra: dict) -> dict:
    """Build shared template context with i18n, theme, and utilities."""
    return {
        "lang": lang,
        "theme": theme,
        "toggle_theme": "light" if theme == "dark" else "dark",
        "t": lambda key: t(lang, key),
        "days_left": _days_left,
        "display_name": lambda name, code: code if lang == "en" else (name or code),
        "stock_prefix": _stock_prefix,
        "show_name": lang != "en",
        **extra,
    }


def _render_page(request: Request, template_name: str, context: dict) -> str:
    """Render a Jinja2 template with shared context."""
    context["request"] = request
    template = _jinja_env.get_template(template_name)
    return template.render(**context)
