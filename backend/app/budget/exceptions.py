"""
Cortex Gateway — Budget & Rate Limit Exceptions (Phase 6).

Hierarchy:
    RateLimitExceeded   → HTTP 429 Too Many Requests
    BudgetExceeded      → HTTP 402 Payment Required

Both inherit from a common GatewayControlException so handlers can
be registered in a single place in app/exceptions.py.
"""

from __future__ import annotations

from typing import Optional


class GatewayControlException(Exception):
    """Base class for Phase 6 request control exceptions."""

    status_code: int = 400
    code: str = "CONTROL_ERROR"

    def __init__(self, message: str = "") -> None:
        self.message = message or self.__class__.__doc__ or "Request rejected."
        super().__init__(self.message)


class RateLimitExceeded(GatewayControlException):
    """Rate limit exceeded. Retry after the window resets."""

    status_code: int = 429
    code: str = "RATE_LIMIT_EXCEEDED"

    def __init__(
        self,
        message: str = "Rate limit exceeded. Please retry after the window resets.",
        retry_after_seconds: int = 60,
        scope: str = "unknown",
    ) -> None:
        self.retry_after_seconds = retry_after_seconds
        self.scope = scope
        super().__init__(message)


class BudgetExceeded(GatewayControlException):
    """
    Team budget exhausted.

    HTTP 402 Payment Required — semantically correct when funds are exhausted.
    Distinct from 429 (rate limit), which is time-based.
    """

    status_code: int = 402
    code: str = "BUDGET_EXCEEDED"

    def __init__(
        self,
        message: str = "Team budget exhausted. Contact your administrator to increase the budget.",
        team_id: Optional[str] = None,
        remaining: float = 0.0,
    ) -> None:
        self.team_id = team_id
        self.remaining = remaining
        super().__init__(message)


class BudgetConfigurationError(GatewayControlException):
    """Budget is misconfigured or data is inconsistent."""

    status_code: int = 500
    code: str = "BUDGET_CONFIGURATION_ERROR"
