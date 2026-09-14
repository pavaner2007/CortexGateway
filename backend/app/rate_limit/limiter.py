"""
Cortex Gateway — Redis Rate Limiter (Phase 6 / Gap 3 fix).

Implements a **sliding-window counter** rate limiter using an atomic Lua script.

Algorithm (sliding window counter):
    Two adjacent fixed-window counters are kept in Redis (current + previous).
    The effective request count is a weighted sum:

        effective = prev_count × (1 - elapsed_fraction) + curr_count

    where elapsed_fraction = (now - current_window_start) / window_seconds.

    This smooths the boundary burst: even if a client fires N requests at the
    tail of the previous window, they count proportionally in the next window.
    Unlike a pure fixed-window counter, the maximum burst is limited to
    ≈ limit × (1 + fraction_of_previous_window_remaining), which approaches
    `limit` as the window rolls over — not 2× limit.

Atomicity guarantee:
    A single Lua script is executed on the Redis server in one round-trip.
    Both the INCR and the two GET operations are serialized by Redis,
    eliminating all read-then-write race conditions.

Redis key format:
    ratelimit:<scope>:<identifier>:<window_start>

    scope       : 'key' | 'team' | 'org'
    identifier  : api_key_id | team_id | organization_id
    window_start: Unix timestamp of the start of the current fixed window

    The *previous* window key uses window_start - window_seconds.
"""

from __future__ import annotations

import math
import time
from typing import Optional

from redis.asyncio import Redis

from app.core.logging import logger
from app.rate_limit.models import RateLimitOutcome, RateLimitResult

# Sliding-window counter Lua script.
# Atomically:
#   1. INCR the current-window counter.
#   2. Set expiry on first hit to 2× window (keeps prev window data alive).
#   3. GET the previous-window counter.
#   4. Compute the weighted effective count.
#   5. Return (effective_count_int, ttl, current_count).
#
# KEYS[1]: current window key  (ratelimit:<scope>:<id>:<curr_window_start>)
# KEYS[2]: previous window key (ratelimit:<scope>:<id>:<curr_window_start - window>)
# ARGV[1]: limit            (int)
# ARGV[2]: window_seconds   (int)
# ARGV[3]: elapsed_ms       (int, milliseconds elapsed since current window started)
#
# Returns: {effective_count (int, ceiling), ttl_seconds, current_count}
_LUA_SCRIPT = """
local curr_key  = KEYS[1]
local prev_key  = KEYS[2]
local limit     = tonumber(ARGV[1])
local window    = tonumber(ARGV[2])
local elapsed   = tonumber(ARGV[3]) / 1000.0   -- convert ms → seconds

-- Increment current window
local curr_count = redis.call('INCR', curr_key)
if curr_count == 1 then
    -- Keep key alive for 2 windows so prev window data survives into next window
    redis.call('EXPIRE', curr_key, window * 2)
end

-- Read previous window count (0 if expired / doesn't exist)
local prev_count = tonumber(redis.call('GET', prev_key) or '0')

-- Sliding-window effective count
-- Weight previous window by fraction of window NOT yet elapsed
local fraction = elapsed / window           -- 0.0 at window start, 1.0 at end
local effective = prev_count * (1.0 - fraction) + curr_count

-- Ceiling to integer for comparison
local effective_int = math.ceil(effective)

local ttl = redis.call('TTL', curr_key)
if ttl < 0 then ttl = window end

return {effective_int, ttl, curr_count}
"""



