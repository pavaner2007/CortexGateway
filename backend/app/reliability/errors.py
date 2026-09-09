"""
Cortex Gateway — Reliability Errors & Classification (Phase 4).

Provides transient failure detection, circuit breaker failure classification,
and typed reliability exceptions that inherit from the Phase 2 ProviderException hierarchy.
"""

from __future__ import annotations

import httpx

from app.providers.exceptions import (
    InvalidModelError,
    InvalidProviderError,
    ProviderAuthError,
    ProviderDisabledError,
    ProviderException,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


class TotalDeadlineExceededError(ProviderTimeoutError):
    """Raised when the total end-to-end request timeout deadline is exceeded."""

    code = "PROVIDER_TIMEOUT"
    status_code = 504

    def __init__(self, message: str = "Total request deadline exceeded across provider attempts.", **kwargs) -> None:
        super().__init__(message, **kwargs)


class CircuitOpenError(ProviderUnavailableError):
    """Raised when a provider's circuit breaker is in OPEN state and fast-fails."""

    code = "PROVIDER_UNAVAILABLE"
    status_code = 503

    def __init__(self, provider: str, **kwargs) -> None:
        message = f"Provider '{provider}' circuit breaker is OPEN. Requests are temporarily blocked."
        super().__init__(message, **kwargs)
        self.provider = provider


class FailoverExhaustedError(ProviderUnavailableError):
    """Raised when all failover candidates have been exhausted."""

    code = "PROVIDER_UNAVAILABLE"
    status_code = 503

    def __init__(self, message: str = "All failover candidates failed or were unavailable.", **kwargs) -> None:
        super().__init__(message, **kwargs)


def is_transient_error(exc: Exception) -> bool:
    """
    Determine if an exception represents a transient failure that should be retried.

    Retryable:
      - ProviderTimeoutError (HTTP 504, connection timeouts)
      - ProviderUnavailableError (HTTP 503, connection drops)
      - ProviderRateLimitError (HTTP 429)
      - Generic 5xx ProviderError / HTTP 500, 502, 503, 504
      - Network/connect errors (httpx.TimeoutException, httpx.NetworkError, ConnectionError)

    Non-Retryable:
      - InvalidModelError (HTTP 400)
      - InvalidProviderError (HTTP 404)
      - ProviderDisabledError (HTTP 503 explicit config)
      - ProviderAuthError (HTTP 502 invalid/missing API key)
      - ValueError / TypeError / Pydantic validation errors
    """
    # Non-retryable permanent exceptions
    if isinstance(exc, (InvalidModelError, InvalidProviderError, ProviderDisabledError, ProviderAuthError)):
        return False

    if isinstance(exc, (ValueError, TypeError)):
        return False

    # Retryable provider exceptions
    if isinstance(exc, (ProviderTimeoutError, ProviderUnavailableError, ProviderRateLimitError)):
        return True

    # Retryable low-level HTTP/network exceptions
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, ConnectionError, TimeoutError)):
        return True

    # Check status_code if ProviderException
    if isinstance(exc, ProviderException):
        return exc.status_code in {429, 500, 502, 503, 504}

    return False


def is_circuit_breaker_failure(exc: Exception) -> bool:
    """
    Determine if an exception represents a provider instability failure
    that counts toward tripping the circuit breaker.

    Counts toward circuit:
      - Timeouts
      - Connection refused / network failure
      - HTTP 5xx server errors
      - Provider unavailable

    Does NOT count toward circuit:
      - 4xx client errors (bad request, invalid model, bad params)
      - Auth / API key errors
      - Validation errors
    """
    if isinstance(exc, (InvalidModelError, InvalidProviderError, ProviderDisabledError, ProviderAuthError)):
        return False

    if isinstance(exc, (ValueError, TypeError)):
        return False

    if isinstance(exc, (ProviderTimeoutError, ProviderUnavailableError)):
        return True

    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, ConnectionError, TimeoutError)):
        return True

    if isinstance(exc, ProviderException):
        # 5xx status codes indicate server instability
        return exc.status_code in {500, 502, 503, 504}

    return False
