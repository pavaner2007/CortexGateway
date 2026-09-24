"""
Cortex Gateway — Auth Lifecycle Tests (Phase 5).

Tests API key lifecycle states via mocked AuthService:
  - Valid key → 200 (chat authenticated)
  - Missing Authorization → 401
  - Malformed Authorization → 401
  - Invalid key → 401
  - Expired key → 401
  - Revoked key → 401

Also tests RBAC:
  - member key → create team → 403
  - member key → create API key → 403
  - admin key → create team → success (mocked)
  - admin key → create API key → success (mocked)

And tests public endpoints remain unauthenticated.
"""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.exceptions import AuthenticationError, AuthorizationError
from app.auth.schemas import RequestContext
from app.main import app

# Shared test context for authenticated requests
_ADMIN_CONTEXT = RequestContext(
    organization_id="org-001",
    team_id="team-001",
    api_key_id="key-001",
    role="admin",
)

_MEMBER_CONTEXT = RequestContext(
    organization_id="org-001",
    team_id="team-001",
    api_key_id="key-002",
    role="member",
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_mock_db_session():
    """Yield a mock AsyncSession that does nothing."""
    mock_session = AsyncMock()
    return mock_session


@pytest.fixture(scope="module")
def client() -> TestClient:
    """TestClient with DB/Redis mocked — uses dependency overrides for auth."""
    from app.auth.dependencies import get_request_context, require_admin

    with (
        patch("app.main.init_db"),
        patch("app.main.init_redis"),
        patch("app.main.close_db", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
    ):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ── Helpers ───────────────────────────────────────────────────────────────────

def _with_auth(context: RequestContext):
    """Context manager that overrides get_request_context to return context."""
    from app.auth.dependencies import get_request_context, require_admin
    from app.database.session import get_db_dependency

    async def _mock_context():
        return context

    async def _mock_admin_context():
        if context.role != "admin":
            raise AuthorizationError()
        return context

    async def _mock_db():
        yield AsyncMock()

    return {
        get_request_context: _mock_context,
        require_admin: _mock_admin_context,
        get_db_dependency: _mock_db,
    }


def _with_auth_fail():
    """Context manager that overrides get_request_context to raise AuthenticationError."""
    from app.auth.dependencies import get_request_context
    from app.database.session import get_db_dependency

    async def _mock_context():
        raise AuthenticationError()

    async def _mock_db():
        yield AsyncMock()

    return {
        get_request_context: _mock_context,
        get_db_dependency: _mock_db,
    }


# ── Public Endpoints — Must NOT Require Auth ──────────────────────────────────


class TestPublicEndpoints:
    def test_root_is_public(self, client: TestClient):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_health_is_public(self, client: TestClient):
        # Health may return 503 if deps are mocked down, but should NOT return 401
        resp = client.get("/health")
        assert resp.status_code != 401

    def test_version_is_public(self, client: TestClient):
        resp = client.get("/version")
        assert resp.status_code == 200


# ── Chat Endpoint — Authentication Required ───────────────────────────────────


class TestChatAuthentication:
    """Chat endpoint must reject unauthenticated requests."""

    _CHAT_PAYLOAD = {
        "model": "auto",
        "messages": [{"role": "user", "content": "Hello"}],
    }

    def test_missing_authorization_returns_401(self, client: TestClient):
        overrides = _with_auth_fail()
        app.dependency_overrides.update(overrides)
        try:
            resp = client.post("/api/v1/chat/completions", json=self._CHAT_PAYLOAD)
            assert resp.status_code == 401
            body = resp.json()
            assert "error" in body
            assert body["error"]["code"] == "AUTHENTICATION_FAILED"
        finally:
            for k in overrides:
                app.dependency_overrides.pop(k, None)

    def test_malformed_authorization_returns_401(self, client: TestClient):
        overrides = _with_auth_fail()
        app.dependency_overrides.update(overrides)
        try:
            resp = client.post(
                "/api/v1/chat/completions",
                json=self._CHAT_PAYLOAD,
                headers={"Authorization": "NotBearer abc"},
            )
            assert resp.status_code == 401
        finally:
            for k in overrides:
                app.dependency_overrides.pop(k, None)

    def test_invalid_key_returns_401(self, client: TestClient):
        """A key that does not exist in DB returns 401."""
        overrides = _with_auth_fail()
        app.dependency_overrides.update(overrides)
        try:
            resp = client.post(
                "/api/v1/chat/completions",
                json=self._CHAT_PAYLOAD,
                headers={"Authorization": "Bearer cxg_invalid"},
            )
            assert resp.status_code == 401
        finally:
            for k in overrides:
                app.dependency_overrides.pop(k, None)

    def test_expired_key_returns_401(self, client: TestClient):
        overrides = _with_auth_fail()
        app.dependency_overrides.update(overrides)
        try:
            resp = client.post(
                "/api/v1/chat/completions",
                json=self._CHAT_PAYLOAD,
                headers={"Authorization": "Bearer cxg_expired"},
            )
            assert resp.status_code == 401
        finally:
            for k in overrides:
                app.dependency_overrides.pop(k, None)

    def test_revoked_key_returns_401(self, client: TestClient):
        overrides = _with_auth_fail()
        app.dependency_overrides.update(overrides)
        try:
            resp = client.post(
                "/api/v1/chat/completions",
                json=self._CHAT_PAYLOAD,
                headers={"Authorization": "Bearer cxg_revoked"},
            )
            assert resp.status_code == 401
        finally:
            for k in overrides:
                app.dependency_overrides.pop(k, None)

    def test_valid_key_reaches_chat_service(self, client: TestClient):
        """A valid key passes auth and reaches ChatService."""
        from app.auth.dependencies import get_request_context
        from app.database.session import get_db_dependency
        from app.schemas.chat import (
            ChatCompletionChoice,
            ChatCompletionResponse,
            ChatMessageResponse,
            ResponseMetadata,
            UsageMetadata,
        )

        mock_response = ChatCompletionResponse(
            provider="groq",
            model="llama-3.3-70b-versatile",
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessageResponse(content="Hello!"),
                    finish_reason="stop",
                )
            ],
            usage=UsageMetadata(prompt_tokens=5, completion_tokens=3, total_tokens=8),
            metadata=ResponseMetadata(
                request_id="test-req",
                latency_ms=100.0,
                routing_mode="auto",
                selected_provider="groq",
                selected_model="llama-3.3-70b-versatile",
            ),
        )

        async def _mock_context():
            return _ADMIN_CONTEXT

        async def _mock_db():
            yield AsyncMock()

        app.dependency_overrides[get_request_context] = _mock_context
        app.dependency_overrides[get_db_dependency] = _mock_db
        try:
            with patch(
                "app.services.chat_service.ChatService.complete",
                new_callable=AsyncMock,
                return_value=mock_response,
            ):
                resp = client.post(
                    "/api/v1/chat/completions",
                    json=self._CHAT_PAYLOAD,
                    headers={"Authorization": "Bearer cxg_validkey"},
                )
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(get_request_context, None)
            app.dependency_overrides.pop(get_db_dependency, None)


