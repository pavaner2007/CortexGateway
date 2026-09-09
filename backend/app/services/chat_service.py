"""
Cortex Gateway — Chat Service (Phase 4).

Orchestrates the chat completion flow:
    Chat API → ChatService → RoutingEngine → ReliabilityExecutor → ProviderRegistry → Provider Adapter

ChatService responsibilities:
  1. Receive a validated ChatCompletionRequest.
  2. If manual routing, select specified provider and model.
  3. If intelligent routing, query RoutingEngine to select optimal (provider, model).
  4. Delegate execution to ReliabilityExecutor (deadlines, circuit breakers, retries, failovers).
  5. Return the normalized ChatCompletionResponse with reliability metadata.
"""

from __future__ import annotations

from typing import Optional

from app.core.logging import logger
from app.providers.registry import ProviderRegistry
from app.reliability.executor import ReliabilityExecutor
from app.routing.router import RoutingEngine
from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse


class ChatService:
    """
    Application-layer service for chat completions.

    Orchestrates routing selection, reliability resilience, and runtime stats tracking.
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
    ) -> ChatCompletionResponse:
        """
        Execute a chat completion using manual or intelligent routing with reliability.

        Args:
            request:    Validated Cortex chat completion request.
            request_id: Current request ID from middleware.

        Returns:
            Normalized ChatCompletionResponse.

        Raises:
            InvalidProviderError: Provider not registered.
            InvalidManualRoutingError: Manual routing missing parameters.
            NoRoutableProviderError: No available provider for routing.
            NoCapableProviderError: No provider supports required capabilities.
            Any ProviderException subclass from the adapter or reliability engine.
        """
        # Determine routing path
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
            # Intelligent routing engine evaluation
            decision = await self._routing_engine.route(request)
            target_provider_name = decision.provider
            target_model_name = decision.model
            effective_routing_mode = decision.routing_mode

        logger.info(
            "Chat completion routing resolved",
            request_id=request_id,
            routing_mode=effective_routing_mode,
            target_provider=target_provider_name,
            target_model=target_model_name,
            message_count=len(request.messages),
        )

        # Delegate execution to ReliabilityExecutor
        return await self._reliability_executor.execute(
            request=request,
            request_id=request_id,
            initial_provider=target_provider_name,
            initial_model=target_model_name,
            routing_mode=effective_routing_mode,
        )
