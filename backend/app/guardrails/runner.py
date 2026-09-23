"""
Cortex Gateway — Guardrail Runner (Phase 9E).

Orchestrates all enabled guardrails for a single request.

Pipeline:
    1. prompt_size  (always first; BLOCK only)
    2. pii          (off / warn / block)
    3. injection    (off / warn / block)

Rules:
    - "off" means the detector does NOT execute at all.
    - All enabled guardrails run regardless of earlier warn results.
    - Execution stops early ONLY after prompt_size triggers (always a block
      and the prompt is inherently too large to meaningfully check further).
    - Final action: "block" if any result is block; "warn" if any warn and
      no block; None if all clean.
    - Results are deterministic for the same inputs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.guardrails.base import GuardrailRunResult
from app.guardrails.injection import InjectionGuardrail
from app.guardrails.pii import PiiGuardrail
from app.guardrails.prompt_size import PromptSizeGuardrail

if TYPE_CHECKING:
    from app.policy.schemas import GuardrailsPolicy
    from app.schemas.chat import ChatCompletionRequest


class GuardrailRunner:
    """
    Stateless orchestrator that evaluates all guardrails and aggregates results.
    """

    @staticmethod
    def build_prompt(request: ChatCompletionRequest) -> str:
        """
        Combine all message contents into a single string for pattern matching.

        The join is space-delimited to preserve word boundaries.
        Neither the original message objects nor the combined string is stored.
        """
        return " ".join(m.content for m in request.messages)

    @classmethod
    def run(
        cls,
        request: ChatCompletionRequest,
        policy: GuardrailsPolicy,
    ) -> GuardrailRunResult:
        """
        Execute all enabled guardrails in order and aggregate results.

        Args:
            request: The incoming chat completion request (messages read-only).
            policy:  Resolved guardrails configuration for the requesting team.

        Returns:
            GuardrailRunResult summarising all triggered guardrails.
            Never raises — all internal errors are silently absorbed and
            treated as no-trigger so a guardrail failure is never fatal.
        """
        run_result = GuardrailRunResult()

        try:
            prompt = cls.build_prompt(request)

            # ── 1. Prompt size ────────────────────────────────────────────
            size_guard = PromptSizeGuardrail(max_chars=policy.max_prompt_length)
            size_result = size_guard.check(prompt)
            if size_result is not None and size_result.triggered:
                run_result.triggered_names.append(size_result.guardrail)
                run_result.results.append(size_result)
                # Prompt is too large — skip remaining checks (block is certain
                # and further scanning a huge string wastes CPU).
                run_result.final_action = "block"
                return run_result

            # ── 2. PII ────────────────────────────────────────────────────
            pii_guard = PiiGuardrail(action=policy.pii_detection)  # type: ignore[arg-type]
            pii_result = pii_guard.check(prompt)
            if pii_result is not None and pii_result.triggered:
                run_result.triggered_names.append(pii_result.guardrail)
                run_result.results.append(pii_result)

            # ── 3. Injection ──────────────────────────────────────────────
            inj_guard = InjectionGuardrail(action=policy.injection_detection)  # type: ignore[arg-type]
            inj_result = inj_guard.check(prompt)
            if inj_result is not None and inj_result.triggered:
                run_result.triggered_names.append(inj_result.guardrail)
                run_result.results.append(inj_result)

            # ── Aggregate final action ────────────────────────────────────
            if any(r.action == "block" for r in run_result.results):
                run_result.final_action = "block"
            elif run_result.results:
                run_result.final_action = "warn"
            # else: final_action remains None (clean)

        except Exception:
            # Guardrail failure must never be fatal to the request.
            # Fail-open: treat as no guardrail trigger.
            pass

        return run_result
