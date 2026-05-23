"""Tests for admin portal — auth, stats, and sync endpoints."""

import datetime

import pytest
from httpx import AsyncClient

from database import PageViewLog

ADMIN_TOKEN = "test-admin-token"


@pytest.mark.asyncio
async def test_admin_page_no_token(client: AsyncClient):
    """Admin page shows 'not configured' when ADMIN_TOKEN is empty."""
    import config
    original = config.ADMIN_TOKEN
    config.ADMIN_TOKEN = ""
    resp = await client.get("/admin")
    assert resp.status_code == 200
    assert "not configured" in resp.text.lower()
    config.ADMIN_TOKEN = original


@pytest.mark.asyncio
async def test_admin_page_login_form(seeded_client: AsyncClient):
    """Admin page shows login form when token is configured but not authed."""
    resp = await seeded_client.get("/admin")
    assert resp.status_code == 200
    assert "Admin Login" in resp.text or "管理员登录" in resp.text


@pytest.mark.asyncio
async def test_admin_page_dashboard(seeded_client: AsyncClient):
    """Admin page shows dashboard when authed."""
    resp = await seeded_client.get("/admin", cookies={"admin_token": ADMIN_TOKEN})
    assert resp.status_code == 200
    assert "Data Sync" in resp.text or "数据同步" in resp.text
    # sync-message element exists (transient status, hidden by default)
    assert "sync-message" in resp.text
    # last-sync span is intact (was previously destroyed by textContent)
    assert "last-sync" in resp.text


@pytest.mark.asyncio
async def test_admin_login_success(client: AsyncClient):
    """Login with correct token sets cookie."""
    resp = await client.post("/api/admin/login", data={"token": ADMIN_TOKEN})
    assert resp.status_code == 200
    assert "admin_token" in resp.cookies


@pytest.mark.asyncio
async def test_admin_login_failure(client: AsyncClient):
    """Login with wrong token returns 403."""
    resp = await client.post("/api/admin/login", data={"token": "wrong"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_stats_requires_auth(client: AsyncClient):
    """Stats endpoint returns 403 without admin cookie."""
    resp = await client.get("/api/admin/stats")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_stats_with_auth(seeded_client: AsyncClient):
    """Stats endpoint returns data when authed."""
    resp = await seeded_client.get("/api/admin/stats", cookies={"admin_token": ADMIN_TOKEN})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_admin_sync_requires_auth(client: AsyncClient):
    """Sync endpoint returns 403 without admin cookie."""
    resp = await client.post("/api/admin/sync")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_sync_trigger(seeded_client: AsyncClient):
    """Sync endpoint starts sync process when authed."""
    resp = await seeded_client.post("/api/admin/sync", cookies={"admin_token": ADMIN_TOKEN})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("started", "running")


@pytest.mark.asyncio
async def test_admin_sync_status(seeded_client: AsyncClient):
    """Sync status endpoint returns status object."""
    resp = await seeded_client.get("/api/admin/sync-status", cookies={"admin_token": ADMIN_TOKEN})
    assert resp.status_code == 200
    data = resp.json()
    assert "running" in data
    assert "last_sync" in data
