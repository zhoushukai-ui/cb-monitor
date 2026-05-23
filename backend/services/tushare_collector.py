"""Tushare Pro data collector — stock fundamentals and industry data.

Requires TUSHARE_TOKEN set in environment (get one at https://tushare.pro).
If no token is configured, all functions are no-ops.
"""

import datetime
import logging

import pandas as pd

from config import TUSHARE_TOKEN

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────

def _ts_code(stock_code: str) -> str:
    """Convert simple stock code (600000) to Tushare format (600000.SH)."""
    if not stock_code:
        return ""
    if stock_code.startswith(("60", "68", "90")):
        return f"{stock_code}.SH"
    if stock_code.startswith(("00", "30")):
        return f"{stock_code}.SZ"
    if stock_code[0] in ("4", "8"):
        return f"{stock_code}.BJ"
    return stock_code


def _simple_code(ts_code: str) -> str:
    """Convert Tushare ts_code (600000.SH) back to simple code (600000)."""
    return ts_code.split(".")[0] if "." in ts_code else ts_code


def _get_pro():
    """Create a Tushare Pro API instance if token is available."""
    if not TUSHARE_TOKEN:
        return None
    import tushare as ts
    ts.set_token(TUSHARE_TOKEN)
    return ts.pro_api()


# ── Fetchers ────────────────────────────────────────────────────────

async def fetch_stock_basic(pro) -> pd.DataFrame:
    """Fetch all A-share stock listings with industry classification.

    Returns DataFrame with columns: ts_code, name, industry, market.
    Industry is Shenwan first-level classification (申万一级行业).
    """
    logger.info("Fetching Tushare stock_basic…")

    try:
        df = pro.stock_basic(
            fields="ts_code,name,industry,market,list_status"
        )
    except Exception as exc:
        logger.error("Tushare stock_basic fetch failed: %s", exc)
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    # Keep only A-share main board / SME / GEM / STAR
    valid_markets = {"主板", "中小板", "创业板", "科创板"}
    df = df[df.get("market", "").isin(valid_markets)].copy()

    return df


async def fetch_daily_basic(pro, stock_codes: list[str]) -> pd.DataFrame:
    """Fetch daily PE/PB/market-cap for a list of stock codes.

    Args:
        pro: Tushare Pro API instance.
        stock_codes: Simple stock codes like ["600000", "000001"].

    Returns DataFrame with columns: ts_code, pe_ttm, pb, total_mv, trade_date.
    """
    if not stock_codes:
        return pd.DataFrame()

    ts_codes = [_ts_code(c) for c in stock_codes if c]
    if not ts_codes:
        return pd.DataFrame()

    logger.info("Fetching Tushare daily_basic for %d stocks…", len(ts_codes))

    # Use the most recent weekday as trade date
    trade_date = datetime.date.today()
    while trade_date.weekday() >= 5:  # Mon=0, Sun=6 → Sat/Sun skip back
        trade_date -= datetime.timedelta(days=1)
    trade_date_str = trade_date.strftime("%Y%m%d")

    rows = []
    # Tushare free tier allows batch query with comma-separated codes
    for i in range(0, len(ts_codes), 200):  # batch in chunks of 200
        batch = ts_codes[i:i + 200]
        try:
            df = pro.daily_basic(
                ts_code=",".join(batch),
                trade_date=trade_date_str,
                fields="ts_code,trade_date,pe_ttm,pb,total_mv",
            )
            if df is not None and not df.empty:
                rows.append(df)
        except Exception as exc:
            logger.warning("Tushare daily_basic batch failed: %s", exc)

    if not rows:
        return pd.DataFrame()

    result = pd.concat(rows, ignore_index=True)
    return result


# ── Store to DB ────────────────────────────────────────────────────

async def store_stock_info(session, df: pd.DataFrame):
    """Upsert stock fundamental data into StockInfo table."""
    if df is None or df.empty:
        return 0

    from sqlalchemy import select
    from database import StockInfo

    # Determine data source type: basic (industry) or daily (PE/PB)
    has_industry = "industry" in df.columns
    has_fundamentals = "pe_ttm" in df.columns

    today = datetime.date.today()
    count = 0

    for _, row in df.iterrows():
        ts_code = row.get("ts_code", "")
        simple = _simple_code(ts_code) if ts_code else row.get("stock_code", "")
        if not simple:
            continue

        # Check existing
        result = await session.execute(
            select(StockInfo).where(StockInfo.stock_code == simple)
        )
        existing = result.scalar_one_or_none()

        if existing:
            if has_industry and row.get("industry"):
                existing.industry = row["industry"]
                existing.stock_name = row.get("name", existing.stock_name)
            if has_fundamentals:
                if row.get("pe_ttm"):
                    existing.pe_ttm = float(row["pe_ttm"])
                if row.get("pb"):
                    existing.pb = float(row["pb"])
                if row.get("total_mv"):
                    existing.market_cap = float(row["total_mv"])
            existing.snapshot_date = today
        else:
            data = {
                "stock_code": simple,
                "stock_name": row.get("name") or row.get("stock_name", ""),
                "snapshot_date": today,
            }
            if has_industry:
                data["industry"] = row.get("industry")
            if has_fundamentals:
                data["pe_ttm"] = row.get("pe_ttm")
                data["pb"] = row.get("pb")
                data["market_cap"] = row.get("total_mv")
            session.add(StockInfo(**data))

        count += 1

    await session.commit()
    logger.info("Stored %d stock info records", count)
    return count


# ── Main entry point ───────────────────────────────────────────────

async def collect_stock_info(session):
    """Fetch stock fundamentals and industry data from Tushare.

    This is called from collect_all() in collector.py.
    Returns a dict with record counts or skips if token is unset.
    """
    pro = _get_pro()
    if pro is None:
        logger.info("TUSHARE_TOKEN not set — skipping Tushare data collection")
        return {"stock_info": 0, "daily_basic": 0}

    from sqlalchemy import func, select
    from database import Bond, StockInfo

    today = datetime.date.today()

    # 1. Stock basic (industry) — only if we have no industry data yet
    basic_count = 0
    result = await session.execute(
        select(func.count()).select_from(StockInfo).where(StockInfo.industry.isnot(None))
    )
    has_industry_data = result.scalar() > 0

    if not has_industry_data:
        basic_df = await fetch_stock_basic(pro)
        basic_count = await store_stock_info(session, basic_df)
        logger.info("Stock basic (industry) done — sleeping 65s for rate limit…")
        import asyncio
        await asyncio.sleep(65)
    else:
        logger.info("Industry data already exists — skipping stock_basic")

    # 2. Daily fundamentals for stocks we know about
    result = await session.execute(
        select(Bond.stock_code)
        .where(Bond.snapshot_date == today, Bond.stock_code.isnot(None))
        .distinct()
    )
    known_stocks = [row[0] for row in result.fetchall() if row[0]]

    daily_df = await fetch_daily_basic(pro, known_stocks)
    daily_count = await store_stock_info(session, daily_df)

    return {
        "stock_info": basic_count,
        "daily_basic": daily_count,
    }
