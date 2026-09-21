"""
Cortex Gateway — PII Detection Guardrail (Phase 9E).

IMPORTANT — LIMITATIONS DISCLAIMER:
    The PII detector uses pattern matching and heuristics only.
    It is NOT a comprehensive PII classifier.
    It may produce false positives (flagging benign text) and
    false negatives (missing real PII).
    It must NOT be treated as a security guarantee or a substitute
    for a proper data-loss prevention (DLP) system.

Patterns detected (best-effort):
    EMAIL_ADDRESS   — standard RFC-5321 email shapes
    PHONE_NUMBER    — common North American and international formats
    SSN             — US Social Security Number: NNN-NN-NNNN
    CREDIT_CARD     — 13–19 digit sequences with common separators

Security:
    - Only the reason_code (e.g. "EMAIL_ADDRESS") is recorded, never the
      matched string or surrounding context.
    - Patterns are compiled once at import time for efficiency.
"""

from __future__ import annotations

import re
from typing import List, Literal, Optional, Tuple

from app.guardrails.base import GuardrailResult

# ---------------------------------------------------------------------------
# Compiled patterns — compiled once at module load
# ---------------------------------------------------------------------------

_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    (
        "EMAIL_ADDRESS",
        re.compile(
            r"""
            (?<!\w)                 # not preceded by word char
            [A-Za-z0-9._%+\-]+     # local part
            @                      # @
            [A-Za-z0-9.\-]+        # domain labels
            \.                     # dot
            [A-Za-z]{2,}           # TLD
            (?!\w)                 # not followed by word char
            """,
            re.VERBOSE,
        ),
    ),
    (
        "PHONE_NUMBER",
        re.compile(
            r"""
            (?<!\d)                # not preceded by digit
            (?:
                \+?1[\s.\-]?       # optional +1 country code
            )?
            (?:\(\d{3}\)|\d{3})    # area code
            [\s.\-]?               # separator
            \d{3}                  # exchange
            [\s.\-]?               # separator
            \d{4}                  # subscriber
            (?!\d)                 # not followed by digit
            """,
            re.VERBOSE,
        ),
    ),
    (
        "SSN",
        re.compile(
            r"""
            (?<!\d)
            \b\d{3}-\d{2}-\d{4}\b
            (?!\d)
            """,
            re.VERBOSE,
        ),
    ),
    (
        "CREDIT_CARD",
        re.compile(
            r"""
            (?<!\d)
            \d{4}                  # first group
            [\s\-]?
            \d{4}                  # second group
            [\s\-]?
            \d{4}                  # third group
            [\s\-]?
            \d{1,7}                # final group (1–7 more digits → 13–19 total)
            (?!\d)
            """,
            re.VERBOSE,
        ),
    ),
]


class PiiGuardrail:
    """
    Best-effort heuristic PII detector.

    Parameters:
        action: "off" | "warn" | "block"
                "off" — detector does NOT execute (not merely ignored).
    """

    NAME = "pii"

    def __init__(self, action: Literal["off", "warn", "block"]) -> None:
        self._action = action

    def check(self, prompt: str) -> Optional[GuardrailResult]:
        """
        Scan prompt for PII patterns.

        Returns:
            GuardrailResult if a pattern matches; None if action is "off"
            or no patterns match.

        Security:
            Never includes the matched string in the returned result.
        """
        if self._action == "off":
            return None  # detector must not execute when off

        for reason_code, pattern in _PATTERNS:
            if pattern.search(prompt):
                # Return immediately on first match — reason_code identifies
                # the pattern type, never the matched value itself.
                return GuardrailResult(
                    triggered=True,
                    guardrail=self.NAME,
                    action=self._action,
                    reason_code=reason_code,
                )

        return None  # no PII patterns found
