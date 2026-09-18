"""
Cortex Gateway — Candidate Builder (Phase 3 + Phase 9A).

Gathers candidate (provider, model) pairs by combining:
1. Registered providers from ProviderRegistry
2. Available models (via provider.list_models() or registry fallback)
3. Provider health checks
4. Metadata from ModelMetadataCatalog (costs, capabilities, baseline latency)
5. Runtime statistics from ProviderStatsTracker (observed latency, success rate)

Phase 9A — Ollama intersection:
  For Ollama specifically, eligibility requires BOTH:
    (a) Model is in the registry (provider="ollama", enabled=true)
    (b) Model is currently installed locally (returned by list_models())

  If a model is in the registry but not installed → silently excluded.
  If a model is installed but not in the registry → excluded (no metadata).
  No automatic downloads. No error raised for missing models.

  For Gemini and Groq, behavior is unchanged: the registry provides
  metadata and the live model list is used as-is.
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

        Ollama-specific:
          Eligible models = (registry models for ollama) ∩ (live installed models).
          Models in the registry but not installed are silently excluded.
        """
        registered_providers = self._registry.list_providers()
        if not registered_providers:
            return []

        candidates: List[RoutingCandidate] = []

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
                live_models = await provider_obj.list_models()
            except Exception:
                live_models = []

            return provider_obj.name, is_healthy, live_models

        results = await asyncio.gather(
            *[_inspect_provider(p) for p in registered_providers],
            return_exceptions=True,
        )

        for res in results:
            if not res or isinstance(res, Exception):
                continue
            provider_name, is_healthy, live_models = res

            # Determine which models to enumerate for this provider
            if provider_name == "ollama":
                models = _resolve_ollama_models(
                    live_models=live_models,
                    catalog_models=self._metadata_catalog.provider_model_names("ollama"),
                )
                if not models:
                    logger.debug(
                        "Ollama: no models satisfy registry ∩ installed constraint",
                        live_count=len(live_models),
                        registry_count=len(
                            self._metadata_catalog.provider_model_names("ollama")
                        ),
                    )
            else:
                # For cloud providers: use live list if available,
                # fall back to registry models if empty
                if live_models:
                    models = live_models
                else:
                    models = self._metadata_catalog.provider_model_names(provider_name)

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


def _resolve_ollama_models(
    live_models: List[str],
    catalog_models: List[str],
) -> List[str]:
    """
    Compute Ollama-eligible models = registry ∩ installed.

    Args:
        live_models:    Models currently installed and served by the local Ollama runtime.
        catalog_models: Models registered in the model_registry table for provider='ollama'.

    Returns:
        Intersection — models that are both registered AND currently installed.
        Models only in the registry (not installed) are excluded.
        Models only installed (not registered) are excluded (no metadata).
    """
    # Normalize: strip whitespace, lowercase tags for matching
    live_set = {m.strip() for m in live_models}

    eligible = []
    for catalog_model in catalog_models:
        normalized = catalog_model.strip()
        if normalized in live_set:
            eligible.append(catalog_model)
        else:
            # Try bare name match (e.g. catalog has 'llama3.2', live has 'llama3.2:latest')
            bare = normalized.split(":")[0]
            if any(lm.split(":")[0] == bare for lm in live_set):
                eligible.append(catalog_model)

    return eligible
