"""
Cortex Gateway — Test Configuration and Fixtures.

Provides:
- ``client``         : HTTPX TestClient wrapping the FastAPI app.
- ``mock_db_up``     : Patches check_db_health to return "connected".
- ``mock_db_down``   : Patches check_db_health to return "disconnected".
- ``mock_redis_up``  : Patches check_redis_health to return "connected".
- ``mock_redis_down``: Patches check_redis_health to return "disconnected".

These fixtures run without any external Docker services.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    """
    Session-scoped synchronous TestClient.

    ``TestClient`` manages the ASGI lifespan automatically.
    We skip the real DB/Redis init by patching them at module level.
    """
    # Patch init_db and init_redis so the lifespan startup does not attempt
    # real network connections during tests.
    with (
        patch("app.main.init_db"),
        patch("app.main.init_redis"),
        patch("app.main.close_db", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
    ):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


@pytest.fixture()
def mock_db_up():
    """Simulate a healthy PostgreSQL connection."""
    with patch(
        "app.api.v1.endpoints.health.check_db_health",
        new_callable=AsyncMock,
        return_value="connected",
    ):
        yield


@pytest.fixture()
def mock_db_down():
    """Simulate an unreachable PostgreSQL."""
    with patch(
        "app.api.v1.endpoints.health.check_db_health",
        new_callable=AsyncMock,
        return_value="disconnected",
    ):
        yield


@pytest.fixture()
def mock_redis_up():
    """Simulate a healthy Redis connection."""
    with patch(
        "app.api.v1.endpoints.health.check_redis_health",
        new_callable=AsyncMock,
        return_value="connected",
    ):
        yield


@pytest.fixture()
def mock_redis_down():
    """Simulate an unreachable Redis."""
    with patch(
        "app.api.v1.endpoints.health.check_redis_health",
        new_callable=AsyncMock,
        return_value="disconnected",
    ):
        yield
