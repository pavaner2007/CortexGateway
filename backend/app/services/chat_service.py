"""
Cortex Gateway — Chat Service (Phase 4 + Phase 5 + Phase 6 + Phase 9B).

Orchestrates the full chat completion pipeline:

    Phase 5 Auth → RequestContext
        ↓
    Phase 6 Rate Limiting (API key / Team / Org)
        ↓
    Phase 9B Semantic Cache Lookup
        ↓ (MISS only)
    Phase 6 Budget Pre-Check + Reservation
        ↓
    Phase 3 Routing Engine (provider/model selection)
        ↓
    Phase 4 Reliability Executor (retries, circuit breakers, failover)
        ↓
    Provider Adapter → LLM
        ↓
    Phase 6 Actual Cost Calculation
        ↓
    Phase 6 Budget Reconciliation
        ↓
    Phase 9B Cache Write (background, non-blocking)
        ↓
    Response with cost/budget/cache metadata

ChatService responsibilities:
  1. Enforce rate limits using RequestContext.team_id, org_id, api_key_id.
  2. Perform semantic cache lookup (Phase 9B). On HIT: return immediately.
  3. Estimate request cost and check/reserve budget.
  4. For DOWNGRADE policy, attempt to find a cheaper candidate.
  5. Delegate execution to ReliabilityExecutor.
  6. Reconcile actual cost against the budget reservation.
  7. Schedule async cache write after successful provider response.
  8. Return normalized ChatCompletionResponse with Phase 6 + 9B metadata.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from app.auth.schemas import RequestContext

from app.core.logging import logger
from app.providers.registry import ProviderRegistry
from app.reliability.executor import ReliabilityExecutor
from app.routing.candidates import CandidateBuilder
from app.routing.models import RoutingCandidate
from app.routing.router import RoutingEngine
from app.routing.scorer import CandidateScorer
from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse


class ChatService:
    """
    Application-layer service for chat completions.

    Orchestrates rate limiting, budget reservation, routing, reliability,
    and budget reconciliation in the correct pipeline order.
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        routing_engine: Optional[RoutingEngine] = None,
        reliability_executor: Optional[ReliabilityExecutor] = None,
    ) -> None:
        self._registry = registry
        self._routing_engine = routing_engine or RoutingEngine(registry=registry)
        self._reliability_executor = reliability_executor or ReliabilityExecutor(
            registry=self._registry,
            routing_engine=self._routing_engine,
        )

    @property
    def routing_engine(self) -> RoutingEngine:
        return self._routing_engine

    @property
    def reliability_executor(self) -> ReliabilityExecutor:
        return self._reliability_executor

    async def complete(
        self,
        request: ChatCompletionRequest,
        request_id: str,
        context: Optional["RequestContext"] = None,
        # Phase 6 injectable dependencies (None = disabled / no-op)
        rate_limiter: object = None,
        budget_service: object = None,
        cost_calculator: object = None,
        settings: object = None,
        team_rate_limit_service: object = None,
        # Phase 9B
        semantic_cache: object = None,
    ) -> ChatCompletionResponse:
        """
        Execute a chat completion with rate limiting and budget management.

        Args:
            request:                 Validated Cortex chat completion request.
            request_id:              Current request ID from middleware.
            context:                 Authenticated RequestContext (Phase 5).
            rate_limiter:            RateLimiter instance (Phase 6). None = disabled.
            budget_service:          BudgetService instance (Phase 6). None = disabled.
            team_rate_limit_service: TeamRateLimitService instance for per-team limits. None = disabled.
            cost_calculator:         CostCalculator instance (Phase 6). None = disabled.
            settings:                Settings instance for Phase 6 config flags.

        Returns:
            Normalized ChatCompletionResponse with Phase 6 + Phase 9B metadata.
        """
        from app.config.settings import get_settings as _get_settings

        s = settings or _get_settings()

        # ── 1. Rate Limiting ──────────────────────────────────────────────────
        rate_limit_remaining: Optional[int] = None

        if context and rate_limiter and getattr(s, "rate_limit_enabled", True):
            from app.budget.exceptions import RateLimitExceeded
            from app.rate_limit.limiter import RateLimiter

            # Resolve effective team limits: per-team DB override → global default
            team_rpm = s.rate_limit_team_requests
            team_window = s.rate_limit_team_window_seconds

            if team_rate_limit_service is not None and context.team_id:
                try:
                    team_override = await team_rate_limit_service.get(context.team_id)
                    if team_override is not None and team_override.requests_per_minute is not None:
                        team_rpm = team_override.requests_per_minute
                except Exception:
                    # Fail-open: DB unavailable → use global default
                    pass

            outcome = await rate_limiter.check_all(
                api_key_id=context.api_key_id,
                team_id=context.team_id,
                org_id=context.organization_id,
                key_limit=s.rate_limit_api_key_requests,
                key_window=s.rate_limit_api_key_window_seconds,
                team_limit=team_rpm,
                team_window=team_window,
                org_limit=s.rate_limit_org_requests,
                org_window=s.rate_limit_org_window_seconds,
            )
            if not outcome.allowed:
                raise RateLimitExceeded(
                    message="Rate limit exceeded. Please retry after the window resets.",
                    retry_after_seconds=outcome.binding_result.retry_after_seconds,
                    scope=outcome.binding_result.scope,
                )
            rate_limit_remaining = outcome.binding_result.remaining

        # ── 2. Determine Routing Path ─────────────────────────────────────────
        is_manual = (
            request.routing_mode == "manual"
            or (
                bool(request.provider)
                and request.model.lower() != "auto"
                and request.routing_mode is None
                and not request.required_capabilities
            )
        )

        effective_routing_mode = "manual" if is_manual else (request.routing_mode or "auto")

        if is_manual:
            target_provider_name = request.provider
            target_model_name = request.model
            if not target_provider_name or target_model_name.lower() == "auto":
                from app.routing.exceptions import InvalidManualRoutingError
                raise InvalidManualRoutingError(
                    "Manual routing mode requires both a valid 'provider' and a concrete 'model' name."
                )
        else:
            decision = await self._routing_engine.route(request)
            target_provider_name = decision.provider
            target_model_name = decision.model
            effective_routing_mode = decision.routing_mode

        # ── 3. Semantic Cache Lookup (Phase 9B) ────────────────────────────
        # Rate limiting already applied (cache hits count as requests).
        # Budget reservation intentionally deferred — cache hits cost $0.
        if semantic_cache is not None and context:
            cached_response = await semantic_cache.lookup(request, context)
            if cached_response is not None:
                cached_response.metadata.rate_limit_remaining = rate_limit_remaining
                cached_response.metadata.request_id = request_id
                return cached_response  # short-circuit: no budget, routing, or provider

        # ── 4. Budget Pre-Check + Reservation ───────────────────────────────
        estimated_cost: float = 0.0
        budget_warning: bool = False
        budget_downgraded: bool = False
        budget_obj = None

        if context and budget_service and cost_calculator and getattr(s, "budget_enabled", True):
            estimated_cost = cost_calculator.estimate_cost(
                provider=target_provider_name,
                model=target_model_name,
                request=request,
            )

            budget_policy = await self._get_budget_policy(
                budget_service, context.team_id
            )

            if budget_policy == "DOWNGRADE":
                # Try downgrade path before reservation
                target_provider_name, target_model_name, estimated_cost, budget_downgraded = (
                    await self._attempt_budget_downgrade(
                        request=request,
                        context=context,
                        budget_service=budget_service,
                        cost_calculator=cost_calculator,
                        original_provider=target_provider_name,
                        original_model=target_model_name,
                        estimated_cost=estimated_cost,
                    )
                )

            # Reserve the estimated cost (may raise BudgetExceeded for BLOCK)
            budget_obj, budget_warning = await budget_service.check_and_reserve(
                team_id=context.team_id,
                estimated_cost=estimated_cost,
                warning_threshold_percent=getattr(s, "budget_warning_threshold_percent", 80),
            )

        logger.info(
            "Chat completion routing resolved",
            request_id=request_id,
            routing_mode=effective_routing_mode,
            target_provider=target_provider_name,
            target_model=target_model_name,
            message_count=len(request.messages),
            estimated_cost=estimated_cost,
            org_id=context.organization_id if context else None,
            team_id=context.team_id if context else None,
            key_id=context.api_key_id if context else None,
        )

        # ── 5. Provider Execution (Phase 3 + Phase 4) ─────────────────────────
        actual_cost: float = 0.0
        response: Optional[ChatCompletionResponse] = None

        try:
            response = await self._reliability_executor.execute(
                request=request,
                request_id=request_id,
                initial_provider=target_provider_name,
                initial_model=target_model_name,
                routing_mode=effective_routing_mode,
            )
        except Exception:
            # Provider failed — release budget reservation, do not charge
            if context and budget_service and estimated_cost > 0:
                try:
                    await budget_service.release_reservation(
                        team_id=context.team_id,
                        estimated_cost=estimated_cost,
                    )
                except Exception as release_exc:
                    logger.error(
                        "Failed to release budget reservation after provider failure",
                        team_id=context.team_id,
                        error=str(release_exc),
                    )
            raise

        # ── 6. Actual Cost + Budget Reconciliation ────────────────────────────
        remaining_budget: Optional[float] = None

        if context and budget_service and cost_calculator and estimated_cost >= 0:
            # Use the provider/model that actually served the request
            actual_provider = response.metadata.selected_provider or target_provider_name
            actual_model = response.metadata.selected_model or target_model_name

            actual_cost = cost_calculator.calculate_actual_cost(
                provider=actual_provider,
                model=actual_model,
                usage=response.usage,
                estimated_cost=estimated_cost,
            )

            reconciled_budget = await budget_service.reconcile(
                team_id=context.team_id,
                estimated_cost=estimated_cost,
                actual_cost=actual_cost,
            )

            if reconciled_budget and getattr(s, "budget_expose_remaining", False):
                remaining_budget = reconciled_budget.remaining_amount

        # ── 7. Attach Phase 6 + 9B Metadata to Response ─────────────────────
        response.metadata.estimated_cost = round(estimated_cost, 8) if estimated_cost else None
        response.metadata.actual_cost = round(actual_cost, 8) if actual_cost else None
        response.metadata.remaining_budget = remaining_budget
        response.metadata.budget_warning = budget_warning
        response.metadata.budget_downgraded = budget_downgraded
        response.metadata.rate_limit_remaining = rate_limit_remaining
        # cache_hit stays False — this is a normal provider response

        # ── 8. Trigger cache write (Phase 9B) ─────────────────────────────
        # Non-blocking fire-and-forget; cache failures never affect the response.
        if semantic_cache is not None and context:
            import asyncio
            asyncio.ensure_future(semantic_cache.store(request, context, response))

        return response

    async def _get_budget_policy(
        self,
        budget_service: object,
        team_id: str,
    ) -> str:
        """Return the effective policy for the team's active budget, or 'BLOCK' default."""
        budget = await budget_service.get_budget(team_id)
        if budget is None or not budget.enabled:
            return "NONE"
        return budget.policy.upper()

    async def _attempt_budget_downgrade(
        self,
        request: ChatCompletionRequest,
        context: "RequestContext",
        budget_service: object,
        cost_calculator: object,
        original_provider: str,
        original_model: str,
        estimated_cost: float,
    ):
        """
        For DOWNGRADE policy: attempt to find a cheaper provider/model.

        Returns (provider, model, estimated_cost, was_downgraded) tuple.

        If the original candidate fits in the budget, no downgrade occurs.
        If no cheaper candidate fits, raises BudgetExceeded.
        """
        from app.budget.exceptions import BudgetExceeded

        budget = await budget_service.get_budget(context.team_id)
        if budget is None or not budget.enabled:
            return original_provider, original_model, estimated_cost, False

        remaining = budget.remaining_amount

        # Check if the original candidate already fits
        if estimated_cost <= remaining:
            return original_provider, original_model, estimated_cost, False

        # Need to find a cheaper candidate
        logger.info(
            "Budget downgrade triggered",
            team_id=context.team_id,
            original_provider=original_provider,
            original_model=original_model,
            estimated_cost=estimated_cost,
            remaining_budget=remaining,
        )

        # Build all candidates via Phase 3 candidate builder
        all_candidates: List[RoutingCandidate] = (
            await self._routing_engine._candidate_builder.build_candidates()
        )

        # Filter: must be healthy, have required capabilities, and fit in budget
        required_caps = request.required_capabilities or []
        affordable: List[RoutingCandidate] = []

        for c in all_candidates:
            if not c.is_healthy:
                continue
            # Skip the original (already too expensive)
            if c.provider == original_provider and c.model == original_model:
                continue
            # Capability check
            if required_caps:
                cap_set = {cap.lower() for cap in c.capabilities}
                if not all(r.lower() in cap_set for r in required_caps):
                    continue
            # Cost check: estimate cost for this candidate
            candidate_cost = cost_calculator.estimate_cost(
                provider=c.provider,
                model=c.model,
                request=request,
            )
            if candidate_cost <= remaining:
                affordable.append(c)

        if not affordable:
            raise BudgetExceeded(
                message=(
                    f"Budget exhausted and no cheaper compatible provider found. "
                    f"Remaining: ${remaining:.6f}."
                ),
                team_id=context.team_id,
                remaining=remaining,
            )

        # Use Phase 3 scorer to select the best affordable candidate
        scorer = CandidateScorer()
        scored = scorer.score_candidates(candidates=affordable)
        best = scored[0].candidate

        new_estimated_cost = cost_calculator.estimate_cost(
            provider=best.provider,
            model=best.model,
            request=request,
        )

        logger.info(
            "Budget downgrade selected",
            team_id=context.team_id,
            downgrade_provider=best.provider,
            downgrade_model=best.model,
            new_estimated_cost=new_estimated_cost,
        )

        return best.provider, best.model, new_estimated_cost, True
