"""Tests for server-rendered HTML page routes."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_homepage_empty(client: AsyncClient):
    """Homepage returns 200 and shows expected heading with no data."""
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "Convertible Bond" in resp.text or "可转债" in resp.text


@pytest.mark.asyncio
async def test_homepage_with_data(seeded_client: AsyncClient):
    """Homepage shows upcoming events when data exists."""
    resp = await seeded_client.get("/")
    assert resp.status_code == 200
    # Should contain bond codes from seeded data
    assert "123456" in resp.text


@pytest.mark.asyncio
async def test_homepage_search(seeded_client: AsyncClient):
    """Homepage search filters results."""
    resp = await seeded_client.get("/", params={"search": "123456"})
    assert resp.status_code == 200
    assert "123456" in resp.text

    resp = await seeded_client.get("/", params={"search": "NONEXISTENT"})
    assert resp.status_code == 200
    assert "No" in resp.text or "没有" in resp.text


@pytest.mark.asyncio
async def test_ranking_page(seeded_client: AsyncClient):
    """Ranking page lists bonds in a table."""
    resp = await seeded_client.get("/ranking")
    assert resp.status_code == 200
    assert "123456" in resp.text
    assert "654321" in resp.text


@pytest.mark.asyncio
async def test_ranking_page_empty(client: AsyncClient):
    """Ranking page handles no data gracefully."""
    resp = await client.get("/ranking")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_ranking_sort(seeded_client: AsyncClient):
    """Ranking sorting parameters work."""
    resp = await seeded_client.get("/ranking", params={"sort_by": "price", "order": "desc"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_ranking_search(seeded_client: AsyncClient):
    """Ranking search by bond code."""
    resp = await seeded_client.get("/ranking", params={"search": "123456"})
    assert resp.status_code == 200
    assert "123456" in resp.text

    resp = await seeded_client.get("/ranking", params={"search": "NONEXISTENT"})
    assert resp.status_code == 200
    assert "No bonds match" in resp.text or "没有" in resp.text


@pytest.mark.asyncio
async def test_ranking_rating_filter(seeded_client: AsyncClient):
    """Ranking rating filter works."""
    resp = await seeded_client.get("/ranking", params={"rating": "AA+"})
    assert resp.status_code == 200
    assert "123456" in resp.text  # only AA+ bond

    resp = await seeded_client.get("/ranking", params={"rating": "AAA"})
    assert resp.status_code == 200
    assert "123456" not in resp.text


@pytest.mark.asyncio
async def test_calendar_page(seeded_client: AsyncClient):
    """Calendar page lists redemption events."""
    resp = await seeded_client.get("/calendar")
    assert resp.status_code == 200
    assert "123456" in resp.text


@pytest.mark.asyncio
async def test_calendar_page_empty(client: AsyncClient):
    """Calendar page handles no data."""
    resp = await client.get("/calendar")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_calendar_status_filter(seeded_client: AsyncClient):
    """Calendar status filter works."""
    resp = await seeded_client.get("/calendar", params={"status": "announced"})
    assert resp.status_code == 200

    resp = await seeded_client.get("/calendar", params={"status": "completed"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_bond_detail_found(seeded_client: AsyncClient):
    """Bond detail page shows bond info."""
    resp = await seeded_client.get("/bond/123456")
    assert resp.status_code == 200
    assert "123456" in resp.text
    assert "105.0" in resp.text  # price


@pytest.mark.asyncio
async def test_bond_detail_not_found(client: AsyncClient):
    """Bond detail page shows 'not found' for unknown bonds."""
    resp = await client.get("/bond/999999")
    assert resp.status_code == 200
    assert "not found" in resp.text.lower() or "Bond not found" in resp.text


@pytest.mark.asyncio
async def test_bond_detail_with_event(seeded_client: AsyncClient):
    """Bond detail shows redemption event section."""
    resp = await seeded_client.get("/bond/123456")
    assert resp.status_code == 200
    # Should contain redemption event data
    assert "Redemption" in resp.text or "强赎" in resp.text


@pytest.mark.asyncio
async def test_bond_detail_stock_fundamentals(seeded_client: AsyncClient):
    """Bond detail page shows stock fundamentals when available."""
    resp = await seeded_client.get("/bond/123456")
    assert resp.status_code == 200
    assert "Stock Fundamentals" in resp.text or "正股基本面" in resp.text


@pytest.mark.asyncio
async def test_bond_detail_external_links(seeded_client: AsyncClient):
    """Bond detail page includes external links."""
    resp = await seeded_client.get("/bond/123456")
    assert resp.status_code == 200
    assert "eastmoney" in resp.text or "jisilu" in resp.text


@pytest.mark.asyncio
async def test_english_language(client: AsyncClient):
    """Page content respects language cookie."""
    resp = await client.get("/", cookies={"lang": "en"})
    assert resp.status_code == 200
    assert "Redemption Calendar" in resp.text


@pytest.mark.asyncio
async def test_chinese_language(client: AsyncClient):
    """Chinese language shows translated content."""
    resp = await client.get("/", cookies={"lang": "zh"})
    assert resp.status_code == 200
    assert "强赎日历" in resp.text or "可转债" in resp.text
