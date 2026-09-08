"""
Cortex Gateway — Google Gemini Provider Adapter (Phase 2).

Translates Cortex ChatCompletionRequest → Gemini API → ChatCompletionResponse.
Uses the official google-generativeai async SDK.

Gemini-specific terminology mapping (internal only):
    Cortex 'messages'       → Gemini 'contents' with 'parts'
    Cortex 'system' role    → Gemini 'system_instruction'
    Gemini 'usageMetadata'  → Cortex UsageMetadata
        promptTokenCount    → prompt_tokens
        candidatesTokenCount → completion_tokens
        totalTokenCount     → total_tokens
"""

from __future__ import annotations

import time
from typing import List, Optional

import google.generativeai as genai
from google.api_core.exceptions import (
    DeadlineExceeded,
    GoogleAPIError,
    PermissionDenied,
    ResourceExhausted,
    ServiceUnavailable,
    Unauthenticated,
)
from google.generativeai.types import GenerationConfig

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
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]


class GeminiProvider(BaseLLMProvider):
    """
    Provider adapter for Google Gemini API.

    Uses the official google-generativeai SDK configured with an API key.
    Translates Cortex schema to Gemini content format internally.
    """

    def __init__(self, api_key: str, timeout: int = 30) -> None:
        genai.configure(api_key=api_key)
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "gemini"

    async def chat(
        self,
        request: ChatCompletionRequest,
        request_id: str,
    ) -> ChatCompletionResponse:
        """Execute chat completion via Gemini and normalize the response."""
        # Separate system prompt from conversation messages
        system_instruction: Optional[str] = None
        history = []
        last_user_content: Optional[str] = None

        for msg in request.messages:
            if msg.role == "system":
                system_instruction = msg.content
            elif msg.role == "user":
                last_user_content = msg.content
                history.append({"role": "user", "parts": [msg.content]})
            elif msg.role == "assistant":
                history.append({"role": "model", "parts": [msg.content]})

        if last_user_content is None:
            from app.providers.exceptions import ProviderError as PE
            raise PE("At least one user message is required for Gemini.")

        # Build generation config
        gen_config_kwargs: dict = {}
        if request.temperature is not None:
            gen_config_kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            gen_config_kwargs["max_output_tokens"] = request.max_tokens
        if request.top_p is not None:
            gen_config_kwargs["top_p"] = request.top_p
        if request.stop:
            gen_config_kwargs["stop_sequences"] = request.stop

        gen_config = GenerationConfig(**gen_config_kwargs) if gen_config_kwargs else None

        model_kwargs: dict = {"model_name": request.model}
        if system_instruction:
            model_kwargs["system_instruction"] = system_instruction
        if gen_config:
            model_kwargs["generation_config"] = gen_config

        t_start = time.monotonic()
        try:
            model = genai.GenerativeModel(**model_kwargs)
            # Use chat session with history (excluding last user message)
            chat_history = history[:-1]  # all but last user message
            chat = model.start_chat(history=chat_history)
            response = await chat.send_message_async(last_user_content)
        except DeadlineExceeded as exc:
            raise ProviderTimeoutError(
                "Gemini request timed out.", details=str(exc)
            ) from exc
        except (Unauthenticated, PermissionDenied) as exc:
            raise ProviderAuthError(
                "Gemini authentication failed. Check your API key.",
                details=type(exc).__name__,
            ) from exc
        except ResourceExhausted as exc:
            raise ProviderRateLimitError(
                "Gemini rate limit reached. Please try again later.",
                details=str(exc),
            ) from exc
        except ServiceUnavailable as exc:
            raise ProviderUnavailableError(
                "Gemini is currently unavailable.", details=str(exc)
            ) from exc
        except GoogleAPIError as exc:
            msg = str(exc)
            if "not found" in msg.lower() or "invalid" in msg.lower():
                raise InvalidModelError(
                    f"Gemini model not found: {request.model}",
                    details=msg,
                ) from exc
            raise ProviderError(
                "Gemini returned an error.", details=msg
            ) from exc
        except Exception as exc:
            raise ProviderError(
                "Unexpected error from Gemini.", details=str(exc)
            ) from exc

        latency_ms = (time.monotonic() - t_start) * 1000

        # Extract text content
        content = ""
        try:
            content = response.text
        except Exception:
            # response.text raises if blocked — handle gracefully
            content = ""

        # Normalize usage (Gemini uses different field names)
        usage = UsageMetadata()
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            usage = UsageMetadata(
                prompt_tokens=getattr(um, "prompt_token_count", None),
                completion_tokens=getattr(um, "candidates_token_count", None),
                total_tokens=getattr(um, "total_token_count", None),
            )

        # Normalize finish reason
        finish_reason: Optional[str] = None
        try:
            if response.candidates:
                finish_reason = str(response.candidates[0].finish_reason.name).lower()
        except Exception:
            pass

        logger.info(
            "Gemini chat completed",
            request_id=request_id,
            model=request.model,
            latency_ms=round(latency_ms, 2),
            total_tokens=usage.total_tokens,
        )

        return ChatCompletionResponse(
            provider=self.name,
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessageResponse(content=content),
                    finish_reason=finish_reason,
                )
            ],
            usage=usage,
            metadata=ResponseMetadata(
                request_id=request_id,
                latency_ms=round(latency_ms, 2),
            ),
        )

    async def health_check(self) -> bool:
        """Lightweight health check — attempt to list models."""
        try:
            models = [m async for m in await genai.list_models_async()]  # type: ignore[attr-defined]
            return len(models) > 0
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        """Fetch available Gemini models."""
        try:
            models = genai.list_models()
            return sorted(
                m.name.replace("models/", "")
                for m in models
                if "generateContent" in (m.supported_generation_methods or [])
                and "gemini" in m.name.lower()
            )
        except (Unauthenticated, PermissionDenied) as exc:
            raise ProviderAuthError(
                "Gemini authentication failed. Check your API key.",
                details=type(exc).__name__,
            ) from exc
        except Exception:
            # Return known list on any failure
            return _KNOWN_MODELS
