"""
Cortex Gateway — Auth-Specific Exceptions (Phase 5).

Authentication and Authorization errors map to HTTP 401/403.
These are registered in app/exceptions.py alongside the existing
ProviderException handlers.

Error conventions:
  AuthenticationError  → HTTP 401  (who are you? / key invalid)
  AuthorizationError   → HTTP 403  (I know who you are, but you can't do this)
"""

from __future__ import annotations


class AuthenticationError(Exception):
    """
    Raised when an API key is missing, malformed, expired, or revoked.

    The message returned to clients is intentionally generic to avoid
    leaking information about key existence or failure reason.
    """

    code = "AUTHENTICATION_FAILED"
    status_code = 401

    def __init__(
        self,
        message: str = "Authentication required. Provide a valid API key.",
    ) -> None:
        super().__init__(message)
        self.message = message


class AuthorizationError(Exception):
    """
    Raised when an authenticated key lacks permission for the requested operation.

    Authentication succeeded but the role does not permit the action.
    """

    code = "FORBIDDEN"
    status_code = 403

    def __init__(
        self,
        message: str = "You do not have permission to perform this action.",
    ) -> None:
        super().__init__(message)
        self.message = message
