"""
Cortex Gateway — Base LLM Provider Interface (Phase 2).

All provider adapters must implement BaseLLMProvider.
This ABC is the single contract that:
  - Chat routes depend on (via ChatService)
  - The ProviderRegistry stores
  - Tests mock

Adding a new provider requires:
  1. Subclass BaseLLMProvider
  2. Implement all abstract methods
  3. Register in ProviderRegistry during lifespan startup

No other files (routes, services, registry) need modification.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse


class BaseLLMProvider(ABC):
    """
    Abstract base class for all LLM provider adapters.

    Implementations are required to:
    - Be fully asynchronous (no blocking I/O in async methods).
    - Transform Cortex requests to provider-specific payloads internally.
    - Return Cortex-normalized responses (never provider-specific structures).
    - Translate provider errors into ProviderException subclasses.
    - Measure and report provider latency in milliseconds.
    - Never log or expose API keys.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Canonical lowercase provider name (e.g. 'openai', 'groq')."""
        ...

    @abstractmethod
    async def chat(
        self,
        request: ChatCompletionRequest,
        request_id: str,
    ) -> ChatCompletionResponse:
        """
        Execute a chat completion request and return a normalized response.

        Args:
            request:    Validated Cortex chat completion request.
            request_id: Current request ID from middleware (for logging + metadata).

        Returns:
            ChatCompletionResponse with all fields normalized to Cortex schema.

        Raises:
            ProviderTimeoutError: Provider request timed out.
            ProviderRateLimitError: Provider rate limit hit.
            ProviderAuthError: Invalid or missing API key.
            ProviderUnavailableError: Provider service unavailable.
            InvalidModelError: Model not recognized by provider.
            ProviderError: Any other unclassified upstream error.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Perform a lightweight provider health check.

        Returns True when the provider is reachable and operational.
        Must NOT raise — return False on any failure.
        Must NOT make expensive calls (prefer a lightweight ping or model list).
        """
        ...

    @abstractmethod
    async def list_models(self) -> List[str]:
        """
        Return the list of model identifiers available from this provider.

        Returns:
            List of model ID strings (e.g. ['gpt-4o', 'gpt-4o-mini']).

        Raises:
            ProviderUnavailableError: If model list cannot be fetched.
            ProviderAuthError: If authentication fails during model fetch.
        """
        ...
