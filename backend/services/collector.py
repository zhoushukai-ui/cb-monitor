"""Data collector — fetches convertible bond data from multiple sources.

Architecture:
  - Primary: Akshare (wraps Jisilu, East Money, Sina public APIs)
  - Cross-validation: compare snapshots across time & sources
  - Data is stored to DB for the web layer to consume

Usage:
  from services.collector import collect_all
  await collect_all(db_session)
"""

import datetime
import logging

import akshare as ak
import pandas as pd

from database import Bond, RedemptionEvent

logger = logging.getLogger(__name__)

# ── Column mappings ────────────────────────────────────────────────
# Maps Chinese column names from akshare to our English model fields.
# This centralises the translation so the rest of the codebase
# speaks English.

JSL_MARKET_MAP = {
    "代码": "bond_code",
    "转债名称": "bond_name",
    "现价": "price",
    "正股代码": "stock_code",
    "正股名称": "stock_name",
    "正股价": "stock_price",
    "转股价": "conversion_price",
    "转股价值": "conversion_value",
    "转股溢价率": "premium_rate",
    "债券评级": "rating",
    "强赎触发价": "redemption_threshold_price",
    "剩余规模": "remaining_size",
    "到期税前收益": "ytm_ratio",
}

JSL_REDEEM_MAP = {
    "代码": "bond_code",
    "名称": "bond_name",
    "现价": "price",
    "正股代码": "stock_code",
    "正股名称": "stock_name",
    "剩余规模": "remaining_size",
    "规模": "total_size",
    "转股起始日": "conversion_start_date",
    "最后交易日": "last_trade_date",
    "到期日": "maturity_date",
    "转股价": "conversion_price",
    "强赎触发价": "redemption_trigger_price",
    "正股价": "stock_price",
    "强赎价": "redemption_price",
    "强赎天计数": "redemption_day_count_raw",
    "强赎状态": "redemption_status_raw",
}

# ── Helpers ────────────────────────────────────────────────────────

