"""
Cortex Gateway — Semantic Cache Exceptions (Phase 9B).

These exceptions are internal to the cache layer and must NEVER propagate
to the chat pipeline — all callers must treat them as non-fatal.
"""


class EmbeddingError(Exception):
    """Raised when embedding generation fails (Ollama unavailable, model not installed, etc.)."""


class CacheUnavailableError(Exception):
    """Raised when the Redis cache cannot be accessed."""
