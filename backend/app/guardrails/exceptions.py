"""
Cortex Gateway — Guardrail Exceptions (Phase 9E).

GuardrailBlocked is raised when at least one enabled guardrail produces a
"block" action.  It carries enough metadata to build the error response and
the RequestLog entry without exposing any prompt content or matched values.
"""

from __future__ import annotations

from typing import List, Optional


class GuardrailBlocked(Exception):
    """
    Raised when one or more enabled guardrails block the request.

    Maps to HTTP 400 INVALID_REQUEST in app/exceptions.py.

    Attributes:
        guardrail:         Primary guardrail that caused the block
                           (first blocked one in execution order).
        guardrails_triggered: All guardrail names that triggered (warn or block).
        reason_code:       Bounded-vocabulary reason code for the primary block.
        message:           Human-readable message safe for external exposure.
    """

    status_code: int = 400
    code: str = "INVALID_REQUEST"

    def __init__(
        self,
        guardrail: str,
        guardrails_triggered: List[str],
        reason_code: Optional[str] = None,
        message: str = "Request blocked by guardrail.",
    ) -> None:
        self.guardrail = guardrail
        self.guardrails_triggered = guardrails_triggered
        self.reason_code = reason_code
        self.message = message
        super().__init__(message)
