"""
Cortex Gateway — Endpoint Tests.

Tests for:
  GET /         — Root endpoint
  GET /version  — Version endpoint
  GET /health   — Health endpoint (all dependency combinations)

All tests run without Docker. PostgreSQL and Redis health checks are mocked.
"""

import pytest
from fastapi.testclient import TestClient

from app.config.settings import get_settings

settings = get_settings()


# ═══════════════════════════════════════════════════════════════════════════════
# GET /
# ═══════════════════════════════════════════════════════════════════════════════


class TestRoot:
    def test_root_returns_200(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200

    def test_root_response_shape(self, client: TestClient) -> None:
        data = client.get("/").json()
        assert "name" in data
        assert "version" in data
        assert "status" in data

    def test_root_name_matches_settings(self, client: TestClient) -> None:
        data = client.get("/").json()
        assert data["name"] == settings.app_name

    def test_root_version_matches_settings(self, client: TestClient) -> None:
        data = client.get("/").json()
        assert data["version"] == settings.app_version

    def test_root_status_is_running(self, client: TestClient) -> None:
        data = client.get("/").json()
        assert data["status"] == "running"

    def test_root_has_request_id_header(self, client: TestClient) -> None:
        response = client.get("/")
        assert "x-request-id" in response.headers

    def test_root_propagates_request_id(self, client: TestClient) -> None:
        custom_id = "test-request-id-123"
        response = client.get("/", headers={"X-Request-ID": custom_id})
        assert response.headers.get("x-request-id") == custom_id


# ═══════════════════════════════════════════════════════════════════════════════
# GET /version
# ═══════════════════════════════════════════════════════════════════════════════


class TestVersion:
    def test_version_returns_200(self, client: TestClient) -> None:
        response = client.get("/version")
        assert response.status_code == 200

    def test_version_has_version_key(self, client: TestClient) -> None:
        data = client.get("/version").json()
        assert "version" in data

    def test_version_matches_settings(self, client: TestClient) -> None:
        """Version must come from centralized settings, not be hardcoded."""
        data = client.get("/version").json()
        assert data["version"] == settings.app_version

    def test_version_is_non_empty_string(self, client: TestClient) -> None:
        data = client.get("/version").json()
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# GET /health — Healthy
# ═══════════════════════════════════════════════════════════════════════════════


class TestHealthAllHealthy:
    def test_health_returns_200_when_all_healthy(
        self, client: TestClient, mock_db_up, mock_redis_up
    ) -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_status_is_healthy(
        self, client: TestClient, mock_db_up, mock_redis_up
    ) -> None:
        data = client.get("/health").json()
        assert data["status"] == "healthy"

    def test_health_database_connected(
        self, client: TestClient, mock_db_up, mock_redis_up
    ) -> None:
        data = client.get("/health").json()
        assert data["database"] == "connected"

    def test_health_redis_connected(
        self, client: TestClient, mock_db_up, mock_redis_up
    ) -> None:
        data = client.get("/health").json()
        assert data["redis"] == "connected"

    def test_health_version_present(
        self, client: TestClient, mock_db_up, mock_redis_up
    ) -> None:
        data = client.get("/health").json()
        assert data["version"] == settings.app_version


# ═══════════════════════════════════════════════════════════════════════════════
# GET /health — Database Down
# ═══════════════════════════════════════════════════════════════════════════════


class TestHealthDatabaseDown:
    def test_returns_503(
        self, client: TestClient, mock_db_down, mock_redis_up
    ) -> None:
        response = client.get("/health")
        assert response.status_code == 503

    def test_status_is_degraded(
        self, client: TestClient, mock_db_down, mock_redis_up
    ) -> None:
        data = client.get("/health").json()
        assert data["status"] == "degraded"

    def test_database_disconnected(
        self, client: TestClient, mock_db_down, mock_redis_up
    ) -> None:
        data = client.get("/health").json()
        assert data["database"] == "disconnected"

    def test_redis_still_connected(
        self, client: TestClient, mock_db_down, mock_redis_up
    ) -> None:
        """Redis is independently reported even when DB is down."""
        data = client.get("/health").json()
        assert data["redis"] == "connected"

    def test_app_does_not_crash(
        self, client: TestClient, mock_db_down, mock_redis_up
    ) -> None:
        """The application must remain responsive when DB is unavailable."""
        response = client.get("/health")
        assert response.json() is not None

    def test_no_stack_trace_in_response(
        self, client: TestClient, mock_db_down, mock_redis_up
    ) -> None:
        body = response = client.get("/health").text
        assert "Traceback" not in body
        assert "Exception" not in body


# ═══════════════════════════════════════════════════════════════════════════════
# GET /health — Redis Down
# ═══════════════════════════════════════════════════════════════════════════════


class TestHealthRedisDown:
    def test_returns_503(
        self, client: TestClient, mock_db_up, mock_redis_down
    ) -> None:
        response = client.get("/health")
        assert response.status_code == 503

    def test_status_is_degraded(
        self, client: TestClient, mock_db_up, mock_redis_down
    ) -> None:
        data = client.get("/health").json()
        assert data["status"] == "degraded"

    def test_redis_disconnected(
        self, client: TestClient, mock_db_up, mock_redis_down
    ) -> None:
        data = client.get("/health").json()
        assert data["redis"] == "disconnected"

    def test_database_still_connected(
        self, client: TestClient, mock_db_up, mock_redis_down
    ) -> None:
        """DB is independently reported even when Redis is down."""
        data = client.get("/health").json()
        assert data["database"] == "connected"

    def test_app_does_not_crash(
        self, client: TestClient, mock_db_up, mock_redis_down
    ) -> None:
        response = client.get("/health")
        assert response.json() is not None


# ═══════════════════════════════════════════════════════════════════════════════
# GET /health — Both Down
# ═══════════════════════════════════════════════════════════════════════════════


class TestHealthBothDown:
    def test_returns_503(
        self, client: TestClient, mock_db_down, mock_redis_down
    ) -> None:
        response = client.get("/health")
        assert response.status_code == 503

    def test_status_is_degraded(
        self, client: TestClient, mock_db_down, mock_redis_down
    ) -> None:
        data = client.get("/health").json()
        assert data["status"] == "degraded"

    def test_database_disconnected(
        self, client: TestClient, mock_db_down, mock_redis_down
    ) -> None:
        data = client.get("/health").json()
        assert data["database"] == "disconnected"

    def test_redis_disconnected(
        self, client: TestClient, mock_db_down, mock_redis_down
    ) -> None:
        data = client.get("/health").json()
        assert data["redis"] == "disconnected"

    def test_app_remains_responsive(
        self, client: TestClient, mock_db_down, mock_redis_down
    ) -> None:
        """Application must still return a structured response when all deps fail."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "redis" in data

    def test_no_internal_details_exposed(
        self, client: TestClient, mock_db_down, mock_redis_down
    ) -> None:
        body = client.get("/health").text
        assert "Traceback" not in body
        assert "password" not in body.lower()
        assert "secret" not in body.lower()
