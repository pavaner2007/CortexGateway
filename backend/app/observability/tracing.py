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
import logging
from collections.abc import Generator

# opentelemetry imports are deferred inside each function.
# This allows the module to be imported when opentelemetry is not installed
# (CI / test environments where OTEL_ENABLED=false).

_otel_logger = logging.getLogger("cortex.tracing")


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
        # No-op: install a non-recording tracer so get_tracer() always works.
        # opentelemetry import is guarded — safe when package is absent.
        try:
            from opentelemetry import trace  # noqa: PLC0415
            trace.set_tracer_provider(trace.NoOpTracerProvider())
        except ModuleNotFoundError:
            pass  # package absent — no-op is implicit, spans are never created
        return

    from opentelemetry import trace  # noqa: PLC0415
    from opentelemetry.sdk.resources import Resource  # noqa: PLC0415
    from opentelemetry.sdk.trace import TracerProvider  # noqa: PLC0415
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter  # noqa: PLC0415

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # noqa: PLC0415
                OTLPSpanExporter,
            )
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        except Exception as exc:  # pragma: no cover
            _otel_logger.warning("OTel OTLP exporter init failed; tracing disabled: %s", exc)
            trace.set_tracer_provider(trace.NoOpTracerProvider())
            return
    else:
        # No endpoint -> console exporter for local debugging only
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)


def get_tracer():
    """Return the module-scoped tracer. Returns a no-op tracer if opentelemetry is absent."""
    try:
        from opentelemetry import trace  # noqa: PLC0415
        return trace.get_tracer("cortex.gateway")
    except ModuleNotFoundError:  # pragma: no cover
        return _NoOpTracer()


def get_current_trace_id() -> str | None:
    """
    Return the current OTel trace ID as a 32-char hex string, or None.

    Used to populate RequestLog.trace_id for cross-system correlation.
    """
    try:
        from opentelemetry import trace  # noqa: PLC0415
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx is None or not ctx.is_valid:
            return None
        return format(ctx.trace_id, "032x")
    except ModuleNotFoundError:  # pragma: no cover
        return None


class _NoOpTracer:  # pragma: no cover
    """Minimal no-op tracer used when opentelemetry is not installed."""
    def start_as_current_span(self, name: str):
        return contextlib.nullcontext(None)


@contextlib.contextmanager
def safe_span(name: str, **attributes) -> Generator:
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
        # OTel span creation failed or opentelemetry absent -- yield None and continue
        span_ctx = None
        span = None

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

