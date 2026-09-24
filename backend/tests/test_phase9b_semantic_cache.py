"""
Cortex Gateway — Phase 9B Semantic Cache Tests.

Test coverage:
  TC01 - Similar prompt → cache hit (high similarity)
  TC02 - Dissimilar prompt → cache miss (low similarity)
  TC03 - Threshold boundary: equality → hit; below → miss
  TC04 - Cache disabled globally → embedding never called
  TC05 - Streaming request → cache bypass
  TC06 - No user message → cache bypass (not eligible)
  TC07 - Team isolation: Team A's entry NOT visible to Team B
  TC08 - Per-team disable flag → bypass for that team, other team unaffected
  TC09 - Embedding failure → cache miss, no exception raised
  TC10 - Redis write failure → no exception, store failure logged
  TC11 - Config hash mismatch → cache miss (different temperature)
  TC12 - Cache hit: cache_hit=True in response metadata
  TC13 - Cache miss: cache_hit=False in response metadata (default)
  TC14 - cosine_similarity: identical vectors → 1.0
  TC15 - cosine_similarity: zero vector → 0.0
  TC16 - cosine_similarity: length mismatch → 0.0
  TC17 - extract_embedding_text: returns last user message
  TC18 - build_config_hash: same params → same hash; different → different
  TC19 - OllamaEmbeddingClient: parses new-format response {embeddings: [[...]]}
  TC20 - OllamaEmbeddingClient: parses old-format response {embedding: [...]}
  TC21 - OllamaEmbeddingClient: 404 → EmbeddingError with helpful message
  TC22 - OllamaEmbeddingClient: empty text → EmbeddingError
  TC23 - SemanticCache.lookup: Redis index read failure → returns None
  TC24 - SemanticCache.store: eviction via LTRIM on full index
  TC25 - build_semantic_cache: disabled → SemanticCache with enabled=False
"""

from __future__ import annotations

import json
import math
import uuid
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.schemas.chat import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ChatMessageResponse,
    ResponseMetadata,
    UsageMetadata,
)
from app.semantic_cache.cache import SemanticCache, build_semantic_cache
from app.semantic_cache.embedding import OllamaEmbeddingClient
from app.semantic_cache.exceptions import EmbeddingError
from app.semantic_cache.similarity import (
    build_config_hash,
    cosine_similarity,
    extract_embedding_text,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_request(
    user_msg: str = "What is the capital of France?",
    temperature: float | None = None,
    max_tokens: int | None = None,
    system_msg: str | None = None,
    stream: bool | None = False,
) -> ChatCompletionRequest:
    messages = []
    if system_msg:
        messages.append(ChatMessage(role="system", content=system_msg))
    messages.append(ChatMessage(role="user", content=user_msg))
    return ChatCompletionRequest(
        model="llama3.2",
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=stream,
    )


def _make_response(content: str = "Paris") -> ChatCompletionResponse:
    return ChatCompletionResponse(
        provider="ollama",
        model="llama3.2",
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessageResponse(role="assistant", content=content),
                finish_reason="stop",
            )
        ],
        usage=UsageMetadata(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        metadata=ResponseMetadata(
            request_id="test-req-id",
            latency_ms=100.0,
            selected_provider="ollama",
            selected_model="llama3.2",
        ),
    )


def _make_context(team_id: str = "team-123", request_id: str = "req-abc") -> MagicMock:
    ctx = MagicMock()
    ctx.team_id = team_id
    ctx.organization_id = "org-456"
    ctx.api_key_id = "key-789"
    ctx.request_id = request_id
    return ctx


def _unit_vector(dim: int, index: int = 0) -> list[float]:
    """Return a unit vector with 1.0 at position index, 0.0 elsewhere."""
    v = [0.0] * dim
    v[index] = 1.0
    return v


def _norm_vector(*values: float) -> list[float]:
    """Return the L2-normalized form of a list of floats."""
    magnitude = math.sqrt(sum(x * x for x in values))
    if magnitude == 0:
        return list(values)
    return [x / magnitude for x in values]


def _make_redis_hash(
    embedding: list[float],
    response: ChatCompletionResponse,
    config_hash: str,
) -> dict:
    """Build a fake Redis hash entry dict as SemanticCache would store it."""
    return {
        "embedding": json.dumps(embedding),
        "response_json": SemanticCache._serialize_response(response),
        "provider": response.provider,
        "model": response.model,
        "config_hash": config_hash,
        "created_at": "2026-09-19T12:00:00+00:00",
    }


