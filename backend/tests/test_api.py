"""Tests for JSON API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_bonds_empty(client: AsyncClient):
    """GET /api/bonds returns empty list when no data."""
    resp = await client.get("/api/bonds")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_bonds_with_data(seeded_client: AsyncClient):
    """GET /api/bonds returns bond data as JSON."""
    resp = await seeded_client.get("/api/bonds")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    codes = {b["bond_code"] for b in data}
    assert "123456" in codes
    assert "654321" in codes


@pytest.mark.asyncio
async def test_list_bonds_includes_stock_info(seeded_client: AsyncClient):
    """Bond API response includes stock fundamentals."""
    resp = await seeded_client.get("/api/bonds")
    data = resp.json()
    bond = next(b for b in data if b["bond_code"] == "600000" or b.get("bond_code") == "123456")
    assert bond["industry"] is not None
    assert bond["pe_ttm"] is not None
    assert bond["pb"] is not None
    assert bond["market_cap"] is not None


@pytest.mark.asyncio
async def test_list_bonds_search(seeded_client: AsyncClient):
    """GET /api/bonds?search= filters results."""
    resp = await seeded_client.get("/api/bonds", params={"search": "123456"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["bond_code"] == "123456"


@pytest.mark.asyncio
async def test_list_bonds_sort(seeded_client: AsyncClient):
    """GET /api/bonds with sort params returns ordered results."""
    resp = await seeded_client.get("/api/bonds", params={"sort_by": "price", "order": "desc"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["price"] >= data[1]["price"]


@pytest.mark.asyncio
async def test_list_redemptions_empty(client: AsyncClient):
    """GET /api/redemptions returns empty list when no data."""
    resp = await client.get("/api/redemptions")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_redemptions_with_data(seeded_client: AsyncClient):
    """GET /api/redemptions returns event data."""
    resp = await seeded_client.get("/api/redemptions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    types = {e["event_type"] for e in data}
    assert "redemption" in types
    assert "maturity" in types


@pytest.mark.asyncio
async def test_list_redemptions_status_filter(seeded_client: AsyncClient):
    """GET /api/redemptions?status= filters by status."""
    resp = await seeded_client.get("/api/redemptions", params={"status": "announced"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "announced"


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """GET /health returns ok."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
