"""
Cortex Gateway — Groq Provider Adapter (Phase 2).

Groq uses an OpenAI-compatible API, so we use the official Groq async SDK.
Translates Cortex ChatCompletionRequest → Groq API → ChatCompletionResponse.
"""

from __future__ import annotations

import time
from typing import List

from groq import APIConnectionError, APIStatusError, APITimeoutError, AsyncGroq

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

_KNOWN_MODELS: List[str] = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "llama3-8b-8192",
    "llama3-70b-8192",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]


class GroqProvider(BaseLLMProvider):
    """
    Provider adapter for Groq Chat Completions API.

    Uses the official groq async SDK (AsyncGroq).
    Groq's API is OpenAI-compatible, making normalization straightforward.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.groq.com/openai/v1",
        timeout: int = 30,
    ) -> None:
        self._client = AsyncGroq(
            api_key=api_key,
            timeout=float(timeout),
        )
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "groq"

    async def chat(
        self,
        request: ChatCompletionRequest,
        request_id: str,
    ) -> ChatCompletionResponse:
        """Execute chat completion via Groq and normalize the response."""
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
                "Groq request timed out.", details=str(exc)
            ) from exc
        except APIStatusError as exc:
            self._raise_from_status(exc)
        except APIConnectionError as exc:
            raise ProviderUnavailableError(
                "Could not connect to Groq.", details=str(exc)
            ) from exc
        except Exception as exc:
            raise ProviderError(
                "Unexpected error from Groq.", details=str(exc)
            ) from exc

        latency_ms = (time.monotonic() - t_start) * 1000

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
            "Groq chat completed",
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
        """Lightweight health check via model list."""
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        """Fetch available models from Groq API."""
        try:
            response = await self._client.models.list()
            return sorted(m.id for m in response.data)
        except APIStatusError as exc:
            self._raise_from_status(exc)
        except APITimeoutError as exc:
            raise ProviderTimeoutError(
                "Groq model list timed out.", details=str(exc)
            ) from exc
        except Exception:
            # Groq API key exists but model list failed — return known list
            return _KNOWN_MODELS

    def _raise_from_status(self, exc: APIStatusError) -> None:
        """Translate Groq HTTP status errors into Cortex provider errors."""
        status = exc.status_code
        if status in (401, 403):
            raise ProviderAuthError(
                "Groq authentication failed. Check your API key.",
                details=f"HTTP {status}",
            ) from exc
        if status == 429:
            raise ProviderRateLimitError(
                "Groq rate limit reached. Please try again later.",
                details=f"HTTP {status}",
            ) from exc
        if status == 404:
            raise InvalidModelError(
                f"Model not found on Groq: {exc.message}",
                details=f"HTTP {status}",
            ) from exc
        if status >= 500:
            raise ProviderUnavailableError(
                "Groq is currently unavailable.",
                details=f"HTTP {status}",
            ) from exc
        raise ProviderError(
            f"Groq returned an error: {exc.message}",
            details=f"HTTP {status}",
        ) from exc
