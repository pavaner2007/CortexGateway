"""
Cortex Gateway — Chat Completion Schemas (Phase 2).

Provider-agnostic Pydantic v2 schemas for the unified chat completion API.
Provider-specific structures must NEVER appear here or leak to clients.
"""

from __future__ import annotations

import time
import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ── Request schemas ───────────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    """A single message in a chat conversation."""

    role: Literal["system", "user", "assistant"] = Field(
        ..., description="The role of the message author."
    )
    content: str = Field(..., description="The content of the message.")

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Message content cannot be empty.")
        return v


class ChatCompletionRequest(BaseModel):
    """
    Provider-agnostic chat completion request.

    Supports:
    - Manual routing: explicit provider + concrete model name.
    - Intelligent routing: model='auto' or routing_mode specified.
    """

    provider: str | None = Field(
        None,
        description="The LLM provider (e.g. 'gemini', 'groq', 'ollama'). Optional when intelligent routing is used.",
    )
    model: str = Field(
        ...,
        description="The model identifier understood by the provider, or 'auto' to let Cortex Gateway select the best model.",
    )
    messages: list[ChatMessage] = Field(
        ..., description="Conversation messages. Must contain at least one message."
    )
    routing_mode: Literal["manual", "auto", "lowest_cost", "lowest_latency", "best_available", "capability_based"] | None = Field(
        None,
        description="Routing policy: 'manual', 'auto', 'lowest_cost', 'lowest_latency', 'best_available', or 'capability_based'.",
    )
    required_capabilities: list[str] | None = Field(
        None,
        description="List of required capabilities (e.g. ['vision', 'json', 'code']). Incompatible models will be filtered out.",
    )
    temperature: float | None = Field(
        None,
        ge=0.0,
        le=2.0,
        description="Sampling temperature in [0.0, 2.0]. Provider defaults apply when omitted.",
    )
    max_tokens: int | None = Field(
        None,
        gt=0,
        description="Maximum tokens to generate. Must be positive when supplied.",
    )
    top_p: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling probability in [0.0, 1.0].",
    )
    stop: list[str] | None = Field(
        None,
        description="Stop sequences. Generation halts when any sequence is produced.",
    )
    failover_enabled: bool | None = Field(
        True,
        description="Enable automatic failover if the selected provider fails.",
    )
    stream: bool | None = Field(
        False,
        description="If true, responses will be streamed. Note: streaming bypasses semantic cache.",
    )

    @field_validator("provider", mode="before")
    @classmethod
    def normalize_provider(cls, v: str | None) -> str | None:
        """Lowercase and strip the provider name for consistent lookup."""
        if isinstance(v, str):
            val = v.strip().lower()
            return val if val else None
        return v

    @field_validator("model", mode="before")
    @classmethod
    def normalize_model(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @model_validator(mode="after")
    def messages_not_empty(self) -> ChatCompletionRequest:
        if not self.messages:
            raise ValueError("The 'messages' list cannot be empty.")
        return self


# ── Response schemas ──────────────────────────────────────────────────────────


class ChatMessageResponse(BaseModel):
    """The assistant message returned inside a choice."""

    role: Literal["assistant"] = "assistant"
    content: str


class ChatCompletionChoice(BaseModel):
    """A single completion choice."""

    index: int
    message: ChatMessageResponse
    finish_reason: str | None = None


class UsageMetadata(BaseModel):
    """
    Normalized token usage.

    Fields are Optional because not every provider returns all values.
    Do NOT fabricate counts; use None when data is unavailable.
    """

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ResponseMetadata(BaseModel):
    """Gateway-level metadata attached to every response."""

    request_id: str
    latency_ms: float = Field(
        description="Provider request latency in milliseconds."
    )
    routing_mode: str | None = Field(
        None,
        description="Routing mode applied to this request.",
    )
    selected_provider: str | None = Field(
        None,
        description="Actual provider that fulfilled the completion.",
    )
    selected_model: str | None = Field(
        None,
        description="Actual model that fulfilled the completion.",
    )
    original_provider: str | None = Field(
        None,
        description="Initially selected provider before any failover.",
    )
    failover_triggered: bool = Field(
        False,
        description="True if automatic failover occurred.",
    )
    retry_count: int = Field(
        0,
        description="Total number of retry attempts executed.",
    )
    failover_attempts: int = Field(
        0,
        description="Number of fallback candidate providers attempted.",
    )
    circuit_breaker_state: str | None = Field(
        None,
        description="Circuit breaker state of selected provider.",
    )
    # ── Phase 6: Cost & Budget metadata ──────────────────────────────────────
    estimated_cost: float | None = Field(
        None,
        description="Estimated USD cost for this request (pre-execution).",
    )
    actual_cost: float | None = Field(
        None,
        description="Actual USD cost calculated from provider token usage.",
    )
    remaining_budget: float | None = Field(
        None,
        description="Remaining team budget after this request (only exposed when BUDGET_EXPOSE_REMAINING=true).",
    )
    budget_warning: bool = Field(
        False,
        description="True if budget threshold was crossed (WARN policy).",
    )
    budget_downgraded: bool = Field(
        False,
        description="True if request was downgraded to a cheaper provider/model due to budget constraints.",
    )
    # ── Phase 6: Rate limit metadata ─────────────────────────────────────────
    rate_limit_remaining: int | None = Field(
        None,
        description="Remaining requests in the tightest-bound rate-limit window.",
    )
    # ── Phase 9B: Semantic Cache metadata ───────────────────────────
    cache_hit: bool = Field(
        False,
        description="True if this response was served from the semantic cache (no provider call made).",
    )
    # ── Phase 9D: Experiment metadata ───────────────────────────────
    experiment_id: str | None = Field(
        None,
        description="Experiment ID assigned to this request. Null for non-experiment and cache-hit requests.",
    )
    experiment_version: int | None = Field(
        None,
        description="Experiment version at the time of assignment.",
    )
    experiment_arm: str | None = Field(
        None,
        description=(
            "Arm name assigned by the experiment. "
            "May differ from selected_provider/model if Phase 4 failover occurred."
        ),
    )


class ChatCompletionResponse(BaseModel):
    """
    Cortex Gateway unified chat completion response.

    This is the only response structure clients ever see.
    Provider-specific fields are normalized inside each adapter.
    """

    id: str = Field(
        default_factory=lambda: f"ctx_{uuid.uuid4().hex[:12]}",
        description="Unique Cortex Gateway completion ID.",
    )
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(
        default_factory=lambda: int(time.time()),
        description="Unix timestamp of when this completion was generated.",
    )
    provider: str
    model: str
    choices: list[ChatCompletionChoice]
    usage: UsageMetadata
    metadata: ResponseMetadata


# ── Provider discovery schemas ────────────────────────────────────────────────


class ProviderInfo(BaseModel):
    """Safe metadata about a registered provider."""

    name: str
    enabled: bool
    available: bool = Field(
        description="True when the provider is enabled AND has a valid API key configured."
    )


class ProviderListResponse(BaseModel):
    """Response body for GET /api/v1/providers."""

    providers: list[ProviderInfo]


class ProviderDetailResponse(BaseModel):
    """Response body for GET /api/v1/providers/{provider}."""

    name: str
    enabled: bool
    available: bool
    capabilities: list[str] = Field(
        default_factory=lambda: ["chat"],
        description="Supported capabilities of this provider.",
    )


class ModelListResponse(BaseModel):
    """Response body for GET /api/v1/providers/{provider}/models."""

    provider: str
    models: list[str]
