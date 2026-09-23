"""
Cortex Gateway — Prompt-Injection Detection Guardrail (Phase 9E).

IMPORTANT — LIMITATIONS DISCLAIMER:
    This is a best-effort heuristic/pattern-based detector only.
    It is NOT a complete prompt-injection defense.
    It can miss sophisticated attacks and may flag benign text.
    It must NOT be treated as a security guarantee or a security boundary.
    It does not protect against all prompt-injection techniques.

Patterns detected:
    Common instruction-override phrases used in naive prompt-injection attacks:
      - "ignore previous instructions"
      - "ignore all previous"
      - "disregard previous instructions"
      - "disregard the system prompt"
      - "forget your previous instructions"
      - "forget your instructions"
      - "override the system instructions"
      - "override your instructions"
      - "do not follow the previous instructions"
      - "reveal the system prompt"
      - "reveal your instructions"
      - "repeat your system prompt"

    Matching is case-insensitive and tolerates minor whitespace variations.

Security:
    Only "INJECTION_PATTERN" reason_code is recorded, never the matched text.
"""

from __future__ import annotations

import re
from typing import Literal

from app.guardrails.base import GuardrailResult

# ---------------------------------------------------------------------------
# Compiled injection patterns — compiled once at module load
# ---------------------------------------------------------------------------

_INJECTION_PHRASES: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+the\s+system\s+prompt", re.IGNORECASE),
    re.compile(r"forget\s+(your\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"forget\s+your\s+instructions", re.IGNORECASE),
    re.compile(r"override\s+the\s+system\s+instructions", re.IGNORECASE),
    re.compile(r"override\s+your\s+instructions", re.IGNORECASE),
    re.compile(r"do\s+not\s+follow\s+(the\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"reveal\s+the\s+system\s+prompt", re.IGNORECASE),
    re.compile(r"reveal\s+your\s+instructions", re.IGNORECASE),
    re.compile(r"repeat\s+your\s+system\s+prompt", re.IGNORECASE),
    re.compile(r"ignore\s+your\s+previous\s+instructions", re.IGNORECASE),
]


class InjectionGuardrail:
    """
    Best-effort heuristic prompt-injection detector.

    Parameters:
        action: "off" | "warn" | "block"
                "off" — detector does NOT execute.
    """

    NAME = "injection"

    def __init__(self, action: Literal["off", "warn", "block"]) -> None:
        self._action = action

    def check(self, prompt: str) -> GuardrailResult | None:
        """
        Scan prompt for known injection phrases.

        Returns:
            GuardrailResult if a pattern matches; None if action is "off"
            or no patterns match.

        Security:
            Never includes the matched string in the returned result.
        """
        if self._action == "off":
            return None  # detector must not execute when off

        for pattern in _INJECTION_PHRASES:
            if pattern.search(prompt):
                return GuardrailResult(
                    triggered=True,
                    guardrail=self.NAME,
                    action=self._action,
                    reason_code="INJECTION_PATTERN",
                )

        return None  # no injection patterns found
