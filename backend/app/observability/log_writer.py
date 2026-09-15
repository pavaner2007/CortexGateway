"""
Cortex Gateway — Async Request Log Writer (Phase 7).

Design:
  - Accepts a plain dict of log fields (no live ORM objects).
  - Creates its OWN async database session — never reuses the
    request-scoped session which may already be closed.
  - Any failure (DB unavailable, constraint violation, etc.) is caught,
    logged, and silently discarded — the chat response is never affected.
  - Called via FastAPI BackgroundTasks so the write happens after the
    response is returned to the client.

Security:
  - Prompt content, completion content, API keys and other secrets must
    never appear in the log_data dict passed to this module.
  - This module trusts the caller to pass only safe metadata.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.logging import logger
from app.database.session import get_db_session
from app.observability.models import RequestLog


async def write_request_log(log_data: Dict[str, Any]) -> None:
    """
    Persist one RequestLog row.

    This function is designed to be called via FastAPI BackgroundTasks.
    It creates its own session, commits, and silently swallows any error.

    Args:
        log_data: Dict of RequestLog field values. Unknown keys are ignored.
    """
    try:
        # Map known keys — ignore any unrecognised field
        allowed = {
            "request_id", "trace_id", "organization_id", "team_id",
            "provider", "model", "routing_mode", "status", "http_status_code",
            "error_code", "latency_ms", "prompt_tokens", "completion_tokens",
            "total_tokens", "estimated_cost", "actual_cost",
            "retry_count", "failover_triggered", "failover_from_provider",
            "failover_to_provider", "circuit_breaker_state",
            "budget_policy_applied", "budget_action",
        }
        safe = {k: v for k, v in log_data.items() if k in allowed}

        # Ensure request_id is always present
        if not safe.get("request_id"):
            logger.warning("write_request_log called with no request_id; skipping")
            return

        async with get_db_session() as session:
            entry = RequestLog(**safe)
            session.add(entry)
            # commit is handled by get_db_session context manager

        logger.debug(
            "RequestLog written",
            request_id=safe.get("request_id"),
            status=safe.get("status"),
        )

    except Exception as exc:
        # Observability failure must NEVER bubble up to the caller.
        logger.error(
            "RequestLog write failed (observability non-fatal)",
            error=str(exc),
            request_id=log_data.get("request_id", "unknown"),
        )


def build_success_log(
    *,
    request_id: str,
    context,  # Optional[RequestContext]
    response,  # ChatCompletionResponse
    trace_id: Optional[str] = None,
    budget_policy: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build the log_data dict from a successful ChatCompletionResponse.

    Extracts all available metadata from response.metadata without
    re-computing anything that Phase 3–6 already calculated.
    """
    meta = response.metadata
    usage = response.usage

    # Resolve failover provider names from original_provider / selected_provider
    failover_from = None
    failover_to = None
    if meta.failover_triggered:
        failover_from = meta.original_provider
        failover_to = meta.selected_provider

    return {
        "request_id": request_id,
        "trace_id": trace_id,
        "organization_id": context.organization_id if context else None,
        "team_id": context.team_id if context else None,
        "provider": meta.selected_provider,
        "model": meta.selected_model,
        "routing_mode": meta.routing_mode,
        "status": "success",
        "http_status_code": 200,
        "latency_ms": meta.latency_ms,
        "prompt_tokens": usage.prompt_tokens if usage else None,
        "completion_tokens": usage.completion_tokens if usage else None,
        "total_tokens": usage.total_tokens if usage else None,
        "estimated_cost": meta.estimated_cost,
        "actual_cost": meta.actual_cost,
        "retry_count": meta.retry_count,
        "failover_triggered": meta.failover_triggered,
        "failover_from_provider": failover_from,
        "failover_to_provider": failover_to,
        "circuit_breaker_state": meta.circuit_breaker_state,
        "budget_policy_applied": budget_policy,
        "budget_action": (
            "downgraded" if meta.budget_downgraded
            else "warned" if meta.budget_warning
            else "none"
        ),
        "error_code": None,
    }


def build_error_log(
    *,
    request_id: str,
    context,  # Optional[RequestContext]
    status: str,
    http_status_code: int,
    error_code: str,
    trace_id: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    budget_policy: Optional[str] = None,
    budget_action: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build the log_data dict for a failed / rejected request.
    provider and model may be None when the request was rejected pre-routing.
    """
    return {
        "request_id": request_id,
        "trace_id": trace_id,
        "organization_id": context.organization_id if context else None,
        "team_id": context.team_id if context else None,
        "provider": provider,
        "model": model,
        "routing_mode": None,
        "status": status,
        "http_status_code": http_status_code,
        "error_code": error_code,
        "latency_ms": None,
        "retry_count": 0,
        "failover_triggered": False,
        "budget_policy_applied": budget_policy,
        "budget_action": budget_action,
    }