class RateLimiter:
    """
    Redis-backed **sliding-window counter** rate limiter.

    Uses two adjacent fixed-window counters weighted by elapsed time fraction
    to prevent the 2× burst-at-boundary issue of plain fixed-window counters.

    Usage:
        limiter = RateLimiter(redis=redis_client)
        outcome = await limiter.check_all(
            api_key_id=..., team_id=..., org_id=...,
            key_limit=100, key_window=60,
            team_limit=500, team_window=60,
            org_limit=2000, org_window=60,
        )
        if not outcome.allowed:
            raise RateLimitExceeded(retry_after=outcome.binding_result.retry_after_seconds)
    """

    def __init__(self, redis: Optional[Redis]) -> None:
        self._redis = redis
        # Pre-register the Lua script for efficiency (cached by Redis)
        self._script = None

    async def _get_script(self) -> object:
        """Lazily register the Lua script with Redis."""
        if self._script is None and self._redis is not None:
            self._script = self._redis.register_script(_LUA_SCRIPT)
        return self._script

    async def _check_scope(
        self,
        scope: str,
        identifier: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """
        Atomically increment and check a single rate-limit scope.

        If Redis is unavailable (client is None), returns an always-allowed
        result so the application does not fail closed when Redis is down.

        This is an intentional fail-open design: missing Redis should not
        block all traffic. Operators should monitor Redis health separately.
        """
        if self._redis is None:
            # Fail-open: Redis unavailable → allow all requests
            logger.warning(
                "Rate limiter: Redis unavailable — failing open",
                scope=scope,
                identifier=identifier,
            )
            return RateLimitResult(
                allowed=True,
                scope=scope,
                limit=limit,
                current_count=0,
                remaining=limit,
                retry_after_seconds=0,
            )

        now_float = time.time()
        now = int(now_float)
        window_start = (now // window_seconds) * window_seconds
        prev_window_start = window_start - window_seconds
        curr_key = f"ratelimit:{scope}:{identifier}:{window_start}"
        prev_key = f"ratelimit:{scope}:{identifier}:{prev_window_start}"
        # Milliseconds elapsed since current window started (for weighted calculation)
        elapsed_ms = int((now_float - window_start) * 1000)

        try:
            script = await self._get_script()
            result = await script(
                keys=[curr_key, prev_key],
                args=[limit, window_seconds, elapsed_ms],
            )
            count = int(result[0])   # effective sliding-window count (ceiling)
            ttl = int(result[1]) if result[1] > 0 else window_seconds
        except Exception as exc:
            # Fail-open: Redis error → allow request, log the error
            logger.error(
                "Rate limiter: Redis error — failing open",
                scope=scope,
                identifier=identifier,
                error=str(exc),
            )
            return RateLimitResult(
                allowed=True,
                scope=scope,
                limit=limit,
                current_count=0,
                remaining=limit,
                retry_after_seconds=0,
            )

        allowed = count <= limit
        remaining = max(0, limit - count)

        logger.debug(
            "Rate limit check",
            scope=scope,
            identifier=identifier,
            count=count,
            limit=limit,
            allowed=allowed,
            ttl=ttl,
        )

        return RateLimitResult(
            allowed=allowed,
            scope=scope,
            limit=limit,
            current_count=count,
            remaining=remaining,
            retry_after_seconds=ttl if not allowed else 0,
        )

    async def check_all(
        self,
        *,
        api_key_id: str,
        team_id: str,
        org_id: str,
        key_limit: int,
        key_window: int,
        team_limit: int,
        team_window: int,
        org_limit: int,
        org_window: int,
    ) -> RateLimitOutcome:
        """
        Check rate limits for all three scopes: API key, team, organization.

        All three counters are incremented atomically.
        A request is rejected if ANY scope exceeds its limit.
        The tightest (most restrictive) result is returned as `binding_result`.

        Note: All three counters are always incremented even when one fails.
        This is correct behavior — the client used a request slot even if rejected.
        """
        # Check all scopes (always increment all counters)
        key_result = await self._check_scope("key", api_key_id, key_limit, key_window)
        team_result = await self._check_scope("team", team_id, team_limit, team_window)
        org_result = await self._check_scope("org", org_id, org_limit, org_window)

        # Determine overall outcome — reject if any scope fails
        all_results = [key_result, team_result, org_result]
        blocked = [r for r in all_results if not r.allowed]

        if blocked:
            # Most restrictive = highest retry_after (longest wait)
            binding = max(blocked, key=lambda r: r.retry_after_seconds)
            return RateLimitOutcome(
                allowed=False,
                binding_result=binding,
                key_result=key_result,
                team_result=team_result,
                org_result=org_result,
            )

        # All passed — binding result is tightest remaining count
        binding = min(all_results, key=lambda r: r.remaining)
        return RateLimitOutcome(
            allowed=True,
            binding_result=binding,
            key_result=key_result,
            team_result=team_result,
            org_result=org_result,
        )
