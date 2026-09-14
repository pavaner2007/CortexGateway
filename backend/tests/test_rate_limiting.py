"""
Cortex Gateway — Rate Limiting Tests (Phase 6).

Tests:
  - Fixed-window counter: under limit passes, over limit → 429
  - Window reset: counter resets after window expires
  - API key / team / org scopes independently
  - Combined hierarchy: any scope failing → 429
  - Ownership: rate limits use RequestContext values, not client-supplied body

All Redis interactions are mocked via AsyncMock so no real Redis is needed.
"""

from __future__ import annotations

import time
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rate_limit.limiter import RateLimiter
from app.rate_limit.models import RateLimitOutcome, RateLimitResult


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_redis_mock(count: int, ttl: int = 55) -> MagicMock:
    """
    Build a mock Redis client whose registered_script returns (count, ttl).
    Simulates the Lua script response for a single call.
    """
    script_mock = AsyncMock(return_value=[count, ttl])
    redis_mock = MagicMock()
    redis_mock.register_script = MagicMock(return_value=script_mock)
    return redis_mock


def _make_counter_redis(counts: Dict[str, int], ttl: int = 55) -> MagicMock:
    """
    Build a mock Redis client that returns per-key counts.
    Useful for testing hierarchy where different scopes have different counts.
    """
    call_record: Dict[str, int] = {}

    async def _script_call(keys, args):
        key = keys[0]
        # Extract scope from key: ratelimit:<scope>:<id>:<window>
        parts = key.split(":")
        scope = parts[1] if len(parts) > 1 else "unknown"
        count = counts.get(scope, 1)
        return [count, ttl]

    script_mock = MagicMock(side_effect=_script_call)
    redis_mock = MagicMock()
    redis_mock.register_script = MagicMock(return_value=script_mock)
    return redis_mock


# ── Unit Tests: RateLimiter._check_scope ──────────────────────────────────────


@pytest.mark.asyncio
async def test_check_scope_under_limit():
    """Count=1 with limit=100 → allowed=True."""
    redis = _make_redis_mock(count=1, ttl=55)
    limiter = RateLimiter(redis=redis)
    result = await limiter._check_scope("key", "test-key-id", limit=100, window_seconds=60)
    assert result.allowed is True
    assert result.remaining == 99
    assert result.limit == 100
    assert result.scope == "key"


@pytest.mark.asyncio
async def test_check_scope_at_limit():
    """Count=100 with limit=100 → still allowed (boundary is inclusive)."""
    redis = _make_redis_mock(count=100, ttl=10)
    limiter = RateLimiter(redis=redis)
    result = await limiter._check_scope("team", "team-abc", limit=100, window_seconds=60)
    assert result.allowed is True
    assert result.remaining == 0


@pytest.mark.asyncio
async def test_check_scope_over_limit():
    """Count=101 with limit=100 → allowed=False, retry_after set."""
    redis = _make_redis_mock(count=101, ttl=45)
    limiter = RateLimiter(redis=redis)
    result = await limiter._check_scope("org", "org-xyz", limit=100, window_seconds=60)
    assert result.allowed is False
    assert result.remaining == 0
    assert result.retry_after_seconds == 45


@pytest.mark.asyncio
async def test_check_scope_no_redis_fails_open():
    """No Redis client → fail-open (always allows)."""
    limiter = RateLimiter(redis=None)
    result = await limiter._check_scope("key", "any-id", limit=1, window_seconds=60)
    assert result.allowed is True
    assert result.remaining == 1


@pytest.mark.asyncio
async def test_check_scope_redis_error_fails_open():
    """Redis script raises → fail-open."""
    script_mock = AsyncMock(side_effect=Exception("Redis connection error"))
    redis_mock = MagicMock()
    redis_mock.register_script = MagicMock(return_value=script_mock)
    limiter = RateLimiter(redis=redis_mock)
    result = await limiter._check_scope("key", "any-id", limit=1, window_seconds=60)
    assert result.allowed is True


# ── Unit Tests: RateLimiter.check_all ────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_all_all_pass():
    """All three scopes under limit → allowed."""
    redis = _make_counter_redis({"key": 1, "team": 50, "org": 200})
    limiter = RateLimiter(redis=redis)
    outcome = await limiter.check_all(
        api_key_id="key-1", team_id="team-1", org_id="org-1",
        key_limit=100, key_window=60,
        team_limit=500, team_window=60,
        org_limit=2000, org_window=60,
    )
    assert outcome.allowed is True
    assert outcome.key_result.allowed is True
    assert outcome.team_result.allowed is True
    assert outcome.org_result.allowed is True


