"""
Cortex Gateway — Reliability Models (Phase 4).

Data structures and enums for circuit breaking, retries, and failover tracking.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

from app.schemas.chat import ChatCompletionResponse


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class AttemptRecord:
    """Record of an individual provider attempt."""

    provider: str
    model: str
    attempt_number: int
    is_failover: bool
    is_success: bool
    latency_ms: float = 0.0
    error: str | None = None


@dataclass
class ReliabilityContext:
    """Context and execution state across the entire request lifecycle."""

    request_id: str
    deadline_timestamp: float
    original_provider: str | None = None
    original_model: str | None = None
    selected_provider: str | None = None
    selected_model: str | None = None
    attempted_providers: set[str] = field(default_factory=set)
    retry_count: int = 0
    failover_attempts: int = 0
    failover_triggered: bool = False
    attempts: list[AttemptRecord] = field(default_factory=list)
    start_time: float = field(default_factory=time.monotonic)

    def is_deadline_exceeded(self) -> bool:
        """Return True if the total request deadline has passed."""
        return time.monotonic() >= self.deadline_timestamp

    def remaining_deadline_seconds(self) -> float:
        """Return remaining seconds before overall request deadline."""
        return max(0.0, self.deadline_timestamp - time.monotonic())


@dataclass
class ReliabilityResult:
    """Outcome of resilient execution."""

    response: ChatCompletionResponse
    context: ReliabilityContext