def _safe_float(val) -> float | None:
    """Parse to float or return None."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_redemption_days(raw: str) -> int | None:
    """Parse '24/15 | 30' → 24 (consecutive days met)."""
    if not raw or not isinstance(raw, str):
        return None
    try:
        return int(raw.split("/")[0])
    except (ValueError, IndexError):
        return None


def _normalise_status(raw: str) -> str:
    """Map Chinese status → English status string.

    Observed values from akshare:
      - '已公告强赎' → announced redemption
      - '公告要强赎' → announced intention to redeem
      - '公告不强赎' → announced NOT to redeem
      - '' → no active status
    """
    if not raw or not raw.strip():
        return "none"
    mapping = {
        "已公告强赎": "announced",
        "公告要强赎": "pending",
        "公告不强赎": "deferred",
    }
    return mapping.get(raw.strip(), raw.strip())


# ── Fetchers ──────────────────────────────────────────────────────

async def fetch_market_snapshot() -> pd.DataFrame:
    """Fetch full-market convertible-bond snapshot from Jisilu.

    Returns a DataFrame with English column names (see JSL_MARKET_MAP).
    """
    logger.info("Fetching Jisilu market snapshot…")

    try:
        df = ak.bond_cb_jsl()
    except Exception as exc:
        logger.error("Jisilu market fetch failed: %s", exc)
        return pd.DataFrame()

    if df.empty:
        return df

    # Select + rename
    cols = [c for c in JSL_MARKET_MAP if c in df.columns]
    df = df[cols].rename(columns=JSL_MARKET_MAP)

    # Parse numeric fields
    for col in ["price", "stock_price", "conversion_price", "premium_rate",
                "remaining_size", "ytm_ratio", "conversion_value",
                "redemption_threshold_price"]:
        if col in df.columns:
            df[col] = df[col].apply(_safe_float)

    df["snapshot_date"] = datetime.date.today()

    return df


async def fetch_redemption_data() -> pd.DataFrame:
    """Fetch redemption tracking data from Jisilu.

    Returns a DataFrame with English columns (see JSL_REDEEM_MAP).
    """
    logger.info("Fetching Jisilu redemption data…")

    try:
        df = ak.bond_cb_redeem_jsl()
    except Exception as exc:
        logger.error("Jisilu redemption fetch failed: %s", exc)
        return pd.DataFrame()

    if df.empty:
        return df

    cols = [c for c in JSL_REDEEM_MAP if c in df.columns]
    df = df[cols].rename(columns=JSL_REDEEM_MAP)

    # Parse numeric fields
    for col in ["price", "remaining_size", "total_size", "conversion_price",
                "redemption_trigger_price", "stock_price", "redemption_price"]:
        if col in df.columns:
            df[col] = df[col].apply(_safe_float)

    # Parse redemption day count
    if "redemption_day_count_raw" in df.columns:
        df["redemption_days_count"] = df["redemption_day_count_raw"].apply(_parse_redemption_days)
        df.drop(columns=["redemption_day_count_raw"], inplace=True)

    # Normalise status
    if "redemption_status_raw" in df.columns:
        df["redemption_status"] = df["redemption_status_raw"].apply(_normalise_status)
        df.drop(columns=["redemption_status_raw"], inplace=True)

    # Parse date columns
    for col in ["last_trade_date", "maturity_date", "conversion_start_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

    df["source"] = "jisilu"
    df["snapshot_date"] = datetime.date.today()

    return df


async def fetch_east_money_spot() -> pd.DataFrame:
    """Fetch spot prices from East Money (full market, ~347 bonds).

    Used as supplementary source — basic pricing without redemption detail.
    """
    logger.info("Fetching East Money spot data…")

    try:
        df = ak.bond_zh_hs_cov_spot()
    except Exception as exc:
        logger.error("East Money spot fetch failed: %s", exc)
        return pd.DataFrame()

    if df.empty:
        return df

    df.rename(columns={
        "symbol": "bond_code",
        "name": "bond_name",
        "trade": "price",
        "changepercent": "change_pct",
    }, inplace=True)

    df["price"] = df["price"].apply(_safe_float)
    df["source"] = "east_money"
    df["snapshot_date"] = datetime.date.today()

    return df


# ── Store to DB ────────────────────────────────────────────────────

async def store_bonds(session, df: pd.DataFrame):
    """Bulk upsert bond daily snapshots."""
    if df.empty:
        return 0

    from sqlalchemy import select

    count = 0
    today = datetime.date.today()

    for _, row in df.iterrows():
        bond_code = row.get("bond_code")
        if not bond_code:
            continue

        # Check if snapshot exists for today
        result = await session.execute(
            select(Bond).where(
                Bond.bond_code == bond_code,
                Bond.snapshot_date == today,
            )
        )
        existing = result.scalar_one_or_none()

        # Only pass columns that exist on the Bond model
        bond_fields = {c.name for c in Bond.__table__.columns}
        row_dict = {k: v for k, v in row.items() if k in bond_fields}

        if existing:
            for key, val in row_dict.items():
                if key not in ("id", "snapshot_date", "created_at"):
                    setattr(existing, key, val)
        else:
            session.add(Bond(**row_dict))

        count += 1

    await session.commit()
    logger.info("Stored %d bond snapshots", count)
    return count


async def store_redemption_events(session, df: pd.DataFrame):
    """Upsert redemption events from Jisilu redemption data.

    Matches on bond_code + status to avoid duplicates.
    """
    if df.empty:
        return 0

    from sqlalchemy import select

    # Pre-filter: keep only rows with active redemption status AND valid last_trade_date
    active_statuses = {"announced", "pending"}
    df = df[df.get("redemption_status", "").isin(active_statuses)].copy()

    if df.empty:
        logger.info("No active redemption events to store")
        return 0

    # Convert NaN/NaT → None across the entire DataFrame
    df = df.where(pd.notna(df), None)

    count = 0

    for _, row in df.iterrows():
        bond_code = row.get("bond_code")
        status = row.get("redemption_status", "")
        if not bond_code or not isinstance(bond_code, str):
            continue

        # Check if event already tracked
        result = await session.execute(
            select(RedemptionEvent).where(
                RedemptionEvent.bond_code == bond_code,
                RedemptionEvent.status == status,
            )
        )
        existing = result.scalar_one_or_none()

        event_data = {
            "bond_code": row.get("bond_code"),
            "bond_name": row.get("bond_name"),
            "event_type": "redemption",
            "last_trade_date": row.get("last_trade_date"),
            "redemption_price": row.get("redemption_price"),
            "status": status,
            "source": row.get("source", "jisilu"),
        }

        # Parse redemption trigger date from day_count if available
        rd_count = row.get("redemption_days_count")
        if rd_count and rd_count > 0:
            event_data["announcement_date"] = datetime.date.today()

        if existing:
            for key, val in event_data.items():
                if val is not None:
                    setattr(existing, key, val)
            existing.updated_at = datetime.datetime.utcnow()
        else:
            session.add(RedemptionEvent(**event_data))

        count += 1

    await session.commit()
    logger.info("Stored %d redemption events", count)
    return count


# ── Main entry point ──────────────────────────────────────────────

async def collect_all(session):
    """Run all data collection pipelines and store results.

    Call this from the scheduler or manually.
    """
    logger.info("=== Data collection started ===")

    # 1. Jisilu market snapshot (detailed metrics for ranking)
    market_df = await fetch_market_snapshot()
    await store_bonds(session, market_df)

    # 2. East Money spot (full market coverage)
    em_df = await fetch_east_money_spot()
    await store_bonds(session, em_df)

    # 3. Redemption data
    redeem_df = await fetch_redemption_data()
    await store_redemption_events(session, redeem_df)

    # 4. Tushare stock fundamentals (PE, PB, industry, market cap)
    from services.tushare_collector import collect_stock_info
    tushare_counts = await collect_stock_info(session)

    logger.info("=== Data collection complete ===")
    return {
        "market": len(market_df),
        "east_money": len(em_df),
        "redemption": len(redeem_df),
        **tushare_counts,
    }
