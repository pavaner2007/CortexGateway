"""
Cortex Gateway — In-Memory Circuit Breaker (Phase 4).

Implements the standard 3-state circuit breaker pattern (CLOSED, OPEN, HALF_OPEN)
at provider granularity with thread-safe in-memory state tracking.
"""

from __future__ import annotations

import asyncio
import time
from typing import Dict, Optional

from app.core.logging import logger
from app.reliability.errors import is_circuit_breaker_failure
from app.reliability.models import CircuitState


class ProviderCircuitBreaker:
    """
    In-memory Circuit Breaker for a single LLM provider.

    States:
      - CLOSED: Normal operation. All requests pass through.
      - OPEN: Failing provider. Requests short-circuit immediately.
      - HALF_OPEN: Cooldown expired. Allows limited trial request(s).
    """

    def __init__(
        self,
        provider: str,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
        half_open_trials: int = 1,
    ) -> None:
        self.provider = provider.lower().strip()
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.half_open_trials = half_open_trials

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_trial_count: int = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._resolve_state()

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def _resolve_state(self) -> CircuitState:
        """Resolve effective state accounting for cooldown transitions."""
        if self._state == CircuitState.OPEN:
            if self._last_failure_time is not None:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self.cooldown_seconds:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_trial_count = 0
                    logger.info(
                        "Circuit breaker transitioned to HALF_OPEN",
                        event="circuit_half_open",
                        provider=self.provider,
                        cooldown_seconds=self.cooldown_seconds,
                    )
        return self._state

    def can_execute(self) -> bool:
        """
        Check if a request is allowed to execute against the provider.

        Returns:
            True if allowed (CLOSED or eligible HALF_OPEN trial), False if blocked (OPEN).
        """
        st = self._resolve_state()
        if st == CircuitState.CLOSED:
            return True

        if st == CircuitState.HALF_OPEN:
            if self._half_open_trial_count < self.half_open_trials:
                self._half_open_trial_count += 1
                return True
            return False

        # OPEN state
        return False

    def record_success(self) -> None:
        """Record successful execution. Closes circuit from HALF_OPEN or resets failures."""
        st = self._resolve_state()
        if st == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._half_open_trial_count = 0
            self._last_failure_time = None
            logger.info(
                "Circuit breaker reset to CLOSED after successful probe",
                event="circuit_closed",
                provider=self.provider,
            )
        elif st == CircuitState.CLOSED:
            self._failure_count = 0

    def record_failure(self, exc: Exception) -> None:
        """
        Record a request failure. Only stability failures count toward tripping the circuit.
        """
        if not is_circuit_breaker_failure(exc):
            return

        now = time.monotonic()
        self._last_failure_time = now
        st = self._resolve_state()

        if st == CircuitState.HALF_OPEN:
            # Probe failed -> reopen circuit
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit breaker reopened to OPEN after probe failure",
                event="circuit_opened",
                provider=self.provider,
                error=str(exc),
            )
        elif st == CircuitState.CLOSED:
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker tripped to OPEN",
                    event="circuit_opened",
                    provider=self.provider,
                    failure_count=self._failure_count,
                    threshold=self.failure_threshold,
                    error=str(exc),
                )

    def trip(self) -> None:
        """Force circuit state to OPEN (useful for testing or explicit outage triggers)."""
        self._state = CircuitState.OPEN
        self._last_failure_time = time.monotonic()
        self._failure_count = self.failure_threshold
        logger.warning(
            "Circuit breaker manually tripped to OPEN",
            event="circuit_opened",
            provider=self.provider,
        )

    def reset(self) -> None:
        """Reset breaker to clean initial CLOSED state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_trial_count = 0
        self._last_failure_time = None


class CircuitBreakerRegistry:
    """Registry maintaining per-provider circuit breakers."""

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
        half_open_trials: int = 1,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.half_open_trials = half_open_trials
        self._breakers: Dict[str, ProviderCircuitBreaker] = {}

    def get_breaker(self, provider: str) -> ProviderCircuitBreaker:
        """Retrieve or construct the circuit breaker for the given provider."""
        key = provider.lower().strip()
        if key not in self._breakers:
            self._breakers[key] = ProviderCircuitBreaker(
                provider=key,
                failure_threshold=self.failure_threshold,
                cooldown_seconds=self.cooldown_seconds,
                half_open_trials=self.half_open_trials,
            )
        return self._breakers[key]

    def can_execute(self, provider: str) -> bool:
        return self.get_breaker(provider).can_execute()

    def record_success(self, provider: str) -> None:
        self.get_breaker(provider).record_success()

    def record_failure(self, provider: str, exc: Exception) -> None:
        self.get_breaker(provider).record_failure(exc)

    def get_state(self, provider: str) -> CircuitState:
        return self.get_breaker(provider).state

    def reset_all(self) -> None:
        """Reset all circuit breakers to CLOSED."""
        for breaker in self._breakers.values():
            breaker.reset()


_circuit_breaker_registry_instance: Optional[CircuitBreakerRegistry] = None


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Return or create the global CircuitBreakerRegistry singleton."""
    global _circuit_breaker_registry_instance
    if _circuit_breaker_registry_instance is None:
        from app.config.settings import get_settings

        s = get_settings()
        _circuit_breaker_registry_instance = CircuitBreakerRegistry(
            failure_threshold=s.circuit_breaker_failure_threshold,
            cooldown_seconds=s.circuit_breaker_cooldown_seconds,
            half_open_trials=s.circuit_breaker_half_open_trials,
        )
    return _circuit_breaker_registry_instance


def set_circuit_breaker_registry(reg: Optional[CircuitBreakerRegistry]) -> None:
    """Override the global registry singleton (useful for testing)."""
    global _circuit_breaker_registry_instance
    _circuit_breaker_registry_instance = reg
