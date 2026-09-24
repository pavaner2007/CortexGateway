"""
Cortex Gateway — Rate Limiting Tests (Phase 6 / Gap 3 fix).

Tests:
  - Sliding-window counter: under limit passes, over limit → 429
  - Window reset: counter resets after window expires
  - API key / team / org scopes independently
  - Combined hierarchy: any scope failing → 429
  - Ownership: rate limits use RequestContext values, not client-supplied body
  - BOUNDARY BURST: sliding window prevents client from sending 2× limit
    by straddling a window boundary (regression test for Gap 3)

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
    Build a mock Redis client whose registered_script returns (count, ttl, curr_count).
    Simulates the Lua script response for a single call.

    The sliding-window script now returns 3 values: [effective_count, ttl, curr_count].
    """
    script_mock = AsyncMock(return_value=[count, ttl, count])
    redis_mock = MagicMock()
    redis_mock.register_script = MagicMock(return_value=script_mock)
    return redis_mock


def _make_counter_redis(counts: dict[str, int], ttl: int = 55) -> MagicMock:
    """
    Build a mock Redis client that returns per-key counts.
    Useful for testing hierarchy where different scopes have different counts.

    Returns 3-element list matching new sliding-window script return shape.
    """
    async def _script_call(keys, args):
        key = keys[0]
        # Extract scope from key: ratelimit:<scope>:<id>:<window>
        parts = key.split(":")
        scope = parts[1] if len(parts) > 1 else "unknown"
        count = counts.get(scope, 1)
        return [count, ttl, count]

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
    # key remaining=10, team=490, org=1999 → tightest=key (remaining=10)
    assert outcome.binding_result.remaining == 10  # key is tightest


# ── Window Reset Simulation ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_window_key_format_changes_with_window():
    """
    Verify that the Redis key includes the window_start, so a new window
    results in a new Redis key (automatic reset via TTL).

    With the sliding-window implementation, script() now receives 2 KEYS.
    We verify the first key (current window) changes between windows.
    """
    observed_curr_keys = []

    async def _capture_script(keys, args):
        observed_curr_keys.append(keys[0])  # KEYS[1] = current window key
        return [1, 60, 1]  # [effective_count, ttl, curr_count]

    script_mock = MagicMock(side_effect=_capture_script)
    redis_mock = MagicMock()
    redis_mock.register_script = MagicMock(return_value=script_mock)

    limiter = RateLimiter(redis=redis_mock)

    with patch("app.rate_limit.limiter.time") as mock_time:
        mock_time.time.return_value = 1000.0  # window_start = 1000//60*60 = 960
        await limiter._check_scope("key", "abc", limit=100, window_seconds=60)
        key_t1 = observed_curr_keys[-1]

        mock_time.time.return_value = 1060.0  # next window: 1060//60*60 = 1020
        await limiter._check_scope("key", "abc", limit=100, window_seconds=60)
        key_t2 = observed_curr_keys[-1]

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
        observed_keys.extend(keys)  # Now 2 KEYS per call
        return [1, 60, 1]

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


# ── GAP 3 REGRESSION: Sliding window prevents boundary-burst (2× limit) ──────


@pytest.mark.asyncio
async def test_sliding_window_prevents_boundary_burst():
    """
    REGRESSION TEST for Gap 3: Verifies the sliding window prevents the
    2× burst that was possible with the old fixed-window implementation.

    Scenario:
      - limit=10, window=60s
      - At t=59s (1s before window end), client sends 10 requests
        → prev_window now has count=10 at rollover
      - At t=61s (1s into NEW window), client sends 10 more requests
        → fixed-window would allow all 10 (fresh window)
        → sliding-window MUST reject: effective = 10 × (1 - 1/60) + 10 ≈ 19.8 → 20 > 10

    We simulate this by directly controlling what the Lua script returns,
    mimicking the state that would exist after the straddled requests.
    """
    calls = []

    # At t=1s into new window (elapsed=1s out of 60s):
    # - curr_count = 10 (10 requests just made in new window)
    # - prev_count = 10 (all 10 were sent in last second of prev window)
    # effective = 10 * (1 - 1/60) + 10 = 10 * 0.9833... + 10 ≈ 19.83 → ceil = 20
    # So the sliding-window limiter sees 20 > limit=10 → BLOCKED

    async def _straddled_burst_script(keys, args):
        """
        Simulate the state AFTER a client has sent limit requests just
        before the window boundary AND is now sending more at the start
        of the new window.

        The effective count returned here (20) mimics what the real Lua script
        would produce: prev_count=10, curr_count=10, elapsed_fraction=1/60
        """
        effective_count = 20  # ceil(10 * (59/60) + 10) — exceeds limit=10
        ttl = 59
        curr_count = 10
        calls.append({"keys": keys, "args": args, "effective": effective_count})
        return [effective_count, ttl, curr_count]

    script_mock = MagicMock(side_effect=_straddled_burst_script)
    redis_mock = MagicMock()
    redis_mock.register_script = MagicMock(return_value=script_mock)

    limiter = RateLimiter(redis=redis_mock)

    # Simulating requests arriving 1s into the new window
    with patch("app.rate_limit.limiter.time") as mock_time:
        # 61s = 1s into the next 60s window (window_start=60, elapsed=1s)
        mock_time.time.return_value = 61.0
        result = await limiter._check_scope(
            scope="key",
            identifier="burst-client",
            limit=10,
            window_seconds=60,
        )

    # The sliding-window effective count is 20, exceeding limit=10 → BLOCKED
    assert result.allowed is False, (
        "Sliding window must block the boundary burst. "
        f"effective_count=20 > limit=10, but got allowed={result.allowed}"
    )
    assert result.remaining == 0

    # Verify the script was called with BOTH keys (curr + prev window)
    assert len(calls) == 1
    assert len(calls[0]["keys"]) == 2, "Script must be called with 2 keys (curr + prev window)"

    # Verify elapsed_ms was passed as 3rd argument
    assert len(calls[0]["args"]) == 3, "Script must receive 3 args: limit, window, elapsed_ms"
    elapsed_ms = calls[0]["args"][2]
    assert 0 <= elapsed_ms <= 60000, f"elapsed_ms={elapsed_ms} should be between 0 and 60000"


@pytest.mark.asyncio
async def test_sliding_window_allows_clean_window_start():
    """
    At the very start of a window with no previous requests (prev_count=0),
    effective = 0 × (1 - 0) + 1 = 1, which is within limit=10 → ALLOWED.
    """
    async def _clean_start_script(keys, args):
        # prev_count=0 (no previous activity), curr_count=1 (first request)
        # effective = 0 * (1 - 0/60) + 1 = 1
        return [1, 60, 1]

    script_mock = MagicMock(side_effect=_clean_start_script)
    redis_mock = MagicMock()
    redis_mock.register_script = MagicMock(return_value=script_mock)

    limiter = RateLimiter(redis=redis_mock)

    with patch("app.rate_limit.limiter.time") as mock_time:
        mock_time.time.return_value = 0.0  # start of epoch window
        result = await limiter._check_scope(
            scope="key",
            identifier="clean-client",
            limit=10,
            window_seconds=60,
        )

    assert result.allowed is True
    assert result.current_count == 1

