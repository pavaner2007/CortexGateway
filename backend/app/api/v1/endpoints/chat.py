"""
Cortex Gateway — Chat Completion Endpoint (Phase 2 + Phase 5).

Provides:
    POST /api/v1/chat/completions

Route handlers contain ZERO provider-specific logic.
All provider routing, transformation, and normalization is handled by
ChatService → ProviderRegistry → BaseLLMProvider.

Phase 5: All requests now require a valid API key via
    Authorization: Bearer <cxg_...>
The RequestContext is extracted by get_request_context and passed to
ChatService for ownership tracking and future rate limiting.
"""

from fastapi import APIRouter, Depends, status

from app.auth.dependencies import get_request_context
from app.auth.schemas import RequestContext
from app.middleware.request_id import get_request_id
from app.providers.registry import ProviderRegistry, get_registry
from app.routing.router import RoutingEngine, get_routing_engine
from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse
from app.services.chat_service import ChatService

router = APIRouter()


def _get_chat_service(
    reg: ProviderRegistry = Depends(get_registry),
    router_engine: RoutingEngine = Depends(get_routing_engine),
) -> ChatService:
    """FastAPI dependency: construct ChatService with global registry and routing engine."""
    return ChatService(registry=reg, routing_engine=router_engine)


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
        403: {"description": "Insufficient permissions"},
        404: {"description": "Provider not found"},
        429: {"description": "Provider rate limited"},
        502: {"description": "Provider error"},
        503: {"description": "Provider unavailable or disabled"},
        504: {"description": "Provider timeout"},
    },
)
async def chat_completions(
    request: ChatCompletionRequest,
    context: RequestContext = Depends(get_request_context),
    service: ChatService = Depends(_get_chat_service),
) -> ChatCompletionResponse:
    """
    Unified chat completion endpoint.

    Accepts a provider-agnostic request and returns a normalized response
    regardless of which LLM provider is selected.

    The request context (organization_id, team_id, api_key_id, role) is
    available to the chat service for logging and future rate limiting.
    """
    request_id = get_request_id()
    return await service.complete(request, request_id, context=context)
