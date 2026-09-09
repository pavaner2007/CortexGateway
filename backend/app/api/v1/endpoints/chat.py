"""
Cortex Gateway — Chat Completion Endpoint (Phase 2).

Provides:
    POST /api/v1/chat/completions

Route handlers contain ZERO provider-specific logic.
All provider routing, transformation, and normalization is handled by
ChatService → ProviderRegistry → BaseLLMProvider.
"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

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
        "The client explicitly selects the provider via the `provider` field."
    ),
    tags=["Chat"],
    responses={
        200: {"description": "Chat completion successful"},
        400: {"description": "Invalid request or model"},
        404: {"description": "Provider not found"},
        429: {"description": "Provider rate limited"},
        502: {"description": "Provider error"},
        503: {"description": "Provider unavailable or disabled"},
        504: {"description": "Provider timeout"},
    },
)
async def chat_completions(
    request: ChatCompletionRequest,
    service: ChatService = Depends(_get_chat_service),
) -> ChatCompletionResponse:
    """
    Unified chat completion endpoint.

    Accepts a provider-agnostic request and returns a normalized response
    regardless of which LLM provider is selected.
    """
    request_id = get_request_id()
    return await service.complete(request, request_id)
