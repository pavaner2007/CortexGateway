"""
Cortex Gateway — Ollama Embedding Client (Phase 9B).

Calls Ollama POST /api/embed to generate text embeddings for semantic caching.

Design rules:
  - Does NOT subclass OllamaProvider (different API contract).
  - Reuses settings.ollama_base_url and settings.ollama_timeout_seconds.
  - If Ollama is unreachable or the model is not installed, raises EmbeddingError.
  - Callers must catch EmbeddingError and treat it as a cache miss.
  - Never logs prompt content.
  - Configured model must be pulled by the operator; no auto-download.
"""

from __future__ import annotations

from typing import List

import httpx

from app.core.logging import logger
from app.semantic_cache.exceptions import EmbeddingError


class OllamaEmbeddingClient:
    """
    HTTP client for Ollama's embedding endpoint.

    Usage::

        client = OllamaEmbeddingClient(
            base_url="http://localhost:11434",
            model="nomic-embed-text",
            timeout=30,
        )
        vector = await client.embed("some text")
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: int = 30,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = float(timeout)

    @property
    def model(self) -> str:
        return self._model

    async def embed(self, text: str) -> List[float]:
        """
        Generate an embedding vector for the given text.

        Args:
            text: The text to embed. Must not be empty.

        Returns:
            List[float] — the embedding vector.

        Raises:
            EmbeddingError: if Ollama is unreachable, the model is missing,
                            or the response is malformed.
        """
        if not text or not text.strip():
            raise EmbeddingError("Cannot embed empty text.")

        endpoint = f"{self._base_url}/api/embed"
        payload = {"model": self._model, "input": text}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(endpoint, json=payload)
        except httpx.TimeoutException as exc:
            raise EmbeddingError(
                f"Ollama embedding request timed out (model={self._model!r})."
            ) from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise EmbeddingError(
                f"Could not connect to Ollama for embeddings (model={self._model!r}). "
                "Ensure Ollama is running and the model is pulled."
            ) from exc
        except Exception as exc:
            raise EmbeddingError(
                f"Unexpected error contacting Ollama embedding endpoint: {exc}"
            ) from exc

        if response.status_code == 404:
            raise EmbeddingError(
                f"Embedding model {self._model!r} not found in Ollama. "
                f"Run: ollama pull {self._model}"
            )

        if response.status_code != 200:
            raise EmbeddingError(
                f"Ollama embedding endpoint returned HTTP {response.status_code}."
            )

        try:
            data = response.json()
            # Ollama ≥0.1.26: {"embeddings": [[...], ...]}
            embeddings = data.get("embeddings")
            if embeddings and isinstance(embeddings, list) and embeddings[0]:
                return [float(x) for x in embeddings[0]]

            # Older Ollama: {"embedding": [...]}
            embedding = data.get("embedding")
            if embedding and isinstance(embedding, list):
                return [float(x) for x in embedding]

            raise EmbeddingError(
                f"Unexpected embedding response structure from Ollama: {list(data.keys())}"
            )
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(
                f"Failed to parse Ollama embedding response: {exc}"
            ) from exc

        # Log the successful embedding (dimension only — no text content)
        logger.debug(
            "Embedding generated",
            model=self._model,
            dimensions=len(embeddings[0]) if embeddings else 0,
        )
