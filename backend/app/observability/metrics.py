"""
Cortex Gateway — Prometheus Metrics Registry (Phase 7).

Exposes the following metrics via GET /metrics:

  gateway_requests_total{provider, model, status}
      Counter. One increment per completed client request (not per retry).

  gateway_request_latency_seconds{provider, model}
      Histogram. Provider-level latency in seconds. Buckets cover typical
      LLM response times (10ms → 60s).

  provider_requests_total{provider}
      Counter. Total provider calls (includes retries; each call counted).

  provider_errors_total{provider, error_code}
      Counter. Provider-level errors keyed by normalized error code.

  provider_latency_seconds{provider}
      Histogram. Per-provider call latency in seconds.

  fallback_requests_total{from_provider, to_provider}
      Counter. Incremented once per failover event.

  circuit_breaker_state{provider}
      Gauge. Current circuit-breaker state: 0=CLOSED, 1=OPEN, 2=HALF_OPEN.
      Updated whenever a provider call completes or the breaker trips.

  budget_downgrade_total
      Counter. Incremented when DOWNGRADE policy triggers a provider switch.

  rate_limit_exceeded_total{scope}
      Counter. Incremented when any scope (api_key/team/organization) rejects.

Cardinality contract:
  SAFE labels:  provider, model, status, error_code, scope, from_provider, to_provider
                — all are normalized, bounded-cardinality controlled values.
  NEVER labels: team_id, organization_id, request_id, api_key_id
                — these are high-cardinality identifiers.
  Use analytics APIs (backed by RequestLog) for per-team / per-request detail.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, REGISTRY

# ── Buckets tuned for LLM workloads (10ms → 120s) ──────────────────────────
_LATENCY_BUCKETS = (
    0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0
)

# ── Request-level metrics (one gateway request = one client call) ─────────────

gateway_requests_total = Counter(
    "gateway_requests_total",
    "Total number of chat completion requests received by the gateway.",
    ["provider", "model", "status"],
)

gateway_request_latency_seconds = Histogram(
    "gateway_request_latency_seconds",
    "End-to-end provider call latency in seconds (from routing to response).",
    ["provider", "model"],
    buckets=_LATENCY_BUCKETS,
)

# ── Provider-level metrics (counts each attempt, including retries) ───────────

provider_requests_total = Counter(
    "provider_requests_total",
    "Total provider calls including retries and failover attempts.",
    ["provider"],
)

provider_errors_total = Counter(
    "provider_errors_total",
    "Provider call failures keyed by normalized error code.",
    ["provider", "error_code"],
)

provider_latency_seconds = Histogram(
    "provider_latency_seconds",
    "Per-provider call latency in seconds.",
    ["provider"],
    buckets=_LATENCY_BUCKETS,
)

# ── Reliability metrics ───────────────────────────────────────────────────────

fallback_requests_total = Counter(
    "fallback_requests_total",
    "Number of failover events (from_provider → to_provider).",
    ["from_provider", "to_provider"],
)

circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state per provider: 0=CLOSED, 1=OPEN, 2=HALF_OPEN.",
    ["provider"],
)

# ── Budget metrics ────────────────────────────────────────────────────────────

budget_downgrade_total = Counter(
    "budget_downgrade_total",
    "Number of requests downgraded to a cheaper provider due to budget constraints.",
    [],
)

# ── Rate limit metrics ────────────────────────────────────────────────────────

rate_limit_exceeded_total = Counter(
    "rate_limit_exceeded_total",
    "Number of requests rejected by the rate limiter, labelled by scope.",
    ["scope"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

_CB_STATE_MAP = {"CLOSED": 0, "OPEN": 1, "HALF_OPEN": 2}


def update_circuit_breaker_state(provider: str, state_str: str) -> None:
    """Set the circuit_breaker_state gauge for a provider."""
    numeric = _CB_STATE_MAP.get(state_str.upper(), 0)
    circuit_breaker_state.labels(provider=provider).set(numeric)


def record_provider_attempt(
    *,
    provider: str,
    latency_ms: float,
    success: bool,
    error_code: str = "",
) -> None:
    """
    Record one provider call attempt (retries each count separately).

    Called from the reliability executor after each attempt, not from
    the chat endpoint. This is intentionally provider-attempt granularity.
    """
    provider_requests_total.labels(provider=provider).inc()
    provider_latency_seconds.labels(provider=provider).observe(latency_ms / 1000.0)
    if not success and error_code:
        provider_errors_total.labels(
            provider=provider, error_code=error_code
        ).inc()


def record_gateway_request(
    *,
    provider: str,
    model: str,
    status: str,
    latency_ms: float,
) -> None:
    """
    Record one completed client request (not per-retry).

    status: "success" | "failure" | "rate_limited" | "budget_blocked" | "timeout"
    """
    gateway_requests_total.labels(
        provider=provider, model=model, status=status
    ).inc()
    if latency_ms > 0:
        gateway_request_latency_seconds.labels(
            provider=provider, model=model
        ).observe(latency_ms / 1000.0)
