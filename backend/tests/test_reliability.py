"""
Cortex Gateway — Phase 4 Reliability & Resilience Test Suite.

Comprehensive offline unit and integration tests covering:
- Transient error and circuit failure classification
- Exponential backoff and jitter calculations
- Circuit breaker state machine (CLOSED -> OPEN -> HALF_OPEN -> CLOSED / OPEN)
- Retry loop with configurable max_retries and non-blocking sleep
- Total request deadline enforcement
- Automatic failover using Phase 3 Scorer and loop prevention
- Manual routing failover toggle (failover_enabled=True / False)
- Capability preservation during failover (e.g., vision)
- Ollama simulated outages and prevention of cascading latency
- Reliability response metadata assertions

100% offline, zero real API credentials or live servers required.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.providers.exceptions import (
    InvalidModelError,
    InvalidProviderError,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.providers.registry import ProviderRegistry
from app.reliability.circuit_breaker import (
    CircuitBreakerRegistry,
    ProviderCircuitBreaker,
)
from app.reliability.errors import (
    CircuitOpenError,
    FailoverExhaustedError,
    TotalDeadlineExceededError,
    is_circuit_breaker_failure,
    is_transient_error,
)
from app.reliability.executor import ReliabilityExecutor
from app.reliability.models import CircuitState
from app.reliability.retry import RetryPolicy
from app.routing.router import RoutingEngine
from app.schemas.chat import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ChatMessageResponse,
    ResponseMetadata,
    UsageMetadata,
)


def _make_request(
    model: str = "auto",
    provider: str | None = None,
    routing_mode: str | None = None,
    required_capabilities: list[str] | None = None,
    failover_enabled: bool = True,
) -> ChatCompletionRequest:
    return ChatCompletionRequest(
        provider=provider,
        model=model,
        routing_mode=routing_mode,  # type: ignore
        required_capabilities=required_capabilities,
        failover_enabled=failover_enabled,
        messages=[ChatMessage(role="user", content="Hello")],
    )


def _make_response(
    provider: str,
    model: str,
    content: str = "Reliable response",
    latency_ms: float = 120.0,
) -> ChatCompletionResponse:
    return ChatCompletionResponse(
        provider=provider,
        model=model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessageResponse(content=content),
                finish_reason="stop",
            )
        ],
        usage=UsageMetadata(prompt_tokens=10, completion_tokens=15, total_tokens=25),
        metadata=ResponseMetadata(request_id="req-test-123", latency_ms=latency_ms),
    )


# ── 1. Error Classification Tests ─────────────────────────────────────────────


class TestErrorClassification:
    def test_transient_errors_identified(self) -> None:
        assert is_transient_error(ProviderTimeoutError("timeout")) is True
        assert is_transient_error(ProviderUnavailableError("service down")) is True
        assert is_transient_error(ProviderRateLimitError("rate limited")) is True
        assert is_transient_error(ProviderError("500 internal", details="")) is True
        assert is_transient_error(ConnectionResetError("conn reset")) is True
        assert is_transient_error(TimeoutError("sys timeout")) is True

    def test_non_transient_errors_identified(self) -> None:
        assert is_transient_error(InvalidModelError("bad model")) is False
        assert is_transient_error(InvalidProviderError("bad provider")) is False
        assert is_transient_error(ProviderAuthError("bad api key")) is False
        assert is_transient_error(ValueError("invalid parameter")) is False
        assert is_transient_error(TypeError("type mismatch")) is False

    def test_circuit_breaker_failure_classification(self) -> None:
        assert is_circuit_breaker_failure(ProviderTimeoutError("timeout")) is True
        assert is_circuit_breaker_failure(ProviderUnavailableError("down")) is True
        assert is_circuit_breaker_failure(ConnectionResetError("reset")) is True

        # Client / auth errors do not count toward circuit breaker
        assert is_circuit_breaker_failure(InvalidModelError("bad model")) is False
        assert is_circuit_breaker_failure(InvalidProviderError("bad provider")) is False
        assert is_circuit_breaker_failure(ProviderAuthError("bad key")) is False


# ── 2. Retry Policy & Backoff Tests ───────────────────────────────────────────


class TestRetryPolicy:
    def test_exponential_backoff_calculation(self) -> None:
        policy = RetryPolicy(
            base_delay_seconds=0.25,
            max_delay_seconds=2.0,
            jitter=False,
        )
        assert policy.compute_delay(0) == 0.25
        assert policy.compute_delay(1) == 0.50
        assert policy.compute_delay(2) == 1.00
        assert policy.compute_delay(3) == 2.00
        assert policy.compute_delay(4) == 2.00  # clamped to max_delay

    def test_jitter_adds_positive_variation(self) -> None:
        policy = RetryPolicy(
            base_delay_seconds=0.25,
            max_delay_seconds=2.0,
            jitter=True,
        )
        delay = policy.compute_delay(0)
        assert delay >= 0.25
        assert delay <= 0.25 * 1.16

    @pytest.mark.asyncio
    async def test_custom_sleep_func_called(self) -> None:
        mock_sleep = AsyncMock()
        policy = RetryPolicy(base_delay_seconds=0.5, jitter=False, sleep_func=mock_sleep)
        await policy.sleep(0.5)
        mock_sleep.assert_awaited_once_with(0.5)


# ── 3. Circuit Breaker State Machine Tests ────────────────────────────────────


class TestCircuitBreaker:
    def test_initial_state_is_closed(self) -> None:
        breaker = ProviderCircuitBreaker(provider="groq", failure_threshold=3)
        assert breaker.state == CircuitState.CLOSED
        assert breaker.can_execute() is True
        assert breaker.failure_count == 0

    def test_failures_increment_and_trip_to_open(self) -> None:
        breaker = ProviderCircuitBreaker(provider="groq", failure_threshold=3)

        breaker.record_failure(ProviderTimeoutError("timeout 1"))
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 1

        breaker.record_failure(ProviderTimeoutError("timeout 2"))
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 2

        breaker.record_failure(ProviderUnavailableError("unavailable 3"))
        assert breaker.state == CircuitState.OPEN
        assert breaker.can_execute() is False

    def test_client_error_does_not_trip_circuit(self) -> None:
        breaker = ProviderCircuitBreaker(provider="gemini", failure_threshold=2)
        breaker.record_failure(InvalidModelError("bad model"))
        breaker.record_failure(ProviderAuthError("invalid key"))
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    def test_open_circuit_transitions_to_half_open_after_cooldown(self) -> None:
        breaker = ProviderCircuitBreaker(
            provider="ollama",
            failure_threshold=1,
            cooldown_seconds=0.1,
            half_open_trials=1,
        )
        breaker.record_failure(ProviderUnavailableError("down"))
        assert breaker.state == CircuitState.OPEN
        assert breaker.can_execute() is False

        # Wait for cooldown
        time.sleep(0.12)
        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.can_execute() is True

    def test_half_open_trial_success_resets_to_closed(self) -> None:
        breaker = ProviderCircuitBreaker(
            provider="groq",
            failure_threshold=1,
            cooldown_seconds=0.05,
            half_open_trials=1,
        )
        breaker.record_failure(ProviderTimeoutError("timeout"))
        time.sleep(0.12)
        assert breaker.state == CircuitState.HALF_OPEN

        # Trial probe succeeds
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    def test_half_open_trial_failure_reopens_circuit(self) -> None:
        breaker = ProviderCircuitBreaker(
            provider="groq",
            failure_threshold=1,
            cooldown_seconds=0.05,
            half_open_trials=1,
        )
        breaker.record_failure(ProviderTimeoutError("timeout"))
        time.sleep(0.12)
        assert breaker.state == CircuitState.HALF_OPEN

        # Trial probe fails
        breaker.record_failure(ProviderTimeoutError("probe timeout"))
        assert breaker.state == CircuitState.OPEN
        assert breaker.can_execute() is False

    def test_half_open_limits_concurrent_trials(self) -> None:
        breaker = ProviderCircuitBreaker(
            provider="gemini",
            failure_threshold=1,
            cooldown_seconds=0.05,
            half_open_trials=1,
        )
        breaker.record_failure(ProviderTimeoutError("timeout"))
        time.sleep(0.12)
        assert breaker.state == CircuitState.HALF_OPEN

        # 1st trial allowed
        assert breaker.can_execute() is True
        # 2nd trial blocked while trial 1 is in-flight
        assert breaker.can_execute() is False


# ── 4. Reliability Executor: Retry Tests ──────────────────────────────────────


class TestReliabilityExecutorRetries:
    @pytest.fixture
    def mock_env(self) -> tuple[ProviderRegistry, RoutingEngine, CircuitBreakerRegistry]:
        reg = ProviderRegistry()
        p = MagicMock()
        p.name = "groq"
        p.list_models = AsyncMock(return_value=["llama-3.3-70b-versatile"])
        p.health_check = AsyncMock(return_value=True)
        reg.register(p)

        router = RoutingEngine(registry=reg)
        cb_reg = CircuitBreakerRegistry(failure_threshold=5, cooldown_seconds=30.0)
        return reg, router, cb_reg

    @pytest.mark.asyncio
    async def test_success_after_transient_retries(
        self, mock_env: tuple[ProviderRegistry, RoutingEngine, CircuitBreakerRegistry]
    ) -> None:
        reg, router, cb_reg = mock_env
        p = reg.get("groq")

        # Fails twice with timeout, then succeeds on 3rd attempt
        call_count = 0

        async def _chat_side_effect(req: ChatCompletionRequest, req_id: str) -> ChatCompletionResponse:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ProviderTimeoutError("Temporary timeout")
            return _make_response("groq", "llama-3.3-70b-versatile")

        p.chat = AsyncMock(side_effect=_chat_side_effect)

        # Fast zero-delay sleep for unit testing
        fast_retry = RetryPolicy(max_retries=2, base_delay_seconds=0.0, jitter=False, sleep_func=AsyncMock())
        executor = ReliabilityExecutor(
            registry=reg,
            routing_engine=router,
            circuit_registry=cb_reg,
            retry_policy=fast_retry,
        )

        req = _make_request(provider="groq", model="llama-3.3-70b-versatile", routing_mode="manual")
        resp = await executor.execute(req, "test-req-1", "groq", "llama-3.3-70b-versatile", "manual")

        assert resp.provider == "groq"
        assert resp.metadata.retry_count == 2
        assert resp.metadata.failover_triggered is False
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_non_transient_client_error_does_not_retry(
        self, mock_env: tuple[ProviderRegistry, RoutingEngine, CircuitBreakerRegistry]
    ) -> None:
        reg, router, cb_reg = mock_env
        p = reg.get("groq")
        p.chat = AsyncMock(side_effect=InvalidModelError("Unknown model"))

        fast_retry = RetryPolicy(max_retries=2, sleep_func=AsyncMock())
        executor = ReliabilityExecutor(
            registry=reg,
            routing_engine=router,
            circuit_registry=cb_reg,
            retry_policy=fast_retry,
        )

        req = _make_request(provider="groq", model="unknown-model", routing_mode="manual", failover_enabled=False)
        with pytest.raises(InvalidModelError):
            await executor.execute(req, "test-req-2", "groq", "unknown-model", "manual")

        # Called exactly once (0 retries)
        assert p.chat.call_count == 1

    @pytest.mark.asyncio
    async def test_total_deadline_exceeded_stops_retries(
        self, mock_env: tuple[ProviderRegistry, RoutingEngine, CircuitBreakerRegistry]
    ) -> None:
        reg, router, cb_reg = mock_env
        p = reg.get("groq")
        p.chat = AsyncMock(side_effect=ProviderTimeoutError("Provider down"))

        # Zero deadline forces immediate deadline exception
        executor = ReliabilityExecutor(
            registry=reg,
            routing_engine=router,
            circuit_registry=cb_reg,
            retry_policy=RetryPolicy(max_retries=5),
            total_request_timeout_seconds=-1.0,  # Expired
        )

        req = _make_request(provider="groq", model="llama-3.3-70b-versatile", routing_mode="manual", failover_enabled=False)
        with pytest.raises(TotalDeadlineExceededError):
            await executor.execute(req, "test-req-3", "groq", "llama-3.3-70b-versatile", "manual")


# ── 5. Reliability Executor: Failover Tests ───────────────────────────────────


class TestReliabilityExecutorFailover:
    @pytest.fixture
    def multi_provider_env(self) -> tuple[ProviderRegistry, RoutingEngine, CircuitBreakerRegistry]:
        reg = ProviderRegistry()

        # 1. Gemini
        gemini = MagicMock()
        gemini.name = "gemini"
        gemini.list_models = AsyncMock(return_value=["gemini-1.5-flash", "gemini-1.5-pro"])
        gemini.health_check = AsyncMock(return_value=True)
        reg.register(gemini)

        # 2. Groq
        groq = MagicMock()
        groq.name = "groq"
        groq.list_models = AsyncMock(return_value=["llama-3.3-70b-versatile", "llama-3.1-8b-instant"])
        groq.health_check = AsyncMock(return_value=True)
        reg.register(groq)

        # 3. Ollama
        ollama = MagicMock()
        ollama.name = "ollama"
        ollama.list_models = AsyncMock(return_value=["llama3.2", "qwen2.5", "llava:latest"])
        ollama.health_check = AsyncMock(return_value=True)
        reg.register(ollama)

        router = RoutingEngine(registry=reg)
        cb_reg = CircuitBreakerRegistry(failure_threshold=3, cooldown_seconds=30.0)
        return reg, router, cb_reg

    @pytest.mark.asyncio
    async def test_primary_failure_triggers_automatic_failover(
        self, multi_provider_env: tuple[ProviderRegistry, RoutingEngine, CircuitBreakerRegistry]
    ) -> None:
        """When Gemini fails and exhausts retries, it fails over to Groq which succeeds."""
        reg, router, cb_reg = multi_provider_env
        gemini = reg.get("gemini")
        groq = reg.get("groq")

        gemini.chat = AsyncMock(side_effect=ProviderUnavailableError("Gemini 503 outage"))
        groq.chat = AsyncMock(return_value=_make_response("groq", "llama-3.3-70b-versatile"))

        fast_retry = RetryPolicy(max_retries=1, base_delay_seconds=0.0, jitter=False, sleep_func=AsyncMock())
        executor = ReliabilityExecutor(
            registry=reg,
            routing_engine=router,
            circuit_registry=cb_reg,
            retry_policy=fast_retry,
            max_failover_attempts=2,
        )

        req = _make_request(model="auto", routing_mode="auto")
        resp = await executor.execute(req, "test-req-fo", "gemini", "gemini-1.5-flash", "auto")

        assert resp.provider == "groq"
        assert resp.metadata.original_provider == "gemini"
        assert resp.metadata.selected_provider == "groq"
        assert resp.metadata.failover_triggered is True
        assert resp.metadata.failover_attempts == 1
        assert gemini.chat.call_count == 2  # 1 initial + 1 retry
        assert groq.chat.call_count == 1

    @pytest.mark.asyncio
    async def test_manual_mode_with_failover_disabled_prevents_failover(
        self, multi_provider_env: tuple[ProviderRegistry, RoutingEngine, CircuitBreakerRegistry]
    ) -> None:
        """When failover_enabled=False in manual mode, failure returns the primary error directly."""
        reg, router, cb_reg = multi_provider_env
        gemini = reg.get("gemini")
        gemini.chat = AsyncMock(side_effect=ProviderUnavailableError("Gemini outage"))

        fast_retry = RetryPolicy(max_retries=1, base_delay_seconds=0.0, jitter=False, sleep_func=AsyncMock())
        executor = ReliabilityExecutor(
            registry=reg,
            routing_engine=router,
            circuit_registry=cb_reg,
            retry_policy=fast_retry,
        )

        req = _make_request(
            provider="gemini",
            model="gemini-1.5-flash",
            routing_mode="manual",
            failover_enabled=False,
        )

        with pytest.raises(ProviderUnavailableError):
            await executor.execute(req, "test-req-manual", "gemini", "gemini-1.5-flash", "manual")

    @pytest.mark.asyncio
    async def test_failover_preserves_required_capabilities(
        self, multi_provider_env: tuple[ProviderRegistry, RoutingEngine, CircuitBreakerRegistry]
    ) -> None:
        """When vision is required and Gemini fails, failover selects an eligible vision model (e.g. Ollama llava)."""
        reg, router, cb_reg = multi_provider_env
        gemini = reg.get("gemini")
        ollama = reg.get("ollama")

        # Gemini flash fails
        gemini.chat = AsyncMock(side_effect=ProviderUnavailableError("Gemini down"))
        ollama.chat = AsyncMock(return_value=_make_response("ollama", "llava:latest"))

        fast_retry = RetryPolicy(max_retries=1, base_delay_seconds=0.0, jitter=False, sleep_func=AsyncMock())
        executor = ReliabilityExecutor(
            registry=reg,
            routing_engine=router,
            circuit_registry=cb_reg,
            retry_policy=fast_retry,
        )

        req = _make_request(
            model="auto",
            routing_mode="capability_based",
            required_capabilities=["vision"],
        )

        resp = await executor.execute(req, "test-req-cap", "gemini", "gemini-1.5-flash", "capability_based")
        assert resp.provider == "ollama"
        assert resp.model == "llava:latest"
        assert resp.metadata.failover_triggered is True


# ── 6. Ollama Outage & No Cascading Slowness ──────────────────────────────────


class TestOllamaReliabilityAndNoCascadingSlowness:
    @pytest.mark.asyncio
    async def test_ollama_open_circuit_prevents_cascading_slowness(self) -> None:
        """
        Trip Ollama circuit breaker.
        Next request must short-circuit Ollama with 0 HTTP calls and route directly to Groq.
        """
        reg = ProviderRegistry()

        ollama = MagicMock()
        ollama.name = "ollama"
        ollama.list_models = AsyncMock(return_value=["llama3.2"])
        ollama.health_check = AsyncMock(return_value=True)
        ollama.chat = AsyncMock(side_effect=ProviderUnavailableError("Connection refused"))
        reg.register(ollama)

        groq = MagicMock()
        groq.name = "groq"
        groq.list_models = AsyncMock(return_value=["llama-3.3-70b-versatile"])
        groq.health_check = AsyncMock(return_value=True)
        groq.chat = AsyncMock(return_value=_make_response("groq", "llama-3.3-70b-versatile"))
        reg.register(groq)

        router = RoutingEngine(registry=reg)
        cb_reg = CircuitBreakerRegistry(failure_threshold=2, cooldown_seconds=30.0)

        # Manually trip Ollama circuit breaker to OPEN
        cb_reg.get_breaker("ollama").trip()
        assert cb_reg.can_execute("ollama") is False

        fast_retry = RetryPolicy(max_retries=1, base_delay_seconds=0.0, jitter=False, sleep_func=AsyncMock())
        executor = ReliabilityExecutor(
            registry=reg,
            routing_engine=router,
            circuit_registry=cb_reg,
            retry_policy=fast_retry,
        )

        req = _make_request(model="auto", routing_mode="lowest_cost")
        resp = await executor.execute(req, "test-req-fast", "ollama", "llama3.2", "lowest_cost")

        # Response fulfilled by Groq without invoking Ollama.chat()
        assert resp.provider == "groq"
        assert resp.metadata.original_provider == "ollama"
        assert resp.metadata.selected_provider == "groq"
        assert resp.metadata.failover_triggered is True
        assert ollama.chat.call_count == 0  # Zero HTTP calls to dead Ollama!
