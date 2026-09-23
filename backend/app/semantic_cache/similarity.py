"""
Cortex Gateway — Semantic Similarity Utilities (Phase 9B).

Provides:
  - cosine_similarity(a, b): pure-Python cosine similarity.
  - extract_embedding_text(request): extract semantic content from a chat request.
  - build_config_hash(request): SHA-256 of response-affecting parameters.
"""

from __future__ import annotations

import hashlib
import json
import math

from app.schemas.chat import ChatCompletionRequest


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    Returns a value in [-1.0, 1.0].
    Returns 0.0 if either vector is zero-length to avoid division by zero.

    Implementation uses pure Python math — no numpy/scipy dependency.
    """
    if len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    # Clamp to [-1.0, 1.0] to guard against floating-point rounding
    return max(-1.0, min(1.0, dot / (norm_a * norm_b)))


def extract_embedding_text(request: ChatCompletionRequest) -> str:
    """
    Extract the semantic text to embed from a chat request.

    Only the user-facing message content is embedded — NOT:
    - request_id
    - API key / team_id
    - routing configuration

    The system prompt (if any) is excluded from the embedding text and
    instead captured in the config_hash to ensure different system
    prompts produce different cache namespaces.

    Returns the last user message's content (most semantically meaningful).
    If no user message exists, uses all non-system message content joined.
    """
    user_messages = [
        msg.content for msg in request.messages if msg.role == "user"
    ]
    if user_messages:
        return user_messages[-1]

    # Fallback: join all non-system content
    return " ".join(
        msg.content for msg in request.messages if msg.role != "system"
    ).strip()


def build_config_hash(request: ChatCompletionRequest) -> str:
    """
    Build a short SHA-256 hash of request parameters that materially affect
    the response. Used to distinguish semantically identical prompts that
    require different responses (different temperature, system prompt, etc.).

    Fields included:
      - System prompt text (if present)
      - temperature
      - max_tokens
      - top_p
      - stop sequences
      - required_capabilities

    Fields NOT included (they don't affect response content):
      - routing_mode, provider, model (routing decisions, not response shapers)
      - failover_enabled (reliability config)
      - team_id (captured in cache key namespace)

    Returns a 16-character hex prefix of the SHA-256 digest.
    This is long enough to be collision-resistant at project scale.
    """
    system_prompt: str | None = None
    for msg in request.messages:
        if msg.role == "system":
            system_prompt = msg.content
            break

    config = {
        "system_prompt": system_prompt,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "top_p": request.top_p,
        "stop": sorted(request.stop) if request.stop else None,
        "required_capabilities": sorted(request.required_capabilities)
        if request.required_capabilities
        else None,
    }

    raw = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
