"""
Cortex Gateway — Phase 8 Backend Addition Tests.

Tests for:
  1. GET /api/v1/auth/me — returns context from authenticated key
  2. GET /api/v1/analytics/requests?request_id=X — single-record lookup
"""

from __future__ import annotations

from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.schemas import RequestContext
from app.main import app

# ── 1. GET /api/v1/auth/me ────────────────────────────────────────────────────


class TestAuthMe:
    """Tests for the GET /api/v1/auth/me endpoint."""

    def test_me_returns_context_for_authenticated_key(self) -> None:
        """Authenticated admin key → 200 with org/team/key/role."""
        from app.auth.dependencies import get_request_context

        ctx = RequestContext(
            organization_id="org-me-1",
            team_id="team-me-1",
            api_key_id="key-me-1",
            role="admin",
        )

        with (
            patch("app.main.init_db"),
            patch("app.main.init_redis"),
            patch("app.main.close_db", new_callable=AsyncMock),
            patch("app.main.close_redis", new_callable=AsyncMock),
        ):
            with TestClient(app, raise_server_exceptions=True) as client:
                app.dependency_overrides[get_request_context] = lambda: ctx
                resp = client.get("/api/v1/auth/me")
                app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["organization_id"] == "org-me-1"
        assert data["team_id"] == "team-me-1"
        assert data["api_key_id"] == "key-me-1"
        assert data["role"] == "admin"

    def test_me_works_for_member_role(self) -> None:
        """Member role also returns context — /auth/me allows any valid key."""
        from app.auth.dependencies import get_request_context

        ctx = RequestContext(
            organization_id="org-me-2",
            team_id="team-me-2",
            api_key_id="key-me-2",
            role="member",
        )

        with (
            patch("app.main.init_db"),
            patch("app.main.init_redis"),
            patch("app.main.close_db", new_callable=AsyncMock),
            patch("app.main.close_redis", new_callable=AsyncMock),
        ):
            with TestClient(app, raise_server_exceptions=True) as client:
                app.dependency_overrides[get_request_context] = lambda: ctx
                resp = client.get("/api/v1/auth/me")
                app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["role"] == "member"

    def test_me_unauthenticated_returns_401(self) -> None:
        """No valid Authorization header → AuthenticationError → 401."""
        from app.auth.dependencies import get_request_context
        from app.auth.exceptions import AuthenticationError
        from app.database.session import get_db_dependency

        async def _fail_auth():
            raise AuthenticationError()

        async def _mock_db():
            yield AsyncMock()

        with (
            patch("app.main.init_db"),
            patch("app.main.init_redis"),
            patch("app.main.close_db", new_callable=AsyncMock),
            patch("app.main.close_redis", new_callable=AsyncMock),
        ):
            with TestClient(app, raise_server_exceptions=False) as client:
                app.dependency_overrides[get_request_context] = _fail_auth
                app.dependency_overrides[get_db_dependency] = _mock_db
                resp = client.get("/api/v1/auth/me")
                app.dependency_overrides.clear()

        assert resp.status_code == 401

    def test_me_response_has_no_secret_fields(self) -> None:
        """Response must NOT contain key_hash or any secret."""
        from app.auth.dependencies import get_request_context

        ctx = RequestContext(
            organization_id="org-me-3",
            team_id="team-me-3",
            api_key_id="key-me-3",
            role="admin",
        )

        with (
            patch("app.main.init_db"),
            patch("app.main.init_redis"),
            patch("app.main.close_db", new_callable=AsyncMock),
            patch("app.main.close_redis", new_callable=AsyncMock),
        ):
            with TestClient(app, raise_server_exceptions=True) as client:
                app.dependency_overrides[get_request_context] = lambda: ctx
                resp = client.get("/api/v1/auth/me")
                app.dependency_overrides.clear()

        data = resp.json()
        assert "key_hash" not in data
        assert "key" not in data
        # Only these four fields expected
        expected_keys = {"organization_id", "team_id", "api_key_id", "role"}
        assert set(data.keys()) == expected_keys


