"""
Cortex Gateway — Prompt-Size Guardrail (Phase 9E).

Validates that the combined prompt does not exceed the configured maximum
character count.

Measurement:
    len(prompt) where prompt is the space-joined content of all messages.
    This is a Unicode character count, NOT a token count.
    Token-based limits can be added as future work if a lightweight tokenizer
    becomes available in the project.

Action:
    Prompt size is always a hard BLOCK — there is no "warn" option.
    If max_prompt_length is None the check is fully disabled.
"""

from __future__ import annotations

from app.guardrails.base import GuardrailResult


class PromptSizeGuardrail:
    """
    Hard-limit guardrail on combined prompt length.

    Parameters:
        max_chars: Maximum allowed Unicode character count.  Must be > 0.
                   None disables the guardrail entirely.
    """

    NAME = "prompt_size"

    def __init__(self, max_chars: int | None) -> None:
        self._max_chars = max_chars

    def check(self, prompt: str) -> GuardrailResult | None:
        """
        Check prompt length against the configured maximum.

        Returns:
            GuardrailResult(triggered=True, action="block") if the prompt
            exceeds the limit; None if disabled or within bounds.
        """
        if self._max_chars is None:
            return None  # guardrail disabled — do not execute

        length = len(prompt)
        if length > self._max_chars:
            return GuardrailResult(
                triggered=True,
                guardrail=self.NAME,
                action="block",
                reason_code="MAX_LENGTH_EXCEEDED",
            )
        return None  # within bounds — no trigger
