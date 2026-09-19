"""
Cortex Gateway — Chat Completion Endpoint (Phase 2 + Phase 5 + Phase 6 + Phase 7).

Provides:
    POST /api/v1/chat/completions

Phase 5: All requests require a valid API key.
Phase 6: Rate limiting and budget management are injected into ChatService.
         All three Phase 6 dependencies (rate_limiter, budget_service,
         cost_calculator) are injected from FastAPI dependency functions so
         they can be overridden in tests without touching global state.
Phase 7: Observability layer — strictly non-blocking:
         - One RequestLog row written via BackgroundTasks (own DB session).
         - Prometheus counters/histograms incremented.
         - None of the above can fail the request.
         - All exceptions from the pipeline are re-raised after logging;
           the exception handler chain in app/exceptions.py handles the response.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_request_context
from app.auth.schemas import RequestContext
from app.budget.cost import CostCalculator
from app.budget.service import BudgetService
from app.config.settings import Settings, get_settings
from app.database.session import get_db_dependency
from app.middleware.request_id import get_request_id
from app.providers.registry import ProviderRegistry, get_registry
from app.rate_limit.limiter import RateLimiter
from app.routing.metadata import ModelMetadataCatalog
from app.routing.router import RoutingEngine, get_routing_engine
from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse
from app.semantic_cache.cache import SemanticCache
from app.services.chat_service import ChatService
from app.utils.redis_client import get_redis
from app.policy.resolver import PolicyResolver
from app.policy.schemas import GLOBAL_DEFAULT_POLICY, ResolvedPolicy

router = APIRouter()


def _get_chat_service(
    reg: ProviderRegistry = Depends(get_registry),
    router_engine: RoutingEngine = Depends(get_routing_engine),
) -> ChatService:
    """Construct ChatService with the global registry and routing engine."""
    return ChatService(registry=reg, routing_engine=router_engine)


def _get_rate_limiter(
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> RateLimiter:
    """Return RateLimiter backed by the shared Redis client."""
    if not settings.rate_limit_enabled:
        return RateLimiter(redis=None)  # disabled — always allows
    return RateLimiter(redis=redis)


def _get_budget_service(
    session: AsyncSession = Depends(get_db_dependency),
) -> BudgetService:
    """Return BudgetService using the request-scoped DB session."""
    return BudgetService(session=session)


def _get_cost_calculator(
    settings: Settings = Depends(get_settings),
) -> CostCalculator:
    """Return CostCalculator using the DB-backed shared ModelMetadataCatalog.

    Phase 9A: Using _shared_catalog instead of a per-request fresh catalog
    so pricing reflects any admin changes to the model registry.
    """
    from app.routing.metadata import _shared_catalog
    return CostCalculator(catalog=_shared_catalog)


def _get_semantic_cache(
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> SemanticCache:
    """Return the SemanticCache backed by the shared Redis client.

    Phase 9B: Constructed fresh per-request (cheap — no I/O) using
    the module-level _semantic_cache singleton when available.
    """
    from app.main import _semantic_cache
    if _semantic_cache is not None:
        return _semantic_cache
    # Fallback (e.g. during tests without main.py lifespan)
    from app.semantic_cache.cache import build_semantic_cache
    return build_semantic_cache(redis=redis, settings=settings)


async def _get_resolved_policy(
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_dependency),
) -> ResolvedPolicy:
    """
    Phase 9C: Resolve the effective team policy once per request.

    Uses the same FastAPI-injected DB session so tests can override
    get_db_dependency without needing a real PostgreSQL connection.
    Falls back to the global default if the DB is unavailable.
    """
    try:
        resolver = PolicyResolver(session)
        return await resolver.resolve(context.team_id)
    except Exception:
        return GLOBAL_DEFAULT_POLICY


@router.post(
    "/chat/completions",
    response_model=ChatCompletionResponse,
    status_code=status.HTTP_200_OK,
    summary="Unified Chat Completion",
    description=(
        "Send a chat completion request to any supported LLM provider "
        "through the unified Cortex Gateway interface. "
        "Requires a valid API key: Authorization: Bearer <cxg_...>."
    ),
    tags=["Chat"],
    responses={
        200: {"description": "Chat completion successful"},
        400: {"description": "Invalid request or model"},
        401: {"description": "Authentication required"},
        402: {"description": "Team budget exhausted"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Provider not found"},
        429: {"description": "Rate limit exceeded or provider rate limited"},
        502: {"description": "Provider error"},
        503: {"description": "Provider unavailable or disabled"},
        504: {"description": "Provider timeout"},
    },
)
async def chat_completions(
    request: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    context: RequestContext = Depends(get_request_context),
    service: ChatService = Depends(_get_chat_service),
    rate_limiter: RateLimiter = Depends(_get_rate_limiter),
    budget_service: BudgetService = Depends(_get_budget_service),
    cost_calculator: CostCalculator = Depends(_get_cost_calculator),
    semantic_cache: SemanticCache = Depends(_get_semantic_cache),
    settings: Settings = Depends(get_settings),
    resolved_policy: ResolvedPolicy = Depends(_get_resolved_policy),
) -> ChatCompletionResponse:
    """
    Unified chat completion endpoint.

    Phase 9C: resolve the team policy ONCE here (via _get_resolved_policy Depends),
    before calling ChatService. The single ResolvedPolicy object is passed down
    and is the only source of truth for routing strategy, fallback, budget action,
    and cache enable for this request.

    Phase 7 observability is additive and non-blocking:
    - All exceptions from the pipeline are always re-raised.
    - Observability logging is registered as BackgroundTasks BEFORE raising.
    - The exception handler in app/exceptions.py handles the HTTP response.
    """
    from app.budget.exceptions import BudgetExceeded, RateLimitExceeded
    from app.observability.log_writer import (
        build_error_log,
        build_success_log,
        write_request_log,
    )
    from app.observability.metrics import (
        budget_downgrade_total,
        fallback_requests_total,
        rate_limit_exceeded_total,
        record_gateway_request,
        semantic_cache_hits_total,
        semantic_cache_misses_total,
        update_circuit_breaker_state,
    )
    from app.observability.tracing import get_current_trace_id

    request_id = get_request_id()

    # ── Run the core pipeline ─────────────────────────────────────────────────
    # Any exception here is caught, logged (non-blocking), and re-raised.
    # The exception handler chain produces the final HTTP error response.
    try:
        response = await service.complete(
            request,
            request_id,
            context=context,
            rate_limiter=rate_limiter,
            budget_service=budget_service,
            cost_calculator=cost_calculator,
            settings=settings,
            semantic_cache=semantic_cache,
            resolved_policy=resolved_policy,
        )

    except RateLimitExceeded as exc:
        try:
            rate_limit_exceeded_total.labels(scope=exc.scope).inc()
        except Exception:
            pass
        if settings.request_log_enabled:
            try:
                background_tasks.add_task(
                    write_request_log,
                    build_error_log(
                        request_id=request_id,
                        context=context,
                        status="rate_limited",
                        http_status_code=429,
                        error_code=exc.code,
                        trace_id=get_current_trace_id(),
                    ),
                )
            except Exception:
                pass
        raise  # → app/exceptions.py rate_limit_exceeded_handler → 429

    except BudgetExceeded as exc:
        if settings.request_log_enabled:
            try:
                background_tasks.add_task(
                    write_request_log,
                    build_error_log(
                        request_id=request_id,
                        context=context,
                        status="budget_blocked",
                        http_status_code=402,
                        error_code=exc.code,
                        budget_action="blocked",
                        trace_id=get_current_trace_id(),
                    ),
                )
            except Exception:
                pass
        raise  # → app/exceptions.py budget_exceeded_handler → 402

    except Exception as exc:
        if settings.request_log_enabled:
            try:
                background_tasks.add_task(
                    write_request_log,
                    build_error_log(
                        request_id=request_id,
                        context=context,
                        status="failure",
                        http_status_code=getattr(exc, "status_code", 500),
                        error_code=getattr(exc, "code", type(exc).__name__),
                        trace_id=get_current_trace_id(),
                    ),
                )
            except Exception:
                pass
        raise  # → app/exceptions.py appropriate handler

    # ── Success path ──────────────────────────────────────────────────────────
    meta = response.metadata

    # Resolve budget policy for RequestLog — use the resolved policy (Phase 9C)
    # rather than a second DB read.
    budget_policy: str | None = resolved_policy.budget.action

    # ── Prometheus (non-blocking; failure is silent) ──────────────────────────
    try:
        provider_label = meta.selected_provider or "unknown"
        model_label = meta.selected_model or "unknown"

        record_gateway_request(
            provider=provider_label,
            model=model_label,
            status="success",
            latency_ms=meta.latency_ms or 0,
        )

        # Phase 9B: cache hit / miss counters
        if meta.cache_hit:
            semantic_cache_hits_total.inc()
        else:
            semantic_cache_misses_total.inc()

        if meta.failover_triggered and meta.original_provider:
            fallback_requests_total.labels(
                from_provider=meta.original_provider,
                to_provider=provider_label,
            ).inc()

        if meta.budget_downgraded:
            budget_downgrade_total.inc()

        if meta.circuit_breaker_state:
            update_circuit_breaker_state(provider_label, meta.circuit_breaker_state)

    except Exception:
        pass

    # ── RequestLog background write (non-blocking) ────────────────────────
    if settings.request_log_enabled:
        try:
            log_data = build_success_log(
                request_id=request_id,
                context=context,
                response=response,
                trace_id=get_current_trace_id(),
                budget_policy=budget_policy,
                cache_hit=meta.cache_hit,  # Phase 9B
            )
            background_tasks.add_task(write_request_log, log_data)
        except Exception:
            pass

    return response
