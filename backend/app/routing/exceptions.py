"""
Cortex Gateway — Routing Exceptions (Phase 3).

Typed exceptions for routing errors inheriting from ProviderException
so they integrate seamlessly with global exception handlers.
"""

from __future__ import annotations

from typing import Optional
from app.providers.exceptions import ProviderException


class RoutingException(ProviderException):
    """Base class for all routing-related exceptions."""
    status_code: int = 400
    code: str = "ROUTING_ERROR"


class NoRoutableProviderError(RoutingException):
    """Raised when no registered/enabled providers are available for routing."""
    status_code: int = 503
    code: str = "NO_ROUTABLE_PROVIDER"

    def __init__(
        self,
        message: str = "No healthy, enabled providers are available to route this request.",
        details: Optional[str] = None,
    ) -> None:
        super().__init__(message, details=details)


class NoCapableProviderError(RoutingException):
    """Raised when no provider/model satisfies the requested capabilities."""
    status_code: int = 400
    code: str = "NO_CAPABLE_PROVIDER"

    def __init__(
        self,
        message: str = "No available provider supports the required capabilities.",
        details: Optional[str] = None,
    ) -> None:
        super().__init__(message, details=details)


class InvalidRoutingModeError(RoutingException):
    """Raised when an invalid routing mode is specified."""
    status_code: int = 400
    code: str = "INVALID_ROUTING_MODE"

    def __init__(
        self,
        message: str = "Invalid routing mode specified.",
        details: Optional[str] = None,
    ) -> None:
        super().__init__(message, details=details)


class InvalidManualRoutingError(RoutingException):
    """Raised when manual routing is selected without specifying both provider and a concrete model."""
    status_code: int = 400
    code: str = "INVALID_MANUAL_ROUTING"

    def __init__(
        self,
        message: str = "Manual routing mode requires both a valid provider and a concrete model name.",
        details: Optional[str] = None,
    ) -> None:
        super().__init__(message, details=details)
