"""JSON API routes — for AJAX / future SPA client consumption."""

import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, Bond, RedemptionEvent, StockInfo

router = APIRouter(prefix="/api")


@router.get("/bonds")
async def list_bonds(
    sort_by: str = Query("premium_rate"),
    order: str = Query("asc"),
    search: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    """Return latest bond snapshot as JSON array."""
    latest_subq = select(Bond.snapshot_date).order_by(desc(Bond.snapshot_date)).limit(1).scalar_subquery()
    query = select(Bond).where(Bond.snapshot_date == latest_subq)

    if search:
        query = query.where(
            Bond.bond_name.ilike(f"%{search}%") | Bond.bond_code.ilike(f"%{search}%")
        )

    sort_col = getattr(Bond, sort_by, Bond.premium_rate)
    order_fn = asc if order == "asc" else desc
    query = query.order_by(order_fn(sort_col)).limit(500)

    result = await db.execute(query)
    bonds = result.scalars().all()

    # Enrich with stock fundamentals
    stock_codes = [b.stock_code for b in bonds if b.stock_code]
    stock_map = {}
    if stock_codes:
        sr = await db.execute(
            select(StockInfo).where(StockInfo.stock_code.in_(stock_codes))
        )
        for si in sr.scalars().all():
            stock_map[si.stock_code] = si

    def _enrich(bond) -> dict:
        si = stock_map.get(bond.stock_code) if bond.stock_code else None
        return {
            "bond_code": bond.bond_code,
            "bond_name": bond.bond_name,
            "price": bond.price,
            "premium_rate": bond.premium_rate,
            "ytm_ratio": bond.ytm_ratio,
            "remaining_size": bond.remaining_size,
            "rating": bond.rating,
            "stock_price": bond.stock_price,
            "conversion_price": bond.conversion_price,
            "conversion_value": bond.conversion_value,
            "redemption_days_count": bond.redemption_days_count,
            "industry": si.industry if si else None,
            "pe_ttm": si.pe_ttm if si else None,
            "pb": si.pb if si else None,
            "market_cap": si.market_cap if si else None,
        }

    return [_enrich(b) for b in bonds]


@router.get("/redemptions")
async def list_redemptions(
    status: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    """Return active redemption events as JSON array."""
    query = select(RedemptionEvent).order_by(
        RedemptionEvent.last_trade_date.asc().nullslast()
    )

    if status:
        query = query.where(RedemptionEvent.status == status)
    else:
        query = query.where(
            RedemptionEvent.status.in_(["announced", "ongoing"])
        )

    result = await db.execute(query)
    events = result.scalars().all()

    today = datetime.date.today()

    return [
        {
            "bond_code": e.bond_code,
            "bond_name": e.bond_name,
            "event_type": e.event_type,
            "announcement_date": str(e.announcement_date) if e.announcement_date else None,
            "last_trade_date": str(e.last_trade_date) if e.last_trade_date else None,
            "redemption_price": e.redemption_price,
            "status": e.status,
            "days_left": (e.last_trade_date - today).days if e.last_trade_date else None,
        }
        for e in events
    ]
