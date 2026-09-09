"""
Cortex Gateway — Reliability Executor (Phase 4).

Coordinates total deadline enforcement, circuit breaker checks, retry with backoff,
failover candidate selection via Phase 3 Scorer, runtime stats tracking, and response metadata.
"""

from __future__ import annotations

import time
from typing import Optional

from app.core.logging import logger
from app.providers.exceptions import ProviderException
from app.providers.registry import ProviderRegistry
from app.reliability.circuit_breaker import CircuitBreakerRegistry, get_circuit_breaker_registry
from app.reliability.errors import (
    CircuitOpenError,
    FailoverExhaustedError,
    TotalDeadlineExceededError,
    is_transient_error,
)
from app.reliability.failover import FailoverSelector
from app.reliability.models import AttemptRecord, ReliabilityContext
from app.reliability.retry import RetryPolicy
from app.routing.router import RoutingEngine, get_routing_engine
from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse


class ReliabilityExecutor:
    """
    Executes chat completions with reliability, resilience, and graceful degradation.
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        routing_engine: RoutingEngine,
        circuit_registry: Optional[CircuitBreakerRegistry] = None,
        retry_policy: Optional[RetryPolicy] = None,
        failover_selector: Optional[FailoverSelector] = None,
        total_request_timeout_seconds: float = 120.0,
        max_failover_attempts: int = 2,
    ) -> None:
        self._registry = registry
        self._routing_engine = routing_engine
        self._circuit_registry = circuit_registry or get_circuit_breaker_registry()
        self._retry_policy = retry_policy or RetryPolicy()
        self.total_request_timeout_seconds = total_request_timeout_seconds
        self.max_failover_attempts = max_failover_attempts
        self._failover_selector = failover_selector or FailoverSelector(
            routing_engine=self._routing_engine,
            circuit_registry=self._circuit_registry,
            max_failover_attempts=self.max_failover_attempts,
        )

    @property
    def circuit_registry(self) -> CircuitBreakerRegistry:
        return self._circuit_registry

    @property
    def retry_policy(self) -> RetryPolicy:
        return self._retry_policy

    async def execute(
        self,
        request: ChatCompletionRequest,
        request_id: str,
        initial_provider: str,
        initial_model: str,
        routing_mode: Optional[str] = "auto",
    ) -> ChatCompletionResponse:
        """
        Execute request with deadlines, circuit breaker, retry, and failover.
        """
        now = time.monotonic()
        context = ReliabilityContext(
            request_id=request_id,
            deadline_timestamp=now + self.total_request_timeout_seconds,
            original_provider=initial_provider,
            original_model=initial_model,
            selected_provider=initial_provider,
            selected_model=initial_model,
        )

        current_provider = initial_provider
        current_model = initial_model
        is_failover = False
        last_error: Optional[Exception] = None

        # Outer loop handles failover attempts across candidate providers
        while context.failover_attempts <= self.max_failover_attempts:
            if context.is_deadline_exceeded():
                logger.error(
                    "Total request deadline exceeded before provider attempt",
                    event="deadline_exceeded",
                    request_id=request_id,
                    provider=current_provider,
                )
                raise TotalDeadlineExceededError()

            context.attempted_providers.add(current_provider.lower())
            context.selected_provider = current_provider
            context.selected_model = current_model

            # ── 1. Circuit Breaker Check ───────────────────────────────────────
            if not self._circuit_registry.can_execute(current_provider):
                logger.warning(
                    "Circuit breaker is OPEN; short-circuiting provider call",
                    event="circuit_short_circuit",
                    request_id=request_id,
                    provider=current_provider,
                )
                circuit_err = CircuitOpenError(current_provider)
                last_error = circuit_err

                # If failover is disabled, fail immediately
                if request.failover_enabled is False:
                    raise circuit_err

                # Attempt failover to next best candidate
                fallback = await self._failover_selector.select_fallback(
                    request, context.attempted_providers
                )
                if not fallback:
                    raise circuit_err

                context.failover_triggered = True
                context.failover_attempts += 1
                current_provider = fallback.provider
                current_model = fallback.model
                is_failover = True
                continue

            # ── 2. Provider Retry Loop ─────────────────────────────────────────
            max_attempts = 1 + self._retry_policy.max_retries
            provider_succeeded = False

            for attempt_idx in range(max_attempts):
                if context.is_deadline_exceeded():
                    logger.error(
                        "Total request deadline exceeded during retry loop",
                        event="deadline_exceeded",
                        request_id=request_id,
                        provider=current_provider,
                        attempt=attempt_idx + 1,
                    )
                    raise TotalDeadlineExceededError()

                if attempt_idx > 0:
                    delay = self._retry_policy.compute_delay(attempt_idx - 1)
                    if (time.monotonic() + delay) >= context.deadline_timestamp:
                        logger.error(
                            "Total request deadline would be exceeded by backoff sleep",
                            event="deadline_exceeded",
                            request_id=request_id,
                            provider=current_provider,
                        )
                        raise TotalDeadlineExceededError()

                    logger.info(
                        "Applying exponential backoff before retry",
                        event="provider_retry",
                        request_id=request_id,
                        provider=current_provider,
                        model=current_model,
                        attempt=attempt_idx + 1,
                        delay_seconds=delay,
                    )
                    context.retry_count += 1
                    await self._retry_policy.sleep(delay)

                logger.info(
                    "Executing provider attempt",
                    event="provider_attempt",
                    request_id=request_id,
                    provider=current_provider,
                    model=current_model,
                    attempt=attempt_idx + 1,
                    is_failover=is_failover,
                )

                attempt_start = time.monotonic()
                try:
                    provider = self._registry.get(current_provider)
                    resolved_request = request.model_copy(
                        update={"provider": current_provider, "model": current_model}
                    )
                    response = await provider.chat(resolved_request, request_id)

                    # ── Success Path ──────────────────────────────────────────
                    attempt_latency = (time.monotonic() - attempt_start) * 1000
                    context.attempts.append(
                        AttemptRecord(
                            provider=current_provider,
                            model=current_model,
                            attempt_number=attempt_idx + 1,
                            is_failover=is_failover,
                            is_success=True,
                            latency_ms=round(attempt_latency, 2),
                        )
                    )

                    # Record success in circuit breaker & Phase 3 stats tracker
                    self._circuit_registry.record_success(current_provider)
                    self._routing_engine.stats_tracker.record_success(
                        current_provider, current_model, response.metadata.latency_ms
                    )

                    # Attach reliability metadata to response
                    response.metadata.routing_mode = routing_mode
                    response.metadata.selected_provider = current_provider
                    response.metadata.selected_model = current_model
                    response.metadata.original_provider = context.original_provider
                    response.metadata.failover_triggered = context.failover_triggered
                    response.metadata.retry_count = context.retry_count
                    response.metadata.failover_attempts = context.failover_attempts
                    response.metadata.circuit_breaker_state = self._circuit_registry.get_state(
                        current_provider
                    ).value

                    logger.info(
                        "Request completed successfully",
                        event="request_completed",
                        request_id=request_id,
                        selected_provider=current_provider,
                        selected_model=current_model,
                        original_provider=context.original_provider,
                        failover_triggered=context.failover_triggered,
                        retry_count=context.retry_count,
                        failover_attempts=context.failover_attempts,
                    )
                    return response

                except Exception as exc:
                    attempt_latency = (time.monotonic() - attempt_start) * 1000
                    last_error = exc
                    context.attempts.append(
                        AttemptRecord(
                            provider=current_provider,
                            model=current_model,
                            attempt_number=attempt_idx + 1,
                            is_failover=is_failover,
                            is_success=False,
                            latency_ms=round(attempt_latency, 2),
                            error=str(exc),
                        )
                    )
                    self._routing_engine.stats_tracker.record_failure(
                        current_provider, current_model
                    )

                    logger.warning(
                        "Provider attempt failed",
                        event="provider_attempt_failed",
                        request_id=request_id,
                        provider=current_provider,
                        model=current_model,
                        attempt=attempt_idx + 1,
                        error=str(exc),
                        is_transient=is_transient_error(exc),
                    )

                    # Non-transient errors (e.g. InvalidModelError, client errors) do not retry
                    if not is_transient_error(exc):
                        raise exc

                    # If this was the last retry attempt, trip circuit counter
                    if attempt_idx == (max_attempts - 1):
                        self._circuit_registry.record_failure(current_provider, exc)

            # ── 3. Failover Trigger ────────────────────────────────────────────
            # If failover is explicitly disabled by client (e.g. failover_enabled=False in manual mode)
            if request.failover_enabled is False:
                logger.info(
                    "Failover skipped because failover_enabled=False",
                    request_id=request_id,
                    provider=current_provider,
                )
                if last_error:
                    raise last_error
                raise FailoverExhaustedError()

            if context.failover_attempts >= self.max_failover_attempts:
                logger.warning(
                    "Max failover attempts reached",
                    event="failover_exhausted",
                    request_id=request_id,
                    failover_attempts=context.failover_attempts,
                )
                if last_error:
                    raise last_error
                raise FailoverExhaustedError()

            # Find next eligible candidate
            fallback = await self._failover_selector.select_fallback(
                request, context.attempted_providers
            )
            if not fallback:
                logger.warning(
                    "No further eligible fallback candidates available",
                    event="failover_no_candidates",
                    request_id=request_id,
                    attempted_providers=list(context.attempted_providers),
                )
                if last_error:
                    raise last_error
                raise FailoverExhaustedError()

            context.failover_triggered = True
            context.failover_attempts += 1
            current_provider = fallback.provider
            current_model = fallback.model
            is_failover = True

            logger.info(
                "Triggering failover to next candidate",
                event="failover_triggered",
                request_id=request_id,
                original_provider=context.original_provider,
                fallback_provider=current_provider,
                fallback_model=current_model,
                retry_count=context.retry_count,
                failover_attempts=context.failover_attempts,
            )

        # If all failover attempts fail
        if last_error:
            raise last_error
        raise FailoverExhaustedError()


_reliability_executor_instance: Optional[ReliabilityExecutor] = None


def get_reliability_executor(
    registry: Optional[ProviderRegistry] = None,
    routing_engine: Optional[RoutingEngine] = None,
) -> ReliabilityExecutor:
    """Return or construct the global ReliabilityExecutor singleton."""
    global _reliability_executor_instance
    if _reliability_executor_instance is None:
        from app.config.settings import get_settings
        from app.providers.registry import get_registry
        from app.routing.router import get_routing_engine

        s = get_settings()
        reg = registry or get_registry()
        router = routing_engine or get_routing_engine(reg)
        cb_reg = get_circuit_breaker_registry()
        retry_pol = RetryPolicy(
            max_retries=s.reliability_max_retries,
            base_delay_seconds=s.reliability_retry_base_delay_seconds,
            max_delay_seconds=s.reliability_retry_max_delay_seconds,
            jitter=s.reliability_retry_jitter,
        )
        _reliability_executor_instance = ReliabilityExecutor(
            registry=reg,
            routing_engine=router,
            circuit_registry=cb_reg,
            retry_policy=retry_pol,
            total_request_timeout_seconds=float(s.reliability_total_request_timeout_seconds),
            max_failover_attempts=s.reliability_max_failover_attempts,
        )
    return _reliability_executor_instance


def set_reliability_executor(executor: Optional[ReliabilityExecutor]) -> None:
    """Override the global executor singleton (useful for testing)."""
    global _reliability_executor_instance
    _reliability_executor_instance = executor
