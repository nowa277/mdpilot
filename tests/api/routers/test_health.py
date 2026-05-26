"""Tests for health check endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

from mdpilot.api.app import create_app


@pytest.fixture
def app():
    """Create test application."""
    return create_app()


@pytest.fixture
async def client(app):
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestHealthEndpoints:
    """Test health check endpoints."""

    @pytest.mark.asyncio
    async def test_database_health_success(self, client):
        """Test database health check with successful connection."""
        with patch("mdpilot.api.routers.health.get_engine") as mock_get_engine:
            # Mock engine and pool
            mock_pool = MagicMock()
            mock_pool.size.return_value = 5
            mock_pool.checkedin.return_value = 4
            mock_pool.checkedout.return_value = 1
            mock_pool.overflow.return_value = 0

            mock_engine = MagicMock()
            mock_engine.pool = mock_pool

            # Mock async connection
            mock_conn = MagicMock()
            mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_conn.__aexit__ = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchone = AsyncMock(return_value=(1,))
            mock_conn.execute = AsyncMock(return_value=mock_result)

            mock_engine.connect.return_value = mock_conn
            mock_get_engine.return_value = mock_engine

            response = await client.get("/api/v1/health/db")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["connected"] is True
            assert data["pool_size"] == 5
            assert data["checked_in"] == 4
            assert data["checked_out"] == 1
            assert data["overflow"] == 0
            assert "successful" in data["message"]

    @pytest.mark.asyncio
    async def test_database_health_failure(self, client):
        """Test database health check with connection failure."""
        with patch("mdpilot.api.routers.health.get_engine") as mock_get_engine:
            mock_engine = MagicMock()
            mock_conn = MagicMock()
            mock_conn.__aenter__ = AsyncMock(side_effect=Exception("Connection failed"))
            mock_engine.connect.return_value = mock_conn
            mock_get_engine.return_value = mock_engine

            response = await client.get("/api/v1/health/db")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["connected"] is False
            assert "Connection failed" in data["message"]

    @pytest.mark.asyncio
    async def test_overall_health_healthy(self, client):
        """Test overall health check when database is healthy."""
        with patch("mdpilot.api.routers.health.get_engine") as mock_get_engine:
            # Mock healthy database
            mock_pool = MagicMock()
            mock_pool.size.return_value = 5
            mock_pool.checkedin.return_value = 4
            mock_pool.checkedout.return_value = 1
            mock_pool.overflow.return_value = 0

            mock_engine = MagicMock()
            mock_engine.pool = mock_pool

            mock_conn = MagicMock()
            mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_conn.__aexit__ = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchone = AsyncMock(return_value=(1,))
            mock_conn.execute = AsyncMock(return_value=mock_result)

            mock_engine.connect.return_value = mock_conn
            mock_get_engine.return_value = mock_engine

            response = await client.get("/api/v1/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["database"]["status"] == "healthy"
            assert data["database"]["connected"] is True

    @pytest.mark.asyncio
    async def test_overall_health_degraded(self, client):
        """Test overall health check when database is unhealthy."""
        with patch("mdpilot.api.routers.health.get_engine") as mock_get_engine:
            mock_engine = MagicMock()
            mock_conn = MagicMock()
            mock_conn.__aenter__ = AsyncMock(side_effect=Exception("Connection failed"))
            mock_engine.connect.return_value = mock_conn
            mock_get_engine.return_value = mock_engine

            response = await client.get("/api/v1/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert data["database"]["status"] == "unhealthy"
            assert data["database"]["connected"] is False

    @pytest.mark.asyncio
    async def test_database_health_pool_stats(self, client):
        """Test database health returns correct pool statistics."""
        with patch("mdpilot.api.routers.health.get_engine") as mock_get_engine:
            # Mock pool with specific stats
            mock_pool = MagicMock()
            mock_pool.size.return_value = 10
            mock_pool.checkedin.return_value = 7
            mock_pool.checkedout.return_value = 3
            mock_pool.overflow.return_value = 2

            mock_engine = MagicMock()
            mock_engine.pool = mock_pool

            mock_conn = MagicMock()
            mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_conn.__aexit__ = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchone = AsyncMock(return_value=(1,))
            mock_conn.execute = AsyncMock(return_value=mock_result)

            mock_engine.connect.return_value = mock_conn
            mock_get_engine.return_value = mock_engine

            response = await client.get("/api/v1/health/db")

            assert response.status_code == 200
            data = response.json()
            assert data["pool_size"] == 10
            assert data["checked_in"] == 7
            assert data["checked_out"] == 3
            assert data["overflow"] == 2
