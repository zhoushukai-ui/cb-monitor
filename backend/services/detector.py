"""Event detection — finds new or changed redemption events
by comparing consecutive data snapshots.

Used for alert generation (email notifications).
For MVP this is minimal; the calendar page reads redemption_events directly.
"""

import datetime
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import RedemptionEvent

logger = logging.getLogger(__name__)


async def get_upcoming_events(
    session: AsyncSession,
    days_ahead: int = 30,
) -> list[RedemptionEvent]:
    """Return active redemption events with deadlines within *days_ahead*.

    Results are ordered by last_trade_date ASC (most urgent first).
    """
    today = datetime.date.today()
    cutoff = today + datetime.timedelta(days=days_ahead)

    result = await session.execute(
        select(RedemptionEvent)
        .where(
            RedemptionEvent.status.in_(["announced", "ongoing"]),
            RedemptionEvent.last_trade_date.isnot(None),
            RedemptionEvent.last_trade_date <= cutoff,
            RedemptionEvent.last_trade_date >= today,
        )
        .order_by(RedemptionEvent.last_trade_date.asc())
    )
    return list(result.scalars().all())


async def get_active_redemptions(session: AsyncSession) -> list[RedemptionEvent]:
    """Return all bonds currently in announced/ongoing redemption."""
    result = await session.execute(
        select(RedemptionEvent).where(
            RedemptionEvent.status.in_(["announced", "ongoing"]),
        ).order_by(RedemptionEvent.last_trade_date.asc().nullslast())
    )
    return list(result.scalars().all())
