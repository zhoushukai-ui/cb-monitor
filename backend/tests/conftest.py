"""Shared fixtures for all tests.

Uses an in-memory SQLite database to isolate tests from real data.
Overrides the app's ``get_db`` dependency so every test gets a clean DB.
"""

import datetime
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# ── Override config BEFORE any app imports ───────────────────────────

import config as app_config

app_config.DATABASE_URL = "sqlite+aiosqlite://"
app_config.ADMIN_TOKEN = "test-admin-token"

from database import Base, get_db, Bond, RedemptionEvent, StockInfo
from main import app

# ── Fixtures ─────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a clean in-memory database for each test."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with AsyncSessionLocal() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI test client with overridden DB dependency."""

    async def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_db(db_session: AsyncSession) -> AsyncSession:
    """Seed the database with sample bonds and events."""
    today = datetime.date.today()

    db_session.add_all([
        Bond(
            bond_code="123456",
            bond_name="测试转债",
            stock_code="600000",
            stock_name="测试股票",
            price=105.0,
            stock_price=25.0,
            conversion_price=20.0,
            premium_rate=5.0,
            ytm_ratio=-2.5,
            remaining_size=3.5,
            total_size=10.0,
            rating="AA+",
            redemption_days_count=5,
            redemption_threshold_price=30.0,
            conversion_value=125.0,
            source="test",
            snapshot_date=today,
        ),
        Bond(
            bond_code="654321",
            bond_name="Sample Bond",
            stock_code="000001",
            stock_name="Sample Stock",
            price=98.0,
            stock_price=15.0,
            conversion_price=18.0,
            premium_rate=15.0,
            ytm_ratio=3.0,
            remaining_size=1.2,
            total_size=5.0,
            rating="AA",
            redemption_days_count=12,
            redemption_threshold_price=22.0,
            conversion_value=83.33,
            source="test",
            snapshot_date=today,
        ),
    ])

    next_week = today + datetime.timedelta(days=7)
    db_session.add_all([
        RedemptionEvent(
            bond_code="123456",
            bond_name="测试转债",
            event_type="redemption",
            announcement_date=today - datetime.timedelta(days=3),
            last_trade_date=next_week,
            redemption_price=100.5,
            status="announced",
            source="test",
        ),
        RedemptionEvent(
            bond_code="654321",
            bond_name="Sample Bond",
            event_type="maturity",
            announcement_date=today - datetime.timedelta(days=30),
            last_trade_date=today + datetime.timedelta(days=60),
            redemption_price=100.0,
            status="ongoing",
            source="test",
        ),
    ])

    db_session.add_all([
        StockInfo(
            stock_code="600000",
            stock_name="测试股票",
            industry="银行",
            pe_ttm=6.5,
            pb=0.8,
            market_cap=1200.0,
            snapshot_date=today,
        ),
        StockInfo(
            stock_code="000001",
            stock_name="Sample Stock",
            industry="信息技术",
            pe_ttm=25.0,
            pb=3.2,
            market_cap=500.0,
            snapshot_date=today,
        ),
    ])

    await db_session.commit()
    return db_session


@pytest_asyncio.fixture
async def seeded_client(seeded_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Test client with pre-seeded data."""

    async def _get_db_override():
        yield seeded_db

    app.dependency_overrides[get_db] = _get_db_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