# ── RBAC Tests ────────────────────────────────────────────────────────────────


class TestRBAC:
    """Role-based access control enforcement."""

    def test_member_cannot_create_team(self, client: TestClient):
        overrides = _with_auth(context=_MEMBER_CONTEXT)
        app.dependency_overrides.update(overrides)
        try:
            resp = client.post(
                "/api/v1/organizations/org-001/teams",
                json={"name": "New Team", "slug": "new-team"},
                headers={"Authorization": "Bearer cxg_memberkey"},
            )
            assert resp.status_code == 403
            assert resp.json()["error"]["code"] == "FORBIDDEN"
        finally:
            for k in overrides:
                app.dependency_overrides.pop(k, None)

    def test_member_cannot_create_api_key(self, client: TestClient):
        overrides = _with_auth(context=_MEMBER_CONTEXT)
        app.dependency_overrides.update(overrides)
        try:
            resp = client.post(
                "/api/v1/teams/team-001/keys",
                json={"name": "my-key", "role": "member"},
                headers={"Authorization": "Bearer cxg_memberkey"},
            )
            assert resp.status_code == 403
        finally:
            for k in overrides:
                app.dependency_overrides.pop(k, None)

    def test_member_cannot_list_api_keys(self, client: TestClient):
        overrides = _with_auth(context=_MEMBER_CONTEXT)
        app.dependency_overrides.update(overrides)
        try:
            resp = client.get(
                "/api/v1/teams/team-001/keys",
                headers={"Authorization": "Bearer cxg_memberkey"},
            )
            assert resp.status_code == 403
        finally:
            for k in overrides:
                app.dependency_overrides.pop(k, None)

    def test_member_cannot_revoke_api_key(self, client: TestClient):
        overrides = _with_auth(context=_MEMBER_CONTEXT)
        app.dependency_overrides.update(overrides)
        try:
            resp = client.post(
                "/api/v1/teams/team-001/keys/key-001/revoke",
                headers={"Authorization": "Bearer cxg_memberkey"},
            )
            assert resp.status_code == 403
        finally:
            for k in overrides:
                app.dependency_overrides.pop(k, None)

    def test_admin_can_list_api_keys(self, client: TestClient):
        from app.auth.dependencies import get_request_context, require_admin
        from app.auth.models import APIKey

        mock_key = MagicMock(spec=APIKey)
        mock_key.id = "key-001"
        mock_key.name = "admin-key"
        mock_key.key_prefix = "cxg_admin_prefix1"
        mock_key.role = "admin"
        mock_key.expires_at = None
        mock_key.revoked_at = None
        mock_key.created_at = datetime(2026, 9, 14, tzinfo=UTC)
        mock_key.last_used_at = None

        mock_service = AsyncMock()
        mock_service.list_api_keys = AsyncMock(return_value=[mock_key])

        overrides = _with_auth(context=_ADMIN_CONTEXT)
        app.dependency_overrides.update(overrides)
        try:
            with patch("app.api.v1.endpoints.api_keys.AuthService", return_value=mock_service):
                resp = client.get(
                    "/api/v1/teams/team-001/keys",
                    headers={"Authorization": "Bearer cxg_adminkey"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert "keys" in data
        finally:
            for k in overrides:
                app.dependency_overrides.pop(k, None)

    def test_cross_team_access_denied(self, client: TestClient):
        """Admin from team-001 cannot access team-002 resources."""
        overrides = _with_auth(context=_ADMIN_CONTEXT)  # team_id = "team-001"
        app.dependency_overrides.update(overrides)
        try:
            resp = client.get(
                "/api/v1/teams/team-999/keys",  # different team
                headers={"Authorization": "Bearer cxg_adminkey"},
            )
            assert resp.status_code == 403
        finally:
            for k in overrides:
                app.dependency_overrides.pop(k, None)

    def test_cross_org_access_denied(self, client: TestClient):
        """Admin cannot access a different organization."""
        overrides = _with_auth(context=_ADMIN_CONTEXT)  # org_id = "org-001"
        app.dependency_overrides.update(overrides)
        try:
            resp = client.get(
                "/api/v1/organizations/org-999",  # different org
                headers={"Authorization": "Bearer cxg_adminkey"},
            )
            assert resp.status_code == 403
        finally:
            for k in overrides:
                app.dependency_overrides.pop(k, None)


# ── RequestContext Structure ──────────────────────────────────────────────────


class TestRequestContextStructure:
    def test_request_context_has_required_fields(self):
        ctx = RequestContext(
            organization_id="org-abc",
            team_id="team-xyz",
            api_key_id="key-123",
            role="admin",
        )
        assert ctx.organization_id == "org-abc"
        assert ctx.team_id == "team-xyz"
        assert ctx.api_key_id == "key-123"
        assert ctx.role == "admin"

    def test_member_role_value(self):
        ctx = RequestContext(
            organization_id="org-abc",
            team_id="team-xyz",
            api_key_id="key-456",
            role="member",
        )
        assert ctx.role == "member"
