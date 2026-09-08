"""
Cortex Gateway — Provider Exception Hierarchy (Phase 2).

All provider-specific errors are translated into these typed exceptions
inside the provider adapters. The global exception handler in
app/exceptions.py maps them to consistent HTTP responses with the
standard Cortex error envelope.

Error codes map to HTTP status codes:
    INVALID_PROVIDER             → 404
    PROVIDER_DISABLED            → 503
    INVALID_MODEL                → 400
    PROVIDER_TIMEOUT             → 504
    PROVIDER_RATE_LIMITED        → 429
    PROVIDER_UNAVAILABLE         → 503
    PROVIDER_AUTHENTICATION_FAILED → 502 (never expose key details)
    PROVIDER_ERROR               → 502
"""

from __future__ import annotations

from typing import Optional


class ProviderException(Exception):
    """
    Base class for all provider-related exceptions.

    Attributes:
        code:    Machine-readable error code (included in response).
        message: Human-readable error message (included in response).
        status_code: HTTP status code to return.
    """

    code: str = "PROVIDER_ERROR"
    status_code: int = 502

    def __init__(self, message: str, *, details: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details  # internal only — never returned to clients


class InvalidProviderError(ProviderException):
    """Raised when the requested provider is not registered."""

    code = "INVALID_PROVIDER"
    status_code = 404


class ProviderDisabledError(ProviderException):
    """Raised when the provider is registered but explicitly disabled."""

    code = "PROVIDER_DISABLED"
    status_code = 503


class InvalidModelError(ProviderException):
    """Raised when the model is not recognized by the provider."""

    code = "INVALID_MODEL"
    status_code = 400


class ProviderTimeoutError(ProviderException):
    """Raised when the provider request exceeds the configured timeout."""

    code = "PROVIDER_TIMEOUT"
    status_code = 504


class ProviderRateLimitError(ProviderException):
    """Raised when the provider returns a rate limit response."""

    code = "PROVIDER_RATE_LIMITED"
    status_code = 429


class ProviderUnavailableError(ProviderException):
    """Raised when the provider service is temporarily unavailable."""

    code = "PROVIDER_UNAVAILABLE"
    status_code = 503


class ProviderAuthError(ProviderException):
    """
    Raised when provider authentication fails (invalid/missing API key).

    The response message MUST NOT reveal key details.
    """

    code = "PROVIDER_AUTHENTICATION_FAILED"
    status_code = 502


class ProviderError(ProviderException):
    """Generic provider error for unclassified upstream failures."""

    code = "PROVIDER_ERROR"
    status_code = 502
