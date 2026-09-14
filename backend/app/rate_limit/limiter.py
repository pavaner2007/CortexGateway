"""
Cortex Gateway — Redis Rate Limiter (Phase 6).

Implements a fixed-window counter rate limiter using an atomic Lua script.

Atomicity guarantee:
    A single Lua script is executed on the Redis server in one round-trip.
    The INCR and EXPIREAT operations are serialized by Redis, eliminating
    the read-then-write race condition of naive GET → Python increment → SET.

Redis key format:
    ratelimit:<scope>:<identifier>:<window_start>

    scope       : 'key' | 'team' | 'org'
    identifier  : api_key_id | team_id | organization_id
    window_start: Unix timestamp of the start of the current window

Window start calculation:
    window_start = floor(now / window_seconds) * window_seconds

This means all windows are aligned to epoch multiples of window_seconds,
making window resets predictable and deterministic across multiple workers.
"""

from __future__ import annotations

import math
import time
from typing import Optional

from redis.asyncio import Redis

from app.core.logging import logger
from app.rate_limit.models import RateLimitOutcome, RateLimitResult

# Lua script: atomically increment counter, set expiry on first increment,
# and return (count, ttl).
# KEYS[1]: Redis key
# ARGV[1]: limit (int)
# ARGV[2]: window_seconds (int)
_LUA_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local count = redis.call('INCR', key)
if count == 1 then
    redis.call('EXPIRE', key, window)
end
local ttl = redis.call('TTL', key)
return {count, ttl}
"""


class RateLimiter:
    """
    Redis-backed fixed-window rate limiter.

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

        now = int(time.time())
        window_start = (now // window_seconds) * window_seconds
        redis_key = f"ratelimit:{scope}:{identifier}:{window_start}"

        try:
            script = await self._get_script()
            result = await script(keys=[redis_key], args=[limit, window_seconds])
            count = int(result[0])
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
