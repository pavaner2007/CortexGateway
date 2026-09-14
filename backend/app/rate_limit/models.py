"""
Cortex Gateway — Rate Limit Models (Phase 6).

Data structures for rate limit check results.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RateLimitResult:
    """
    Result of a rate-limit check for a single scope (key / team / org).

    Attributes:
        allowed:             True if the request is within the limit.
        scope:               Which scope was checked ('key', 'team', 'org').
        limit:               Configured maximum requests per window.
        current_count:       Current count after this request was counted.
        remaining:           Remaining requests in the current window (0 when blocked).
        retry_after_seconds: Seconds until the window resets (for Retry-After header).
    """

    allowed: bool
    scope: str        # 'key' | 'team' | 'org'
    limit: int
    current_count: int
    remaining: int
    retry_after_seconds: int


@dataclass
class RateLimitOutcome:
    """
    Combined outcome from checking all three rate-limit scopes.

    A request passes only if all three scopes allow it.
    `binding_result` is the tightest (most restrictive) result.
    """

    allowed: bool
    binding_result: RateLimitResult        # The scope that determined the outcome
    key_result: RateLimitResult
    team_result: RateLimitResult
    org_result: RateLimitResult
