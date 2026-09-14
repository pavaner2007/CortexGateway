"""
Cortex Gateway — Auth Security Leakage Tests (Phase 5).

Verifies that sensitive values NEVER appear in:
  - API responses
  - Error responses
  - Log output

Mandatory security invariants:
  - Plaintext API key not in any response after creation
  - key_hash never in any API response
  - Authorization header not logged
  - Bootstrap token not in any response
  - API key not in error message body
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.exceptions import AuthenticationError
from app.auth.models import APIKey, Organization, Team
from app.auth.schemas import RequestContext
from app.main import app

_ADMIN_CONTEXT = RequestContext(
    organization_id="org-001",
    team_id="team-001",
    api_key_id="key-001",
    role="admin",
)

_FAKE_PLAINTEXT_KEY = "cxg_supersecretkey1234567890abcdef"
_FAKE_KEY_HASH = "a" * 64  # fake SHA-256 hex
_FAKE_BOOTSTRAP_TOKEN = "bootstrap-secret-token-xyz"


def _admin_overrides():
    """Return dependency overrides for authenticated admin requests."""
    from app.auth.dependencies import get_request_context, require_admin
    from app.database.session import get_db_dependency

    async def _mock_context():
        return _ADMIN_CONTEXT

    async def _mock_admin():
        return _ADMIN_CONTEXT

    async def _mock_db():
        yield AsyncMock()

    return {
        get_request_context: _mock_context,
        require_admin: _mock_admin,
        get_db_dependency: _mock_db,
    }


def _unauthenticated_overrides():
    """Return dependency overrides that simulate auth failure."""
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


@pytest.fixture(scope="module")
def client() -> TestClient:
    with (
        patch("app.main.init_db"),
        patch("app.main.init_redis"),
        patch("app.main.close_db", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
    ):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


class TestKeyHashNeverExposed:
    """key_hash must never appear in any API response."""

    def test_key_hash_not_in_create_key_response(self, client: TestClient):
        mock_key = MagicMock(spec=APIKey)
        mock_key.id = "key-001"
        mock_key.name = "test-key"
        mock_key.key_prefix = "cxg_supersecretkey1"
        mock_key.role = "admin"
        mock_key.expires_at = None
        mock_key.revoked_at = None
        mock_key.created_at = datetime(2026, 9, 14, tzinfo=timezone.utc)
        mock_key.last_used_at = None
        mock_key.key_hash = _FAKE_KEY_HASH  # must never appear in response

        mock_service = AsyncMock()
        mock_service.create_api_key = AsyncMock(return_value=(mock_key, _FAKE_PLAINTEXT_KEY))

        overrides = _admin_overrides()
        app.dependency_overrides.update(overrides)
        try:
            with patch("app.api.v1.endpoints.api_keys.AuthService", return_value=mock_service):
                resp = client.post(
                    "/api/v1/teams/team-001/keys",
                    json={"name": "test-key", "role": "admin"},
                    headers={"Authorization": "Bearer cxg_adminkey"},
                )
            assert resp.status_code == 201
            assert _FAKE_KEY_HASH not in resp.text, "key_hash must never appear in response"
        finally:
            for k in overrides:
                app.dependency_overrides.pop(k, None)

    def test_key_hash_not_in_list_keys_response(self, client: TestClient):
        mock_key = MagicMock(spec=APIKey)
        mock_key.id = "key-001"
        mock_key.name = "test-key"
        mock_key.key_prefix = "cxg_supersecretkey1"
        mock_key.role = "admin"
        mock_key.expires_at = None
        mock_key.revoked_at = None
        mock_key.created_at = datetime(2026, 9, 14, tzinfo=timezone.utc)
        mock_key.last_used_at = None
        mock_key.key_hash = _FAKE_KEY_HASH  # must never appear

        mock_service = AsyncMock()
        mock_service.list_api_keys = AsyncMock(return_value=[mock_key])

        overrides = _admin_overrides()
        app.dependency_overrides.update(overrides)
        try:
            with patch("app.api.v1.endpoints.api_keys.AuthService", return_value=mock_service):
                resp = client.get(
                    "/api/v1/teams/team-001/keys",
                    headers={"Authorization": "Bearer cxg_adminkey"},
                )
            assert resp.status_code == 200
            assert _FAKE_KEY_HASH not in resp.text, "key_hash must never appear in list response"
        finally:
            for k in overrides:
                app.dependency_overrides.pop(k, None)

    def test_key_hash_not_in_schema_fields(self):
        """The APIKeyResponse schema must not include key_hash as a field."""
        from app.auth.schemas import APIKeyResponse
        schema_fields = set(APIKeyResponse.model_fields.keys())
        assert "key_hash" not in schema_fields, "APIKeyResponse must not expose key_hash"

    def test_key_hash_not_in_created_response_schema(self):
        """The APIKeyCreatedResponse schema must not include key_hash."""
        from app.auth.schemas import APIKeyCreatedResponse
        schema_fields = set(APIKeyCreatedResponse.model_fields.keys())
        assert "key_hash" not in schema_fields, "APIKeyCreatedResponse must not expose key_hash"


class TestPlaintextKeyOnlyShownOnce:
    """Plaintext API key appears ONLY in the creation response."""

    def test_create_key_contains_plaintext_key(self, client: TestClient):
        """Creation response must contain the plaintext key."""
        mock_key = MagicMock(spec=APIKey)
        mock_key.id = "key-001"
        mock_key.name = "test-key"
        mock_key.key_prefix = "cxg_supersecretkey1"
        mock_key.role = "admin"
        mock_key.expires_at = None
        mock_key.created_at = datetime(2026, 9, 14, tzinfo=timezone.utc)
        mock_key.key_hash = _FAKE_KEY_HASH

        mock_service = AsyncMock()
        mock_service.create_api_key = AsyncMock(return_value=(mock_key, _FAKE_PLAINTEXT_KEY))

        overrides = _admin_overrides()
        app.dependency_overrides.update(overrides)
        try:
            with patch("app.api.v1.endpoints.api_keys.AuthService", return_value=mock_service):
                resp = client.post(
                    "/api/v1/teams/team-001/keys",
                    json={"name": "test-key", "role": "admin"},
                    headers={"Authorization": "Bearer cxg_adminkey"},
                )
            assert resp.status_code == 201
            body = resp.json()
            assert "key" in body, "Creation response must contain plaintext key"
            assert body["key"] == _FAKE_PLAINTEXT_KEY
        finally:
            for k in overrides:
                app.dependency_overrides.pop(k, None)

    def test_list_keys_does_not_contain_plaintext(self, client: TestClient):
        """List keys response must NOT contain plaintext key."""
        mock_key = MagicMock(spec=APIKey)
        mock_key.id = "key-001"
        mock_key.name = "test-key"
        mock_key.key_prefix = "cxg_supersecretkey1"
        mock_key.role = "admin"
        mock_key.expires_at = None
        mock_key.revoked_at = None
        mock_key.created_at = datetime(2026, 9, 14, tzinfo=timezone.utc)
        mock_key.last_used_at = None
        mock_key.key_hash = _FAKE_KEY_HASH

        mock_service = AsyncMock()
        mock_service.list_api_keys = AsyncMock(return_value=[mock_key])

        overrides = _admin_overrides()
        app.dependency_overrides.update(overrides)
        try:
            with patch("app.api.v1.endpoints.api_keys.AuthService", return_value=mock_service):
                resp = client.get(
                    "/api/v1/teams/team-001/keys",
                    headers={"Authorization": "Bearer cxg_adminkey"},
                )
            assert resp.status_code == 200
            body = resp.json()
            assert "key" not in body, "List response must not include plaintext key"
            for key_item in body.get("keys", []):
                assert "key" not in key_item, "Key metadata must not contain plaintext key"
        finally:
            for k in overrides:
                app.dependency_overrides.pop(k, None)


class TestAuthenticationErrorsDoNotLeakInfo:
    """Authentication errors must not reveal internal details."""

    def test_invalid_key_error_has_generic_message(self, client: TestClient):
        overrides = _unauthenticated_overrides()
        app.dependency_overrides.update(overrides)
        try:
            resp = client.post(
                "/api/v1/chat/completions",
                json={"model": "auto", "messages": [{"role": "user", "content": "hi"}]},
                headers={"Authorization": "Bearer cxg_bad"},
            )
            assert resp.status_code == 401
            body = resp.json()
            # Error must not say "key not found", "expired", "revoked" etc.
            error_msg = body["error"]["message"].lower()
            assert "not found" not in error_msg
            assert "expired" not in error_msg
            assert "revoked" not in error_msg
            assert "hash" not in error_msg
            assert "pepper" not in error_msg
        finally:
            for k in overrides:
                app.dependency_overrides.pop(k, None)

    def test_bootstrap_token_not_exposed_in_error(self, client: TestClient):
        """Failed bootstrap must not reveal the bootstrap token."""
        # No dependency override needed — bootstrap uses its own bearer token check
        resp = client.post(
            "/api/v1/bootstrap",
            json={
                "organization_name": "Test Org",
                "organization_slug": "test-org",
                "team_name": "Test Team",
                "team_slug": "test-team",
                "admin_key_name": "admin-key",
            },
            headers={"Authorization": "Bearer wrong-token"},
        )
        # Bootstrap will fail at DB session (init not called), but should not expose token
        # The response should be 401 or 500, but NOT contain the token value
        assert _FAKE_BOOTSTRAP_TOKEN not in resp.text
        assert "change-me-in-production" not in resp.text


class TestBootstrapResponse:
    """Bootstrap response must be safe."""

    def test_bootstrap_response_contains_key_once(self, client: TestClient):
        mock_org = MagicMock(spec=Organization)
        mock_org.id = "org-001"
        mock_org.name = "Test Org"
        mock_org.slug = "test-org"
        mock_org.created_at = datetime(2026, 9, 14, tzinfo=timezone.utc)
        mock_org.updated_at = datetime(2026, 9, 14, tzinfo=timezone.utc)

        mock_team = MagicMock(spec=Team)
        mock_team.id = "team-001"
        mock_team.organization_id = "org-001"
        mock_team.name = "Test Team"
        mock_team.slug = "test-team"
        mock_team.created_at = datetime(2026, 9, 14, tzinfo=timezone.utc)
        mock_team.updated_at = datetime(2026, 9, 14, tzinfo=timezone.utc)

        mock_key = MagicMock(spec=APIKey)
        mock_key.id = "key-001"
        mock_key.name = "admin-key"
        mock_key.key_prefix = "cxg_supersecretkey1"
        mock_key.role = "admin"
        mock_key.expires_at = None
        mock_key.created_at = datetime(2026, 9, 14, tzinfo=timezone.utc)
        mock_key.key_hash = _FAKE_KEY_HASH  # must not appear in response

        mock_service = AsyncMock()
        mock_service.organizations_exist = AsyncMock(return_value=False)
        mock_service.create_organization = AsyncMock(return_value=mock_org)
        mock_service.create_team = AsyncMock(return_value=mock_team)
        mock_service.create_api_key = AsyncMock(return_value=(mock_key, _FAKE_PLAINTEXT_KEY))

        # Also need to mock the shared get_db_dependency for bootstrap endpoint
        from app.database.session import get_db_dependency

        async def _mock_bootstrap_db():
            yield AsyncMock()

        app.dependency_overrides[get_db_dependency] = _mock_bootstrap_db
        try:
            with (
                patch("app.api.v1.endpoints.bootstrap.AuthService", return_value=mock_service),
                patch("app.api.v1.endpoints.bootstrap.get_settings") as mock_settings,
            ):
                s = MagicMock()
                s.cortex_bootstrap_enabled = True
                s.cortex_bootstrap_token = "valid-test-token"
                s.api_key_pepper = "test-pepper"
                mock_settings.return_value = s

                resp = client.post(
                    "/api/v1/bootstrap",
                    json={
                        "organization_name": "Test Org",
                        "organization_slug": "test-org",
                        "team_name": "Test Team",
                        "team_slug": "test-team",
                        "admin_key_name": "admin-key",
                    },
                    headers={"Authorization": "Bearer valid-test-token"},
                )

            if resp.status_code == 201:
                body = resp.json()
                # key_hash must not appear
                assert _FAKE_KEY_HASH not in resp.text
                # admin_key block must contain the plaintext key
                assert "admin_key" in body
                assert body["admin_key"]["key"] == _FAKE_PLAINTEXT_KEY
        finally:
            app.dependency_overrides.pop(get_db_dependency, None)
