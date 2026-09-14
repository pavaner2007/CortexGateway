"""
Cortex Gateway — Chat Completion Endpoint (Phase 2 + Phase 5 + Phase 6).

Provides:
    POST /api/v1/chat/completions

Phase 5: All requests require a valid API key.
Phase 6: Rate limiting and budget management are injected into ChatService.
         All three Phase 6 dependencies (rate_limiter, budget_service,
         cost_calculator) are injected from FastAPI dependency functions so
         they can be overridden in tests without touching global state.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
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
from app.services.chat_service import ChatService
from app.utils.redis_client import get_redis

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
    """Return CostCalculator with a ModelMetadataCatalog reflecting Ollama pricing from settings."""
    catalog = ModelMetadataCatalog(
        ollama_default_cost=settings.ollama_cost_per_1k_input_tokens,
    )
    return CostCalculator(catalog=catalog)


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
    context: RequestContext = Depends(get_request_context),
    service: ChatService = Depends(_get_chat_service),
    rate_limiter: RateLimiter = Depends(_get_rate_limiter),
    budget_service: BudgetService = Depends(_get_budget_service),
    cost_calculator: CostCalculator = Depends(_get_cost_calculator),
    settings: Settings = Depends(get_settings),
) -> ChatCompletionResponse:
    """
    Unified chat completion endpoint with rate limiting and budget management.

    Pipeline:
        Auth → Rate Limit → Budget Reserve → Routing → Reliability → Provider
        → Actual Cost → Budget Reconcile → Response
    """
    request_id = get_request_id()
    return await service.complete(
        request,
        request_id,
        context=context,
        rate_limiter=rate_limiter,
        budget_service=budget_service,
        cost_calculator=cost_calculator,
        settings=settings,
    )
