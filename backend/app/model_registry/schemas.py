"""
Cortex Gateway — Model Registry Pydantic Schemas (Phase 9A).

Validation rules:
  - provider: must be a known supported value
  - model_name: non-empty string
  - costs: >= 0.0
  - context_window: > 0
  - baseline_latency_ms: > 0
  - capabilities: subset of KNOWN_CAPABILITIES — unknown values rejected
  - enabled: boolean

Capabilities are stored as a list of strings matching Phase 3's internal
List[str] format exactly, avoiding any conversion layer.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# Exhaustive set of capability tokens recognized by the routing engine.
# Phase 3 uses these strings directly; unknown values are rejected on write.
KNOWN_CAPABILITIES = frozenset(
    {
        "text",
        "vision",
        "json",
        "code",
        "tools",
        "function_calling",
        "complex_reasoning",
    }
)

KNOWN_PROVIDERS = frozenset({"gemini", "groq", "ollama", "openai"})


class ModelRegistryCreate(BaseModel):
    """Request body for POST /api/v1/models."""

    provider: str = Field(..., min_length=1, max_length=100)
    model_name: str = Field(..., min_length=1, max_length=255)
    display_name: str | None = Field(None, max_length=255)

    input_cost_per_1k: float = Field(
        default=0.0, ge=0.0, description="USD cost per 1,000 input tokens."
    )
    output_cost_per_1k: float = Field(
        default=0.0, ge=0.0, description="USD cost per 1,000 output tokens."
    )

    capabilities: list[str] = Field(
        default_factory=lambda: ["text"],
        description="Capability tokens. Allowed: text, vision, json, code, tools, "
        "function_calling, complex_reasoning.",
    )
    context_window: int = Field(
        default=8192, gt=0, description="Maximum context window in tokens."
    )
    baseline_latency_ms: float = Field(
        default=500.0, gt=0.0, description="Baseline latency in milliseconds."
    )
    enabled: bool = Field(default=True)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in KNOWN_PROVIDERS:
            raise ValueError(
                f"Unknown provider {v!r}. Supported: {sorted(KNOWN_PROVIDERS)}"
            )
        return normalized

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("model_name must not be empty or whitespace.")
        return stripped

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("capabilities must contain at least one entry.")
        unknown = set(v) - KNOWN_CAPABILITIES
        if unknown:
            raise ValueError(
                f"Unknown capability tokens: {sorted(unknown)}. "
                f"Allowed: {sorted(KNOWN_CAPABILITIES)}"
            )
        # De-duplicate while preserving order
        seen: set = set()
        result = []
        for cap in v:
            if cap not in seen:
                seen.add(cap)
                result.append(cap)
        return result

    model_config = {"extra": "forbid"}


class ModelRegistryUpdate(BaseModel):
    """Request body for PATCH /api/v1/models/{id}. All fields optional."""

    display_name: str | None = Field(None, max_length=255)
    input_cost_per_1k: float | None = Field(None, ge=0.0)
    output_cost_per_1k: float | None = Field(None, ge=0.0)
    capabilities: list[str] | None = None
    context_window: int | None = Field(None, gt=0)
    baseline_latency_ms: float | None = Field(None, gt=0.0)
    enabled: bool | None = None

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        if not v:
            raise ValueError("capabilities must contain at least one entry.")
        unknown = set(v) - KNOWN_CAPABILITIES
        if unknown:
            raise ValueError(
                f"Unknown capability tokens: {sorted(unknown)}. "
                f"Allowed: {sorted(KNOWN_CAPABILITIES)}"
            )
        seen: set = set()
        result = []
        for cap in v:
            if cap not in seen:
                seen.add(cap)
                result.append(cap)
        return result

    model_config = {"extra": "forbid"}


class ModelRegistryResponse(BaseModel):
    """Response schema for model registry entries."""

    id: str
    provider: str
    model_name: str
    display_name: str | None
    input_cost_per_1k: float
    output_cost_per_1k: float
    cost_per_1k_tokens: float
    capabilities: list[str]
    context_window: int
    baseline_latency_ms: float
    enabled: bool
    added_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, entry: object) -> ModelRegistryResponse:
        from app.model_registry.models import ModelRegistryEntry
        e: ModelRegistryEntry = entry  # type: ignore[assignment]
        return cls(
            id=e.id,
            provider=e.provider,
            model_name=e.model_name,
            display_name=e.display_name,
            input_cost_per_1k=e.input_cost_per_1k,
            output_cost_per_1k=e.output_cost_per_1k,
            cost_per_1k_tokens=e.cost_per_1k_tokens,
            capabilities=e.capabilities,
            context_window=e.context_window,
            baseline_latency_ms=e.baseline_latency_ms,
            enabled=e.enabled,
            added_at=e.added_at,
            updated_at=e.updated_at,
        )


class ModelRegistryListResponse(BaseModel):
    """Paginated list of model registry entries."""

    models: list[ModelRegistryResponse]
    total: int
