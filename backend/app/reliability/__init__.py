"""
Cortex Gateway — Reliability & Resilience Package (Phase 4).
"""

from app.reliability.circuit_breaker import (
    CircuitBreakerRegistry,
    ProviderCircuitBreaker,
    get_circuit_breaker_registry,
    set_circuit_breaker_registry,
)
from app.reliability.errors import (
    CircuitOpenError,
    FailoverExhaustedError,
    TotalDeadlineExceededError,
    is_circuit_breaker_failure,
    is_transient_error,
)
from app.reliability.executor import (
    ReliabilityExecutor,
    get_reliability_executor,
    set_reliability_executor,
)
from app.reliability.failover import FailoverSelector
from app.reliability.models import (
    AttemptRecord,
    CircuitState,
    ReliabilityContext,
    ReliabilityResult,
)
from app.reliability.retry import RetryPolicy

__all__ = [
    "CircuitState",
    "AttemptRecord",
    "ReliabilityContext",
    "ReliabilityResult",
    "CircuitOpenError",
    "FailoverExhaustedError",
    "TotalDeadlineExceededError",
    "is_transient_error",
    "is_circuit_breaker_failure",
    "ProviderCircuitBreaker",
    "CircuitBreakerRegistry",
    "get_circuit_breaker_registry",
    "set_circuit_breaker_registry",
    "RetryPolicy",
    "FailoverSelector",
    "ReliabilityExecutor",
    "get_reliability_executor",
    "set_reliability_executor",
]
