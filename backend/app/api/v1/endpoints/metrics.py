"""
Cortex Gateway — Prometheus Metrics Endpoint (Phase 7).

GET /metrics

Returns Prometheus text exposition format for scraping by a Prometheus server.
This endpoint is unauthenticated (standard Prometheus convention — protect
at the network/load-balancer level in production).
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter(tags=["Observability"])


@router.get(
    "/metrics",
    summary="Prometheus Metrics",
    description=(
        "Expose gateway metrics in Prometheus text exposition format. "
        "Scrape this endpoint with Prometheus. "
        "Standard convention: protect with network policy in production."
    ),
    responses={200: {"content": {"text/plain": {}}}},
)
async def prometheus_metrics() -> Response:
    """Return all registered Prometheus metrics in text exposition format."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