# ── 2. Analytics requests?request_id= filter ─────────────────────────────────


class TestAnalyticsRequestIdFilter:
    """Tests for request_id filter on GET /api/v1/analytics/requests."""

    def test_request_id_filter_passes_through_to_service(self) -> None:
        """request_id= query param must be forwarded to the analytics service."""
        from datetime import datetime, timezone

        from app.auth.dependencies import require_admin
        from app.observability.analytics_schemas import RequestLogItem
        from app.observability.analytics_service import AnalyticsService

        ctx = RequestContext(
            organization_id="org-f1",
            team_id="team-f1",
            api_key_id="key-f1",
            role="admin",
        )

        # Simulate one matching log row
        mock_row = MagicMock()
        mock_row.request_id = "req-specific-abc"
        mock_row.team_id = "team-f1"
        mock_row.organization_id = "org-f1"
        mock_row.provider = "groq"
        mock_row.model = "llama3-8b"
        mock_row.routing_mode = "auto"
        mock_row.status = "success"
        mock_row.http_status_code = 200
        mock_row.latency_ms = 310.0
        mock_row.prompt_tokens = 10
        mock_row.completion_tokens = 20
        mock_row.total_tokens = 30
        mock_row.estimated_cost = 0.001
        mock_row.actual_cost = 0.001
        mock_row.retry_count = 0
        mock_row.failover_triggered = False
        mock_row.failover_from_provider = None
        mock_row.failover_to_provider = None
        mock_row.circuit_breaker_state = None
        mock_row.budget_policy_applied = None
        mock_row.budget_action = None
        mock_row.error_code = None
        mock_row.trace_id = None
        mock_row.created_at = datetime(2026, 9, 15, tzinfo=UTC)

        async def fake_list_requests(**kwargs):
            # Verify request_id was passed through
            assert kwargs.get("request_id") == "req-specific-abc"
            return [mock_row], 1

        mock_service = MagicMock(spec=AnalyticsService)
        mock_service.list_requests = fake_list_requests

        with (
            patch("app.main.init_db"),
            patch("app.main.init_redis"),
            patch("app.main.close_db", new_callable=AsyncMock),
            patch("app.main.close_redis", new_callable=AsyncMock),
        ):
            with TestClient(app, raise_server_exceptions=True) as client:
                from app.api.v1.endpoints.analytics import _get_analytics_service
                app.dependency_overrides[require_admin] = lambda: ctx
                app.dependency_overrides[_get_analytics_service] = lambda: mock_service
                resp = client.get(
                    "/api/v1/analytics/requests",
                    params={"request_id": "req-specific-abc"},
                )
                app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["pagination"]["total"] == 1
        assert data["data"][0]["request_id"] == "req-specific-abc"

    def test_request_id_filter_absent_returns_all(self) -> None:
        """Omitting request_id= does not break the endpoint (backward compatible)."""
        from app.auth.dependencies import require_admin
        from app.observability.analytics_service import AnalyticsService

        ctx = RequestContext(
            organization_id="org-f2",
            team_id="team-f2",
            api_key_id="key-f2",
            role="admin",
        )

        async def fake_list_requests(**kwargs):
            # request_id should be None when not provided
            assert kwargs.get("request_id") is None
            return [], 0

        mock_service = MagicMock(spec=AnalyticsService)
        mock_service.list_requests = fake_list_requests

        with (
            patch("app.main.init_db"),
            patch("app.main.init_redis"),
            patch("app.main.close_db", new_callable=AsyncMock),
            patch("app.main.close_redis", new_callable=AsyncMock),
        ):
            with TestClient(app, raise_server_exceptions=True) as client:
                from app.api.v1.endpoints.analytics import _get_analytics_service
                app.dependency_overrides[require_admin] = lambda: ctx
                app.dependency_overrides[_get_analytics_service] = lambda: mock_service
                resp = client.get("/api/v1/analytics/requests")
                app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["pagination"]["total"] == 0