def _make_cache(
    enabled: bool = True,
    threshold: float = 0.92,
    max_entries: int = 500,
    redis=None,
    embedding_client=None,
) -> SemanticCache:
    return SemanticCache(
        redis=redis,
        enabled=enabled,
        version="v1",
        ttl_seconds=3600,
        similarity_threshold=threshold,
        max_entries_per_team=max_entries,
        embedding_client=embedding_client,
    )


# ── TC14–TC16: cosine_similarity ──────────────────────────────────────────────


class TestCosineSimilarity:
    def test_tc14_identical_vectors_return_one(self):
        """TC14 - Identical vectors → 1.0."""
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-9)

    def test_tc15_zero_vector_returns_zero(self):
        """TC15 - Zero vector → 0.0 (avoids division by zero)."""
        v = [1.0, 2.0, 3.0]
        z = [0.0, 0.0, 0.0]
        assert cosine_similarity(v, z) == 0.0
        assert cosine_similarity(z, v) == 0.0
        assert cosine_similarity(z, z) == 0.0

    def test_tc16_length_mismatch_returns_zero(self):
        """TC16 - Mismatched vector lengths → 0.0."""
        a = [1.0, 2.0]
        b = [1.0, 2.0, 3.0]
        assert cosine_similarity(a, b) == 0.0

    def test_orthogonal_vectors_return_zero(self):
        """Orthogonal vectors → 0.0."""
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-9)

    def test_opposite_vectors_return_minus_one(self):
        """Opposite vectors → −1.0."""
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0, abs=1e-9)


# ── TC17: extract_embedding_text ─────────────────────────────────────────────


class TestExtractEmbeddingText:
    def test_tc17_returns_last_user_message(self):
        """TC17 - extract_embedding_text returns the last user message."""
        req = ChatCompletionRequest(
            model="llama3.2",
            messages=[
                ChatMessage(role="system", content="You are helpful."),
                ChatMessage(role="user", content="First question"),
                ChatMessage(role="assistant", content="Answer"),
                ChatMessage(role="user", content="Second question"),
            ],
        )
        assert extract_embedding_text(req) == "Second question"

    def test_only_system_message_falls_back_to_empty(self):
        """Only a system message → empty embedding text (no user message)."""
        req = ChatCompletionRequest(
            model="llama3.2",
            messages=[ChatMessage(role="system", content="You are a bot.")],
        )
        # Falls back to joining non-system content, which is empty
        result = extract_embedding_text(req)
        assert result == ""

    def test_no_system_returns_user_message(self):
        req = _make_request("Hello world")
        assert extract_embedding_text(req) == "Hello world"


# ── TC18: build_config_hash ───────────────────────────────────────────────────


class TestBuildConfigHash:
    def test_tc18_same_params_same_hash(self):
        """TC18a - Same parameters → identical hash."""
        r1 = _make_request(temperature=0.5)
        r2 = _make_request(temperature=0.5)
        assert build_config_hash(r1) == build_config_hash(r2)

    def test_tc18_different_temperature_different_hash(self):
        """TC18b - Different temperature → different hash."""
        r1 = _make_request(temperature=0.5)
        r2 = _make_request(temperature=0.9)
        assert build_config_hash(r1) != build_config_hash(r2)

    def test_different_system_prompt_different_hash(self):
        r1 = _make_request(system_msg="You are helpful.")
        r2 = _make_request(system_msg="You are strict.")
        assert build_config_hash(r1) != build_config_hash(r2)

    def test_hash_length_is_16(self):
        r = _make_request()
        h = build_config_hash(r)
        assert len(h) == 16

    def test_stop_sequences_sorted_for_determinism(self):
        r1 = _make_request()
        r1.stop = ["a", "b"]
        r2 = _make_request()
        r2.stop = ["b", "a"]
        assert build_config_hash(r1) == build_config_hash(r2)


# ── TC19–TC22: OllamaEmbeddingClient ─────────────────────────────────────────


