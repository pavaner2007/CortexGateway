"""
Cortex Gateway — Reliability Models (Phase 4).

Data structures and enums for circuit breaking, retries, and failover tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import List, Optional, Set

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
    error: Optional[str] = None


@dataclass
class ReliabilityContext:
    """Context and execution state across the entire request lifecycle."""

    request_id: str
    deadline_timestamp: float
    original_provider: Optional[str] = None
    original_model: Optional[str] = None
    selected_provider: Optional[str] = None
    selected_model: Optional[str] = None
    attempted_providers: Set[str] = field(default_factory=set)
    retry_count: int = 0
    failover_attempts: int = 0
    failover_triggered: bool = False
    attempts: List[AttemptRecord] = field(default_factory=list)
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
