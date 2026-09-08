"""
Cortex Gateway — Chat Service (Phase 2).

Orchestrates the chat completion flow:
    Chat API → ChatService → ProviderRegistry → Provider Adapter

ChatService responsibilities:
  1. Receive a validated ChatCompletionRequest.
  2. Resolve the provider from the registry.
  3. Delegate the request to the provider adapter.
  4. Return the normalized ChatCompletionResponse.

ChatService does NOT contain:
  - Provider-specific HTTP/API logic.
  - Response parsing logic.
  - Request transformation logic.

Those belong exclusively in provider adapters.
"""

from __future__ import annotations

from app.core.logging import logger
from app.providers.registry import ProviderRegistry
from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse


class ChatService:
    """
    Application-layer service for chat completions.

    Thin orchestration layer — resolves provider from registry and delegates.
    """

    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry

    async def complete(
        self,
        request: ChatCompletionRequest,
        request_id: str,
    ) -> ChatCompletionResponse:
        """
        Execute a chat completion using the requested provider.

        Args:
            request:    Validated Cortex chat completion request.
            request_id: Current request ID from middleware.

        Returns:
            Normalized ChatCompletionResponse.

        Raises:
            InvalidProviderError: Provider is not registered/available.
            Any ProviderException subclass from the adapter.
        """
        logger.info(
            "Chat completion requested",
            request_id=request_id,
            provider=request.provider,
            model=request.model,
            message_count=len(request.messages),
        )

        provider = self._registry.get(request.provider)
        response = await provider.chat(request, request_id)

        logger.info(
            "Chat completion fulfilled",
            request_id=request_id,
            provider=request.provider,
            model=response.model,
            latency_ms=response.metadata.latency_ms,
        )

        return response
