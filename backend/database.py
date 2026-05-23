"""Database setup and models.

All schema names in English. Tables store daily snapshots of
convertible bond market data and redemption events.
"""

import datetime

from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text, UniqueConstraint, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from config import DATABASE_URL


class Base(DeclarativeBase):
    pass


# --- Bond Daily Snapshot ---

class Bond(Base):
    """Daily snapshot of a convertible bond's market data."""

    __tablename__ = "bonds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bond_code = Column(String(10), nullable=False, index=True)
    bond_name = Column(String(100))
    stock_code = Column(String(10))
    stock_name = Column(String(100))

    # Pricing
    price = Column(Float, comment="Current bond price (CNY)")
    stock_price = Column(Float, comment="Underlying stock price (CNY)")
    conversion_price = Column(Float, comment="Conversion price (转股价)")
    premium_rate = Column(Float, comment="Premium rate % (溢价率)")

    # Yield
    ytm_ratio = Column(Float, comment="Yield to maturity % (到期收益率)")  # renamed to avoid SQL conflict

    # Size
    remaining_size = Column(Float, comment="Remaining size in 100M CNY (剩余规模/亿)")
    total_size = Column(Float, comment="Total size in 100M CNY")

    # Rating
    rating = Column(String(10), comment="Credit rating (e.g. AAA, AA+)")

    # Redemption tracking
    redemption_days_count = Column(Integer, comment="Consecutive days meeting redemption condition")
    redemption_threshold_price = Column(Float, comment="Redemption trigger stock price")

    # Computed
    conversion_value = Column(Float, comment="Conversion value (转股价值)")

    # Metadata
    source = Column(String(50), comment="Data source identifier")
    snapshot_date = Column(Date, nullable=False, index=True, default=datetime.date.today)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("bond_code", "snapshot_date", name="uq_bond_snapshot"),
    )


# --- Redemption / Put / Maturity Events ---

class RedemptionEvent(Base):
    """Track forced redemption, put option, and maturity events."""

    __tablename__ = "redemption_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bond_code = Column(String(10), nullable=False, index=True)
    bond_name = Column(String(100))

    event_type = Column(
        String(20),
        comment="Event type: redemption (强赎), put (回售), maturity (到期)",
    )
    announcement_date = Column(Date, comment="公告日期")
    registration_date = Column(Date, comment="登记日")
    last_trade_date = Column(Date, comment="最后交易日")
    redemption_date = Column(Date, comment="赎回日")
    redemption_price = Column(Float, comment="赎回价 (CNY)")
    status = Column(
        String(20),
        default="announced",
        comment="Status: announced (已公告), ongoing (进行中), completed (已完成)",
    )

    # Source tracking for cross-validation
    source = Column(String(50), comment="Primary data source")
    confirmed_by = Column(String(100), comment="Secondary sources that confirmed this event")

    # Optional notes (e.g. special conditions)
    notes = Column(Text)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


# --- Stock Fundamentals ---

class StockInfo(Base):
    """Underlying stock fundamental data (PE, PB, industry, market cap).

    This is stock-level data linked via bond.stock_code. Updated daily
    from Tushare Pro. Separate from the daily Bond snapshot because
    multiple bonds may share the same underlying stock.
    """

    __tablename__ = "stock_info"

    stock_code = Column(String(10), primary_key=True, comment="Stock code (正股代码)")
    stock_name = Column(String(100))
    industry = Column(String(50), comment="Shenwan industry classification")
    pe_ttm = Column(Float, comment="PE TTM (滚动市盈率)")
    pb = Column(Float, comment="PB (市净率)")
    market_cap = Column(Float, comment="Total market cap in 100M CNY")
    snapshot_date = Column(Date, nullable=False, default=datetime.date.today)


# --- Page View Tracking ---

class PageViewLog(Base):
    """Daily page view counter for admin analytics."""

    __tablename__ = "page_view_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    path = Column(String(200), nullable=False)
    date = Column(Date, nullable=False, default=datetime.date.today)
    count = Column(Integer, nullable=False, default=1)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("path", "date", name="uq_pageview_path_date"),
    )


# --- Engine ---

def create_engine_sync():
    """Create sync engine (for scripts / seed data)."""
    sync_url = DATABASE_URL.replace("+aiosqlite", "").replace("+asyncpg", "")
    return create_engine(sync_url)


engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Create all tables. Safe to call on every startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """Dependency: yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
