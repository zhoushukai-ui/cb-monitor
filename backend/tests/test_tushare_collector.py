"""Tests for Tushare data collector.

These tests use mocked data since Tushare requires a network token.
We test the helper functions and store logic; integration tests
with the real API are skipped unless TUSHARE_TOKEN is set.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from database import StockInfo
from services.tushare_collector import _ts_code, _simple_code, store_stock_info


class TestHelpers:
    """Tushare code conversion utilities."""

    def test_ts_code_shanghai(self):
        assert _ts_code("600000") == "600000.SH"
        assert _ts_code("688888") == "688888.SH"

    def test_ts_code_shenzhen(self):
        assert _ts_code("000001") == "000001.SZ"
        assert _ts_code("300001") == "300001.SZ"

    def test_ts_code_beijing(self):
        assert _ts_code("830001") == "830001.BJ"
        assert _ts_code("400001") == "400001.BJ"

    def test_ts_code_empty(self):
        assert _ts_code("") == ""

    def test_simple_code(self):
        assert _simple_code("600000.SH") == "600000"
        assert _simple_code("000001.SZ") == "000001"
        assert _simple_code("simple") == "simple"


@pytest.mark.asyncio
async def test_store_stock_info_basic(db_session):
    """Storing stock basic data (industry) works."""
    df = pd.DataFrame([{
        "ts_code": "600000.SH",
        "name": "测试股票",
        "industry": "银行",
    }])

    count = await store_stock_info(db_session, df)

    assert count == 1
    result = await db_session.get(StockInfo, "600000")
    assert result is not None
    assert result.industry == "银行"
    assert result.stock_name == "测试股票"


@pytest.mark.asyncio
async def test_store_stock_info_daily(db_session):
    """Storing daily fundamental data (PE/PB/market cap) works."""
    # Seed basic info first
    basic_df = pd.DataFrame([{
        "ts_code": "600000.SH",
        "name": "测试股票",
        "industry": "银行",
    }])
    await store_stock_info(db_session, basic_df)

    # Then store daily fundamentals
    daily_df = pd.DataFrame([{
        "ts_code": "600000.SH",
        "pe_ttm": 6.5,
        "pb": 0.8,
        "total_mv": 1200.0,
        "trade_date": "20260522",
    }])
    daily_count = await store_stock_info(db_session, daily_df)

    assert daily_count == 1
    result = await db_session.get(StockInfo, "600000")
    assert result.pe_ttm == 6.5
    assert result.pb == 0.8
    assert result.market_cap == 1200.0
    # Industry should be preserved from basic data
    assert result.industry == "银行"


@pytest.mark.asyncio
async def test_store_stock_info_upsert(db_session):
    """Re-storing updates existing record."""
    df = pd.DataFrame([{
        "ts_code": "600000.SH",
        "name": "测试股票",
        "industry": "银行",
    }])
    await store_stock_info(db_session, df)

    df2 = pd.DataFrame([{
        "ts_code": "600000.SH",
        "name": "测试股票",
        "industry": "非银金融",
    }])
    await store_stock_info(db_session, df2)

    result = await db_session.get(StockInfo, "600000")
    assert result.industry == "非银金融"


@pytest.mark.asyncio
async def test_store_stock_info_empty(db_session):
    """Empty DataFrame is handled gracefully."""
    df = pd.DataFrame()
    count = await store_stock_info(db_session, df)
    assert count == 0


@pytest.mark.skip(reason="Requires TUSHARE_TOKEN env var")
@pytest.mark.asyncio
async def test_fetch_stock_basic_integration():
    """Integration test — requires real Tushare token."""
    from services.tushare_collector import fetch_stock_basic, _get_pro

    pro = _get_pro()
    assert pro is not None, "TUSHARE_TOKEN not set"

    df = await fetch_stock_basic(pro)
    assert not df.empty
    assert "ts_code" in df.columns
    assert "industry" in df.columns


@pytest.mark.skip(reason="Requires TUSHARE_TOKEN env var")
@pytest.mark.asyncio
async def test_fetch_daily_basic_integration():
    """Integration test — requires real Tushare token."""
    from services.tushare_collector import fetch_daily_basic, _get_pro

    pro = _get_pro()
    assert pro is not None, "TUSHARE_TOKEN not set"

    df = await fetch_daily_basic(pro, ["600000", "000001"])
    assert not df.empty
    assert "pe_ttm" in df.columns or df.empty  # may be empty on weekends
