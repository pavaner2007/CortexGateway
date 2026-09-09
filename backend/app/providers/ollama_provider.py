"""
Cortex Gateway — Ollama Provider Adapter (Phase 2 Update).

Ollama is a local / self-hosted LLM runtime that serves models over HTTP.
Translates Cortex ChatCompletionRequest → Ollama REST API → ChatCompletionResponse.

Uses asynchronous HTTP communication (httpx.AsyncClient) — no blocking I/O.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import httpx

from app.core.logging import logger
from app.providers.base import BaseLLMProvider
from app.providers.exceptions import (
    InvalidModelError,
    ProviderError,
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


class OllamaProvider(BaseLLMProvider):
    """
    Provider adapter for local/self-hosted Ollama runtime.

    Communicates with Ollama's HTTP API:
      - Chat completions: POST /api/chat
      - Model listing:    GET  /api/tags
      - Health check:     GET  /api/version

    Zero provider API keys required.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        timeout: int = 60,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def base_url(self) -> str:
        return self._base_url

    async def chat(
        self,
        request: ChatCompletionRequest,
        request_id: str,
    ) -> ChatCompletionResponse:
        """
        Execute chat completion via Ollama HTTP API and normalize response.

        Ollama /api/chat payload:
        {
          "model": "llama3.2",
          "messages": [{"role": "user", "content": "..."}],
          "stream": false,
          "options": {
            "temperature": 0.7,
            "top_p": 0.9,
            "num_predict": 500,
            "stop": ["..."]
          }
        }
        """
        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
        ]

        options: Dict[str, Any] = {}
        if request.temperature is not None:
            options["temperature"] = request.temperature
        if request.top_p is not None:
            options["top_p"] = request.top_p
        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens
        if request.stop:
            options["stop"] = request.stop

        payload: Dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "stream": False,
        }
        if options:
            payload["options"] = options

        endpoint = f"{self._base_url}/api/chat"
        t_start = time.monotonic()

        try:
            async with httpx.AsyncClient(timeout=float(self._timeout)) as client:
                response = await client.post(endpoint, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                "Ollama request timed out.",
                details=str(exc),
            ) from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise ProviderUnavailableError(
                "Could not connect to Ollama service. Ensure Ollama is running.",
                details=str(exc),
            ) from exc
        except Exception as exc:
            raise ProviderError(
                "Unexpected error communicating with Ollama.",
                details=str(exc),
            ) from exc

        latency_ms = (time.monotonic() - t_start) * 1000

        # Handle HTTP error statuses
        if response.status_code != 200:
            self._handle_http_error(response, request.model)

        data = response.json()
        message_data = data.get("message", {})
        content = message_data.get("content", "")
        finish_reason = data.get("done_reason") or ("stop" if data.get("done") else None)

        # Token usage evaluation counts
        prompt_tokens: Optional[int] = data.get("prompt_eval_count")
        completion_tokens: Optional[int] = data.get("eval_count")
        total_tokens: Optional[int] = None
        if prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens

        usage = UsageMetadata(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

        choices = [
            ChatCompletionChoice(
                index=0,
                message=ChatMessageResponse(content=content),
                finish_reason=finish_reason,
            )
        ]

        logger.info(
            "Ollama chat completed",
            request_id=request_id,
            model=request.model,
            latency_ms=round(latency_ms, 2),
            total_tokens=usage.total_tokens,
        )

        return ChatCompletionResponse(
            provider=self.name,
            model=data.get("model", request.model),
            choices=choices,
            usage=usage,
            metadata=ResponseMetadata(
                request_id=request_id,
                latency_ms=round(latency_ms, 2),
            ),
        )

    async def health_check(self) -> bool:
        """
        Perform a lightweight ping to Ollama.

        Returns True if reachable and HTTP 200 returned.
        Must NOT raise exceptions.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self._base_url}/api/version")
                return res.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        """
        Fetch installed models dynamically from Ollama GET /api/tags.

        Returns:
            List of model names available in the local Ollama instance.
        """
        try:
            async with httpx.AsyncClient(timeout=float(self._timeout)) as client:
                res = await client.get(f"{self._base_url}/api/tags")
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                "Ollama model list request timed out.",
                details=str(exc),
            ) from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise ProviderUnavailableError(
                "Could not connect to Ollama service to fetch models.",
                details=str(exc),
            ) from exc
        except Exception as exc:
            raise ProviderError(
                "Unexpected error fetching Ollama models.",
                details=str(exc),
            ) from exc

        if res.status_code != 200:
            raise ProviderUnavailableError(
                f"Ollama returned HTTP {res.status_code} while fetching models.",
                details=res.text,
            )

        data = res.json()
        models = [m.get("name") for m in data.get("models", []) if m.get("name")]
        return sorted(models)

    def _handle_http_error(self, response: httpx.Response, requested_model: str) -> None:
        """Map Ollama HTTP error responses to typed Cortex exceptions."""
        status = response.status_code
        body = response.text
        try:
            error_msg = response.json().get("error", body)
        except Exception:
            error_msg = body

        if status == 404:
            # Model not found or endpoint not found
            if "model" in error_msg.lower() or "not found" in error_msg.lower():
                raise InvalidModelError(
                    f"Model '{requested_model}' not found in Ollama.",
                    details=error_msg,
                )
            raise ProviderUnavailableError(
                f"Ollama endpoint not found (HTTP {status}).",
                details=error_msg,
            )
        if status >= 500:
            raise ProviderUnavailableError(
                f"Ollama service returned server error (HTTP {status}).",
                details=error_msg,
            )
        raise ProviderError(
            f"Ollama returned HTTP {status}: {error_msg}",
            details=error_msg,
        )
