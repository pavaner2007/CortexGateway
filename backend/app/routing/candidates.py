"""
Cortex Gateway — Candidate Builder (Phase 3).

Gathers candidate (provider, model) pairs by combining:
1. Registered providers from ProviderRegistry
2. Available models (via provider.list_models() or catalog defaults)
3. Provider health checks
4. Metadata from ModelMetadataCatalog (costs, capabilities, baseline latency)
5. Runtime statistics from ProviderStatsTracker (observed latency, success rate)
"""

from __future__ import annotations

import asyncio
from typing import List, Optional

from app.core.logging import logger
from app.providers.registry import ProviderRegistry
from app.routing.metadata import ModelMetadataCatalog
from app.routing.models import RoutingCandidate
from app.routing.stats import ProviderStatsTracker


class CandidateBuilder:
    """Builds and enriches the candidate list for the routing engine."""

    def __init__(
        self,
        registry: ProviderRegistry,
        metadata_catalog: ModelMetadataCatalog,
        stats_tracker: ProviderStatsTracker,
    ) -> None:
        self._registry = registry
        self._metadata_catalog = metadata_catalog
        self._stats_tracker = stats_tracker

    async def build_candidates(self) -> List[RoutingCandidate]:
        """
        Build candidate representations for all models available across
        all currently registered providers.
        """
        registered_providers = self._registry.list_providers()
        if not registered_providers:
            return []

        candidates: List[RoutingCandidate] = []

        # Check health and gather model lists concurrently across registered providers
        async def _inspect_provider(p_info):
            try:
                provider_obj = self._registry.get(p_info.name)
            except Exception:
                return None

            try:
                is_healthy = await provider_obj.health_check()
            except Exception:
                is_healthy = False

            try:
                models = await provider_obj.list_models()
            except Exception:
                models = []

            return provider_obj.name, is_healthy, models

        results = await asyncio.gather(
            *[_inspect_provider(p) for p in registered_providers],
            return_exceptions=True,
        )

        for res in results:
            if not res or isinstance(res, Exception):
                continue
            provider_name, is_healthy, models = res

            # If provider returned empty model list, fall back to default catalog models for this provider
            if not models:
                models = [
                    m.model
                    for m in self._metadata_catalog._catalog.values()
                    if m.provider == provider_name
                ]

            for model_name in models:
                meta = self._metadata_catalog.get(provider_name, model_name)
                stats = self._stats_tracker.get_stats(provider_name, model_name)

                runtime_lat = stats.latency_ms if stats else None
                success_rate = stats.success_rate if stats else 1.0
                total_reqs = stats.total_requests if stats else 0

                candidate = RoutingCandidate(
                    provider=provider_name,
                    model=model_name,
                    capabilities=meta.capabilities,
                    context_window=meta.context_window,
                    cost_per_1k_tokens=meta.cost_per_1k_tokens,
                    is_healthy=is_healthy,
                    baseline_latency_ms=meta.baseline_latency_ms,
                    runtime_latency_ms=runtime_lat,
                    runtime_success_rate=success_rate,
                    total_requests=total_reqs,
                )
                candidates.append(candidate)

        return candidates
