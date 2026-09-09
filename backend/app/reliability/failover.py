"""
Cortex Gateway — Failover Selector (Phase 4).

Selects the next-best fallback candidate using Phase 3 CandidateBuilder and Scorer
while strictly excluding previously attempted providers and providers with OPEN circuits.
"""

from __future__ import annotations

from typing import Optional, Set

from app.core.logging import logger
from app.reliability.circuit_breaker import CircuitBreakerRegistry
from app.routing.models import RoutingCandidate
from app.routing.router import RoutingEngine
from app.schemas.chat import ChatCompletionRequest


class FailoverSelector:
    """
    Orchestrates fallback candidate discovery and scoring using Phase 3 routing logic.
    """

    def __init__(
        self,
        routing_engine: RoutingEngine,
        circuit_registry: CircuitBreakerRegistry,
        max_failover_attempts: int = 2,
    ) -> None:
        self._routing_engine = routing_engine
        self._circuit_registry = circuit_registry
        self.max_failover_attempts = max_failover_attempts

    async def select_fallback(
        self,
        request: ChatCompletionRequest,
        attempted_providers: Set[str],
    ) -> Optional[RoutingCandidate]:
        """
        Discover and score eligible fallback candidates.

        Args:
            request: The current chat completion request.
            attempted_providers: Set of provider names already tried for this request.

        Returns:
            The highest scoring eligible RoutingCandidate, or None if no candidate remains.
        """
        # 1. Discover all registered candidates
        candidates = await self._routing_engine._candidate_builder.build_candidates()
        if not candidates:
            return None

        # 2. Exclude previously attempted providers (prevents failover loops)
        attempted_lower = {p.lower() for p in attempted_providers}
        eligible = [c for c in candidates if c.provider.lower() not in attempted_lower]
        if not eligible:
            logger.info(
                "No fallback candidates remaining after excluding attempted providers",
                attempted=list(attempted_providers),
            )
            return None

        # 3. Exclude providers with OPEN circuits
        available = [c for c in eligible if self._circuit_registry.can_execute(c.provider)]
        if not available:
            logger.info(
                "All remaining fallback providers currently have OPEN circuits",
                eligible_providers=[c.provider for c in eligible],
            )
            return None

        # 4. Filter by required capabilities (e.g. vision, json)
        required_caps = request.required_capabilities or []
        if required_caps:
            available = self._routing_engine._filter_by_capabilities(available, required_caps)
            if not available:
                logger.info(
                    "No fallback candidate supports required capabilities",
                    required_capabilities=required_caps,
                )
                return None

        # 5. Filter healthy candidates if available
        healthy = [c for c in available if c.is_healthy]
        scoring_pool = healthy if healthy else available

        # 6. Retrieve policy weights based on request routing mode
        mode = self._routing_engine._resolve_routing_mode(request)
        weights = self._routing_engine._policy_registry.get_weights(mode)

        # 7. Score candidates using Phase 3 CandidateScorer
        scored = self._routing_engine._scorer.score_candidates(
            candidates=scoring_pool,
            health_weight=weights.health_weight,
            success_rate_weight=weights.success_rate_weight,
            latency_weight=weights.latency_weight,
            cost_weight=weights.cost_weight,
        )

        if not scored:
            return None

        best = scored[0].candidate
        logger.info(
            "Fallback candidate selected by Phase 3 Scorer",
            event="failover_candidate_selected",
            fallback_provider=best.provider,
            fallback_model=best.model,
            routing_mode=mode,
        )
        return best
