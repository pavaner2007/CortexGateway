"""
Cortex Gateway — Routing Models (Phase 3).

Data structures and types for the Intelligent Routing Engine.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

RoutingMode = Literal[
    "manual",
    "auto",
    "lowest_cost",
    "lowest_latency",
    "best_available",
    "capability_based",
]


class ModelMetadata(BaseModel):
    """Static and catalog metadata for a specific provider model."""

    provider: str
    model: str
    cost_per_1k_tokens: float = Field(
        default=0.0,
        ge=0.0,
        description="Cost in USD per 1,000 tokens (blended prompt/completion).",
    )
    capabilities: List[str] = Field(
        default_factory=lambda: ["text"],
        description="Supported capabilities (e.g. 'text', 'vision', 'code', 'json', 'tools').",
    )
    context_window: int = Field(
        default=8192,
        gt=0,
        description="Maximum context window in tokens.",
    )
    baseline_latency_ms: float = Field(
        default=500.0,
        gt=0.0,
        description="Baseline cold-start latency in milliseconds.",
    )


class RoutingCandidate(BaseModel):
    """
    A concrete provider + model candidate evaluated by the routing engine.
    """

    provider: str
    model: str
    capabilities: List[str] = Field(default_factory=lambda: ["text"])
    context_window: int = 8192
    cost_per_1k_tokens: float = 0.0
    is_healthy: bool = True
    baseline_latency_ms: float = 500.0
    runtime_latency_ms: Optional[float] = None
    runtime_success_rate: float = 1.0
    total_requests: int = 0

    @property
    def effective_latency_ms(self) -> float:
        """Return observed runtime latency if available, else baseline."""
        if self.runtime_latency_ms is not None and self.runtime_latency_ms > 0:
            return self.runtime_latency_ms
        return self.baseline_latency_ms


class RoutingDecision(BaseModel):
    """
    Result of the routing engine's evaluation.
    """

    provider: str
    model: str
    routing_mode: RoutingMode
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Final normalized score in [0.0, 1.0].",
    )
    score_breakdown: Dict[str, float] = Field(
        default_factory=dict,
        description="Breakdown of individual normalized factor scores.",
    )
    candidate: Optional[RoutingCandidate] = None
