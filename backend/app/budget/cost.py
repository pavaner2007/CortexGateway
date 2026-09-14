"""
Cortex Gateway — Cost Calculator (Phase 6).

Calculates estimated and actual costs for chat completion requests.

Design:
    - Estimated cost is calculated BEFORE provider execution (for budget pre-check).
    - Actual cost is calculated AFTER using normalized provider usage.
    - If usage is unavailable (provider didn't return tokens), actual cost
      falls back to estimated cost to avoid silently zeroing out charges.
    - Ollama is zero-cost by default; configurable via settings.

Pricing is sourced from the Phase 3 ModelMetadata catalog (input/output split).
"""

from __future__ import annotations

from typing import Optional

from app.routing.metadata import ModelMetadataCatalog
from app.routing.models import ModelMetadata
from app.schemas.chat import ChatCompletionRequest, UsageMetadata

# Default token estimate when max_tokens is not specified.
# Conservative: assume a short 500-token response.
_DEFAULT_ESTIMATE_OUTPUT_TOKENS: int = 500
# Safety margin multiplier applied to estimated cost to avoid under-reservation.
_ESTIMATION_SAFETY_MARGIN: float = 1.5


class CostCalculator:
    """
    Calculates estimated and actual request costs using catalog pricing.

    Thread-safe: all methods are pure functions over immutable catalog data.
    """

    def __init__(self, catalog: ModelMetadataCatalog) -> None:
        self._catalog = catalog

    def get_metadata(self, provider: str, model: str) -> ModelMetadata:
        """Retrieve model metadata for cost lookup."""
        return self._catalog.get(provider, model)

    def estimate_cost(
        self,
        provider: str,
        model: str,
        request: ChatCompletionRequest,
    ) -> float:
        """
        Estimate the cost of a request before provider execution.

        Strategy:
            1. Estimate input tokens = sum of message character lengths / 4
               (rough approximation; 1 token ≈ 4 English characters)
            2. Estimate output tokens = request.max_tokens or DEFAULT_ESTIMATE_OUTPUT_TOKENS
            3. Apply safety margin to account for underestimation.

        Returns:
            Estimated cost in USD. Returns 0.0 for Ollama when cost is 0.
        """
        meta = self.get_metadata(provider, model)

        # Estimate input tokens from message content length
        total_chars = sum(len(m.content) for m in request.messages)
        estimated_input_tokens = max(1, total_chars // 4)

        # Use explicit max_tokens if provided, otherwise use default estimate
        estimated_output_tokens = request.max_tokens or _DEFAULT_ESTIMATE_OUTPUT_TOKENS

        input_cost = (estimated_input_tokens / 1000.0) * meta.input_cost_per_1k
        output_cost = (estimated_output_tokens / 1000.0) * meta.output_cost_per_1k

        raw_estimate = input_cost + output_cost
        # Apply safety margin (1.5× by default)
        return round(raw_estimate * _ESTIMATION_SAFETY_MARGIN, 8)

    def calculate_actual_cost(
        self,
        provider: str,
        model: str,
        usage: Optional[UsageMetadata],
        estimated_cost: float,
    ) -> float:
        """
        Calculate the actual cost from provider-returned token usage.

        If usage is None or token counts are unavailable, returns the
        estimated cost to avoid silently losing budget tracking data.

        Args:
            provider:       Provider name (e.g. 'groq', 'gemini', 'ollama').
            model:          Model identifier.
            usage:          Normalized token usage from the provider response.
            estimated_cost: Fallback if actual usage is unavailable.

        Returns:
            Actual cost in USD.
        """
        if usage is None:
            return estimated_cost

        meta = self.get_metadata(provider, model)

        prompt_tokens = usage.prompt_tokens or 0
        completion_tokens = usage.completion_tokens or 0

        if prompt_tokens == 0 and completion_tokens == 0:
            # Provider didn't return token counts — use estimate
            return estimated_cost

        input_cost = (prompt_tokens / 1000.0) * meta.input_cost_per_1k
        output_cost = (completion_tokens / 1000.0) * meta.output_cost_per_1k

        return round(input_cost + output_cost, 8)

    def would_exceed_budget(
        self,
        estimated_cost: float,
        current_usage: float,
        limit_amount: float,
        reserved: float = 0.0,
    ) -> bool:
        """
        Return True if adding estimated_cost would exceed the budget limit.

        Takes into account already-reserved amounts from concurrent requests.
        """
        effective_used = current_usage + reserved
        return (effective_used + estimated_cost) > limit_amount
