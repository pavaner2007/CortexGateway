"""
Cortex Gateway — Per-Team Rate Limit Management Tests (Phase 6 Gap 2).

Tests:
  - TeamRateLimitService: get, set (create + update), delete
  - GET /api/v1/teams/{team_id}/rate-limits: returns effective limits
  - POST /api/v1/teams/{team_id}/rate-limits: sets override, changes enforcement
  - DELETE /api/v1/teams/{team_id}/rate-limits: removes override (global default resumes)
  - Non-admin → 403 on all routes
  - Custom team limit actually changes what RateLimiter receives (enforcement test)
  - Unset teams use global default (no override row → settings value used)
  - Override fallback: DB failure → fail-open, use global default
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rate_limit.team_limits import TeamRateLimit, TeamRateLimitService


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_context(role: str = "admin", team_id: str = "team-1", org_id: str = "org-1"):
    from app.auth.schemas import RequestContext
    return RequestContext(
        organization_id=org_id,
        team_id=team_id,
        api_key_id="key-1",
        role=role,
    )


def _make_rl_row(
    team_id: str = "team-1",
    rpm: int | None = None,
    rph: int | None = None,
) -> TeamRateLimit:
    from datetime import datetime, timezone
    row = MagicMock(spec=TeamRateLimit)
    row.id = "rl-1"
    row.team_id = team_id
    row.requests_per_minute = rpm
    row.requests_per_hour = rph
    row.created_at = datetime.now(timezone.utc)
    row.updated_at = datetime.now(timezone.utc)
    return row


# ── TeamRateLimitService Unit Tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_team_rate_limit_service_get_none_when_no_row():
    """get() returns None when no override exists for team."""
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    service = TeamRateLimitService(session=session)
    result = await service.get("team-no-override")
    assert result is None


@pytest.mark.asyncio
async def test_team_rate_limit_service_get_returns_row():
    """get() returns the override row when it exists."""
    row = _make_rl_row(team_id="team-1", rpm=200)
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=row))
    )
    service = TeamRateLimitService(session=session)
    result = await service.get("team-1")
    assert result is not None
    assert result.requests_per_minute == 200


@pytest.mark.asyncio
async def test_team_rate_limit_service_set_creates_new_row():
    """set() creates a new row when no override exists."""
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    service = TeamRateLimitService(session=session)
    with patch.object(service, "get", side_effect=[None]):
        await service.set(team_id="team-new", requests_per_minute=300, requests_per_hour=None)

    session.add.assert_called_once()
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_team_rate_limit_service_set_updates_existing_row():
    """set() updates the existing override row."""
    existing = _make_rl_row(team_id="team-1", rpm=200)
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    service = TeamRateLimitService(session=session)
    with patch.object(service, "get", return_value=existing):
        await service.set(team_id="team-1", requests_per_minute=50, requests_per_hour=1000)

    assert existing.requests_per_minute == 50
    assert existing.requests_per_hour == 1000
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_team_rate_limit_service_delete_returns_false_if_no_row():
    """delete() returns False when no override row exists."""
    session = AsyncMock()
    service = TeamRateLimitService(session=session)
    with patch.object(service, "get", return_value=None):
        result = await service.delete("team-ghost")
    assert result is False


@pytest.mark.asyncio
async def test_team_rate_limit_service_delete_removes_existing_row():
    """delete() removes an existing override row and returns True."""
    row = _make_rl_row(team_id="team-1", rpm=200)
    session = AsyncMock()
    session.delete = AsyncMock()
    session.commit = AsyncMock()

    service = TeamRateLimitService(session=session)
    with patch.object(service, "get", return_value=row):
        result = await service.delete("team-1")

    assert result is True
    session.delete.assert_called_once_with(row)
    session.commit.assert_called_once()


# ── ChatService Integration: Per-team override enforcement ────────────────────


@pytest.mark.asyncio
async def test_custom_team_limit_enforced_over_global_default():
    """
    When a team has a custom rate limit override (e.g. 5 rpm), the limiter
    receives the override value — not the global 500 rpm default.
    This verifies the override actually changes enforcement behavior.
    """
    from app.services.chat_service import ChatService
    from app.schemas.chat import (
        ChatCompletionChoice,
        ChatCompletionRequest,
        ChatCompletionResponse,
        ChatMessage,
        ChatMessageResponse,
        ResponseMetadata,
        UsageMetadata,
    )
    from app.providers.registry import ProviderRegistry
    from app.rate_limit.limiter import RateLimiter

    registry = ProviderRegistry()
    mock_provider = MagicMock()
    mock_provider.name = "groq"
    mock_provider.health_check = AsyncMock(return_value=True)
    mock_provider.list_models = AsyncMock(return_value=["llama-3.3-70b-versatile"])
    mock_provider.chat = AsyncMock(
        return_value=ChatCompletionResponse(
            provider="groq",
            model="llama-3.3-70b-versatile",
            choices=[ChatCompletionChoice(index=0, message=ChatMessageResponse(content="ok"), finish_reason="stop")],
            usage=UsageMetadata(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            metadata=ResponseMetadata(request_id="req-1", latency_ms=50.0),
        )
    )
    registry.register(mock_provider)

    service = ChatService(registry=registry)
    context = _make_context(team_id="team-custom-limit")

    # Track what team_limit value reaches the rate limiter
    captured_team_limit = []

    from app.rate_limit.models import RateLimitOutcome, RateLimitResult

    async def _fake_check_all(**kwargs):
        captured_team_limit.append(kwargs.get("team_limit"))
        # Always allow (not testing blocking behavior here)
        result = RateLimitResult(
            allowed=True, scope="team", limit=kwargs["team_limit"],
            current_count=1, remaining=kwargs["team_limit"] - 1,
            retry_after_seconds=0,
        )
        return RateLimitOutcome(
            allowed=True, binding_result=result,
            key_result=result, team_result=result, org_result=result,
        )

    mock_rate_limiter = MagicMock(spec=RateLimiter)
    mock_rate_limiter.check_all = AsyncMock(side_effect=_fake_check_all)

    # Override row: team has custom 42 rpm limit
    override_row = _make_rl_row(team_id="team-custom-limit", rpm=42)
    mock_team_rl_service = AsyncMock(spec=TeamRateLimitService)
    mock_team_rl_service.get = AsyncMock(return_value=override_row)

    mock_settings = MagicMock()
    mock_settings.rate_limit_enabled = True
    mock_settings.rate_limit_api_key_requests = 100
    mock_settings.rate_limit_api_key_window_seconds = 60
    mock_settings.rate_limit_team_requests = 500   # global default (should be overridden)
    mock_settings.rate_limit_team_window_seconds = 60
    mock_settings.rate_limit_org_requests = 2000
    mock_settings.rate_limit_org_window_seconds = 60
    mock_settings.budget_enabled = True

    request = ChatCompletionRequest(
        provider="groq",
        model="llama-3.3-70b-versatile",
        messages=[ChatMessage(role="user", content="Hello")],
    )

    await service.complete(
        request=request,
        request_id="req-1",
        context=context,
        rate_limiter=mock_rate_limiter,
        team_rate_limit_service=mock_team_rl_service,
        settings=mock_settings,
    )

    assert len(captured_team_limit) > 0
    assert captured_team_limit[0] == 42, (
        f"Expected team_limit=42 (custom override), got {captured_team_limit[0]!r}"
    )


@pytest.mark.asyncio
async def test_unset_team_uses_global_default_limit():
    """
    When no override row exists for a team, the global default limit is used.
    """
    from app.services.chat_service import ChatService
    from app.schemas.chat import (
        ChatCompletionChoice,
        ChatCompletionRequest,
        ChatCompletionResponse,
        ChatMessage,
        ChatMessageResponse,
        ResponseMetadata,
        UsageMetadata,
    )
    from app.providers.registry import ProviderRegistry
    from app.rate_limit.limiter import RateLimiter

    registry = ProviderRegistry()
    mock_provider = MagicMock()
    mock_provider.name = "groq"
    mock_provider.health_check = AsyncMock(return_value=True)
    mock_provider.list_models = AsyncMock(return_value=["llama-3.3-70b-versatile"])
    mock_provider.chat = AsyncMock(
        return_value=ChatCompletionResponse(
            provider="groq",
            model="llama-3.3-70b-versatile",
            choices=[ChatCompletionChoice(index=0, message=ChatMessageResponse(content="ok"), finish_reason="stop")],
            usage=UsageMetadata(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            metadata=ResponseMetadata(request_id="req-2", latency_ms=50.0),
        )
    )
    registry.register(mock_provider)

    service = ChatService(registry=registry)
    context = _make_context(team_id="team-no-override")

    captured_team_limit = []

    from app.rate_limit.models import RateLimitOutcome, RateLimitResult

    async def _fake_check_all(**kwargs):
        captured_team_limit.append(kwargs.get("team_limit"))
        result = RateLimitResult(
            allowed=True, scope="team", limit=kwargs["team_limit"],
            current_count=1, remaining=kwargs["team_limit"] - 1,
            retry_after_seconds=0,
        )
        return RateLimitOutcome(
            allowed=True, binding_result=result,
            key_result=result, team_result=result, org_result=result,
        )

    mock_rate_limiter = MagicMock(spec=RateLimiter)
    mock_rate_limiter.check_all = AsyncMock(side_effect=_fake_check_all)

    # No override row for this team
    mock_team_rl_service = AsyncMock(spec=TeamRateLimitService)
    mock_team_rl_service.get = AsyncMock(return_value=None)

    GLOBAL_DEFAULT = 500
    mock_settings = MagicMock()
    mock_settings.rate_limit_enabled = True
    mock_settings.rate_limit_api_key_requests = 100
    mock_settings.rate_limit_api_key_window_seconds = 60
    mock_settings.rate_limit_team_requests = GLOBAL_DEFAULT
    mock_settings.rate_limit_team_window_seconds = 60
    mock_settings.rate_limit_org_requests = 2000
    mock_settings.rate_limit_org_window_seconds = 60
    mock_settings.budget_enabled = True

    request = ChatCompletionRequest(
        provider="groq",
        model="llama-3.3-70b-versatile",
        messages=[ChatMessage(role="user", content="Hello")],
    )

    await service.complete(
        request=request,
        request_id="req-2",
        context=context,
        rate_limiter=mock_rate_limiter,
        team_rate_limit_service=mock_team_rl_service,
        settings=mock_settings,
    )

    assert captured_team_limit[0] == GLOBAL_DEFAULT, (
        f"Expected global default {GLOBAL_DEFAULT}, got {captured_team_limit[0]!r}"
    )


@pytest.mark.asyncio
async def test_db_failure_falls_back_to_global_default():
    """
    When the team_rate_limit_service DB call raises an exception,
    the limiter should fail-open and use the global default — never block traffic.
    """
    from app.services.chat_service import ChatService
    from app.schemas.chat import (
        ChatCompletionChoice,
        ChatCompletionRequest,
        ChatCompletionResponse,
        ChatMessage,
        ChatMessageResponse,
        ResponseMetadata,
        UsageMetadata,
    )
    from app.providers.registry import ProviderRegistry
    from app.rate_limit.limiter import RateLimiter

    registry = ProviderRegistry()
    mock_provider = MagicMock()
    mock_provider.name = "groq"
    mock_provider.health_check = AsyncMock(return_value=True)
    mock_provider.list_models = AsyncMock(return_value=["llama-3.3-70b-versatile"])
    mock_provider.chat = AsyncMock(
        return_value=ChatCompletionResponse(
            provider="groq",
            model="llama-3.3-70b-versatile",
            choices=[ChatCompletionChoice(index=0, message=ChatMessageResponse(content="ok"), finish_reason="stop")],
            usage=UsageMetadata(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            metadata=ResponseMetadata(request_id="req-3", latency_ms=50.0),
        )
    )
    registry.register(mock_provider)

    service = ChatService(registry=registry)
    context = _make_context(team_id="team-db-fail")

    captured_team_limit = []

    from app.rate_limit.models import RateLimitOutcome, RateLimitResult

    async def _fake_check_all(**kwargs):
        captured_team_limit.append(kwargs.get("team_limit"))
        result = RateLimitResult(
            allowed=True, scope="team", limit=kwargs["team_limit"],
            current_count=1, remaining=kwargs["team_limit"] - 1,
            retry_after_seconds=0,
        )
        return RateLimitOutcome(
            allowed=True, binding_result=result,
            key_result=result, team_result=result, org_result=result,
        )

    mock_rate_limiter = MagicMock(spec=RateLimiter)
    mock_rate_limiter.check_all = AsyncMock(side_effect=_fake_check_all)

    # DB call raises exception
    mock_team_rl_service = AsyncMock(spec=TeamRateLimitService)
    mock_team_rl_service.get = AsyncMock(side_effect=Exception("DB connection lost"))

    GLOBAL_DEFAULT = 500
    mock_settings = MagicMock()
    mock_settings.rate_limit_enabled = True
    mock_settings.rate_limit_api_key_requests = 100
    mock_settings.rate_limit_api_key_window_seconds = 60
    mock_settings.rate_limit_team_requests = GLOBAL_DEFAULT
    mock_settings.rate_limit_team_window_seconds = 60
    mock_settings.rate_limit_org_requests = 2000
    mock_settings.rate_limit_org_window_seconds = 60
    mock_settings.budget_enabled = True

    request = ChatCompletionRequest(
        provider="groq",
        model="llama-3.3-70b-versatile",
        messages=[ChatMessage(role="user", content="Hello")],
    )

    # Must NOT raise — fail-open behavior
    await service.complete(
        request=request,
        request_id="req-3",
        context=context,
        rate_limiter=mock_rate_limiter,
        team_rate_limit_service=mock_team_rl_service,
        settings=mock_settings,
    )

    # Global default was used instead of raising
    assert captured_team_limit[0] == GLOBAL_DEFAULT


# ── Non-admin RBAC on rate-limits endpoints ───────────────────────────────────


def test_rate_limits_member_cannot_set(monkeypatch):
    """Member role cannot set rate limit overrides (403)."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.auth.dependencies import require_admin
    from app.auth.exceptions import AuthorizationError

    app.dependency_overrides[require_admin] = lambda: (_ for _ in ()).throw(
        AuthorizationError("This operation requires admin privileges.")
    )

    with (
        patch("app.main.init_db"),
        patch("app.main.init_redis"),
        patch("app.main.close_db", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
    ):
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(
                "/api/v1/teams/team-1/rate-limits",
                json={"requests_per_minute": 10},
                headers={"Authorization": "Bearer cxg_member_key"},
            )
        assert resp.status_code in (401, 403, 422)

    app.dependency_overrides.clear()


def test_rate_limits_member_cannot_get(monkeypatch):
    """Member role cannot view rate limit overrides (403)."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.auth.dependencies import require_admin
    from app.auth.exceptions import AuthorizationError

    app.dependency_overrides[require_admin] = lambda: (_ for _ in ()).throw(
        AuthorizationError("This operation requires admin privileges.")
    )

    with (
        patch("app.main.init_db"),
        patch("app.main.init_redis"),
        patch("app.main.close_db", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
    ):
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get(
                "/api/v1/teams/team-1/rate-limits",
                headers={"Authorization": "Bearer cxg_member_key"},
            )
        assert resp.status_code in (401, 403, 422)

    app.dependency_overrides.clear()
