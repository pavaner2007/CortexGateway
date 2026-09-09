"""
Cortex Gateway — Chat Completion Schemas (Phase 2).

Provider-agnostic Pydantic v2 schemas for the unified chat completion API.
Provider-specific structures must NEVER appear here or leak to clients.
"""

from __future__ import annotations

import time
import uuid
from typing import List, Literal, Optional

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

    provider: Optional[str] = Field(
        None,
        description="The LLM provider (e.g. 'gemini', 'groq', 'ollama'). Optional when intelligent routing is used.",
    )
    model: str = Field(
        ...,
        description="The model identifier understood by the provider, or 'auto' to let Cortex Gateway select the best model.",
    )
    messages: List[ChatMessage] = Field(
        ..., description="Conversation messages. Must contain at least one message."
    )
    routing_mode: Optional[
        Literal[
            "manual",
            "auto",
            "lowest_cost",
            "lowest_latency",
            "best_available",
            "capability_based",
        ]
    ] = Field(
        None,
        description="Routing policy: 'manual', 'auto', 'lowest_cost', 'lowest_latency', 'best_available', or 'capability_based'.",
    )
    required_capabilities: Optional[List[str]] = Field(
        None,
        description="List of required capabilities (e.g. ['vision', 'json', 'code']). Incompatible models will be filtered out.",
    )
    temperature: Optional[float] = Field(
        None,
        ge=0.0,
        le=2.0,
        description="Sampling temperature in [0.0, 2.0]. Provider defaults apply when omitted.",
    )
    max_tokens: Optional[int] = Field(
        None,
        gt=0,
        description="Maximum tokens to generate. Must be positive when supplied.",
    )
    top_p: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling probability in [0.0, 1.0].",
    )
    stop: Optional[List[str]] = Field(
        None,
        description="Stop sequences. Generation halts when any sequence is produced.",
    )

    @field_validator("provider", mode="before")
    @classmethod
    def normalize_provider(cls, v: Optional[str]) -> Optional[str]:
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
    def messages_not_empty(self) -> "ChatCompletionRequest":
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
    finish_reason: Optional[str] = None


class UsageMetadata(BaseModel):
    """
    Normalized token usage.

    Fields are Optional because not every provider returns all values.
    Do NOT fabricate counts; use None when data is unavailable.
    """

    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class ResponseMetadata(BaseModel):
    """Gateway-level metadata attached to every response."""

    request_id: str
    latency_ms: float = Field(
        description="Provider request latency in milliseconds."
    )
    routing_mode: Optional[str] = Field(
        None,
        description="Routing mode applied to this request.",
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
    choices: List[ChatCompletionChoice]
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

    providers: List[ProviderInfo]


class ProviderDetailResponse(BaseModel):
    """Response body for GET /api/v1/providers/{provider}."""

    name: str
    enabled: bool
    available: bool
    capabilities: List[str] = Field(
        default_factory=lambda: ["chat"],
        description="Supported capabilities of this provider.",
    )


class ModelListResponse(BaseModel):
    """Response body for GET /api/v1/providers/{provider}/models."""

    provider: str
    models: List[str]
