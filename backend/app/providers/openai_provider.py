"""
Cortex Gateway — OpenAI Provider Adapter (Phase 2).

Translates Cortex ChatCompletionRequest → OpenAI API → ChatCompletionResponse.
All OpenAI-specific logic is isolated here; nothing leaks to routes or service.
"""

from __future__ import annotations

import time
from typing import List, Optional

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from app.core.logging import logger
from app.providers.base import BaseLLMProvider
from app.providers.exceptions import (
    InvalidModelError,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.schemas.chat import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessageResponse,
    ResponseMetadata,
    UsageMetadata,
)

# Static fallback model list (used if the API key is missing / list_models fails)
_KNOWN_MODELS: List[str] = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
]


class OpenAIProvider(BaseLLMProvider):
    """
    Provider adapter for OpenAI Chat Completions API.

    Uses the official openai async SDK (AsyncOpenAI).
    Translates Cortex request/response schemas internally.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 30,
    ) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=float(timeout),
        )
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "openai"

    async def chat(
        self,
        request: ChatCompletionRequest,
        request_id: str,
    ) -> ChatCompletionResponse:
        """Execute chat completion via OpenAI and normalize the response."""
        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
        ]

        kwargs: dict = {
            "model": request.model,
            "messages": messages,
        }
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            kwargs["top_p"] = request.top_p
        if request.stop:
            kwargs["stop"] = request.stop

        t_start = time.monotonic()
        try:
            completion = await self._client.chat.completions.create(**kwargs)
        except APITimeoutError as exc:
            raise ProviderTimeoutError(
                "OpenAI request timed out.", details=str(exc)
            ) from exc
        except APIStatusError as exc:
            self._raise_from_status(exc)
        except APIConnectionError as exc:
            raise ProviderUnavailableError(
                "Could not connect to OpenAI.", details=str(exc)
            ) from exc
        except Exception as exc:
            raise ProviderError(
                "Unexpected error from OpenAI.", details=str(exc)
            ) from exc

        latency_ms = (time.monotonic() - t_start) * 1000

        # Normalize usage
        usage = UsageMetadata()
        if completion.usage:
            usage = UsageMetadata(
                prompt_tokens=completion.usage.prompt_tokens,
                completion_tokens=completion.usage.completion_tokens,
                total_tokens=completion.usage.total_tokens,
            )

        choices = [
            ChatCompletionChoice(
                index=c.index,
                message=ChatMessageResponse(
                    content=c.message.content or ""
                ),
                finish_reason=c.finish_reason,
            )
            for c in completion.choices
        ]

        logger.info(
            "OpenAI chat completed",
            request_id=request_id,
            model=request.model,
            latency_ms=round(latency_ms, 2),
            total_tokens=usage.total_tokens,
        )

        return ChatCompletionResponse(
            provider=self.name,
            model=completion.model,
            choices=choices,
            usage=usage,
            metadata=ResponseMetadata(
                request_id=request_id,
                latency_ms=round(latency_ms, 2),
            ),
        )

    async def health_check(self) -> bool:
        """Lightweight health check — list models with a short timeout."""
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        """Fetch available models from OpenAI API."""
        try:
            response = await self._client.models.list()
            return sorted(
                m.id for m in response.data
                if "gpt" in m.id.lower()
            )
        except APIStatusError as exc:
            self._raise_from_status(exc)
        except APITimeoutError as exc:
            raise ProviderTimeoutError(
                "OpenAI model list timed out.", details=str(exc)
            ) from exc
        except Exception as exc:
            raise ProviderUnavailableError(
                "Could not fetch OpenAI models.", details=str(exc)
            ) from exc
        return _KNOWN_MODELS  # unreachable but satisfies type checker

    def _raise_from_status(self, exc: APIStatusError) -> None:
        """Translate OpenAI HTTP status errors into Cortex provider errors."""
        status = exc.status_code
        if status in (401, 403):
            raise ProviderAuthError(
                "OpenAI authentication failed. Check your API key.",
                details=f"HTTP {status}",
            ) from exc
        if status == 429:
            raise ProviderRateLimitError(
                "OpenAI rate limit reached. Please try again later.",
                details=f"HTTP {status}",
            ) from exc
        if status == 404:
            raise InvalidModelError(
                f"Model not found on OpenAI: {exc.message}",
                details=f"HTTP {status}",
            ) from exc
        if status >= 500:
            raise ProviderUnavailableError(
                "OpenAI is currently unavailable.",
                details=f"HTTP {status}",
            ) from exc
        raise ProviderError(
            f"OpenAI returned an error: {exc.message}",
            details=f"HTTP {status}",
        ) from exc
