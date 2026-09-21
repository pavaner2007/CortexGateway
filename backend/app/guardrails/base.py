"""
Cortex Gateway — Guardrail Base Types (Phase 9E).

Defines the shared interface and result types used by all guardrail
implementations. Adding a new guardrail only requires:
  1. Implementing the Guardrail Protocol.
  2. Registering it in GuardrailRunner.

Security note:
  GuardrailResult MUST NOT include the matched value, the original prompt,
  any PII content, or any secret material.  reason_code is a bounded
  vocabulary string (e.g. "EMAIL_ADDRESS") — never a raw substring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class GuardrailResult:
    """
    Result of a single guardrail check.

    Attributes:
        triggered:   True when the guardrail fired.
        guardrail:   Stable identifier: "prompt_size" | "pii" | "injection".
        action:      "warn" | "block" — the configured action for this guardrail.
        reason_code: Bounded-vocabulary string describing WHY it triggered.
                     Examples: "MAX_LENGTH_EXCEEDED", "EMAIL_ADDRESS",
                     "INJECTION_PATTERN".  Never contains the matched value.
    """

    triggered: bool
    guardrail: str
    action: str
    reason_code: Optional[str] = None


@dataclass
class GuardrailRunResult:
    """
    Aggregated result after running all enabled guardrails.

    Attributes:
        triggered_names: List of guardrail identifiers that fired, in
                         execution order. Empty list = nothing triggered.
        final_action:    "block" if any guardrail blocked; "warn" if any
                         warned (and none blocked); None if all clean.
        results:         Individual per-guardrail results that triggered.
    """

    triggered_names: List[str] = field(default_factory=list)
    final_action: Optional[str] = None
    results: List[GuardrailResult] = field(default_factory=list)

    @property
    def any_triggered(self) -> bool:
        return bool(self.triggered_names)

    @property
    def is_blocked(self) -> bool:
        return self.final_action == "block"

    @property
    def is_warned(self) -> bool:
        return self.final_action == "warn"
