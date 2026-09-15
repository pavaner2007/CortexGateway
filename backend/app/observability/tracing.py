"""
Cortex Gateway — OpenTelemetry Tracing (Phase 7).

Architecture:
  - When OTEL_ENABLED=false (default): a no-op tracer is used.
    The gateway runs identically without any collector running.
  - When OTEL_ENABLED=true: an OtlpGrpcExporter sends spans to the
    configured endpoint. Collector unavailability is silently caught.

Spans created:
  gateway.auth          — authentication / key lookup
  gateway.rate_limit    — sliding-window rate limit check
  gateway.budget        — budget pre-check + reconcile
  gateway.routing       — provider/model selection
  gateway.reliability   — executor: retries + circuit breaker + failover
  gateway.provider      — individual provider call attempt

Attributes (low-cardinality only):
  request_id, provider, model, routing_mode, status,
  retry_count, failover_triggered, budget_policy

NEVER added to spans:
  prompt content, completion content, API keys, Authorization headers.

Trace correlation:
  The current trace_id (hex) is exposed via get_current_trace_id() so
  it can be persisted in RequestLog.trace_id for RequestLog → Trace linkage.
"""

from __future__ import annotations

import contextlib
from typing import Generator, Optional

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter


def init_tracing(
    *,
    enabled: bool = False,
    service_name: str = "cortex-gateway",
    otlp_endpoint: str = "",
) -> None:
    """
    Configure the global OTel tracer.

    Called once during application lifespan startup.

    Args:
        enabled:       Whether to enable real tracing (default False).
        service_name:  OTel service.name resource attribute.
        otlp_endpoint: gRPC endpoint for the OTLP exporter, e.g.
                       "http://otel-collector:4317". Empty = disabled.
    """
    if not enabled:
        # No-op provider — trace() calls return non-recording spans.
        trace.set_tracer_provider(trace.NoOpTracerProvider())
        return

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        except Exception as exc:  # pragma: no cover
            # Collector unavailable or package issue → fall back to no-op quietly
            import logging
            logging.getLogger("cortex.tracing").warning(
                "OTel OTLP exporter init failed; tracing disabled: %s", exc
            )
            trace.set_tracer_provider(trace.NoOpTracerProvider())
            return
    else:
        # No endpoint → console exporter for local debugging only
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)


def get_tracer() -> trace.Tracer:
    """Return the module-scoped tracer."""
    return trace.get_tracer("cortex.gateway")


def get_current_trace_id() -> Optional[str]:
    """
    Return the current OTel trace ID as a 32-char hex string, or None.

    Used to populate RequestLog.trace_id for cross-system correlation.
    """
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx is None or not ctx.is_valid:
        return None
    return format(ctx.trace_id, "032x")


@contextlib.contextmanager
def safe_span(name: str, **attributes) -> Generator[trace.Span, None, None]:
    """
    Context manager that creates a child span and sets attributes.

    OTel infrastructure errors are silently absorbed. Application exceptions
    raised inside the ``with`` block are always re-raised so the gateway
    request pipeline behaves correctly.

    Usage::

        with safe_span("gateway.routing", provider="groq") as span:
            decision = await routing_engine.route(request)
            span.set_attribute("model", decision.model)
    """
    tracer = get_tracer()
    span_ctx = None
    try:
        span_ctx = tracer.start_as_current_span(name)
        span = span_ctx.__enter__()
    except Exception:  # pragma: no cover
        # OTel span creation failed — yield a no-op span and continue
        span_ctx = None
        span = trace.NonRecordingSpan(trace.INVALID_SPAN_CONTEXT)

    # Set attributes — silently ignore any OTel errors here
    for key, value in attributes.items():
        if value is not None:
            try:
                span.set_attribute(key, str(value))
            except Exception:  # pragma: no cover
                pass

    try:
        yield span
    except Exception:
        # Exit the span context (mark as error) then re-raise the app exception
        if span_ctx is not None:
            try:
                span_ctx.__exit__(None, None, None)
                span_ctx = None
            except Exception:  # pragma: no cover
                pass
        raise
    else:
        if span_ctx is not None:
            try:
                span_ctx.__exit__(None, None, None)
            except Exception:  # pragma: no cover
                pass