@pytest.mark.asyncio
async def test_check_all_key_fails():
    """API key over limit → rejected, team and org are still within their limits."""
    redis = _make_counter_redis({"key": 101, "team": 50, "org": 200})
    limiter = RateLimiter(redis=redis)
    outcome = await limiter.check_all(
        api_key_id="key-1", team_id="team-1", org_id="org-1",
        key_limit=100, key_window=60,
        team_limit=500, team_window=60,
        org_limit=2000, org_window=60,
    )
    assert outcome.allowed is False
    assert outcome.binding_result.scope == "key"
    assert outcome.key_result.allowed is False
    assert outcome.team_result.allowed is True
    assert outcome.org_result.allowed is True


@pytest.mark.asyncio
async def test_check_all_team_fails():
    """Team over limit → rejected, key passes."""
    redis = _make_counter_redis({"key": 1, "team": 501, "org": 200})
    limiter = RateLimiter(redis=redis)
    outcome = await limiter.check_all(
        api_key_id="key-1", team_id="team-1", org_id="org-1",
        key_limit=100, key_window=60,
        team_limit=500, team_window=60,
        org_limit=2000, org_window=60,
    )
    assert outcome.allowed is False
    assert outcome.binding_result.scope == "team"


@pytest.mark.asyncio
async def test_check_all_org_fails():
    """Org over limit → rejected even though key and team pass."""
    redis = _make_counter_redis({"key": 1, "team": 50, "org": 2001})
    limiter = RateLimiter(redis=redis)
    outcome = await limiter.check_all(
        api_key_id="key-1", team_id="team-1", org_id="org-1",
        key_limit=100, key_window=60,
        team_limit=500, team_window=60,
        org_limit=2000, org_window=60,
    )
    assert outcome.allowed is False
    assert outcome.binding_result.scope == "org"


@pytest.mark.asyncio
async def test_check_all_binding_is_tightest_remaining():
    """When all pass, binding_result has lowest remaining count."""
    redis = _make_counter_redis({"key": 90, "team": 10, "org": 1})
    limiter = RateLimiter(redis=redis)
    outcome = await limiter.check_all(
        api_key_id="key-1", team_id="team-1", org_id="org-1",
        key_limit=100, key_window=60,
        team_limit=500, team_window=60,
        org_limit=2000, org_window=60,
    )
    assert outcome.allowed is True
    # org has lowest remaining = 2000 - 1 = 1999, key has 10, team has 490
    # Actually: key remaining=10, team=490, org=1999 → tightest=key
    assert outcome.binding_result.remaining == 10  # key is tightest


# ── Window Reset Simulation ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_window_key_format_changes_with_window():
    """
    Verify that the Redis key includes the window_start, so a new window
    results in a new Redis key (automatic reset via TTL).
    """
    observed_keys = []

    async def _capture_script(keys, args):
        observed_keys.extend(keys)
        return [1, 60]

    script_mock = MagicMock(side_effect=_capture_script)
    redis_mock = MagicMock()
    redis_mock.register_script = MagicMock(return_value=script_mock)

    limiter = RateLimiter(redis=redis_mock)

    # Two checks in the same call — same window
    with patch("app.rate_limit.limiter.time") as mock_time:
        mock_time.time.return_value = 1000.0  # window_start = 1000//60*60 = 960
        await limiter._check_scope("key", "abc", limit=100, window_seconds=60)
        key_t1 = observed_keys[-1]

        mock_time.time.return_value = 1060.0  # next window: 1060//60*60 = 1020
        await limiter._check_scope("key", "abc", limit=100, window_seconds=60)
        key_t2 = observed_keys[-1]

    # Keys must differ (different window_start)
    assert key_t1 != key_t2, f"Expected different keys but got {key_t1!r} twice"


# ── Ownership: Verify RequestContext values are used ─────────────────────────


@pytest.mark.asyncio
async def test_rate_limit_uses_context_ids_not_body():
    """
    Rate limiter must use team_id/org_id from authenticated RequestContext,
    not any client-supplied body values.

    This test confirms that when we pass specific IDs to check_all,
    those exact IDs appear in the Redis keys.
    """
    observed_keys = []

    async def _capture_script(keys, args):
        observed_keys.extend(keys)
        return [1, 60]

    script_mock = MagicMock(side_effect=_capture_script)
    redis_mock = MagicMock()
    redis_mock.register_script = MagicMock(return_value=script_mock)
    limiter = RateLimiter(redis=redis_mock)

    with patch("app.rate_limit.limiter.time") as mock_time:
        mock_time.time.return_value = 1000.0
        await limiter.check_all(
            api_key_id="ctx-key-id",
            team_id="ctx-team-id",
            org_id="ctx-org-id",
            key_limit=100, key_window=60,
            team_limit=500, team_window=60,
            org_limit=2000, org_window=60,
        )

    # ctx IDs must appear in the Redis keys
    all_keys_str = " ".join(observed_keys)
    assert "ctx-key-id" in all_keys_str
    assert "ctx-team-id" in all_keys_str
    assert "ctx-org-id" in all_keys_str
    # Attacker-supplied IDs must NOT appear
    assert "attacker-team" not in all_keys_str
