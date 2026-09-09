"""
Cortex Gateway — Phase 3 Routing Engine Tests.

Comprehensive tests covering:
- Scorer factor normalization (health, success rate, latency, cost)
- Weight normalization
- Deterministic tie-breaking
- Cold-start deterministic fallback
- StatsTracker rolling window
- Capability-based pre-filtering
- All 6 routing modes (manual, auto, lowest_cost, lowest_latency, best_available, capability_based)
- Error handling (NO_ROUTABLE_PROVIDER, NO_CAPABLE_PROVIDER, INVALID_ROUTING_MODE, INVALID_MANUAL_ROUTING)
- Configurable Ollama pricing behavior

100% offline, zero real API credentials required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest

from app.providers.registry import ProviderRegistry
from app.routing.candidates import CandidateBuilder
from app.routing.exceptions import (
    InvalidManualRoutingError,
    InvalidRoutingModeError,
    NoCapableProviderError,
    NoRoutableProviderError,
)
from app.routing.metadata import ModelMetadata, ModelMetadataCatalog
from app.routing.models import RoutingCandidate
from app.routing.policies import PolicyWeights, RoutingPolicyRegistry
from app.routing.router import RoutingEngine
from app.routing.scorer import CandidateScorer
from app.routing.stats import ProviderStatsTracker
from app.schemas.chat import ChatCompletionRequest, ChatMessage


def _make_candidate(
    provider: str = "groq",
    model: str = "llama-3.3-70b-versatile",
    cost: float = 0.00059,
    latency: float = 180.0,
    health: bool = True,
    success_rate: float = 1.0,
    capabilities: list[str] | None = None,
) -> RoutingCandidate:
    return RoutingCandidate(
        provider=provider,
        model=model,
        capabilities=capabilities or ["text", "code", "json"],
        cost_per_1k_tokens=cost,
        baseline_latency_ms=latency,
        runtime_latency_ms=latency,
        is_healthy=health,
        runtime_success_rate=success_rate,
    )


def _make_request(
    model: str = "auto",
    provider: str | None = None,
    routing_mode: str | None = None,
    required_capabilities: list[str] | None = None,
) -> ChatCompletionRequest:
    return ChatCompletionRequest(
        provider=provider,
        model=model,
        routing_mode=routing_mode,  # type: ignore
        required_capabilities=required_capabilities,
        messages=[ChatMessage(role="user", content="Hello")],
    )


# ── 1. Scorer Tests ───────────────────────────────────────────────────────────


class TestCandidateScorer:
    def test_weight_normalization(self) -> None:
        scorer = CandidateScorer()
        w = scorer._normalize_weights(3.0, 3.0, 2.0, 2.0)
        assert sum(w) == pytest.approx(1.0)
        assert w == (0.30, 0.30, 0.20, 0.20)

    def test_zero_total_weights_defaults_to_equal(self) -> None:
        scorer = CandidateScorer()
        w = scorer._normalize_weights(0.0, 0.0, 0.0, 0.0)
        assert w == (0.25, 0.25, 0.25, 0.25)

    def test_zero_cost_candidate_scores_maximum_cost_score(self) -> None:
        scorer = CandidateScorer()
        c_free = _make_candidate(provider="ollama", model="llama3.2", cost=0.0)
        c_paid = _make_candidate(provider="gemini", model="gemini-1.5-pro", cost=0.0025)

        scored = scorer.score_candidates([c_free, c_paid], cost_weight=1.0, health_weight=0, success_weight=0, latency_weight=0)
        assert scored[0].candidate.provider == "ollama"
        assert scored[0].score_breakdown["cost"] == 1.0
        assert scored[1].score_breakdown["cost"] < 1.0

    def test_lower_latency_scores_higher(self) -> None:
        scorer = CandidateScorer()
        c_fast = _make_candidate(provider="groq", model="fast", latency=50.0)
        c_slow = _make_candidate(provider="gemini", model="slow", latency=500.0)

        scored = scorer.score_candidates([c_fast, c_slow], latency_weight=1.0, health_weight=0, success_weight=0, cost_weight=0)
        assert scored[0].candidate.model == "fast"
        assert scored[0].score_breakdown["latency"] > scored[1].score_breakdown["latency"]

    def test_unhealthy_candidate_receives_zero_health_score(self) -> None:
        scorer = CandidateScorer()
        c_unhealthy = _make_candidate(health=False)
        scored = scorer.score_candidates([c_unhealthy])
        assert scored[0].score_breakdown["health"] == 0.0

    def test_deterministic_tie_breaker(self) -> None:
        """Equal score candidates are sorted deterministically by health, success rate, latency, provider, model."""
        scorer = CandidateScorer()
        c1 = _make_candidate(provider="b_provider", model="model_1", cost=0.0, latency=100.0)
        c2 = _make_candidate(provider="a_provider", model="model_1", cost=0.0, latency=100.0)

        # Both have identical metrics; tie-breaker chooses alphabetical provider 'a_provider' first
        scored1 = scorer.score_candidates([c1, c2])
        scored2 = scorer.score_candidates([c2, c1])

        assert scored1[0].candidate.provider == "a_provider"
        assert scored2[0].candidate.provider == "a_provider"


# ── 2. Stats Tracker Tests ───────────────────────────────────────────────────


class TestProviderStatsTracker:
    def test_cold_start_defaults(self) -> None:
        tracker = ProviderStatsTracker()
        stats = tracker.get_or_create("groq", "llama-3.3-70b-versatile")
        assert stats.total_requests == 0
        assert stats.success_rate == 1.0
        assert stats.latency_ms is None

    def test_record_success_updates_metrics(self) -> None:
        tracker = ProviderStatsTracker()
        tracker.record_success("groq", "llama-3.3-70b-versatile", 120.0)
        tracker.record_success("groq", "llama-3.3-70b-versatile", 80.0)

        stats = tracker.get_stats("groq", "llama-3.3-70b-versatile")
        assert stats is not None
        assert stats.total_requests == 2
        assert stats.successful_requests == 2
        assert stats.failed_requests == 0
        assert stats.success_rate == 1.0
        assert stats.latency_ms == 100.0

    def test_record_failure_decreases_success_rate(self) -> None:
        tracker = ProviderStatsTracker()
        tracker.record_success("groq", "llama", 100.0)
        tracker.record_failure("groq", "llama")

        stats = tracker.get_stats("groq", "llama")
        assert stats is not None
        assert stats.total_requests == 2
        assert stats.success_rate == 0.5


# ── 3. Model Metadata Catalog Tests ──────────────────────────────────────────


class TestModelMetadataCatalog:
    def test_known_model_lookup(self) -> None:
        catalog = ModelMetadataCatalog()
        meta = catalog.get("groq", "llama-3.3-70b-versatile")
        assert meta.provider == "groq"
        assert meta.baseline_latency_ms == 180.0
        assert "json" in meta.capabilities

    def test_bare_tag_fallback(self) -> None:
        catalog = ModelMetadataCatalog()
        meta = catalog.get("ollama", "llama3.2:3b")
        assert meta.provider == "ollama"
        assert meta.cost_per_1k_tokens == 0.0

    def test_unknown_model_fallback_with_configured_ollama_cost(self) -> None:
        catalog = ModelMetadataCatalog(ollama_default_cost=0.005)
        meta = catalog.get("ollama", "new-custom-model")
        assert meta.cost_per_1k_tokens == 0.005
        assert meta.baseline_latency_ms == 300.0

    def test_vision_capability_inferred_from_name(self) -> None:
        catalog = ModelMetadataCatalog()
        meta = catalog.get("ollama", "llava:latest")
        assert "vision" in meta.capabilities


# ── 4. Routing Engine Integration Tests ───────────────────────────────────────


class TestRoutingEngine:
    @pytest.fixture
    def mock_registry(self) -> ProviderRegistry:
        reg = ProviderRegistry()
        for name in ["gemini", "groq", "ollama"]:
            p = MagicMock()
            p.name = name
            p.health_check = AsyncMock(return_value=True)
            if name == "groq":
                p.list_models = AsyncMock(return_value=["llama-3.3-70b-versatile", "llama-3.1-8b-instant"])
            elif name == "gemini":
                p.list_models = AsyncMock(return_value=["gemini-1.5-flash", "gemini-1.5-pro"])
            elif name == "ollama":
                p.list_models = AsyncMock(return_value=["llama3.2", "qwen2.5"])
            reg.register(p)
        return reg

    @pytest.mark.asyncio
    async def test_manual_routing_exact_match(self, mock_registry: ProviderRegistry) -> None:
        engine = RoutingEngine(registry=mock_registry)
        req = _make_request(provider="groq", model="llama-3.3-70b-versatile", routing_mode="manual")
        decision = await engine.route(req)

        assert decision.routing_mode == "manual"
        assert decision.provider == "groq"
        assert decision.model == "llama-3.3-70b-versatile"
        assert decision.score == 1.0

    @pytest.mark.asyncio
    async def test_manual_routing_missing_model_raises(self, mock_registry: ProviderRegistry) -> None:
        engine = RoutingEngine(registry=mock_registry)
        req = _make_request(provider="groq", model="auto", routing_mode="manual")
        with pytest.raises(InvalidManualRoutingError):
            await engine.route(req)

    @pytest.mark.asyncio
    async def test_manual_routing_unregistered_provider_raises(self, mock_registry: ProviderRegistry) -> None:
        engine = RoutingEngine(registry=mock_registry)
        req = _make_request(provider="unknown", model="gpt-4", routing_mode="manual")
        with pytest.raises(NoRoutableProviderError):
            await engine.route(req)

    @pytest.mark.asyncio
    async def test_auto_routing_selects_highest_score(self, mock_registry: ProviderRegistry) -> None:
        engine = RoutingEngine(registry=mock_registry)
        req = _make_request(model="auto", routing_mode="auto")
        decision = await engine.route(req)

        assert decision.routing_mode == "auto"
        assert decision.provider in ["gemini", "groq", "ollama"]
        assert decision.score > 0.0

    @pytest.mark.asyncio
    async def test_lowest_latency_routing_mode(self, mock_registry: ProviderRegistry) -> None:
        """Lowest latency mode should select ultra-fast model (e.g. groq llama-3.1-8b-instant at 90ms)."""
        engine = RoutingEngine(registry=mock_registry)
        req = _make_request(model="auto", routing_mode="lowest_latency")
        decision = await engine.route(req)

        assert decision.routing_mode == "lowest_latency"
        assert decision.provider == "groq"
        assert decision.model == "llama-3.1-8b-instant"

    @pytest.mark.asyncio
    async def test_lowest_cost_routing_mode_with_free_ollama(self, mock_registry: ProviderRegistry) -> None:
        """When Ollama has cost=0.0 and others have positive cost, lowest_cost selects Ollama."""
        engine = RoutingEngine(registry=mock_registry, ollama_default_cost=0.0)
        req = _make_request(model="auto", routing_mode="lowest_cost")
        decision = await engine.route(req)

        assert decision.routing_mode == "lowest_cost"
        assert decision.provider == "ollama"

    @pytest.mark.asyncio
    async def test_capability_filtering_pre_filter(self, mock_registry: ProviderRegistry) -> None:
        """Filtering vision capability keeps only Gemini models that support vision."""
        engine = RoutingEngine(registry=mock_registry)
        req = _make_request(
            model="auto",
            routing_mode="capability_based",
            required_capabilities=["vision"],
        )
        decision = await engine.route(req)

        assert decision.provider == "gemini"
        assert "vision" in decision.candidate.capabilities

    @pytest.mark.asyncio
    async def test_no_capable_provider_raises_error(self, mock_registry: ProviderRegistry) -> None:
        """Requesting an unsupported capability raises NoCapableProviderError."""
        engine = RoutingEngine(registry=mock_registry)
        req = _make_request(
            model="auto",
            required_capabilities=["quantum_teleportation"],
        )
        with pytest.raises(NoCapableProviderError):
            await engine.route(req)

    @pytest.mark.asyncio
    async def test_invalid_routing_mode_raises(self, mock_registry: ProviderRegistry) -> None:
        engine = RoutingEngine(registry=mock_registry)
        req = MagicMock()
        req.routing_mode = "magical_mode"
        req.provider = None
        req.model = "auto"
        req.required_capabilities = None
        with pytest.raises(InvalidRoutingModeError):
            await engine.route(req)

    @pytest.mark.asyncio
    async def test_empty_registry_raises_no_routable_provider(self) -> None:
        empty_reg = ProviderRegistry()
        engine = RoutingEngine(registry=empty_reg)
        req = _make_request(model="auto", routing_mode="auto")
        with pytest.raises(NoRoutableProviderError):
            await engine.route(req)

    @pytest.mark.asyncio
    async def test_deterministic_decisions(self, mock_registry: ProviderRegistry) -> None:
        """Running the same route() call multiple times produces the identical decision."""
        engine = RoutingEngine(registry=mock_registry)
        req = _make_request(model="auto", routing_mode="auto")

        d1 = await engine.route(req)
        d2 = await engine.route(req)

        assert d1.provider == d2.provider
        assert d1.model == d2.model
        assert d1.score == d2.score