class TestOllamaEmbeddingClient:
    def _make_client(self) -> OllamaEmbeddingClient:
        return OllamaEmbeddingClient(
            base_url="http://localhost:11434",
            model="nomic-embed-text",
            timeout=5,
        )

    @pytest.mark.asyncio
    async def test_tc19_new_format_response(self):
        """TC19 - Parses new Ollama {embeddings: [[...]]} format."""
        embedding = [0.1, 0.2, 0.3]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embeddings": [embedding]}

        client = self._make_client()
        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_http

            result = await client.embed("test text")
        assert result == pytest.approx(embedding)

    @pytest.mark.asyncio
    async def test_tc20_old_format_response(self):
        """TC20 - Parses old Ollama {embedding: [...]} format."""
        embedding = [0.4, 0.5, 0.6]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": embedding}

        client = self._make_client()
        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_http

            result = await client.embed("test text")
        assert result == pytest.approx(embedding)

    @pytest.mark.asyncio
    async def test_tc21_not_found_raises_embedding_error(self):
        """TC21 - 404 response → EmbeddingError with helpful message."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        client = self._make_client()
        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_http

            with pytest.raises(EmbeddingError, match="nomic-embed-text"):
                await client.embed("test")

    @pytest.mark.asyncio
    async def test_tc22_empty_text_raises_embedding_error(self):
        """TC22 - Empty text → EmbeddingError before any HTTP call."""
        client = self._make_client()
        with pytest.raises(EmbeddingError, match="empty"):
            await client.embed("")

    @pytest.mark.asyncio
    async def test_whitespace_text_raises_embedding_error(self):
        """Whitespace-only text → EmbeddingError."""
        client = self._make_client()
        with pytest.raises(EmbeddingError, match="empty"):
            await client.embed("   ")


# ── TC01–TC13, TC23–TC25: SemanticCache ──────────────────────────────────────


class TestSemanticCache:
    """Unit tests for SemanticCache using mocked Redis and embedding clients."""

    def _make_embedding_client(self, vector: list[float]) -> AsyncMock:
        client = AsyncMock(spec=OllamaEmbeddingClient)
        client.embed = AsyncMock(return_value=vector)
        return client

    def _make_redis(
        self,
        index_entries: list[str] | None = None,
        hash_data: dict | None = None,
    ) -> AsyncMock:
        """Build a minimal async Redis mock."""
        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=0)  # team not disabled
        redis.lrange = AsyncMock(return_value=index_entries or [])
        redis.hgetall = AsyncMock(return_value=hash_data or {})
        # Pipeline mock
        pipe = AsyncMock()
        pipe.hset = MagicMock(return_value=pipe)
        pipe.expire = MagicMock(return_value=pipe)
        pipe.lpush = MagicMock(return_value=pipe)
        pipe.ltrim = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=[True, True, 1, 1])
        redis.pipeline = MagicMock(return_value=pipe)
        return redis

    # ── TC01: Similar prompt → hit ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_tc01_similar_prompt_returns_cached_response(self):
        """TC01 - Two nearly identical embeddings → cache hit."""
        # Near-identical vectors: both point in the same direction
        stored_vec = _norm_vector(1.0, 0.0, 0.0)
        query_vec = _norm_vector(0.999, 0.001, 0.0)  # similarity ≈ 0.9999

        req = _make_request("What is the capital of France?")
        ctx = _make_context()
        original_response = _make_response("Paris")
        config_hash = build_config_hash(req)

        entry_id = str(uuid.uuid4())
        redis = self._make_redis(
            index_entries=[entry_id],
            hash_data=_make_redis_hash(stored_vec, original_response, config_hash),
        )
        embedding_client = self._make_embedding_client(query_vec)
        cache = _make_cache(enabled=True, threshold=0.92, redis=redis, embedding_client=embedding_client)

        result = await cache.lookup(req, ctx)
        assert result is not None
        assert result.metadata.cache_hit is True
        assert result.choices[0].message.content == "Paris"

    # ── TC02: Dissimilar prompt → miss ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_tc02_dissimilar_prompt_returns_none(self):
        """TC02 - Orthogonal embedding vectors → cache miss."""
        stored_vec = _unit_vector(3, index=0)   # [1, 0, 0]
        query_vec = _unit_vector(3, index=1)    # [0, 1, 0]  → similarity = 0.0

        req = _make_request("What is 2+2?")
        ctx = _make_context()
        original_response = _make_response("4")
        config_hash = build_config_hash(req)

        entry_id = str(uuid.uuid4())
        redis = self._make_redis(
            index_entries=[entry_id],
            hash_data=_make_redis_hash(stored_vec, original_response, config_hash),
        )
        embedding_client = self._make_embedding_client(query_vec)
        cache = _make_cache(enabled=True, threshold=0.92, redis=redis, embedding_client=embedding_client)

        result = await cache.lookup(req, ctx)
        assert result is None

    # ── TC03: Threshold boundary ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_tc03a_exact_threshold_is_a_hit(self):
        """TC03a - Similarity == threshold → hit (inclusive boundary)."""
        # Build two unit vectors with known cosine similarity of 0.92
        # cos(θ) = a·b / (|a||b|) = 0.92 → θ = arccos(0.92)
        theta = math.acos(0.92)
        stored_vec = [1.0, 0.0]
        query_vec = [math.cos(theta), math.sin(theta)]

        req = _make_request("test")
        ctx = _make_context()
        resp = _make_response("result")
        config_hash = build_config_hash(req)

        entry_id = str(uuid.uuid4())
        redis = self._make_redis(
            index_entries=[entry_id],
            hash_data=_make_redis_hash(stored_vec, resp, config_hash),
        )
        embedding_client = self._make_embedding_client(query_vec)
        cache = _make_cache(enabled=True, threshold=0.92, redis=redis, embedding_client=embedding_client)

        result = await cache.lookup(req, ctx)
        assert result is not None

    @pytest.mark.asyncio
    async def test_tc03b_below_threshold_is_a_miss(self):
        """TC03b - Similarity < threshold → miss."""
        # Use orthogonal vectors → similarity = 0.0 < 0.92
        stored_vec = [1.0, 0.0]
        query_vec = [0.0, 1.0]

        req = _make_request("test")
        ctx = _make_context()
        resp = _make_response("result")
        config_hash = build_config_hash(req)

        entry_id = str(uuid.uuid4())
        redis = self._make_redis(
            index_entries=[entry_id],
            hash_data=_make_redis_hash(stored_vec, resp, config_hash),
        )
        embedding_client = self._make_embedding_client(query_vec)
        cache = _make_cache(enabled=True, threshold=0.92, redis=redis, embedding_client=embedding_client)

        result = await cache.lookup(req, ctx)
        assert result is None

    # ── TC04: Global disable ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_tc04_disabled_cache_skips_embedding(self):
        """TC04 - Global disable → embedding never called, returns None."""
        embedding_client = self._make_embedding_client([1.0, 0.0])
        redis = self._make_redis()
        cache = _make_cache(enabled=False, redis=redis, embedding_client=embedding_client)

        req = _make_request()
        ctx = _make_context()
        result = await cache.lookup(req, ctx)

        assert result is None
        embedding_client.embed.assert_not_called()

    # ── TC05: Streaming request → bypass ─────────────────────────────────

    @pytest.mark.asyncio
    async def test_tc05_streaming_request_is_bypassed(self):
        """TC05 - stream=True → not eligible for caching."""
        embedding_client = self._make_embedding_client([1.0, 0.0])
        redis = self._make_redis()
        cache = _make_cache(enabled=True, redis=redis, embedding_client=embedding_client)

        req = _make_request(stream=True)
        ctx = _make_context()
        result = await cache.lookup(req, ctx)

        assert result is None
        embedding_client.embed.assert_not_called()

    # ── TC06: No user message → bypass ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_tc06_no_user_message_bypasses_cache(self):
        """TC06 - Request with only a system message → not eligible."""
        embedding_client = self._make_embedding_client([1.0, 0.0])
        redis = self._make_redis()
        cache = _make_cache(enabled=True, redis=redis, embedding_client=embedding_client)

        req = ChatCompletionRequest(
            model="llama3.2",
            messages=[ChatMessage(role="system", content="You are a bot.")],
        )
        ctx = _make_context()
        result = await cache.lookup(req, ctx)

        assert result is None
        embedding_client.embed.assert_not_called()

    # ── TC07: Team isolation ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_tc07_team_isolation(self):
        """TC07 - Team A's cache entry is NOT visible to Team B."""
        stored_vec = _norm_vector(1.0, 0.0)
        query_vec = stored_vec  # identical → would be hit if in same namespace

        req = _make_request("What is Python?")
        ctx_team_b = _make_context(team_id="team-B")
        resp = _make_response("A language")
        config_hash = build_config_hash(req)

        # Redis returns empty index for team-B (no entries for that team)
        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=0)
        redis.lrange = AsyncMock(return_value=[])  # team-B has no cached entries
        redis.hgetall = AsyncMock(return_value={})

        embedding_client = self._make_embedding_client(query_vec)
        cache = _make_cache(enabled=True, redis=redis, embedding_client=embedding_client)

        result = await cache.lookup(req, ctx_team_b)
        assert result is None

        # Verify the key used was scoped to team-B
        index_key_call = redis.lrange.call_args[0][0]
        assert "team-B" in index_key_call
        assert "team-A" not in index_key_call

    # ── TC08: Per-team disable ────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_tc08_per_team_disable(self):
        """TC08 - Team disable flag in Redis → cache bypass for that team."""
        embedding_client = self._make_embedding_client([1.0, 0.0])

        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=1)  # disabled flag set

        cache = _make_cache(enabled=True, redis=redis, embedding_client=embedding_client)
        req = _make_request()
        ctx = _make_context(team_id="team-disabled")

        result = await cache.lookup(req, ctx)

        assert result is None
        embedding_client.embed.assert_not_called()

    # ── TC09: Embedding failure → miss ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_tc09_embedding_failure_returns_none(self):
        """TC09 - Embedding generation failure → cache miss, no exception propagated."""
        embedding_client = AsyncMock(spec=OllamaEmbeddingClient)
        embedding_client.embed = AsyncMock(side_effect=EmbeddingError("Ollama down"))

        redis = self._make_redis(index_entries=[])
        cache = _make_cache(enabled=True, redis=redis, embedding_client=embedding_client)

        req = _make_request()
        ctx = _make_context()

        # Must not raise
        result = await cache.lookup(req, ctx)
        assert result is None

    # ── TC10: Redis write failure → silent ────────────────────────────────

    @pytest.mark.asyncio
    async def test_tc10_redis_write_failure_is_silent(self):
        """TC10 - Redis pipeline execute fails → no exception, response still served."""
        embedding_client = self._make_embedding_client([1.0, 0.0])

        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=0)
        pipe = AsyncMock()
        pipe.hset = MagicMock(return_value=pipe)
        pipe.expire = MagicMock(return_value=pipe)
        pipe.lpush = MagicMock(return_value=pipe)
        pipe.ltrim = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(side_effect=Exception("Redis connection lost"))
        redis.pipeline = MagicMock(return_value=pipe)

        cache = _make_cache(enabled=True, redis=redis, embedding_client=embedding_client)
        req = _make_request()
        ctx = _make_context()
        resp = _make_response("Paris")

        # Must not raise
        await cache.store(req, ctx, resp)  # No exception should propagate

    # ── TC11: Config hash mismatch → miss ────────────────────────────────

    @pytest.mark.asyncio
    async def test_tc11_config_hash_mismatch_is_miss(self):
        """TC11 - Same prompt, different temperature → config hash mismatch → miss."""
        stored_vec = _norm_vector(1.0, 0.0)
        query_vec = stored_vec  # identical embedding

        req_stored = _make_request(temperature=0.0)
        req_query = _make_request(temperature=1.0)  # different temperature
        resp = _make_response("Paris")

        stored_hash = build_config_hash(req_stored)
        query_hash = build_config_hash(req_query)
        assert stored_hash != query_hash  # Confirm they differ

        entry_id = str(uuid.uuid4())
        redis = self._make_redis(
            index_entries=[entry_id],
            hash_data=_make_redis_hash(stored_vec, resp, stored_hash),  # stored with temp=0
        )
        embedding_client = self._make_embedding_client(query_vec)
        cache = _make_cache(enabled=True, threshold=0.92, redis=redis, embedding_client=embedding_client)

        ctx = _make_context()
        result = await cache.lookup(req_query, ctx)  # queried with temp=1
        assert result is None

    # ── TC12: cache_hit=True on hit ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_tc12_cache_hit_sets_metadata_flag(self):
        """TC12 - Cache hit response has cache_hit=True in metadata."""
        stored_vec = _norm_vector(1.0, 0.0)
        query_vec = stored_vec

        req = _make_request()
        ctx = _make_context()
        resp = _make_response("Paris")
        config_hash = build_config_hash(req)

        entry_id = str(uuid.uuid4())
        redis = self._make_redis(
            index_entries=[entry_id],
            hash_data=_make_redis_hash(stored_vec, resp, config_hash),
        )
        embedding_client = self._make_embedding_client(query_vec)
        cache = _make_cache(enabled=True, threshold=0.0, redis=redis, embedding_client=embedding_client)  # any similarity is hit

        result = await cache.lookup(req, ctx)
        assert result is not None
        assert result.metadata.cache_hit is True
        assert result.metadata.actual_cost == 0.0
        assert result.metadata.estimated_cost == 0.0

    # ── TC13: cache_hit=False on miss / normal response ───────────────────

    def test_tc13_default_response_has_cache_hit_false(self):
        """TC13 - A freshly constructed ChatCompletionResponse has cache_hit=False."""
        resp = _make_response()
        assert resp.metadata.cache_hit is False

    # ── TC23: Redis index read failure ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_tc23_redis_lrange_failure_returns_none(self):
        """TC23 - Redis.lrange raises → treated as cache miss."""
        embedding_client = self._make_embedding_client([1.0, 0.0])

        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=0)
        redis.lrange = AsyncMock(side_effect=Exception("Redis LRANGE failed"))

        cache = _make_cache(enabled=True, redis=redis, embedding_client=embedding_client)
        req = _make_request()
        ctx = _make_context()

        result = await cache.lookup(req, ctx)
        assert result is None

    # ── TC24: LTRIM eviction on store ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_tc24_store_calls_ltrim_for_eviction(self):
        """TC24 - store() calls LTRIM to enforce max_entries_per_team."""
        embedding_client = self._make_embedding_client([1.0, 0.0])
        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=0)

        pipe = MagicMock()
        pipe.hset = MagicMock(return_value=pipe)
        pipe.expire = MagicMock(return_value=pipe)
        pipe.lpush = MagicMock(return_value=pipe)
        pipe.ltrim = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=[True, True, 1, 1])
        redis.pipeline = MagicMock(return_value=pipe)

        max_entries = 10
        cache = _make_cache(enabled=True, max_entries=max_entries, redis=redis, embedding_client=embedding_client)

        req = _make_request()
        ctx = _make_context()
        resp = _make_response("Paris")

        await cache.store(req, ctx, resp)

        # Verify ltrim was called with 0, max_entries - 1
        pipe.ltrim.assert_called_once()
        args = pipe.ltrim.call_args[0]
        assert args[1] == 0
        assert args[2] == max_entries - 1

    # ── TC25: build_semantic_cache factory ───────────────────────────────

    def test_tc25_build_semantic_cache_disabled(self):
        """TC25 - build_semantic_cache with disabled settings → enabled=False."""
        settings = MagicMock()
        settings.semantic_cache_enabled = False
        settings.semantic_cache_version = "v1"
        settings.semantic_cache_ttl_seconds = 3600
        settings.semantic_cache_similarity_threshold = 0.92
        settings.semantic_cache_max_entries_per_team = 500
        settings.semantic_cache_embedding_provider = "ollama"
        settings.semantic_cache_embedding_model = "nomic-embed-text"
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_timeout_seconds = 30

        cache = build_semantic_cache(redis=None, settings=settings)
        assert cache._enabled is False
        assert cache._embedding_client is None

    def test_build_semantic_cache_enabled_creates_ollama_client(self):
        """Enabled with ollama provider → OllamaEmbeddingClient created."""
        settings = MagicMock()
        settings.semantic_cache_enabled = True
        settings.semantic_cache_version = "v1"
        settings.semantic_cache_ttl_seconds = 3600
        settings.semantic_cache_similarity_threshold = 0.92
        settings.semantic_cache_max_entries_per_team = 500
        settings.semantic_cache_embedding_provider = "ollama"
        settings.semantic_cache_embedding_model = "nomic-embed-text"
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_timeout_seconds = 30

        cache = build_semantic_cache(redis=None, settings=settings)
        assert cache._enabled is True
        assert cache._embedding_client is not None
        assert isinstance(cache._embedding_client, OllamaEmbeddingClient)
        assert cache._embedding_client.model == "nomic-embed-text"

    # ── Serialization round-trip ──────────────────────────────────────────

    def test_serialize_deserialize_roundtrip(self):
        """Serializing then deserializing a response preserves choices and usage."""
        original = _make_response("The answer is 42")
        serialized = SemanticCache._serialize_response(original)
        raw = {
            "embedding": "[]",  # not used by _deserialize_response
            "response_json": serialized,
            "config_hash": "abc123",
        }
        reconstructed = SemanticCache._deserialize_response(raw, request_id="test-id")

        assert reconstructed.provider == original.provider
        assert reconstructed.model == original.model
        assert reconstructed.choices[0].message.content == "The answer is 42"
        assert reconstructed.usage.prompt_tokens == 10
        assert reconstructed.metadata.cache_hit is True
        assert reconstructed.metadata.actual_cost == 0.0
