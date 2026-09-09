"""
Cortex Gateway — Routing Engine (Phase 3).

Core orchestrator for intelligent model + provider selection.
Filters by capabilities, checks health, applies policy weights,
scores candidates deterministically, and returns RoutingDecision.
"""

from __future__ import annotations

from typing import List, Optional

from app.core.logging import logger
from app.providers.registry import ProviderRegistry
from app.routing.candidates import CandidateBuilder
from app.routing.exceptions import (
    InvalidManualRoutingError,
    InvalidRoutingModeError,
    NoCapableProviderError,
    NoRoutableProviderError,
)
from app.routing.metadata import ModelMetadataCatalog
from app.routing.models import RoutingCandidate, RoutingDecision, RoutingMode
from app.routing.policies import PolicyWeights, RoutingPolicyRegistry
from app.routing.scorer import CandidateScorer
from app.routing.stats import ProviderStatsTracker
from app.schemas.chat import ChatCompletionRequest


class RoutingEngine:
    """
    Intelligent Multi-LLM Routing Engine.

    Selects the optimal (provider, model) target for incoming requests.
    """

    VALID_MODES = {
        "manual",
        "auto",
        "lowest_cost",
        "lowest_latency",
        "best_available",
        "capability_based",
    }

    def __init__(
        self,
        registry: ProviderRegistry,
        stats_tracker: Optional[ProviderStatsTracker] = None,
        metadata_catalog: Optional[ModelMetadataCatalog] = None,
        policy_registry: Optional[RoutingPolicyRegistry] = None,
        scorer: Optional[CandidateScorer] = None,
        default_mode: RoutingMode = "auto",
        ollama_default_cost: float = 0.0,
    ) -> None:
        self._registry = registry
        self._stats_tracker = stats_tracker or ProviderStatsTracker()
        self._metadata_catalog = metadata_catalog or ModelMetadataCatalog(
            ollama_default_cost=ollama_default_cost
        )
        self._policy_registry = policy_registry or RoutingPolicyRegistry()
        self._scorer = scorer or CandidateScorer()
        self._candidate_builder = CandidateBuilder(
            registry=self._registry,
            metadata_catalog=self._metadata_catalog,
            stats_tracker=self._stats_tracker,
        )
        self._default_mode: RoutingMode = default_mode

    @property
    def stats_tracker(self) -> ProviderStatsTracker:
        return self._stats_tracker

    @property
    def metadata_catalog(self) -> ModelMetadataCatalog:
        return self._metadata_catalog

    async def route(
        self,
        request: ChatCompletionRequest,
    ) -> RoutingDecision:
        """
        Execute intelligent routing decision for a chat completion request.

        Args:
            request: Validated ChatCompletionRequest.

        Returns:
            RoutingDecision containing selected provider, model, score, and breakdown.

        Raises:
            InvalidRoutingModeError: Unknown routing mode.
            InvalidManualRoutingError: Manual routing missing provider or model.
            NoRoutableProviderError: No active or healthy providers available.
            NoCapableProviderError: No provider satisfies required capabilities.
        """
        # Determine effective routing mode
        mode = self._resolve_routing_mode(request)

        # ── 1. Manual Routing Mode ───────────────────────────────────────────
        if mode == "manual":
            if not request.provider or not request.model or request.model.lower() == "auto":
                raise InvalidManualRoutingError(
                    "Manual routing mode requires both 'provider' and a concrete 'model' name."
                )
            if not self._registry.is_registered(request.provider):
                raise NoRoutableProviderError(
                    f"Manual provider '{request.provider}' is not registered or available."
                )
            meta = self._metadata_catalog.get(request.provider, request.model)
            candidate = RoutingCandidate(
                provider=request.provider,
                model=request.model,
                capabilities=meta.capabilities,
                context_window=meta.context_window,
                cost_per_1k_tokens=meta.cost_per_1k_tokens,
                is_healthy=True,
                baseline_latency_ms=meta.baseline_latency_ms,
            )
            return RoutingDecision(
                provider=request.provider,
                model=request.model,
                routing_mode="manual",
                score=1.0,
                score_breakdown={"manual": 1.0},
                candidate=candidate,
            )

        # ── 2. Discover Candidates ───────────────────────────────────────────
        candidates = await self._candidate_builder.build_candidates()
        if not candidates:
            raise NoRoutableProviderError(
                "No active providers are registered in the gateway."
            )

        # If user explicitly requested a specific provider (e.g. provider="groq", model="auto")
        if request.provider and request.provider.lower() != "auto":
            candidates = [
                c for c in candidates if c.provider.lower() == request.provider.lower()
            ]
            if not candidates:
                raise NoRoutableProviderError(
                    f"Requested provider '{request.provider}' has no available candidates."
                )

        # ── 3. Capability Pre-Filtering ──────────────────────────────────────
        # Filter must happen BEFORE scoring
        required_caps = request.required_capabilities or []
        if required_caps:
            candidates = self._filter_by_capabilities(candidates, required_caps)
            if not candidates:
                raise NoCapableProviderError(
                    f"No available provider/model supports all required capabilities: {required_caps}"
                )

        # ── 4. Health Filtering ──────────────────────────────────────────────
        healthy_candidates = [c for c in candidates if c.is_healthy]
        if healthy_candidates:
            candidates = healthy_candidates
        else:
            logger.warning(
                "All matching candidates are currently marked unhealthy; attempting best effort fallback"
            )

        # ── 5. Retrieve Policy Weights ───────────────────────────────────────
        weights = self._policy_registry.get_weights(mode)

        # ── 6. Score & Rank Candidates ───────────────────────────────────────
        scored = self._scorer.score_candidates(
            candidates=candidates,
            health_weight=weights.health_weight,
            success_rate_weight=weights.success_rate_weight,
            latency_weight=weights.latency_weight,
            cost_weight=weights.cost_weight,
        )

        if not scored:
            raise NoRoutableProviderError(
                "Failed to score any candidates for the request."
            )

        best = scored[0]
        logger.info(
            "Routing decision computed",
            routing_mode=mode,
            selected_provider=best.candidate.provider,
            selected_model=best.candidate.model,
            score=best.total_score,
            breakdown=best.score_breakdown,
        )

        return RoutingDecision(
            provider=best.candidate.provider,
            model=best.candidate.model,
            routing_mode=mode,
            score=best.total_score,
            score_breakdown=best.score_breakdown,
            candidate=best.candidate,
        )

    def _resolve_routing_mode(self, request: ChatCompletionRequest) -> RoutingMode:
        """Determine routing mode from request parameters with backward compatibility."""
        if request.routing_mode:
            mode = request.routing_mode.lower()
            if mode not in self.VALID_MODES:
                raise InvalidRoutingModeError(
                    f"Unknown routing mode '{request.routing_mode}'. "
                    f"Supported modes: {sorted(list(self.VALID_MODES))}"
                )
            return mode  # type: ignore

        # If provider and concrete model given (not 'auto') -> manual
        if request.provider and request.model and request.model.lower() != "auto":
            return "manual"

        # If required capabilities given without mode -> capability_based
        if request.required_capabilities:
            return "capability_based"

        return self._default_mode

    @staticmethod
    def _filter_by_capabilities(
        candidates: List[RoutingCandidate],
        required: List[str],
    ) -> List[RoutingCandidate]:
        """Keep only candidates that support all requested capabilities (case-insensitive)."""
        req_set = {r.lower().strip() for r in required if r.strip()}
        filtered: List[RoutingCandidate] = []
        for c in candidates:
            cand_set = {cap.lower().strip() for cap in c.capabilities}
            if req_set.issubset(cand_set):
                filtered.append(c)
        return filtered


from fastapi import Depends
from app.providers.registry import get_registry

_routing_engine_instance: Optional[RoutingEngine] = None


def get_routing_engine(
    registry: ProviderRegistry = Depends(get_registry),
) -> RoutingEngine:
    """Return or construct the global RoutingEngine singleton."""
    global _routing_engine_instance
    if _routing_engine_instance is None:
        from app.config.settings import get_settings

        s = get_settings()
        _routing_engine_instance = RoutingEngine(
            registry=registry,
            default_mode=s.routing_default_mode,  # type: ignore
            ollama_default_cost=s.routing_ollama_cost_per_1k,
        )
    else:
        # Keep registry reference synchronized if overridden in tests
        _routing_engine_instance._registry = registry
        _routing_engine_instance._candidate_builder._registry = registry
    return _routing_engine_instance


def set_routing_engine(engine: Optional[RoutingEngine]) -> None:
    """Set or reset global RoutingEngine instance (useful for testing)."""
    global _routing_engine_instance
    _routing_engine_instance = engine

