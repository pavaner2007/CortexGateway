"""
Cortex Gateway — Semantic Cache (Phase 9B).

Architecture:
  - Redis-backed per-team bounded candidate set.
  - Cosine similarity comparison over the team's embedding index.
  - Fully non-blocking: all failures (embedding, Redis) are treated as cache misses.
  - Team isolation enforced via authenticated team_id in Redis key namespace.
  - Caching is an optimization only — it never blocks a chat completion.

Redis key structure:
  semantic_cache:<version>:team:<team_id>:index
      → Redis List of entry UUIDs (capped at max_entries_per_team)
  semantic_cache:<version>:team:<team_id>:entry:<uuid>
      → Redis Hash with fields: embedding, response_json, provider, model,
                                config_hash, created_at

Security:
  - team_id is always taken from RequestContext (server-authenticated).
  - No prompt text, API keys, or secrets stored in Redis.
  - Entry IDs are random UUIDs — not derived from prompt content.

Eviction:
  - Per-entry TTL via Redis EXPIRE (primary expiration mechanism).
  - Oldest-first eviction via LTRIM when index exceeds max_entries_per_team.
  - No separate cleanup scheduler needed.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from redis.asyncio import Redis

from app.core.logging import logger
from app.schemas.chat import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessageResponse,
    ResponseMetadata,
    UsageMetadata,
)
from app.semantic_cache.embedding import OllamaEmbeddingClient
from app.semantic_cache.exceptions import EmbeddingError
from app.semantic_cache.similarity import (
    build_config_hash,
    cosine_similarity,
    extract_embedding_text,
)

if TYPE_CHECKING:
    from app.auth.schemas import RequestContext


class SemanticCache:
    """
    Semantic cache backed by Redis.

    Usage::

        cache = SemanticCache(redis=redis_client, settings=settings)

        # On incoming request (after rate limiting, before budget reservation):
        result = await cache.lookup(request, context)
        if result is not None:
            return result  # cache hit — skip routing + provider

        # After successful provider response:
        await cache.store(request, context, response)  # non-blocking background
    """

    def __init__(
        self,
        *,
        redis: Redis | None,
        enabled: bool = False,
        version: str = "v1",
        ttl_seconds: int = 3600,
        similarity_threshold: float = 0.92,
        max_entries_per_team: int = 500,
        embedding_client: OllamaEmbeddingClient | None = None,
    ) -> None:
        self._redis = redis
        self._enabled = enabled
        self._version = version
        self._ttl = ttl_seconds
        self._threshold = similarity_threshold
        self._max_entries = max_entries_per_team
        self._embedding_client = embedding_client

    # ── Key helpers ──────────────────────────────────────────────────────────

    def _index_key(self, team_id: str) -> str:
        return f"semantic_cache:{self._version}:team:{team_id}:index"

    def _entry_key(self, team_id: str, entry_id: str) -> str:
        return f"semantic_cache:{self._version}:team:{team_id}:entry:{entry_id}"

    def _disabled_key(self, team_id: str) -> str:
        """Redis key set (value irrelevant) when caching is disabled for a team."""
        return f"semantic_cache:{self._version}:team:{team_id}:disabled"

    # ── Eligibility ──────────────────────────────────────────────────────────

    def _is_eligible(self, request: ChatCompletionRequest) -> bool:
        """
        Return True only for requests that are safe to cache.

        Ineligible:
          - Streaming requests (stream=True)
          - Requests with no user message (nothing to embed meaningfully)
        """
        if request.stream:
            return False
        # Must have at least one user message
        has_user_msg = any(m.role == "user" for m in request.messages)
        return has_user_msg

    async def _is_team_disabled(self, team_id: str) -> bool:
        """Check per-team disable flag stored in Redis."""
        if not self._redis:
            return False
        try:
            result = await self._redis.exists(self._disabled_key(team_id))
            return bool(result)
        except Exception:
            return False

    # ── Embedding ────────────────────────────────────────────────────────────

    async def _get_embedding(self, text: str) -> list[float]:
        """Generate embedding via configured provider. Raises EmbeddingError on failure."""
        if self._embedding_client is None:
            raise EmbeddingError("No embedding client configured.")
        return await self._embedding_client.embed(text)

    # ── Cache Lookup ─────────────────────────────────────────────────────────

    async def lookup(
        self,
        request: ChatCompletionRequest,
        context: RequestContext,
    ) -> ChatCompletionResponse | None:
        """
        Attempt a semantic cache lookup.

        Returns:
            ChatCompletionResponse — if a semantically similar cached response exists.
            None                   — on any miss, failure, or disabled state.

        This method is fully non-fatal: any exception is caught, logged, and
        returns None (treating all errors as cache misses).
        """
        if not self._enabled:
            return None
        if not self._is_eligible(request):
            return None

        team_id = context.team_id
        if not team_id:
            return None

        try:
            if await self._is_team_disabled(team_id):
                logger.debug(
                    "Semantic cache disabled for team (per-team flag)",
                    team_id=team_id,
                )
                return None
        except Exception:
            pass

        if (redis := self._redis) is None:
            return None
        # redis is narrowed to Redis (non-optional) from here onward

        # ── Generate query embedding ───────────────────────────────────────
        text = extract_embedding_text(request)
        try:
            query_embedding = await self._get_embedding(text)
        except EmbeddingError as exc:
            logger.warning(
                "Semantic cache: embedding generation failed — treating as miss",
                reason=str(exc),
                team_id=team_id,
            )
            return None

        config_hash = build_config_hash(request)

        # ── Scan candidate entries ───────────────────────────────────────
        try:
            index_key = self._index_key(team_id)
            entry_ids = await redis.lrange(index_key, 0, -1)  # type: ignore[misc]
        except Exception as exc:
            logger.warning(
                "Semantic cache: Redis index read failed — treating as miss",
                error=str(exc),
                team_id=team_id,
            )
            return None

        best_similarity = -1.0
        best_entry_data: dict | None = None

        for entry_id in entry_ids:
            entry_key = self._entry_key(team_id, entry_id)
            try:
                raw = await redis.hgetall(entry_key)  # type: ignore[misc]
            except Exception:
                continue  # stale or deleted entry — skip

            if not raw:
                # Entry expired or was evicted
                continue

            # Config hash must match — different response-affecting params → miss
            if raw.get("config_hash") != config_hash:
                continue

            # Parse stored embedding
            try:
                stored_embedding = json.loads(raw["embedding"])
            except (KeyError, json.JSONDecodeError):
                continue

            sim = cosine_similarity(query_embedding, stored_embedding)

            if sim > best_similarity:
                best_similarity = sim
                if sim >= self._threshold:
                    best_entry_data = raw

        if best_entry_data is None or best_similarity < self._threshold:
            logger.debug(
                "Semantic cache: miss",
                team_id=team_id,
                best_similarity=round(best_similarity, 4),
                threshold=self._threshold,
                candidates=len(entry_ids),
            )
            return None

        # ── Reconstruct cached response ──────────────────────────────────────
        try:
            response = self._deserialize_response(
                best_entry_data, request_id=context.request_id or str(uuid.uuid4())
            )
        except Exception as exc:
            logger.warning(
                "Semantic cache: failed to deserialize cached response — treating as miss",
                error=str(exc),
                team_id=team_id,
            )
            return None

        logger.info(
            "Semantic cache: HIT",
            team_id=team_id,
            similarity=round(best_similarity, 4),
            cached_provider=best_entry_data.get("provider"),
            cached_model=best_entry_data.get("model"),
        )

        return response

    # ── Cache Store ──────────────────────────────────────────────────────────

    async def store(
        self,
        request: ChatCompletionRequest,
        context: RequestContext,
        response: ChatCompletionResponse,
    ) -> None:
        """
        Store a successful provider response in the semantic cache.

        This method is designed to be called as a background task.
        Any failure is logged and silently ignored — it must never
        affect the user's response.

        Only successful, cache-eligible responses are stored.
        """
        if not self._enabled:
            return
        if not self._is_eligible(request):
            return

        team_id = context.team_id
        if not team_id:
            return

        try:
            if await self._is_team_disabled(team_id):
                return
        except Exception:
            return

        if not self._redis:
            return

        # Generate embedding for the stored entry
        text = extract_embedding_text(request)
        try:
            embedding = await self._get_embedding(text)
        except EmbeddingError as exc:
            logger.warning(
                "Semantic cache: embedding failed during store — skipping cache write",
                reason=str(exc),
                team_id=team_id,
            )
            return

        config_hash = build_config_hash(request)
        entry_id = str(uuid.uuid4())

        try:
            response_json = self._serialize_response(response)
        except Exception as exc:
            logger.warning(
                "Semantic cache: failed to serialize response — skipping cache write",
                error=str(exc),
                team_id=team_id,
            )
            return

        entry_key = self._entry_key(team_id, entry_id)
        index_key = self._index_key(team_id)

        try:
            pipe = self._redis.pipeline()
            pipe.hset(
                entry_key,
                mapping={
                    "embedding": json.dumps(embedding),
                    "response_json": response_json,
                    "provider": response.provider or "",
                    "model": response.model or "",
                    "config_hash": config_hash,
                    "created_at": datetime.now(UTC).isoformat(),
                },
            )
            pipe.expire(entry_key, self._ttl)
            # Add to team index and enforce bounded size (oldest evicted via LTRIM)
            pipe.lpush(index_key, entry_id)
            pipe.ltrim(index_key, 0, self._max_entries - 1)
            await pipe.execute()

            logger.debug(
                "Semantic cache: entry stored",
                team_id=team_id,
                entry_id=entry_id,
                provider=response.provider,
                model=response.model,
                ttl=self._ttl,
            )

        except Exception as exc:
            logger.warning(
                "Semantic cache: Redis write failed — provider response still returned",
                error=str(exc),
                team_id=team_id,
            )

    # ── Team enable/disable ──────────────────────────────────────────────────

    async def disable_for_team(self, team_id: str) -> None:
        """Set the per-team disable flag in Redis."""
        if not self._redis:
            return
        try:
            await self._redis.set(self._disabled_key(team_id), "1")
        except Exception as exc:
            logger.warning("Semantic cache: could not set team disable flag", error=str(exc))

    async def enable_for_team(self, team_id: str) -> None:
        """Clear the per-team disable flag in Redis."""
        if not self._redis:
            return
        try:
            await self._redis.delete(self._disabled_key(team_id))
        except Exception as exc:
            logger.warning("Semantic cache: could not clear team disable flag", error=str(exc))

    # ── Serialization ────────────────────────────────────────────────────────

    @staticmethod
    def _serialize_response(response: ChatCompletionResponse) -> str:
        """Serialize normalized response to JSON for Redis storage."""
        data = {
            "provider": response.provider,
            "model": response.model,
            "choices": [
                {
                    "index": c.index,
                    "message": {"role": c.message.role, "content": c.message.content},
                    "finish_reason": c.finish_reason,
                }
                for c in response.choices
            ],
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }
        return json.dumps(data)

    @staticmethod
    def _deserialize_response(
        raw: dict,
        request_id: str,
    ) -> ChatCompletionResponse:
        """Reconstruct a ChatCompletionResponse from a Redis hash entry."""
        data = json.loads(raw["response_json"])

        choices = [
            ChatCompletionChoice(
                index=c["index"],
                message=ChatMessageResponse(
                    role=c["message"]["role"],
                    content=c["message"]["content"],
                ),
                finish_reason=c.get("finish_reason"),
            )
            for c in data["choices"]
        ]

        usage_data = data.get("usage", {})
        usage = UsageMetadata(
            prompt_tokens=usage_data.get("prompt_tokens"),
            completion_tokens=usage_data.get("completion_tokens"),
            total_tokens=usage_data.get("total_tokens"),
        )

        return ChatCompletionResponse(
            provider=data["provider"],
            model=data["model"],
            choices=choices,
            usage=usage,
            metadata=ResponseMetadata(
                request_id=request_id,
                latency_ms=0.0,  # Cache lookup latency is measured at endpoint level
                routing_mode=None,
                selected_provider=data["provider"],
                selected_model=data["model"],
                cache_hit=True,
                # All cost fields zero — no provider invocation
                estimated_cost=0.0,
                actual_cost=0.0,
            ),
        )


def build_semantic_cache(
    redis: Redis | None,
    settings,  # Settings instance
) -> SemanticCache:
    """
    Factory: construct a SemanticCache from settings.

    Called once during application startup. The returned instance is
    injected into the request pipeline via FastAPI dependency.
    """
    from app.semantic_cache.embedding import OllamaEmbeddingClient

    embedding_client: OllamaEmbeddingClient | None = None

    if settings.semantic_cache_enabled:
        provider = getattr(settings, "semantic_cache_embedding_provider", "ollama").lower()
        model = getattr(settings, "semantic_cache_embedding_model", "nomic-embed-text")

        if provider == "ollama":
            embedding_client = OllamaEmbeddingClient(
                base_url=settings.ollama_base_url,
                model=model,
                timeout=settings.ollama_timeout_seconds,
            )
        else:
            logger.warning(
                "Semantic cache: unsupported embedding provider — cache disabled",
                provider=provider,
            )

    return SemanticCache(
        redis=redis,
        enabled=settings.semantic_cache_enabled,
        version=settings.semantic_cache_version,
        ttl_seconds=settings.semantic_cache_ttl_seconds,
        similarity_threshold=settings.semantic_cache_similarity_threshold,
        max_entries_per_team=settings.semantic_cache_max_entries_per_team,
        embedding_client=embedding_client,
    )
